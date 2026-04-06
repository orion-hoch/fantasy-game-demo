"""
codewords_game.py — Backend for the Code Words multiplayer game (NFL + NBA).

Two modes
---------
**Teams mode (4 players, 5x5):**
  Each team has a Spymaster (clue giver) and a Guesser. 7 tiles per team,
  11 neutral. Spymaster sees their own team's tile colors and gives clues.
  Guesser clicks tiles. First to uncover all 7 wins.

**Duel mode (2 players, 7x7):**
  Each player gives clues about the OTHER player's tiles so the other
  player can find them. 14 tiles per player, 21 neutral.

  Turn flow (Player A's turn):
    1. Player A sees Player B's tile colors and gives a clue about them.
    2. Player B guesses, trying to find B's own tiles based on A's clue.
    3. Turn flips — Player B gives clue about Player A's tiles, Player A
       guesses.

  First player to uncover all 14 of their own tiles wins.
"""

import random
import uuid

from session_store import GameStore


_GAMES = GameStore("codewords_game", ttl_seconds=14400)

MAX_CLUE_LEN = 50

# ── Board sizes per mode ─────────────────────────────────────────────────────

# Teams mode (4-player, 5x5)
TEAMS_BOARD_SIZE = 25
TEAMS_PER_TEAM = 7

# Duel mode (2-player, 7x7)
DUEL_BOARD_SIZE = 49
DUEL_PER_TEAM = 14


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


