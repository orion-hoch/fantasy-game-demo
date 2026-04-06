"""
codewords_game.py — Backend for the Code Words multiplayer game (NFL + NBA).

Game design
-----------
Two-team Codenames played with NFL or NBA Hall-of-Famers. 5x5 board of unique
players. Each game has 7 Team A players, 7 Team B players, 11 Neutral players.
There is no assassin tile.

Roles (4 players, picked in the lobby):
  - Team A Spymaster, Team A Guesser
  - Team B Spymaster, Team B Guesser

Turn flow per team:
  1. Spymaster submits a free-text clue (≤ 50 chars) and a number N.
  2. Guesser may click up to N+1 board tiles, one at a time.
     - Hitting own team's player → +1 reveal for own team, may continue.
     - Hitting opposing team's player → +1 reveal for opponent, turn ends.
     - Hitting neutral → turn ends.
  3. Guesser may end turn voluntarily after at least one guess.
  4. Turn flips to the other team. First team is chosen randomly.

A team wins when all 7 of its players are revealed.
"""

import random
import uuid

from session_store import GameStore


_GAMES = GameStore("codewords_game", ttl_seconds=14400)

BOARD_SIZE = 25
TEAM_A_COUNT = 7
TEAM_B_COUNT = 7
NEUTRAL_COUNT = BOARD_SIZE - TEAM_A_COUNT - TEAM_B_COUNT  # 11
MAX_CLUE_LEN = 50


# ── Player pools ──────────────────────────────────────────────────────────────

# Pool composition:
#  - Hall of Famers, but only "modern era" — first NFL/NBA season >= 1980.
#    (Excludes anyone drafted/playing before 1980 — handles undrafted HOFers
#    like Antonio Gates and Kurt Warner uniformly.)
#  - Active stars from the most recent season(s) who have an id we can use
#    for a headshot.

NBA_HOF_MIN_SEASON = 1980
NFL_HOF_MIN_FROM_YEAR = 1980

NBA_ACTIVE_SEASON = 2025
NBA_ACTIVE_MIN_GAMES = 30
NBA_ACTIVE_MIN_PPG = 12

NFL_ACTIVE_MIN_SEASON = 2024
NFL_ACTIVE_MIN_STARTS = 10


def _fetch_pool(conn, sport: str) -> list:
    """Return list of {name, headshot_url} for the Code Words player pool."""
    if sport == "nba":
        sql = """
            SELECT DISTINCT h.player, p.bbref_id
            FROM nba_hof h
            JOIN nba_player_ids p ON h.player = p.bbref_name
            WHERE h.category = 'Player'
              AND p.bbref_id IS NOT NULL AND p.bbref_id != ''
              AND h.player IN (
                  SELECT player FROM nba_stats GROUP BY player
                  HAVING MIN(season) >= ?
              )
            UNION
            SELECT DISTINCT s.player, p.bbref_id
            FROM nba_stats s
            JOIN nba_player_ids p ON s.player = p.bbref_name
            WHERE s.season = ?
              AND s.games >= ?
              AND s.pts_pg >= ?
              AND p.bbref_id IS NOT NULL AND p.bbref_id != ''
        """
        rows = conn.execute(
            sql,
            (NBA_HOF_MIN_SEASON, NBA_ACTIVE_SEASON, NBA_ACTIVE_MIN_GAMES, NBA_ACTIVE_MIN_PPG),
        ).fetchall()
        seen = set()
        pool = []
        for name, bbref_id in rows:
            if name in seen:
                continue
            seen.add(name)
            pool.append({
                "name": name,
                "headshot_url": f"https://www.basketball-reference.com/req/202106291/images/headshots/{bbref_id}.jpg",
            })
        return pool

    if sport == "nfl":
        sql = """
            SELECT DISTINCT h.player, p.pfr_id
            FROM nfl_hof h
            JOIN nfl_player_ids p ON h.player = p.pfr_name
            WHERE p.pfr_id IS NOT NULL AND p.pfr_id != ''
              AND h.from_year >= ?
            UNION
            SELECT DISTINCT s.player, p.pfr_id
            FROM stats s
            JOIN nfl_player_ids p ON s.player = p.pfr_name
            WHERE s.season >= ?
              AND s.games_started >= ?
              AND p.pfr_id IS NOT NULL AND p.pfr_id != ''
        """
        rows = conn.execute(
            sql,
            (NFL_HOF_MIN_FROM_YEAR, NFL_ACTIVE_MIN_SEASON, NFL_ACTIVE_MIN_STARTS),
        ).fetchall()
        seen = set()
        pool = []
        for name, pfr_id in rows:
            if name in seen:
                continue
            seen.add(name)
            pool.append({
                "name": name,
                "headshot_url": f"https://www.pro-football-reference.com/req/20230307/images/headshots/{pfr_id}.jpg",
            })
        return pool

    raise ValueError(f"Unknown sport: {sport}")


