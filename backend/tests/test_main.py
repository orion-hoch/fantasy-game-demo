"""Basic FastAPI strangler tests."""

import sqlite3

import pytest
from httpx import ASGITransport, AsyncClient

from src.legacy.bridge import ensure_repo_on_path
from src.main import app
from src.player_search import all_players as all_sport_players
from src.redis_client import get_redis_client

ensure_repo_on_path()

import lobby_store  # noqa: E402
import codewords_game  # noqa: E402
import nfl_bullseye  # noqa: E402
import nba_bullseye  # noqa: E402
import nfl_balatro  # noqa: E402
import nba_balatro  # noqa: E402
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


def _bullseye_outside_player(module, sport: str, state: dict) -> tuple[int, str]:
    """Find a (prompt_idx, player) where the player is in the full sport pool
    but NOT among the prompt's "correct answers". Used to assert search/season
    pickers never pre-filter to the answer set."""
    conn = sqlite3.connect("/Users/orionhoch/fantasy_game_demo/fantasy.db")
    try:
        stat = state["stat"]
        if sport == "nfl":
            table = module._stat_table(stat)
            stat_expr = module._stat_expr(stat)
            pos_frag, pos_params = module._pos_filter_clause(stat)
            stat_floor = module._min_val(stat)
            all_rows = conn.execute(
                f"SELECT DISTINCT s.player FROM {table} s WHERE games >= 4 AND {stat_expr} >= ? {pos_frag}",
                [stat_floor] + pos_params,
            ).fetchall()
            all_players = {row[0] for row in all_rows}

            for prompt_idx, prompt in enumerate(state["prompts"]):
                where, prompt_pos_frag, prompt_params = module._build_prompt_where(prompt, stat, apply_stat_floor=True)
                prompt_rows = conn.execute(
                    f"SELECT DISTINCT s.player FROM {table} s {where} {prompt_pos_frag}",
                    prompt_params,
                ).fetchall()
                prompt_players = {row[0] for row in prompt_rows}
                outside = sorted(all_players - prompt_players)
                if outside:
                    return prompt_idx, outside[0]
        else:
            stat_expr = module._stat_expr(stat)
            stat_floor = module._STAT_MIN.get(stat, 0)
            all_rows = conn.execute(
                f"SELECT DISTINCT s.player FROM nba_stats s WHERE games >= 4 AND {stat_expr} >= ? AND s.player IS NOT NULL AND s.player != ''",
                [stat_floor],
            ).fetchall()
            all_players = {row[0] for row in all_rows}

            for prompt_idx, prompt in enumerate(state["prompts"]):
                where, prompt_params = module._build_prompt_where(prompt, stat, apply_stat_floor=True)
                prompt_rows = conn.execute(
                    f"SELECT DISTINCT s.player FROM nba_stats s {where} AND s.player IS NOT NULL AND s.player != ''",
                    prompt_params,
                ).fetchall()
                prompt_players = {row[0] for row in prompt_rows}
                outside = sorted(all_players - prompt_players)
                if outside:
                    return prompt_idx, outside[0]
    finally:
        conn.close()

    raise AssertionError(f"No 'outside' player found for {sport} bullseye state")


