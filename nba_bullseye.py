"""
nba_bullseye.py — Backend logic for NBA Bullseye multiplayer game.

Game flow:
  1. start_game(conn, player_names) — generate prompts, target, return initial state
  2. submit_pick(conn, game_id, player_name, season) — validate & record a pick
  3. search_players(conn, query, prompt_idx, game_id) — autocomplete for current prompt
  4. get_game(game_id) — fetch current state dict
"""

import random
import uuid
from session_store import GameStore

_GAMES = GameStore("nba_bullseye", ttl_seconds=14400)

# ── Constants ──────────────────────────────────────────────────────────────────

STAT_CATEGORIES = ["PTS", "AST", "REB", "STL", "BLK", "3PM", "FGM", "FTM", "TOV"]
MIN_PROMPT_PLAYERS = 5

EASTERN_TEAMS = ["ATL", "BOS", "BRK", "NJN", "CHO", "CHA", "CHI", "CLE",
                 "DET", "IND", "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS", "WSB"]
WESTERN_TEAMS = ["DAL", "DEN", "GSW", "HOU", "LAC", "LAL", "MEM", "VAN",
                 "MIN", "NOP", "NOH", "OKC", "SEA", "PHO", "POR", "SAC", "SAS", "UTA"]

ALL_TEAMS = EASTERN_TEAMS + WESTERN_TEAMS

# Historical → modern franchise mapping
_HIST_TO_MOD = {
    "NJN": "BRK", "SEA": "OKC", "NOH": "NOP", "NOK": "NOP",
    "CHH": "CHA", "CHO": "CHA", "VAN": "MEM", "WSB": "WAS",
}

NBA_DIVISIONS = {
    "Atlantic": ["BOS", "BRK", "NJN", "NYK", "PHI", "TOR"],
    "Central": ["CHI", "CLE", "DET", "IND", "MIL"],
    "Southeast": ["ATL", "CHA", "CHO", "MIA", "ORL", "WAS", "WSB"],
    "Northwest": ["DEN", "MIN", "OKC", "SEA", "POR", "UTA"],
    "Pacific": ["GSW", "LAC", "LAL", "PHO", "SAC"],
    "Southwest": ["DAL", "HOU", "MEM", "VAN", "NOP", "NOH", "SAS"],
}


def _stat_expr(stat: str) -> str:
    """Return the SQL expression for a given stat category."""
    if stat == "PTS":
        return "pts"
    elif stat == "AST":
        return "ast"
    elif stat == "REB":
        return "CAST(ROUND(trb_pg * games) AS INTEGER)"
    elif stat == "STL":
        return "CAST(stl AS INTEGER)"
    elif stat == "BLK":
        return "CAST(blk AS INTEGER)"
    elif stat == "3PM":
        return "CAST(threepm AS INTEGER)"
    elif stat == "FGM":
        return "fgm"
    elif stat == "FTM":
        return "ftm"
    elif stat == "TOV":
        return "CAST(tov AS INTEGER)"
    return "pts"


_STAT_MIN = {
    "PTS": 200, "AST": 100, "REB": 150, "STL": 20, "BLK": 10,
    "3PM": 20, "FGM": 150, "FTM": 50, "TOV": 50,
}

ACCOLADE_OPTIONS = [
    "allstar",
    "top10_draft",
    "top5_draft",
    "nba_hof",
    "all_nba",
    "all_defensive",
    "all_rookie_nba",
    "olympic_team",
    "nba_mvp",
    "nba_fmvp",
    "nba_dpoy",
]


