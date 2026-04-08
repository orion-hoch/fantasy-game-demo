"""Basic FastAPI strangler tests."""

import sqlite3

import pytest
from httpx import ASGITransport, AsyncClient

from src.legacy.bridge import ensure_repo_on_path
from src.main import app
from src.redis_client import get_redis_client

ensure_repo_on_path()

import lobby_store  # noqa: E402
import codewords_game  # noqa: E402
import nfl_bullseye  # noqa: E402
import nba_bullseye  # noqa: E402
import nba_starting5_game  # noqa: E402
import starting6_game  # noqa: E402


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["mode"] == "strangler"


@pytest.mark.asyncio
async def test_health_without_redis_config(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.config.settings.upstash_redis_rest_url", None)
    monkeypatch.setattr("src.config.settings.upstash_redis_rest_token", None)
    get_redis_client.cache_clear()

    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["redis"]["configured"] is False
    assert body["redis"]["status"] == "not_configured"


@pytest.mark.asyncio
async def test_migration_inventory(client: AsyncClient):
    response = await client.get("/api/v1/migration/inventory")
    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "strangler"
    assert body["surfaces"]


@pytest.mark.asyncio
async def test_create_lobby(client: AsyncClient):
    lobby_store._ROOMS._memory.clear()
    response = await client.post(
        "/api/v1/lobbies/create",
        json={"game_type": "nfl_bullseye", "player_name": "Host", "token": "host-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["room"]["game_type"] == "nfl_bullseye"
    assert body["room"]["my_seat"] == 1
    assert body["room_url"].startswith("/lobbies/")


@pytest.mark.asyncio
async def test_claim_and_fetch_lobby(client: AsyncClient):
    lobby_store._ROOMS._memory.clear()
    create = await client.post(
        "/api/v1/lobbies/create",
        json={"game_type": "starting6", "player_name": "Host", "token": "host-token"},
    )
    room_id = create.json()["room"]["room_id"]

    claim = await client.post(
        f"/api/v1/lobbies/{room_id}/claim-seat",
        json={"token": "guest-token", "player_name": "Guest", "seat_number": 2},
    )
    assert claim.status_code == 200
    assert claim.json()["room"]["filled_seat_count"] == 2

    state = await client.get(f"/api/v1/lobbies/{room_id}", params={"token": "guest-token"})
    assert state.status_code == 200
    assert state.json()["room"]["my_seat"] == 2


@pytest.mark.asyncio
async def test_bullseye_start_and_state(client: AsyncClient):
    response = await client.post(
        "/api/v1/bullseye/nfl/start",
        json={"player_names": ["Solo"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["game_id"]
    assert body["state"]["players"] == ["Solo"]

    state = await client.get("/api/v1/bullseye/nfl/state", params={"game_id": body["game_id"]})
    assert state.status_code == 200
    assert state.json()["state"]["game_id"] == body["game_id"]


@pytest.mark.asyncio
async def test_bullseye_search_seasons_and_pick(client: AsyncClient):
    start = await client.post(
        "/api/v1/bullseye/nba/start",
        json={"player_names": ["Solo"]},
    )
    assert start.status_code == 200
    payload = start.json()
    game_id = payload["game_id"]

    search = await client.get(
        "/api/v1/bullseye/nba/search",
        params={"game_id": game_id, "prompt_idx": 0, "q": ""},
    )
    assert search.status_code == 200
    results = search.json()["results"]
    assert results

    state = nba_bullseye.get_game(game_id)
    prompt = state["prompts"][0]
    where, params = nba_bullseye._build_prompt_where(prompt, state["stat"])
    stat_expr = nba_bullseye._stat_expr(state["stat"])
    conn = sqlite3.connect("/Users/orionhoch/fantasy_game_demo/fantasy.db")
    try:
        row = conn.execute(
            f"""
            SELECT s.player, s.season
            FROM nba_stats s
            {where}
            AND {stat_expr} > 0
            LIMIT 1
            """,
            params,
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    player_name, season = row

    pick = await client.post(
        "/api/v1/bullseye/nba/pick",
        json={
            "game_id": game_id,
            "player_name": player_name,
            "season": season,
            "prompt_idx": 0,
            "player_idx": 0,
            "token": None,
        },
    )
    assert pick.status_code == 200
    pick_payload = pick.json()
    assert pick_payload["ok"] is True
    assert pick_payload["state"]["picks"][0][0]["player"] == player_name


@pytest.mark.asyncio
async def test_bullseye_prompts_include_accolades_and_min_player_pool(client: AsyncClient):
    nfl_start = await client.post(
        "/api/v1/bullseye/nfl/start",
        json={"player_names": ["Solo"]},
    )
    assert nfl_start.status_code == 200
    nfl_state = nfl_start.json()["state"]

    nba_start = await client.post(
        "/api/v1/bullseye/nba/start",
        json={"player_names": ["Solo"]},
    )
    assert nba_start.status_code == 200
    nba_state = nba_start.json()["state"]

    assert any(prompt.get("accolade") for prompt in nfl_state["prompts"])
    assert any(prompt.get("accolade") for prompt in nba_state["prompts"])

    conn = sqlite3.connect("/Users/orionhoch/fantasy_game_demo/fantasy.db")
    try:
        nfl_table = nfl_bullseye._stat_table(nfl_state["stat"])
        for prompt in nfl_state["prompts"]:
            where, pos, params = nfl_bullseye._build_prompt_where(prompt, nfl_state["stat"], apply_stat_floor=True)
            row = conn.execute(f"SELECT COUNT(DISTINCT s.player) FROM {nfl_table} s {where} {pos}", params).fetchone()
            assert row is not None
            assert row[0] >= 5

        for prompt in nba_state["prompts"]:
            where, params = nba_bullseye._build_prompt_where(prompt, nba_state["stat"], apply_stat_floor=True)
            row = conn.execute(f"SELECT COUNT(DISTINCT s.player) FROM nba_stats s {where}", params).fetchone()
            assert row is not None
            assert row[0] >= 5
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_lobby_start_redirects_migrated_bullseye_to_svelte_route(client: AsyncClient):
    lobby_store._ROOMS._memory.clear()
    create = await client.post(
        "/api/v1/lobbies/create",
        json={"game_type": "nfl_bullseye", "player_name": "Host", "token": "host-token"},
    )
    room_id = create.json()["room"]["room_id"]

    claim = await client.post(
        f"/api/v1/lobbies/{room_id}/claim-seat",
        json={"token": "guest-token", "player_name": "Guest", "seat_number": 2},
    )
    assert claim.status_code == 200

    start = await client.post(
        f"/api/v1/lobbies/{room_id}/start",
        json={"token": "host-token"},
    )
    assert start.status_code == 200
    assert start.json()["room"]["redirect_url"] == f"/games/nfl/bullseye?room_id={room_id}"


@pytest.mark.asyncio
async def test_fantasy_duel_start_and_pick(client: AsyncClient):
    start = await client.post(
        "/api/v1/fantasy-duel/nfl/start",
        json={"player_names": ["A", "B"]},
    )
    assert start.status_code == 200
    payload = start.json()
    game_id = payload["game_id"]
    state = starting6_game.get_game(game_id)
    current_team = state["currentTeam"]

    conn = sqlite3.connect("/Users/orionhoch/fantasy_game_demo/fantasy.db")
    try:
        row = conn.execute(
            "SELECT player, season FROM stats WHERE team = ? AND pos IN ('QB','WR','RB','TE') AND fantasy_ppr IS NOT NULL LIMIT 1",
            (current_team,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    player_name, season = row

    years = await client.get(
        "/api/v1/fantasy-duel/nfl/years",
        params={"game_id": game_id, "player": player_name},
    )
    assert years.status_code == 200
    assert season in years.json()["years"]

    pick = await client.post(
        "/api/v1/fantasy-duel/nfl/pick",
        json={"game_id": game_id, "player_name": player_name, "season": season},
    )
    assert pick.status_code == 200
    pick_payload = pick.json()
    assert pick_payload["ok"] is True
    assert pick_payload["state"]["players"][0]["roster"]


@pytest.mark.asyncio
async def test_lobby_start_redirects_migrated_fantasy_duel_to_svelte_route(client: AsyncClient):
    lobby_store._ROOMS._memory.clear()
    create = await client.post(
        "/api/v1/lobbies/create",
        json={"game_type": "starting6", "player_name": "Host", "token": "host-token"},
    )
    room_id = create.json()["room"]["room_id"]

    claim = await client.post(
        f"/api/v1/lobbies/{room_id}/claim-seat",
        json={"token": "guest-token", "player_name": "Guest", "seat_number": 2},
    )
    assert claim.status_code == 200

    start = await client.post(
        f"/api/v1/lobbies/{room_id}/start",
        json={"token": "host-token"},
    )
    assert start.status_code == 200
    assert start.json()["room"]["redirect_url"] == f"/games/nfl/fantasy-duel?room_id={room_id}"


@pytest.mark.asyncio
async def test_chain_start_route(client: AsyncClient):
    response = await client.post("/api/v1/chain/nfl/start")
    assert response.status_code == 200
    body = response.json()
    assert body["category"]["id"]
    assert body["valid_count"] >= 1


@pytest.mark.asyncio
async def test_lobby_start_redirects_migrated_chain_to_svelte_route(client: AsyncClient):
    lobby_store._ROOMS._memory.clear()
    create = await client.post(
        "/api/v1/lobbies/create",
        json={"game_type": "chain_coop", "player_name": "Host", "token": "host-token"},
    )
    room_id = create.json()["room"]["room_id"]

    claim = await client.post(
        f"/api/v1/lobbies/{room_id}/claim-seat",
        json={"token": "guest-token", "player_name": "Guest", "seat_number": 2},
    )
    assert claim.status_code == 200

    start = await client.post(
        f"/api/v1/lobbies/{room_id}/start",
        json={"token": "host-token"},
    )
    assert start.status_code == 200
    assert start.json()["room"]["redirect_url"] == f"/games/nfl/chain?room_id={room_id}"


@pytest.mark.asyncio
async def test_chain_lobby_game_state_has_initial_prompt(client: AsyncClient):
    lobby_store._ROOMS._memory.clear()
    create = await client.post(
        "/api/v1/lobbies/create",
        json={"game_type": "chain_coop", "player_name": "Host", "token": "host-token"},
    )
    room_id = create.json()["room"]["room_id"]

    claim = await client.post(
        f"/api/v1/lobbies/{room_id}/claim-seat",
        json={"token": "guest-token", "player_name": "Guest", "seat_number": 2},
    )
    assert claim.status_code == 200

    start = await client.post(
        f"/api/v1/lobbies/{room_id}/start",
        json={"token": "host-token"},
    )
    assert start.status_code == 200

    state = await client.get(f"/api/v1/lobbies/{room_id}/game-state", params={"token": "host-token"})
    assert state.status_code == 200
    payload = state.json()
    assert payload["state"]["chain"]
    assert payload["state"]["chain"][0]["label"]
    assert payload["state"]["validCount"] >= 1


@pytest.mark.asyncio
async def test_codewords_state_and_clue(client: AsyncClient):
    conn = sqlite3.connect("/Users/orionhoch/fantasy_game_demo/fantasy.db")
    try:
        game_id, _ = codewords_game.start_game(
            conn,
            [
                {"name": "A Clue", "token": "a-clue", "team": "A", "role": "spymaster"},
                {"name": "A Guess", "token": "a-guess", "team": "A", "role": "guesser"},
                {"name": "B Clue", "token": "b-clue", "team": "B", "role": "spymaster"},
                {"name": "B Guess", "token": "b-guess", "team": "B", "role": "guesser"},
            ],
            sport="nfl",
            mode="teams",
        )
    finally:
        conn.close()

    full_state = codewords_game.get_game(game_id)
    current_team = full_state["current_team"]
    clue_token = "a-clue" if current_team == "A" else "b-clue"

    state = await client.get("/api/v1/codewords/state", params={"game_id": game_id, "token": clue_token})
    assert state.status_code == 200
    body = state.json()
    assert body["state"]["you"]["role"] == "spymaster"

    clue = await client.post(
        "/api/v1/codewords/clue",
        json={"game_id": game_id, "token": clue_token, "clue": "Champions", "number": 1},
    )
    assert clue.status_code == 200
    clue_body = clue.json()
    assert clue_body["state"]["current_phase"] == "guess"
    assert clue_body["state"]["current_clue"]["text"] == "Champions"


@pytest.mark.asyncio
async def test_lobby_start_redirects_migrated_codewords_to_svelte_route(client: AsyncClient):
    lobby_store._ROOMS._memory.clear()
    create = await client.post(
        "/api/v1/lobbies/create",
        json={"game_type": "nfl_codewords", "player_name": "Host", "token": "host-token"},
    )
    room_id = create.json()["room"]["room_id"]

    for seat_number, token in [(2, "token-2"), (3, "token-3"), (4, "token-4")]:
        claim = await client.post(
            f"/api/v1/lobbies/{room_id}/claim-seat",
            json={"token": token, "player_name": f"P{seat_number}", "seat_number": seat_number},
        )
        assert claim.status_code == 200

    seat_meta_payloads = [
        ("host-token", {"team": "A", "role": "spymaster"}),
        ("token-2", {"team": "A", "role": "guesser"}),
        ("token-3", {"team": "B", "role": "spymaster"}),
        ("token-4", {"team": "B", "role": "guesser"}),
    ]
    for token, meta in seat_meta_payloads:
        seat_meta = await client.post(
            f"/api/v1/lobbies/{room_id}/seat-meta",
            json={"token": token, "meta": meta},
        )
        assert seat_meta.status_code == 200

    start = await client.post(
        f"/api/v1/lobbies/{room_id}/start",
        json={"token": "host-token"},
    )
    assert start.status_code == 200
    assert start.json()["room"]["redirect_url"] == f"/games/nfl/codewords?room_id={room_id}"


@pytest.mark.asyncio
async def test_ttb_start_and_reveal(client: AsyncClient):
    start = await client.post(
        "/api/v1/ttb/nfl/start",
        json={"mode": "classic", "include_defense": False, "hard_mode": False, "min_draft_year": None},
    )
    assert start.status_code == 200
    payload = start.json()
    assert payload["game_id"]
    assert payload["clues"]
    assert payload["hints"]

    reveal = await client.post(
        "/api/v1/ttb/nfl/guess",
        json={"game_id": payload["game_id"], "guess": "", "reveal": True, "skip": False},
    )
    assert reveal.status_code == 200
    assert reveal.json()["player"]


@pytest.mark.asyncio
async def test_nba_ttb_search(client: AsyncClient):
    response = await client.get("/api/v1/ttb/nba/search", params={"q": "leb"})
    assert response.status_code == 200
    assert response.json()["results"]


@pytest.mark.asyncio
async def test_dungeon_rewards_and_search(client: AsyncClient):
    rewards = await client.post(
        "/api/v1/dungeon/nfl/rewards",
        json={"floor": 1, "items": []},
    )
    assert rewards.status_code == 200
    assert rewards.json()["rewards"]

    search = await client.post(
        "/api/v1/dungeon/nfl/search",
        json={"query": "pey", "items": [], "question": None},
    )
    assert search.status_code == 200
    assert search.json()["results"]


@pytest.mark.asyncio
async def test_nba_dungeon_encounter(client: AsyncClient):
    encounter = await client.post(
        "/api/v1/dungeon/nba/encounter",
        json={"floor": 1, "items": [], "used_questions": []},
    )
    assert encounter.status_code == 200
    body = encounter.json()
    assert body["enemy"]["name"]
    assert body["question"]["prompt"]


@pytest.mark.asyncio
async def test_balatro_start_and_legacy_page(client: AsyncClient):
    nfl_start = await client.post("/api/v1/balatro/nfl/start", json={"mode": "normal"})
    assert nfl_start.status_code == 200
    nfl_body = nfl_start.json()
    assert nfl_body["game_id"]
    assert nfl_body["hand"]

    nba_start = await client.post("/api/v1/balatro/nba/start", json={"mode": "normal"})
    assert nba_start.status_code == 200
    nba_body = nba_start.json()
    assert nba_body["game_id"]
    assert nba_body["hand"]

    legacy_page = await client.get("/legacy-balatro/nfl")
    assert legacy_page.status_code == 200
    assert "NFL BALATRO" in legacy_page.text


@pytest.mark.asyncio
async def test_balatro_compat_start_alias(client: AsyncClient):
    response = await client.post("/api/nba_balatro/start", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["game_id"]
    assert body["hand"]
