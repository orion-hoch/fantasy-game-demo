"""
nfl_bullseye.py — Backend logic for NFL Bullseye multiplayer game.

Stat categories: PPR, Pass Yds, Rush Yds, Rec Yds
"""

import random
import uuid
from session_store import GameStore

_GAMES = GameStore("nfl_bullseye", ttl_seconds=14400)
MIN_PROMPT_PLAYERS = 5

# ── Constants ──────────────────────────────────────────────────────────────────

STAT_CATEGORIES = [
    "PPR", "Pass Yds", "Rush Yds", "Rec Yds",
    "Pass TD", "Rush TD", "Rec TD", "Receptions",
    "Sacks", "Solo Tackles", "Def INT",
]

AFC_TEAMS = ["NWE", "MIA", "NYJ", "BUF", "BAL", "CLE", "PIT", "CIN",
             "HOU", "IND", "JAX", "TEN", "KAN", "LAC", "DEN", "LVR", "OAK", "RAI", "SDG"]
NFC_TEAMS = ["DAL", "NYG", "PHI", "WAS", "CHI", "DET", "MIN", "GNB",
             "NOR", "TAM", "ATL", "CAR", "SFO", "SEA", "LAR", "STL", "RAM", "ARI"]

ALL_TEAMS = AFC_TEAMS + NFC_TEAMS

NFL_DIVISIONS = {
    "AFC East": ["NWE", "MIA", "NYJ", "BUF"],
    "AFC North": ["BAL", "CLE", "PIT", "CIN"],
    "AFC South": ["HOU", "IND", "JAX", "TEN"],
    "AFC West": ["KAN", "LAC", "DEN", "LVR", "OAK", "RAI", "SDG"],
    "NFC East": ["DAL", "NYG", "PHI", "WAS"],
    "NFC North": ["CHI", "DET", "MIN", "GNB"],
    "NFC South": ["NOR", "TAM", "ATL", "CAR"],
    "NFC West": ["SFO", "SEA", "LAR", "STL", "RAM", "ARI"],
}

# Historical → modern franchise mapping (same direction as TEAM_MAP in load_data.py)
_NFL_HIST_TO_MOD = {
    "SDG": "LAC",
    "STL": "LAR", "RAM": "LAR",
    "RAI": "LVR", "OAK": "LVR",
    "CRD": "ARI", "CHR": "ARI", "PHO": "ARI",
}

# ── Stat configuration ────────────────────────────────────────────────────────

_STAT_CONFIG = {
    "PPR": {
        "table": "stats",
        "expr": "fantasy_ppr",
        "pos_filter": None,
        "min_val": 50,
    },
    "Pass Yds": {
        "table": "season_stats",
        "expr": "pass_yds",
        "pos_filter": "QB",
        "min_val": 500,
    },
    "Rush Yds": {
        "table": "season_stats",
        "expr": "rush_yds",
        "pos_filter": "RB",
        "min_val": 200,
    },
    "Rec Yds": {
        "table": "season_stats",
        "expr": "rec_yds",
        "pos_filter_in": ("WR", "TE"),
        "min_val": 200,
    },
    "Pass TD": {
        "table": "season_stats",
        "expr": "pass_td",
        "pos_filter": "QB",
        "min_val": 10,
    },
    "Rush TD": {
        "table": "season_stats",
        "expr": "rush_td",
        "pos_filter": "RB",
        "min_val": 5,
    },
    "Rec TD": {
        "table": "season_stats",
        "expr": "rec_td",
        "pos_filter_in": ("WR", "TE"),
        "min_val": 3,
    },
    "Receptions": {
        "table": "season_stats",
        "expr": "rec_rec",
        "pos_filter_in": ("WR", "TE", "RB"),
        "min_val": 30,
    },
    "Sacks": {
        "table": "def_stats",
        "expr": "sacks",
        "pos_filter": None,
        "min_val": 5,
    },
    "Solo Tackles": {
        "table": "def_stats",
        "expr": "solo_tackles",
        "pos_filter": None,
        "min_val": 40,
    },
    "Def INT": {
        "table": "def_stats",
        "expr": "interceptions",
        "pos_filter_in": ("CB", "S"),
        "min_val": 2,
    },
}


def _stat_table(stat: str) -> str:
    return _STAT_CONFIG[stat]["table"]


def _stat_expr(stat: str) -> str:
    return _STAT_CONFIG[stat]["expr"]


def _pos_filter_clause(stat: str) -> tuple:
    """Return (additional_where_fragment, params) for position filtering."""
    cfg = _STAT_CONFIG[stat]
    if cfg.get("pos_filter"):
        return "AND s.pos = ?", [cfg["pos_filter"]]
    if cfg.get("pos_filter_in"):
        positions = cfg["pos_filter_in"]
        ph = ",".join("?" * len(positions))
        return f"AND s.pos IN ({ph})", list(positions)
    return "", []


def _min_val(stat: str) -> int:
    return _STAT_CONFIG[stat].get("min_val", 0)