def _accolade_sql(accolade: str) -> str:
    """Return a SQL fragment (with no leading AND) for an accolade filter."""
    if accolade == "allstar":
        return "EXISTS (SELECT 1 FROM nba_allstars a WHERE a.player = s.player AND a.selections > 0)"
    elif accolade == "top10_draft":
        return "EXISTS (SELECT 1 FROM nba_draft d WHERE d.player = s.player AND d.draft_pick <= 10)"
    elif accolade == "top5_draft":
        return "EXISTS (SELECT 1 FROM nba_draft d WHERE d.player = s.player AND d.draft_pick <= 5)"
    elif accolade == "nba_hof":
        return "EXISTS (SELECT 1 FROM nba_hof h WHERE h.player = s.player)"
    elif accolade == "all_nba":
        return "EXISTS (SELECT 1 FROM nba_allnba an WHERE an.player = s.player)"
    elif accolade == "all_defensive":
        return "EXISTS (SELECT 1 FROM nba_alldefensive ad WHERE ad.player = s.player)"
    elif accolade == "all_rookie_nba":
        return "EXISTS (SELECT 1 FROM nba_allrookie ar WHERE ar.player = s.player)"
    elif accolade == "olympic_team":
        return "EXISTS (SELECT 1 FROM nba_olympic_teams ot WHERE ot.player = s.player)"
    elif accolade == "nba_mvp":
        return "EXISTS (SELECT 1 FROM nba_awards a WHERE a.player = s.player AND a.award = 'MVP' AND a.is_winner = 1)"
    elif accolade == "nba_fmvp":
        return "EXISTS (SELECT 1 FROM nba_awards a WHERE a.player = s.player AND a.award = 'FMVP' AND a.is_winner = 1)"
    elif accolade == "nba_dpoy":
        return "EXISTS (SELECT 1 FROM nba_awards a WHERE a.player = s.player AND a.award = 'DPOY' AND a.is_winner = 1)"
    return None


def _teams_in_clause(teams: list) -> tuple:
    """Return (placeholders, params) for a list of team codes."""
    placeholders = ",".join("?" * len(teams))
    return f"({placeholders})", list(teams)


def _build_prompt_where(prompt: dict, stat: str = None, apply_stat_floor: bool = False) -> tuple:
    """
    Build (where_clause_str, params_list) for a prompt dict.
    Clause starts with "WHERE ".
    """
    clauses = ["games > 20"]
    params = []

    team_filter = prompt.get("team_filter")
    if team_filter in NBA_DIVISIONS:
        ph, p = _teams_in_clause(NBA_DIVISIONS[team_filter])
        clauses.append(f"s.team IN {ph}")
        params.extend(p)
    elif team_filter == "Eastern":
        ph, p = _teams_in_clause(EASTERN_TEAMS)
        clauses.append(f"s.team IN {ph}")
        params.extend(p)
    elif team_filter == "Western":
        ph, p = _teams_in_clause(WESTERN_TEAMS)
        clauses.append(f"s.team IN {ph}")
        params.extend(p)
    elif team_filter and team_filter not in ("any", None):
        # Specific team — expand to historical equivalents
        equiv = [team_filter]
        for hist, mod in _HIST_TO_MOD.items():
            if mod == team_filter:
                equiv.append(hist)
        ph, p = _teams_in_clause(equiv)
        clauses.append(f"s.team IN {ph}")
        params.extend(p)

    yr_min = prompt.get("year_min")
    yr_max = prompt.get("year_max")
    if yr_min:
        clauses.append("s.season >= ?")
        params.append(yr_min)
    if yr_max:
        clauses.append("s.season <= ?")
        params.append(yr_max)

    accolade = prompt.get("accolade")
    ac_sql = _accolade_sql(accolade) if accolade else None
    if ac_sql:
        clauses.append(ac_sql)

    if stat and apply_stat_floor:
        stat_expr = _stat_expr(stat)
        min_val = _STAT_MIN.get(stat, 0)
        if min_val > 0:
            clauses.append(f"{stat_expr} >= ?")
            params.append(min_val)

    return "WHERE " + " AND ".join(clauses), params