def _build_board(conn, sport: str) -> list:
    pool = _fetch_pool(conn, sport)
    if len(pool) < BOARD_SIZE:
        raise ValueError(f"Not enough {sport.upper()} HOF players for a board (need {BOARD_SIZE}, have {len(pool)})")

    chosen = random.sample(pool, BOARD_SIZE)
    teams = (
        ["A"] * TEAM_A_COUNT
        + ["B"] * TEAM_B_COUNT
        + ["neutral"] * NEUTRAL_COUNT
    )
    random.shuffle(teams)

    board = []
    for idx, p in enumerate(chosen):
        board.append({
            "index": idx,
            "name": p["name"],
            "headshot_url": p["headshot_url"],
            "team": teams[idx],
            "revealed": False,
        })
    return board


# ── Player / role validation ─────────────────────────────────────────────────

VALID_TEAMS = ("A", "B")
VALID_ROLES = ("spymaster", "guesser")


def _validate_roster(players: list) -> None:
    if len(players) != 4:
        raise ValueError("Code Words needs exactly 4 players")
    seen_tokens = set()
    by_team_role: dict = {}
    for p in players:
        if not p.get("token"):
            raise ValueError("Missing player token")
        if p["token"] in seen_tokens:
            raise ValueError("Duplicate player token")
        seen_tokens.add(p["token"])
        team = p.get("team")
        role = p.get("role")
        if team not in VALID_TEAMS:
            raise ValueError(f"{p.get('name','Player')} has not picked a team")
        if role not in VALID_ROLES:
            raise ValueError(f"{p.get('name','Player')} has not picked a role")
        key = (team, role)
        if key in by_team_role:
            raise ValueError(f"Two players claimed {team}/{role}; each role must be unique")
        by_team_role[key] = p
    for team in VALID_TEAMS:
        for role in VALID_ROLES:
            if (team, role) not in by_team_role:
                raise ValueError(f"Missing Team {team} {role}")


# ── Public API ───────────────────────────────────────────────────────────────

def start_game(conn, players: list, sport: str) -> tuple:
    """Create a fresh game.

    `players` is a list of dicts with keys: name, token, team ('A'|'B'),
    role ('spymaster'|'guesser').
    """
    if sport not in {"nfl", "nba"}:
        raise ValueError("Sport must be nfl or nba")
    _validate_roster(players)

    board = _build_board(conn, sport)
    starting_team = random.choice(VALID_TEAMS)

    game_id = str(uuid.uuid4())[:8]
    state = {
        "game_id": game_id,
        "sport": sport,
        "board": board,
        "players": [
            {
                "name": p["name"],
                "token": p["token"],
                "team": p["team"],
                "role": p["role"],
            }
            for p in players
        ],
        "starting_team": starting_team,
        "current_team": starting_team,
        "current_phase": "clue",          # 'clue' | 'guess' | 'done'
        "current_clue": None,             # {text, number, remaining}
        "history": [],                    # list of {team, clue, number, guesses:[{index,result}]}
        "winner": None,
        "done": False,
        "team_a_total": TEAM_A_COUNT,
        "team_b_total": TEAM_B_COUNT,
        "team_a_revealed": 0,
        "team_b_revealed": 0,
    }
    _GAMES[game_id] = state
    return game_id, state


def get_game(game_id: str) -> dict | None:
    return _GAMES.get(game_id)


def _player_by_token(state: dict, token: str) -> dict | None:
    for p in state.get("players", []):
        if p.get("token") == token:
            return p
    return None


def submit_clue(game_id: str, token: str, clue_text: str, clue_number: int) -> tuple:
    state = _GAMES.get(game_id)
    if state is None:
        return None, "Game not found"
    if state.get("done"):
        return state, "Game is already over"
    if state.get("current_phase") != "clue":
        return state, "Waiting for the guesser, not for a clue"

    actor = _player_by_token(state, token)
    if actor is None:
        return state, "You are not in this game"
    if actor["team"] != state["current_team"]:
        return state, "It is not your team's turn"
    if actor["role"] != "spymaster":
        return state, "Only the spymaster can give a clue"

    text = (clue_text or "").strip()
    if not text:
        return state, "Clue cannot be empty"
    if len(text) > MAX_CLUE_LEN:
        return state, f"Clue must be {MAX_CLUE_LEN} characters or less"

    try:
        n = int(clue_number)
    except (TypeError, ValueError):
        return state, "Clue number must be an integer"
    own_remaining = _team_remaining(state, actor["team"])
    if n < 1 or n > own_remaining:
        return state, f"Clue number must be between 1 and {own_remaining}"

    state["current_clue"] = {
        "text": text,
        "number": n,
        "remaining": n + 1,  # classic Codenames: N+1 guesses
        "guesses_made": 0,
    }
    state["current_phase"] = "guess"
    state["history"].append({
        "team": actor["team"],
        "clue": text,
        "number": n,
        "guesses": [],
    })
    _GAMES[game_id] = state
    return state, None