NFL_ACCOLADE_OPTIONS = [
    "pro_bowl",
    "all_pro",
    "1st_round",
    "hof",
    "all_rookie_nfl",
    "nfl_mvp",
    "nfl_dpoy",
]


def _accolade_sql(accolade: str) -> str:
    if accolade == "pro_bowl":
        return "EXISTS (SELECT 1 FROM draft d WHERE d.player = s.player AND d.pro_bowls > 0)"
    elif accolade == "all_pro":
        return "EXISTS (SELECT 1 FROM draft d WHERE d.player = s.player AND d.all_pro > 0)"
    elif accolade == "1st_round":
        return "EXISTS (SELECT 1 FROM draft d WHERE d.player = s.player AND d.draft_round = 1)"
    elif accolade == "hof":
        return "EXISTS (SELECT 1 FROM nfl_hof h WHERE h.player = s.player)"
    elif accolade == "all_rookie_nfl":
        return "EXISTS (SELECT 1 FROM nfl_allrookie r WHERE r.player = s.player)"
    elif accolade == "nfl_mvp":
        return "EXISTS (SELECT 1 FROM nfl_awards a WHERE a.player = s.player AND a.award = 'NFL_MVP')"
    elif accolade == "nfl_dpoy":
        return "EXISTS (SELECT 1 FROM nfl_awards a WHERE a.player = s.player AND a.award = 'AP_DPOY')"
    return None


def _teams_in_clause(teams: list) -> tuple:
    placeholders = ",".join("?" * len(teams))
    return f"({placeholders})", list(teams)


def _build_prompt_where(prompt: dict, stat: str, apply_stat_floor: bool = False) -> tuple:
    """
    Return (where_clause, pos_fragment, params) for the given prompt.
    Combined query: SELECT ... FROM {table} s WHERE {where_clause} {pos_fragment}
    """
    clauses = ["games >= 4"]
    params = []

    team_filter = prompt.get("team_filter")
    if team_filter in NFL_DIVISIONS:
        ph, p = _teams_in_clause(NFL_DIVISIONS[team_filter])
        clauses.append(f"s.team IN {ph}")
        params.extend(p)
    elif team_filter == "AFC":
        ph, p = _teams_in_clause(AFC_TEAMS)
        clauses.append(f"s.team IN {ph}")
        params.extend(p)
    elif team_filter == "NFC":
        ph, p = _teams_in_clause(NFC_TEAMS)
        clauses.append(f"s.team IN {ph}")
        params.extend(p)
    elif team_filter and team_filter not in ("any", None):
        # Expand to historical equivalents so SDG/LAC, OAK/LVR, etc. match each other
        equiv = {team_filter}
        for hist, mod in _NFL_HIST_TO_MOD.items():
            if hist == team_filter or mod == team_filter:
                equiv.add(hist)
                equiv.add(mod)
        ph, p = _teams_in_clause(list(equiv))
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

    if apply_stat_floor:
        stat_expr = _stat_expr(stat)
        clauses.append(f"{stat_expr} > ?")
        params.append(_min_val(stat))

    where = "WHERE " + " AND ".join(clauses)

    pos_fragment, pos_params = _pos_filter_clause(stat)
    params.extend(pos_params)

    return where, pos_fragment, params