@pytest.mark.asyncio
@pytest.mark.parametrize("player_names", [["Solo"], ["Host", "Guest"]], ids=["solo", "multiplayer"])
async def test_bullseye_search_and_seasons_never_leak_answers(client: AsyncClient, player_names: list[str]):
    """Bullseye picker UI must never pre-filter to "correct" players or seasons.

    Regression guard for the bug where solo bullseye filtered the search bar
    down to the prompt's answer set. The same invariant is enforced for the
    season dropdown so wrong-team players still expose all their seasons.
    """
    module_specs = [
        ("nfl", nfl_bullseye),
        ("nba", nba_bullseye),
    ]

    for sport, module in module_specs:
        start = await client.post(
            f"/api/v1/bullseye/{sport}/start",
            json={"player_names": player_names},
        )
        assert start.status_code == 200
        game_id = start.json()["game_id"]
        state = module.get_game(game_id)
        assert state is not None

        chosen_prompt_idx, outside_player = _bullseye_outside_player(module, sport, state)

        query = outside_player[:4]
        search = await client.get(
            f"/api/v1/bullseye/{sport}/search",
            params={"game_id": game_id, "prompt_idx": chosen_prompt_idx, "q": query},
        )
        assert search.status_code == 200
        found_players = {row["player"] for row in search.json()["results"]}
        assert outside_player in found_players, (
            f"{sport} bullseye search ({player_names}) leaked answers: "
            f"non-matching player {outside_player!r} missing from results"
        )

        # Direct call into the legacy engine's search — guards the still-live
        # Flask compatibility routes (/api/nba_bullseye/search etc.) which call
        # module.search_players directly without going through the FastAPI service.
        conn = sqlite3.connect("/Users/orionhoch/fantasy_game_demo/fantasy.db")
        try:
            engine_results = module.search_players(conn, query, chosen_prompt_idx, game_id)
        finally:
            conn.close()
        engine_names = {row["player"] for row in engine_results}
        assert outside_player in engine_names, (
            f"{sport} bullseye engine search_players ({player_names}) leaked answers"
        )

        seasons = await client.get(
            f"/api/v1/bullseye/{sport}/seasons",
            params={"game_id": game_id, "prompt_idx": chosen_prompt_idx, "player": outside_player},
        )
        assert seasons.status_code == 200
        assert seasons.json()["seasons"], (
            f"{sport} bullseye seasons ({player_names}) returned empty for "
            f"non-matching player {outside_player!r} — picker is filtering by prompt"
        )


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
async def test_chain_lobby_requires_player_one_start_button_flow(client: AsyncClient):
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

    game_id = start.json()["room"]["game_id"]
    assert game_id

    pre_guess = await client.post(
        "/api/v1/chain/nfl/guess",
        json={"game_id": game_id, "player": "Tom Brady", "token": "host-token"},
    )
    assert pre_guess.status_code == 200
    assert pre_guess.json()["ok"] is False
    assert "not started" in pre_guess.json()["error"].lower()

    guest_start = await client.post(
        f"/api/v1/lobbies/{room_id}/chain/start",
        json={"token": "guest-token"},
    )
    assert guest_start.status_code == 400

    host_start = await client.post(
        f"/api/v1/lobbies/{room_id}/chain/start",
        json={"token": "host-token"},
    )
    assert host_start.status_code == 200
    assert host_start.json()["state"]["started"] is True


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
async def test_balatro_start(client: AsyncClient):
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


@pytest.mark.asyncio
async def test_all_game_search_endpoints_use_full_sport_player_pool(client: AsyncClient):
    conn = sqlite3.connect("/Users/orionhoch/fantasy_game_demo/fantasy.db")
    try:
        samples = {
            "nfl": next((name for name in all_sport_players(conn, "nfl") if len(name) >= 4), None),
            "nba": next((name for name in all_sport_players(conn, "nba") if len(name) >= 4), None),
        }
    finally:
        conn.close()

    assert samples["nfl"]
    assert samples["nba"]

    for sport, sample_player in samples.items():
        assert sample_player is not None
        query = sample_player[:4]

        bull_start = await client.post(
            f"/api/v1/bullseye/{sport}/start",
            json={"player_names": ["Solo"]},
        )
        assert bull_start.status_code == 200
        bull_game_id = bull_start.json()["game_id"]

        duel_start = await client.post(
            f"/api/v1/fantasy-duel/{sport}/start",
            json={"player_names": ["A", "B"]},
        )
        assert duel_start.status_code == 200
        duel_game_id = duel_start.json()["game_id"]

        bull_search = await client.get(
            f"/api/v1/bullseye/{sport}/search",
            params={"game_id": bull_game_id, "prompt_idx": 0, "q": query},
        )
        assert bull_search.status_code == 200
        assert sample_player in {entry["player"] for entry in bull_search.json()["results"]}

        duel_search = await client.get(
            f"/api/v1/fantasy-duel/{sport}/search",
            params={"game_id": duel_game_id, "q": query},
        )
        assert duel_search.status_code == 200
        assert sample_player in set(duel_search.json()["results"])

        chain_search = await client.get(
            f"/api/v1/chain/{sport}/search",
            params={"q": query},
        )
        assert chain_search.status_code == 200
        assert sample_player in {entry["name"] for entry in chain_search.json()["results"]}

        ttb_search = await client.get(
            f"/api/v1/ttb/{sport}/search",
            params={"q": query},
        )
        assert ttb_search.status_code == 200
        assert sample_player in {entry["name"] for entry in ttb_search.json()["results"]}

        dungeon_search = await client.post(
            f"/api/v1/dungeon/{sport}/search",
            json={"query": query, "items": [], "question": None},
        )
        assert dungeon_search.status_code == 200
        assert sample_player in set(dungeon_search.json()["results"])