def submit_guess(game_id: str, token: str, board_index: int) -> tuple:
    state = _GAMES.get(game_id)
    if state is None:
        return None, "Game not found"
    if state.get("done"):
        return state, "Game is already over"
    if state.get("current_phase") != "guess":
        return state, "Waiting for the spymaster's clue"

    actor = _player_by_token(state, token)
    if actor is None:
        return state, "You are not in this game"
    if actor["team"] != state["current_team"]:
        return state, "It is not your team's turn"
    if actor["role"] != "guesser":
        return state, "Only the guesser can pick tiles"

    try:
        idx = int(board_index)
    except (TypeError, ValueError):
        return state, "Invalid tile"
    if not (0 <= idx < BOARD_SIZE):
        return state, "Invalid tile"

    cell = state["board"][idx]
    if cell.get("revealed"):
        return state, "That tile has already been revealed"

    cell["revealed"] = True
    cell_team = cell["team"]
    own_team = actor["team"]
    other_team = "B" if own_team == "A" else "A"

    if cell_team == "A":
        state["team_a_revealed"] += 1
    elif cell_team == "B":
        state["team_b_revealed"] += 1

    result = "own" if cell_team == own_team else ("opponent" if cell_team == other_team else "neutral")

    clue = state["current_clue"] or {}
    clue["guesses_made"] = clue.get("guesses_made", 0) + 1
    clue["remaining"] = max(0, clue.get("remaining", 1) - 1)
    state["current_clue"] = clue

    if state["history"]:
        state["history"][-1]["guesses"].append({"index": idx, "result": result})

    # Win check
    if state["team_a_revealed"] >= state["team_a_total"]:
        state["winner"] = "A"
        state["done"] = True
        state["current_phase"] = "done"
        state["current_clue"] = None
        _GAMES[game_id] = state
        return state, None
    if state["team_b_revealed"] >= state["team_b_total"]:
        state["winner"] = "B"
        state["done"] = True
        state["current_phase"] = "done"
        state["current_clue"] = None
        _GAMES[game_id] = state
        return state, None

    # Turn-end conditions
    if result != "own" or clue["remaining"] <= 0:
        _flip_turn(state)

    _GAMES[game_id] = state
    return state, None


def end_turn(game_id: str, token: str) -> tuple:
    state = _GAMES.get(game_id)
    if state is None:
        return None, "Game not found"
    if state.get("done"):
        return state, "Game is already over"
    if state.get("current_phase") != "guess":
        return state, "Cannot end turn right now"
    actor = _player_by_token(state, token)
    if actor is None:
        return state, "You are not in this game"
    if actor["team"] != state["current_team"]:
        return state, "It is not your team's turn"
    if actor["role"] != "guesser":
        return state, "Only the guesser can end the turn"
    clue = state.get("current_clue") or {}
    if clue.get("guesses_made", 0) < 1:
        return state, "You must make at least one guess before ending the turn"

    _flip_turn(state)
    _GAMES[game_id] = state
    return state, None


def _flip_turn(state: dict) -> None:
    state["current_team"] = "B" if state["current_team"] == "A" else "A"
    state["current_phase"] = "clue"
    state["current_clue"] = None


def _team_remaining(state: dict, team: str) -> int:
    if team == "A":
        return max(1, state["team_a_total"] - state["team_a_revealed"])
    return max(1, state["team_b_total"] - state["team_b_revealed"])


# ── State serialisation ──────────────────────────────────────────────────────

def view_state(state: dict, token: str | None) -> dict:
    """Return a copy of state with hidden tile colors stripped for non-spymasters."""
    actor = _player_by_token(state, token) if token else None
    can_see_full_key = bool(state.get("done")) or (actor is not None and actor.get("role") == "spymaster")

    board_view = []
    for cell in state["board"]:
        out = {
            "index": cell["index"],
            "name": cell["name"],
            "headshot_url": cell["headshot_url"],
            "revealed": cell["revealed"],
        }
        if cell["revealed"] or can_see_full_key:
            out["team"] = cell["team"]
        else:
            out["team"] = None
        board_view.append(out)

    return {
        "game_id": state["game_id"],
        "sport": state["sport"],
        "board": board_view,
        "players": [
            {"name": p["name"], "team": p["team"], "role": p["role"]}
            for p in state["players"]
        ],
        "starting_team": state["starting_team"],
        "current_team": state["current_team"],
        "current_phase": state["current_phase"],
        "current_clue": state.get("current_clue"),
        "history": state.get("history", []),
        "winner": state.get("winner"),
        "done": state.get("done", False),
        "team_a_total": state["team_a_total"],
        "team_b_total": state["team_b_total"],
        "team_a_revealed": state["team_a_revealed"],
        "team_b_revealed": state["team_b_revealed"],
        "team_a_remaining": state["team_a_total"] - state["team_a_revealed"],
        "team_b_remaining": state["team_b_total"] - state["team_b_revealed"],
        "you": (
            {"team": actor["team"], "role": actor["role"], "name": actor["name"]}
            if actor else None
        ),
        "can_see_full_key": can_see_full_key,
    }
