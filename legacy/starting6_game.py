import random
import uuid

from session_store import GameStore


_GAMES = GameStore("starting6_game", ttl_seconds=14400)

SLOTS = [
    {"key": "QB", "label": "QB", "pos": "QB"},
    {"key": "WR1", "label": "WR 1", "pos": "WR"},
    {"key": "WR2", "label": "WR 2", "pos": "WR"},
    {"key": "RB1", "label": "RB 1", "pos": "RB"},
    {"key": "RB2", "label": "RB 2", "pos": "RB"},
    {"key": "TE", "label": "TE", "pos": "TE"},
    {"key": "UTIL", "label": "UTIL", "pos": "UTIL"},
]
BONUS_POSITIONS = ["QB", "WR", "RB", "TE"]
BONUS_DECADES = [1960, 1970, 1980]


def _random_bonus() -> dict:
    return {
        "pos": random.choice(BONUS_POSITIONS),
        "decade": random.choice(BONUS_DECADES),
    }


def _empty_roster() -> dict:
    return {slot["key"]: None for slot in SLOTS}


def _roster_full(roster: dict) -> bool:
    return all(roster.get(slot["key"]) is not None for slot in SLOTS)


def _needed_positions(roster: dict) -> dict:
    needed = {}
    for slot in SLOTS:
        if roster.get(slot["key"]) is None:
            needed[slot["pos"]] = needed.get(slot["pos"], 0) + 1
    return needed


def _pick_matches_bonus(pick: dict, bonus: dict) -> bool:
    return (
        pick.get("pos") == bonus.get("pos")
        and bonus.get("decade") <= int(pick.get("season", 0)) <= bonus.get("decade") + 9
    )


def _roster_total(roster: dict) -> float:
    total = 0.0
    for slot in SLOTS:
        pick = roster.get(slot["key"])
        if pick:
            total += float(pick.get("ppr") or 0) * float(pick.get("bonusMultiplier") or 1)
    return total


def _current_player(state: dict) -> dict:
    return state["players"][state["currentPlayer"]]


def _draw_team(conn) -> str | None:
    row = conn.execute(
        "SELECT team FROM stats WHERE team IS NOT NULL AND team != '' ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def _advance_turn(conn, state: dict):
    if all(_roster_full(player["roster"]) for player in state["players"]):
        state["done"] = True
        totals = [_roster_total(player["roster"]) for player in state["players"]]
        max_total = max(totals) if totals else 0
        winners = [idx for idx, total in enumerate(totals) if total == max_total]
        state["winner"] = {
            "totals": totals,
            "winner_indices": winners,
            "winner_names": [state["players"][idx]["name"] for idx in winners],
        }
        return

    n_players = len(state["players"])
    next_idx = (state["currentPlayer"] + 1) % n_players
    tries = 0
    while _roster_full(state["players"][next_idx]["roster"]) and tries < n_players:
        next_idx = (next_idx + 1) % n_players
        tries += 1
    state["currentPlayer"] = next_idx
    state["currentTeam"] = _draw_team(conn)
    state["bonus"] = _random_bonus()


def start_game(conn, player_names: list, player_tokens: list | None = None) -> tuple:
    if not 2 <= len(player_names) <= 5:
        raise ValueError("Need 2-5 players")
    if player_tokens and len(player_tokens) != len(player_names):
        raise ValueError("Player token count mismatch")

    players = []
    for idx, name in enumerate(player_names):
        players.append({
            "name": (name or f"Player {idx + 1}").strip() or f"Player {idx + 1}",
            "token": player_tokens[idx] if player_tokens else None,
            "roster": _empty_roster(),
        })

    state = {
        "game_id": str(uuid.uuid4())[:8],
        "players": players,
        "currentPlayer": 0,
        "currentTeam": _draw_team(conn),
        "bonus": _random_bonus(),
        "pickedPlayers": [],
        "skipsUsed": [0 for _ in players],
        "done": False,
        "winner": None,
    }
    _GAMES[state["game_id"]] = state
    return state["game_id"], state


def get_game(game_id: str) -> dict | None:
    return _GAMES.get(game_id)


def _validate_actor(state: dict, player_token: str | None):
    if not player_token:
        return None
    current = _current_player(state)
    if current.get("token") and current.get("token") != player_token:
        return "It is not your turn"
    return None


def search_players(conn, query: str, game_id: str) -> list:
    from name_utils import normalize_name
    state = get_game(game_id)
    if state is None:
        return []
    key = normalize_name(query)
    if not key:
        return []
    rows = conn.execute(
        "SELECT DISTINCT player FROM stats WHERE player IS NOT NULL AND player != '' ORDER BY player",
    ).fetchall()
    taken = set(state.get("pickedPlayers") or [])
    candidates = [row[0] for row in rows if row[0] not in taken]
    starts = [p for p in candidates if normalize_name(p).startswith(key)]
    contains = [p for p in candidates if not normalize_name(p).startswith(key) and key in normalize_name(p)]
    return (starts + contains)[:20]


def get_years(conn, game_id: str, player: str) -> list:
    state = get_game(game_id)
    if state is None or not player or player in set(state.get("pickedPlayers") or []):
        return []
    rows = conn.execute(
        "SELECT DISTINCT season FROM stats WHERE player = ? AND team = ? AND fantasy_ppr IS NOT NULL ORDER BY season DESC",
        (player, state["currentTeam"]),
    ).fetchall()
    return [row[0] for row in rows]


def submit_pick(conn, game_id: str, player: str, season: int, player_token: str | None = None) -> tuple:
    state = get_game(game_id)
    if state is None:
        return None, "Game not found"
    if state.get("done"):
        return state, "Game is already complete"
    actor_err = _validate_actor(state, player_token)
    if actor_err:
        return state, actor_err
    if player in set(state.get("pickedPlayers") or []):
        return state, f"{player} has already been drafted"

    row = conn.execute(
        "SELECT player, pos, fantasy_ppr, season, team FROM stats WHERE player = ? AND team = ? AND season = ?",
        (player, state["currentTeam"], int(season)),
    ).fetchone()
    if not row:
        return state, f"{player} ({season}) did not play for the {state['currentTeam']}"

    pick = {"player": row[0], "pos": row[1], "ppr": row[2], "season": row[3], "team": row[4]}
    roster = _current_player(state)["roster"]
    needed = _needed_positions(roster)
    if not needed.get(pick["pos"]) and not needed.get("UTIL"):
        return state, f"{pick['pos']} slots are already full"

    pick["bonusMultiplier"] = 1.5 if _pick_matches_bonus(pick, state["bonus"]) else 1
    slot = next((s for s in SLOTS if s["pos"] == pick["pos"] and roster[s["key"]] is None), None)
    if slot is None:
        slot = next((s for s in SLOTS if s["pos"] == "UTIL" and roster[s["key"]] is None), None)
    if slot is None:
        return state, "No valid slot available"

    roster[slot["key"]] = pick
    state["pickedPlayers"].append(pick["player"])
    _advance_turn(conn, state)
    _GAMES[state["game_id"]] = state
    return state, None


def pass_turn(conn, game_id: str, player_token: str | None = None) -> tuple:
    state = get_game(game_id)
    if state is None:
        return None, "Game not found"
    if state.get("done"):
        return state, "Game is already complete"
    actor_err = _validate_actor(state, player_token)
    if actor_err:
        return state, actor_err
    current_idx = state["currentPlayer"]
    if state["skipsUsed"][current_idx] >= 1:
        return state, "No skips remaining"
    state["skipsUsed"][current_idx] += 1
    _advance_turn(conn, state)
    _GAMES[state["game_id"]] = state
    return state, None