def _build_board(conn, sport: str, mode: str = "teams") -> list:
    if mode == "duel":
        board_size = DUEL_BOARD_SIZE
        per_team = DUEL_PER_TEAM
    else:
        board_size = TEAMS_BOARD_SIZE
        per_team = TEAMS_PER_TEAM

    pool = _fetch_pool(conn, sport)
    if len(pool) < board_size:
        raise ValueError(f"Not enough {sport.upper()} players for a board (need {board_size}, have {len(pool)})")

    chosen = random.sample(pool, board_size)
    neutral_count = board_size - per_team * 2
    teams = (
        ["A"] * per_team
        + ["B"] * per_team
        + ["neutral"] * neutral_count
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


def _validate_roster_teams(players: list) -> None:
    """Validate 4-player teams mode roster."""
    if len(players) != 4:
        raise ValueError("Code Words Teams needs exactly 4 players")
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


def _validate_roster_duel(players: list) -> None:
    """Validate 2-player duel mode roster."""
    if len(players) != 2:
        raise ValueError("Code Words Duel needs exactly 2 players")
    seen_tokens = set()
    for p in players:
        if not p.get("token"):
            raise ValueError("Missing player token")
        if p["token"] in seen_tokens:
            raise ValueError("Duplicate player token")
        seen_tokens.add(p["token"])
        if p.get("team") not in VALID_TEAMS:
            raise ValueError(f"{p.get('name','Player')} has not picked a team")
    teams = [p["team"] for p in players]
    if teams[0] == teams[1]:
        raise ValueError("Both players picked the same team")


# ── Public API ───────────────────────────────────────────────────────────────

def start_game(conn, players: list, sport: str, mode: str = "teams") -> tuple:
    """Create a fresh game.

    mode='teams': 4 players, 5x5 board. Each player has a team + role.
    mode='duel':  2 players, 7x7 board. Each player has a team; both act as
                  clue-giver for the OTHER player's tiles and guesser for
                  their OWN tiles.
    """
    if sport not in {"nfl", "nba"}:
        raise ValueError("Sport must be nfl or nba")
    if mode not in {"teams", "duel"}:
        raise ValueError("Mode must be teams or duel")

    if mode == "duel":
        _validate_roster_duel(players)
        per_team = DUEL_PER_TEAM
        # In duel mode both players have role="dual"
        player_list = [
            {"name": p["name"], "token": p["token"], "team": p["team"], "role": "dual"}
            for p in players
        ]
    else:
        _validate_roster_teams(players)
        per_team = TEAMS_PER_TEAM
        player_list = [
            {"name": p["name"], "token": p["token"], "team": p["team"], "role": p["role"]}
            for p in players
        ]

    board = _build_board(conn, sport, mode=mode)
    starting_team = random.choice(VALID_TEAMS)

    game_id = str(uuid.uuid4())[:8]
    state = {
        "game_id": game_id,
        "sport": sport,
        "mode": mode,
        "board": board,
        "players": player_list,
        "starting_team": starting_team,
        "current_team": starting_team,
        "current_phase": "clue",          # 'clue' | 'guess' | 'done'
        "current_clue": None,             # {text, number, remaining}
        "history": [],                    # list of {team, clue, number, guesses:[{index,result}]}
        "winner": None,
        "done": False,
        "team_a_total": per_team,
        "team_b_total": per_team,
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


def _is_duel(state: dict) -> bool:
    return state.get("mode") == "duel"


def _duel_clue_giver_team(state: dict) -> str:
    """In duel mode, the clue giver is the player whose team == current_team.
    They give clues about the OTHER team's tiles."""
    return state["current_team"]


def _duel_guesser_team(state: dict) -> str:
    """In duel mode, the guesser is the OTHER player (current_team flipped).
    They are trying to find their OWN tiles."""
    return "B" if state["current_team"] == "A" else "A"


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

    duel = _is_duel(state)
    if duel:
        if actor["team"] != _duel_clue_giver_team(state):
            return state, "It is not your turn to give a clue"
        # In duel the clue is about the opponent's tiles
        clue_about_team = _duel_guesser_team(state)
    else:
        if actor["team"] != state["current_team"]:
            return state, "It is not your team's turn"
        if actor["role"] != "spymaster":
            return state, "Only the spymaster can give a clue"
        clue_about_team = actor["team"]

    text = (clue_text or "").strip()
    if not text:
        return state, "Clue cannot be empty"
    if len(text) > MAX_CLUE_LEN:
        return state, f"Clue must be {MAX_CLUE_LEN} characters or less"

    try:
        n = int(clue_number)
    except (TypeError, ValueError):
        return state, "Clue number must be an integer"
    target_remaining = _team_remaining(state, clue_about_team)
    if n < 1 or n > target_remaining:
        return state, f"Clue number must be between 1 and {target_remaining}"

    state["current_clue"] = {
        "text": text,
        "number": n,
        "remaining": n + 1,
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
        return state, "Waiting for the clue giver's clue"

    actor = _player_by_token(state, token)
    if actor is None:
        return state, "You are not in this game"

    duel = _is_duel(state)
    board_size = DUEL_BOARD_SIZE if duel else TEAMS_BOARD_SIZE

    if duel:
        # In duel, the guesser is the player whose tiles are being clued
        expected_guesser_team = _duel_guesser_team(state)
        if actor["team"] != expected_guesser_team:
            return state, "It is not your turn to guess"
        # The guesser is looking for their OWN tiles
        own_team = actor["team"]
    else:
        if actor["team"] != state["current_team"]:
            return state, "It is not your team's turn"
        if actor["role"] != "guesser":
            return state, "Only the guesser can pick tiles"
        own_team = actor["team"]

    try:
        idx = int(board_index)
    except (TypeError, ValueError):
        return state, "Invalid tile"
    if not (0 <= idx < board_size):
        return state, "Invalid tile"

    cell = state["board"][idx]
    if cell.get("revealed"):
        return state, "That tile has already been revealed"

    cell["revealed"] = True
    cell_team = cell["team"]
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

    duel = _is_duel(state)
    if duel:
        if actor["team"] != _duel_guesser_team(state):
            return state, "It is not your turn to guess"
    else:
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
    """Return a serialised view of the game state.

    Visibility rules:
      - Teams mode: spymasters see their own team's tile colors. Guessers
        see none (until revealed).
      - Duel mode:  each player sees the OTHER player's tile colors (because
        they give clues about them). They do NOT see their own team's colors.
      - Everyone sees revealed tiles' colors.
      - When the game is done, everyone sees the full board.
    """
    actor = _player_by_token(state, token) if token else None
    duel = _is_duel(state)
    game_over = bool(state.get("done"))

    board_view = []
    for cell in state["board"]:
        out = {
            "index": cell["index"],
            "name": cell["name"],
            "headshot_url": cell["headshot_url"],
            "revealed": cell["revealed"],
        }
        if cell["revealed"] or game_over:
            out["team"] = cell["team"]
        elif actor is not None:
            if duel:
                # Show the OTHER player's tiles so you can give clues about them
                other_team = "B" if actor["team"] == "A" else "A"
                if cell["team"] == other_team or cell["team"] == "neutral":
                    out["team"] = cell["team"]
                else:
                    out["team"] = None  # hide your own tiles
            else:
                # Teams mode: spymasters see own team colors
                if actor.get("role") == "spymaster":
                    out["team"] = cell["team"]
                else:
                    out["team"] = None
        else:
            out["team"] = None
        board_view.append(out)

    # Determine what this player can see
    if game_over:
        can_see_full_key = True
    elif duel:
        can_see_full_key = False  # nobody sees full key in duel
    elif actor and actor.get("role") == "spymaster":
        can_see_full_key = True
    else:
        can_see_full_key = False

    return {
        "game_id": state["game_id"],
        "sport": state["sport"],
        "mode": state.get("mode", "teams"),
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