def _prompt_player_count(conn, prompt: dict, stat: str) -> int:
    table = _stat_table(stat)
    where, pos_frag, params = _build_prompt_where(prompt, stat, apply_stat_floor=True)
    row = conn.execute(
        f"SELECT COUNT(DISTINCT s.player) FROM {table} s {where} {pos_frag}",
        params,
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _generate_prompts(conn, stat: str) -> list:
    """Generate 5 varied prompts for the stat category with viable player pools."""

    storied_franchises = ["NWE", "DAL", "GNB", "SFO", "PIT", "SEA", "CHI", "NYG", "MIA", "WAS"]
    modern_franchises = ["KAN", "BUF", "PHI", "LAR", "BAL", "DEN", "TAM", "NOR", "LAC", "CLE"]
    division_names = list(NFL_DIVISIONS.keys())

    team_filter_pool = (
        storied_franchises
        + modern_franchises
        + ALL_TEAMS
        + division_names
        + [None, None, None]
    )

    year_ranges = [
        (2015, 2023),
        (2010, 2023),
        (2000, 2013),
        (1990, 2005),
        (1980, 2000),
        (1970, 1990),
        (2005, 2018),
    ]

    prompts = []
    seen = set()

    attempts = 0
    while len(prompts) < 5 and attempts < 400:
        attempts += 1
        team_filter = random.choice(team_filter_pool)
        yr_min, yr_max = random.choice(year_ranges)
        accolade = random.choice(NFL_ACCOLADE_OPTIONS + [None, None])

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
        (None, 2010, 2023, None),
        (None, 2000, 2023, None),
        (None, 1990, 2023, None),
        (random.choice(division_names), 2000, 2023, None),
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
        shuffled = NFL_ACCOLADE_OPTIONS[:]
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
    table = _stat_table(stat)
    stat_expr = _stat_expr(stat)
    pos_frag, pos_params = _pos_filter_clause(stat)
    row = conn.execute(
        f"""
        SELECT AVG({stat_expr}), MAX({stat_expr})
        FROM {table} s
        WHERE games >= 4 AND {stat_expr} > 0 {pos_frag}
        """,
        pos_params,
    ).fetchone()
    mean_val = float(row[0] or 0)
    max_val = float(row[1] or 0)
    if max_val <= 0:
        return 10
    lower = max(1, mean_val)
    upper = max(lower, max_val * 2.5)
    target = random.uniform(lower, upper)
    return max(1, round(target))


def _turn_player_order(prompt_idx: int, n_players: int) -> list:
    if prompt_idx % 2 == 0:
        return list(range(n_players))
    return list(range(n_players - 1, -1, -1))


def _current_turn(state: dict) -> tuple:
    n_players = len(state["players"])
    picks = state["picks"]
    for prompt_idx in range(5):
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
    picks = [[None] * len(player_names) for _ in range(5)]

    state = {
        "game_id": game_id,
        "stat": stat,
        "target": target,
        "players": list(player_names),
        "player_tokens": list(player_tokens) if player_tokens else [None] * len(player_names),
        "prompts": prompts,
        "picks": picks,
        "used_pairs": [],
        "done": False,
        "winner": None,
    }
    _GAMES[game_id] = state
    return game_id, state


def get_game(game_id: str) -> dict | None:
    return _GAMES.get(game_id)


def submit_pick(conn, game_id: str, nfl_player_name: str, season: int,
                prompt_idx: int = None, player_idx: int = None, actor_token: str = None) -> tuple:
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
    stat = state["stat"]
    table = _stat_table(stat)
    stat_expr = _stat_expr(stat)
    prompt = state["prompts"][prompt_idx]

    used_pairs = [tuple(p) for p in state["used_pairs"]]
    used_players = _used_players(state)
    if nfl_player_name in used_players:
        return state, f"{nfl_player_name} has already been used — choose a different player"
    if (nfl_player_name, season) in used_pairs:
        return state, f"{nfl_player_name} ({season}) has already been picked — choose a different player or season"

    where, pos_frag, params = _build_prompt_where(prompt, stat)
    sql = f"""
        SELECT s.player, s.season, s.team, {stat_expr} AS stat_val
        FROM {table} s
        {where} {pos_frag}
        AND s.player = ?
        AND s.season = ?
        AND {stat_expr} > 0
        LIMIT 1
    """
    row = conn.execute(sql, params + [nfl_player_name, season]).fetchone()

    if row is None:
        return state, f"{nfl_player_name} ({season}) does not satisfy the prompt constraints"

    stat_val = int(row[3]) if row[3] is not None else 0
    team = row[2]

    state["picks"][prompt_idx][player_idx] = {
        "player": nfl_player_name,
        "season": season,
        "team": team,
        "stat_val": stat_val,
    }
    state["used_pairs"].append([nfl_player_name, season])

    next_pi, next_pr = _current_turn(state)
    if next_pi is None:
        state["done"] = True
        state["winner"] = _compute_winner(state)

    _GAMES[game_id] = state
    return state, None


def _compute_winner(state: dict) -> dict:
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
    """Return all seasons for a specific player in the full stat pool.

    The list is intentionally not pre-filtered to seasons that satisfy the
    prompt — the user must be able to attempt any season and learn from the
    submit-time validation, never from the picker UI revealing answers.
    """
    state = _GAMES.get(game_id)
    if state is None:
        return []
    if prompt_idx < 0 or prompt_idx >= len(state.get("prompts", [])):
        return []

    stat = state["stat"]
    table = _stat_table(stat)
    stat_expr = _stat_expr(stat)
    used_pairs = [tuple(p) for p in state["used_pairs"]]
    if player_name in _used_players(state):
        return []

    pos_frag, pos_params = _pos_filter_clause(stat)
    sql = f"""
        SELECT s.player, s.season, s.team, {stat_expr} AS stat_val
        FROM {table} s
        WHERE games >= 4
        AND s.player = ?
        AND {stat_expr} > 0
        {pos_frag}
        ORDER BY s.season DESC
    """
    rows = conn.execute(sql, [player_name] + pos_params).fetchall()

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
    """Search the full NFL player pool for the picker UI.

    Results MUST NOT be filtered down to players that satisfy the prompt —
    that would leak the answer set into the search bar. Validation only
    happens at submit time. See `get_player_seasons` for the same invariant
    on the season picker.
    """
    from name_utils import normalize_name
    state = _GAMES.get(game_id)
    if state is None:
        return []
    if prompt_idx < 0 or prompt_idx >= len(state.get("prompts", [])):
        return []

    used_players = _used_players(state)

    stat = state["stat"]
    table = _stat_table(stat)
    stat_floor = _min_val(stat)
    pos_frag, pos_params = _pos_filter_clause(stat)
    rows = conn.execute(
        f"""
        SELECT DISTINCT s.player
        FROM {table} s
        WHERE games >= 4
        AND {_stat_expr(stat)} >= ?
        {pos_frag}
        ORDER BY s.player
        """,
        [stat_floor] + pos_params,
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