@pytest.mark.asyncio
async def test_balatro_api_shop_buy_and_pack_flow(client: AsyncClient):
    module_specs = [
        ("nfl", nfl_balatro, "QB"),
        ("nba", nba_balatro, "G"),
    ]

    for sport, module, pos in module_specs:
        start = await client.post(f"/api/v1/balatro/{sport}/start", json={"mode": "normal"})
        assert start.status_code == 200
        gid = start.json()["game_id"]

        state = module.get_state(gid)
        assert state is not None
        state["status"] = "shopping"
        state["coins"] = 50
        state["shop_items"] = [
            {
                "shop_id": "test-item",
                "type": "skill_card",
                "item_type": "skill_card",
                "pos": pos,
                "cost": 1,
                "name": "Test Skill",
                "desc": "test",
                "section": "training",
            }
        ]
        state["shop_packs"] = [dict(module.PACK_MAP["starter_pack"])]
        module._GAMES[gid] = state

        buy = await client.post(
            f"/api/v1/balatro/{sport}/buy_item",
            json={"game_id": gid, "shop_id": "test-item", "item_type": "skill_card"},
        )
        assert buy.status_code == 200
        assert all(item["shop_id"] != "test-item" for item in buy.json()["shop_items"])

        open_pack = await client.post(
            f"/api/v1/balatro/{sport}/open_pack",
            json={"game_id": gid, "pack_id": "starter_pack"},
        )
        assert open_pack.status_code == 200
        open_body = open_pack.json()
        assert open_body["candidates"]
        assert open_body["picks_allowed"] == open_body["max_picks"]
        assert "cards" in open_body
        assert all(pack.get("id") != "starter_pack" for pack in open_body.get("shop_packs", []))

        selected_id = open_body["candidates"][0]["id"]
        confirm = await client.post(
            f"/api/v1/balatro/{sport}/confirm_pack_picks",
            json={"game_id": gid, "selected_ids": [selected_id]},
        )
        assert confirm.status_code == 200
        confirm_body = confirm.json()
        assert "shop_items" in confirm_body
        assert "shop_packs" in confirm_body


def test_balatro_shop_buy_and_pack_remove_entries():
    db_path = "/Users/orionhoch/fantasy_game_demo/fantasy.db"
    module_specs = [
        ("nfl", nfl_balatro, "QB"),
        ("nba", nba_balatro, "G"),
    ]

    for _sport, module, pos in module_specs:
        conn = sqlite3.connect(db_path)
        try:
            if _sport == "nfl":
                gid, _ = module.start_game(conn, mode="normal")
            else:
                gid, _ = module.start_game(conn)
        finally:
            conn.close()

        state = module.get_state(gid)
        assert state is not None
        state["status"] = "shopping"
        state["coins"] = 50
        state["shop_items"] = [
            {
                "shop_id": "test-item",
                "type": "skill_card",
                "item_type": "skill_card",
                "pos": pos,
                "cost": 1,
                "name": "Test Skill",
                "desc": "test",
                "section": "training",
            }
        ]
        state["shop_packs"] = [dict(module.PACK_MAP["starter_pack"])]
        module._GAMES[gid] = state

        conn = sqlite3.connect(db_path)
        try:
            buy_result, buy_err = module.buy_shop_item(gid, "skill_card", "test-item", conn=conn)
        finally:
            conn.close()
        assert buy_err is None
        assert all(item["shop_id"] != "test-item" for item in buy_result["shop_items"])

        conn = sqlite3.connect(db_path)
        try:
            pack_result, pack_err = module.open_pack(gid, "starter_pack", conn)
        finally:
            conn.close()
        assert pack_err is None
        assert pack_result["picks_allowed"] == pack_result["max_picks"]
        assert "cards" in pack_result
        assert all(pack.get("id") != "starter_pack" for pack in module.get_state(gid).get("shop_packs", []))

        selected_id = pack_result["candidates"][0]["id"]
        confirm_result, confirm_err = module.confirm_pack_picks(gid, [selected_id])
        assert confirm_err is None
        assert "shop_items" in confirm_result
        assert "shop_packs" in confirm_result