def _prompt_player_count(conn, prompt: dict, stat: str) -> int:
    where, params = _build_prompt_where(prompt, stat, apply_stat_floor=True)
    row = conn.execute(
        f"SELECT COUNT(DISTINCT s.player) FROM nba_stats s {where}",
        params,
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _generate_prompts(conn, stat: str) -> list:
    """Generate 5 varied prompts for a stat category with viable player pools."""

    storied_franchises = ["BOS", "LAL", "GSW", "CHI", "MIA", "SAS", "NYK", "PHI", "DET", "HOU"]
    other_franchises = ["DAL", "OKC", "DEN", "POR", "UTA", "SAC", "MIL", "ATL", "CLE", "IND", "ORL", "MIN", "TOR", "BRK", "NOP"]
    division_names = list(NBA_DIVISIONS.keys())

    year_ranges = [
        (2015, 2024),
        (2010, 2024),
        (2000, 2015),
        (1990, 2005),
        (1980, 2000),
        (1970, 1990),
        (1995, 2010),
    ]

    team_filter_pool = (
        storied_franchises
        + other_franchises
        + ALL_TEAMS
        + division_names
        + [None, None, None]
    )

    prompts = []
    seen = set()

    attempts = 0
    while len(prompts) < 5 and attempts < 400:
        attempts += 1
        team_filter = random.choice(team_filter_pool)
        yr_min, yr_max = random.choice(year_ranges)
        accolade = random.choice(ACCOLADE_OPTIONS + [None, None])

        sig = (team_filter, yr_min, yr_max, accolade)
        if sig in seen:
            continue
        seen.add(sig)

        prompt = {
            "team_filter": team_filter,
            "team_filter_label": team_filter or "Any Team",
            "year_min": yr_min,
            "year_max": yr_max,
            "accolade": accolade,
        }

        count = _prompt_player_count(conn, prompt, stat)
        if count < MIN_PROMPT_PLAYERS:
            continue

        prompt["available_count"] = count
        prompts.append(prompt)

    fallback_templates = [
        (None, 2010, 2024, None),
        (None, 2000, 2024, None),
        (None, 1990, 2024, None),
        (random.choice(division_names), 2000, 2024, None),
    ]
    for team_filter, yr_min, yr_max, accolade in fallback_templates:
        if len(prompts) >= 5:
            break
        sig = (team_filter, yr_min, yr_max, accolade)
        if sig in seen:
            continue
        seen.add(sig)
        prompt = {
            "team_filter": team_filter,
            "team_filter_label": team_filter or "Any Team",
            "year_min": yr_min,
            "year_max": yr_max,
            "accolade": accolade,
        }
        count = _prompt_player_count(conn, prompt, stat)
        if count >= MIN_PROMPT_PLAYERS:
            prompt["available_count"] = count
            prompts.append(prompt)

    if len(prompts) < 5:
        raise ValueError("Could not generate Bullseye prompts with enough players")

    if not any(prompt.get("accolade") for prompt in prompts):
        shuffled = ACCOLADE_OPTIONS[:]
        random.shuffle(shuffled)
        for idx, prompt in enumerate(prompts):
            for accolade in shuffled:
                candidate = dict(prompt)
                candidate["accolade"] = accolade
                count = _prompt_player_count(conn, candidate, stat)
                if count >= MIN_PROMPT_PLAYERS:
                    candidate["available_count"] = count
                    prompts[idx] = candidate
                    break
            if any(p.get("accolade") for p in prompts):
                break

    return prompts[:5]


def _compute_target(conn, prompts: list, stat: str) -> int:
    stat_expr = _stat_expr(stat)
    row = conn.execute(
        f"""
        SELECT AVG({stat_expr}), MAX({stat_expr})
        FROM nba_stats s
        WHERE games > 20 AND {stat_expr} > 0
        """
    ).fetchone()
    mean_val = float(row[0] or 0)
    max_val = float(row[1] or 0)
    if max_val <= 0:
        return 500
    lower = max(1, mean_val)
    upper = max(lower, max_val * 2.5)
    target = random.uniform(lower, upper)
    return max(1, int(round(target / 10.0) * 10))


# ── Turn management helpers ───────────────────────────────────────────────────

def _turn_player_order(prompt_idx: int, n_players: int) -> list:
    if prompt_idx % 2 == 0:
        return list(range(n_players))
    return list(range(n_players - 1, -1, -1))

def _current_turn(state: dict) -> tuple:
    """
    Return (player_idx, prompt_idx) for the current pending pick.
    Turn order snakes by prompt row.
    Returns (None, None) if game is finished.
    """
    n_players = len(state["players"])
    n_prompts = 5
    picks = state["picks"]  # list of lists: picks[prompt_idx][player_idx] or None

    for prompt_idx in range(n_prompts):
        for player_idx in _turn_player_order(prompt_idx, n_players):
            if picks[prompt_idx][player_idx] is None:
                return player_idx, prompt_idx
    return None, None


def _used_players(state: dict) -> set:
    used = set()
    for row in state["picks"]:
        for pick in row:
            if pick and pick.get("player"):
                used.add(pick["player"])
    return used


# ── Public API ────────────────────────────────────────────────────────────────

def start_game(conn, player_names: list, player_tokens: list | None = None) -> tuple:
    """
    Initialize a new game.
    Returns (game_id, state_dict).
    """
    if not 1 <= len(player_names) <= 4:
        raise ValueError("Need 1-4 players")
    if player_tokens and len(player_tokens) != len(player_names):
        raise ValueError("Player token count mismatch")

    last_error = None
    stat = None
    prompts = None
    for _ in range(12):
        candidate_stat = random.choice(STAT_CATEGORIES)
        try:
            candidate_prompts = _generate_prompts(conn, candidate_stat)
            stat = candidate_stat
            prompts = candidate_prompts
            break
        except ValueError as exc:
            last_error = exc

    if stat is None or prompts is None:
        raise ValueError(str(last_error or "Could not start Bullseye"))

    target = _compute_target(conn, prompts, stat)

    game_id = str(uuid.uuid4())[:8]

    # picks[prompt_idx][player_idx] = None | {player, season, stat_val, team}
    picks = [[None] * len(player_names) for _ in range(5)]

    state = {
        "game_id": game_id,
        "stat": stat,
        "target": target,
        "players": list(player_names),
        "player_tokens": list(player_tokens) if player_tokens else [None] * len(player_names),
        "prompts": prompts,
        "picks": picks,
        "used_pairs": [],   # list of [player, season] to detect duplicates
        "done": False,
        "winner": None,
    }
    _GAMES[game_id] = state
    return game_id, state


def get_game(game_id: str) -> dict | None:
    return _GAMES.get(game_id)


def submit_pick(conn, game_id: str, nba_player_name: str, season: int,
                prompt_idx: int = None, player_idx: int = None, actor_token: str = None) -> tuple:
    """
    Record a pick. prompt_idx and player_idx select the cell explicitly.
    Returns (state_dict, error_str). error_str is None on success.
    """
    state = _GAMES.get(game_id)
    if state is None:
        return None, "Game not found"

    if state.get("done"):
        return state, "Game is already complete"

    n_players = len(state["players"])
    if prompt_idx is None or player_idx is None or \
       not (0 <= prompt_idx < 5) or not (0 <= player_idx < n_players):
        return state, "Invalid prompt or player index"

    expected_player_idx, expected_prompt_idx = _current_turn(state)
    if (player_idx, prompt_idx) != (expected_player_idx, expected_prompt_idx):
        return state, "It is not that cell's turn"
    expected_token = (state.get("player_tokens") or [None] * n_players)[expected_player_idx]
    if expected_token and actor_token != expected_token:
        return state, "It is not your turn"

    if state["picks"][prompt_idx][player_idx] is not None:
        return state, "This cell has already been filled"

    season = int(season)
    stat_expr = _stat_expr(state["stat"])
    prompt = state["prompts"][prompt_idx]

    # Check for duplicate player-season pair
    used_pairs = [tuple(p) for p in state["used_pairs"]]
    used_players = _used_players(state)
    if nba_player_name in used_players:
        return state, f"{nba_player_name} has already been used — choose a different player"
    if (nba_player_name, season) in used_pairs:
        return state, f"{nba_player_name} ({season}) has already been picked — choose a different player or season"

    # Validate: player-season must satisfy prompt constraints
    where, params = _build_prompt_where(prompt, state["stat"])
    sql = f"""
        SELECT s.player, s.season, s.team, {stat_expr} AS stat_val
        FROM nba_stats s
        {where}
        AND s.player = ?
        AND s.season = ?
        AND {stat_expr} > 0
        LIMIT 1
    """
    row = conn.execute(sql, params + [nba_player_name, season]).fetchone()

    if row is None:
        return state, f"{nba_player_name} ({season}) does not satisfy the prompt constraints"

    stat_val = int(row[3]) if row[3] is not None else 0
    team = row[2]

    # Record pick
    state["picks"][prompt_idx][player_idx] = {
        "player": nba_player_name,
        "season": season,
        "team": team,
        "stat_val": stat_val,
    }
    state["used_pairs"].append([nba_player_name, season])

    # Check if game is finished
    next_pi, next_pr = _current_turn(state)
    if next_pi is None:
        state["done"] = True
        state["winner"] = _compute_winner(state)

    _GAMES[game_id] = state
    return state, None


def _compute_winner(state: dict) -> dict:
    """Determine winner (closest to target, ties split)."""
    target = state["target"]
    n_players = len(state["players"])
    totals = [0] * n_players

    for prompt_idx in range(5):
        for player_idx in range(n_players):
            pick = state["picks"][prompt_idx][player_idx]
            if pick:
                totals[player_idx] += pick["stat_val"]

    diffs = [abs(totals[i] - target) for i in range(n_players)]
    min_diff = min(diffs)
    winners = [i for i, d in enumerate(diffs) if d == min_diff]

    return {
        "totals": totals,
        "diffs": diffs,
        "winner_indices": winners,
        "winner_names": [state["players"][i] for i in winners],
    }


def get_valid_years(conn, game_id: str, prompt_idx: int, player_name: str) -> list:
    seasons = get_player_seasons(conn, game_id, prompt_idx, player_name)
    return [season["season"] for season in seasons]


def get_player_seasons(conn, game_id: str, prompt_idx: int, player_name: str) -> list:
    """Return all seasons for a specific player in the current stat pool."""
    state = _GAMES.get(game_id)
    if state is None:
        return []
    if prompt_idx < 0 or prompt_idx >= len(state.get("prompts", [])):
        return []

    stat_expr = _stat_expr(state["stat"])
    prompt = state["prompts"][prompt_idx]
    used_pairs = [tuple(p) for p in state["used_pairs"]]
    if player_name in _used_players(state):
        return []

    where, params = _build_prompt_where(prompt, state["stat"])
    sql = f"""
        SELECT s.player, s.season, s.team, {stat_expr} AS stat_val
        FROM nba_stats s
        {where}
        AND s.player = ?
        AND {stat_expr} > 0
        ORDER BY s.season DESC
    """
    rows = conn.execute(sql, params + [player_name]).fetchall()

    results = []
    for row in rows:
        pair = (row[0], row[1])
        if pair in used_pairs:
            continue
        results.append({
            "player": row[0],
            "season": row[1],
            "team": row[2],
            "stat_val": int(row[3]) if row[3] is not None else 0,
        })
    return results


def search_players(conn, query: str, prompt_idx: int, game_id: str) -> list:
    from name_utils import normalize_name
    state = _GAMES.get(game_id)
    if state is None:
        return []
    if prompt_idx < 0 or prompt_idx >= len(state.get("prompts", [])):
        return []

    prompt = state["prompts"][prompt_idx]
    where, params = _build_prompt_where(prompt, state["stat"], apply_stat_floor=True)
    used_players = _used_players(state)

    rows = conn.execute(
        f"""
        SELECT DISTINCT s.player
        FROM nba_stats s
        {where}
        AND s.player IS NOT NULL AND s.player != ''
        ORDER BY s.player
        """,
        params,
    ).fetchall()

    key = normalize_name(query)
    candidates = [row[0] for row in rows if row[0] not in used_players]

    if key:
        starts = [p for p in candidates if normalize_name(p).startswith(key)]
        contains = [p for p in candidates if not normalize_name(p).startswith(key) and key in normalize_name(p)]
        candidates = (starts + contains)[:40]
    else:
        candidates = candidates[:40]

    return [{"player": p, "season": None, "team": None, "stat_val": 0} for p in candidates]
