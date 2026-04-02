"""
nfl_bullseye.py — Backend logic for NFL Bullseye multiplayer game.

Stat categories: PPR, Pass Yds, Rush Yds, Rec Yds
"""

import random
import uuid
from session_store import GameStore

_GAMES = GameStore("nfl_bullseye", ttl_seconds=14400)

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
    if team_filter == "AFC":
        ph, p = _teams_in_clause(AFC_TEAMS)
        clauses.append(f"s.team IN {ph}")
        params.extend(p)
    elif team_filter == "NFC":
        ph, p = _teams_in_clause(NFC_TEAMS)
        clauses.append(f"s.team IN {ph}")
        params.extend(p)
    elif team_filter and team_filter not in ("any", None):
        clauses.append("s.team = ?")
        params.append(team_filter)

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


def _generate_prompts(conn, stat: str) -> list:
    """Generate 5 varied prompts for the stat category."""
    table = _stat_table(stat)

    storied_franchises = ["NWE", "DAL", "GNB", "SFO", "PIT", "SEA", "CHI", "NYG", "MIA", "WAS"]
    modern_franchises = ["KAN", "BUF", "PHI", "LAR", "BAL", "DEN", "TAM", "NOR", "LAC", "CLE"]
    team_filter_pool = [
        "any", "any",
        "AFC", "NFC",
        random.choice(storied_franchises),
        random.choice(modern_franchises),
        random.choice(ALL_TEAMS),
    ]
    random.shuffle(team_filter_pool)
    team_filters = team_filter_pool[:5]

    year_ranges = [
        (2015, 2023),
        (2010, 2023),
        (2000, 2013),
        (1990, 2005),
        (1980, 2000),
        (1970, 1990),
        (2005, 2018),
    ]
    random.shuffle(year_ranges)

    accolade_pool = [None, None, "pro_bowl", "1st_round", "all_pro",
                     "hof", "all_rookie_nfl", "nfl_mvp", "nfl_dpoy"]
    random.shuffle(accolade_pool)

    prompts = []
    for i in range(5):
        team_filter = team_filters[i]
        yr_min, yr_max = year_ranges[i]
        accolade = accolade_pool[i]

        prompt = {
            "team_filter": team_filter if team_filter != "any" else None,
            "team_filter_label": team_filter,
            "year_min": yr_min,
            "year_max": yr_max,
            "accolade": accolade,
        }

        # Verify prompt returns enough results
        where, pos_frag, params = _build_prompt_where(prompt, stat, apply_stat_floor=True)
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table} s {where} {pos_frag}", params
        ).fetchone()
        count = row[0] if row else 0

        if count < 5:
            prompt["team_filter"] = None
            prompt["team_filter_label"] = "any"
            prompt["accolade"] = None

        prompts.append(prompt)

    return prompts


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
    if not 2 <= len(player_names) <= 4:
        raise ValueError("Need 2–4 players")
    if player_tokens and len(player_tokens) != len(player_names):
        raise ValueError("Player token count mismatch")

    stat = random.choice(STAT_CATEGORIES)
    prompts = _generate_prompts(conn, stat)
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
    """Return all seasons for a specific player in the current stat pool."""
    state = _GAMES.get(game_id)
    if state is None:
        return []

    stat = state["stat"]
    table = _stat_table(stat)
    stat_expr = _stat_expr(stat)
    used_pairs = [tuple(p) for p in state["used_pairs"]]
    if player_name in _used_players(state):
        return []

    pos_frag, params = _pos_filter_clause(stat)

    sql = f"""
        SELECT s.player, s.season, s.team, {stat_expr} AS stat_val
        FROM {table} s
        WHERE s.player = ?
        AND {stat_expr} > 0 {pos_frag}
        ORDER BY s.season DESC
    """
    rows = conn.execute(sql, [player_name] + params).fetchall()

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

    used_players = _used_players(state)

    stat = state["stat"]
    table = _stat_table(stat)
    stat_expr = _stat_expr(stat)
    pos_frag, pos_params = _pos_filter_clause(stat)

    rows = conn.execute(
        f"""
        SELECT DISTINCT s.player
        FROM {table} s
        WHERE {stat_expr} > 0 {pos_frag}
        ORDER BY s.player
        """,
        pos_params,
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
