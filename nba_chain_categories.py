"""
nba_chain_categories.py
Defines all category types for the NBA Chain Game, plus helper functions.
"""
import random
import sqlite3

# ── Team code → full name ─────────────────────────────────────────────────────
NBA_TEAM_NAMES = {
    "ATL": "Atlanta Hawks",        "BOS": "Boston Celtics",
    "BRK": "Brooklyn Nets",        "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",        "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",     "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",      "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",      "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers", "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",      "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder","ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",   "PHO": "Phoenix Suns",
    "POR": "Portland Trail Blazers","SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",            "WAS": "Washington Wizards",
}
NBA_TEAM_NAME_TO_CODE = {v: k for k, v in NBA_TEAM_NAMES.items()}

EAST_TEAMS = {
    "ATL", "BOS", "BRK", "CHA", "CHI", "CLE", "DET",
    "IND", "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS",
}
WEST_TEAMS = {
    "DAL", "DEN", "GSW", "HOU", "LAC", "LAL", "MEM",
    "MIN", "NOP", "OKC", "PHO", "POR", "SAC", "SAS", "UTA",
}

DIVISIONS = {
    "Atlantic":  {"BOS", "BRK", "NYK", "PHI", "TOR"},
    "Central":   {"CHI", "CLE", "DET", "IND", "MIL"},
    "Southeast": {"ATL", "CHA", "MIA", "ORL", "WAS"},
    "Northwest": {"DEN", "MIN", "OKC", "POR", "UTA"},
    "Pacific":   {"GSW", "LAC", "LAL", "PHO", "SAC"},
    "Southwest": {"DAL", "HOU", "MEM", "NOP", "SAS"},
}

ERA_RANGES = {
    "1980s": (1980, 1989),
    "1990s": (1990, 1999),
    "2000s": (2000, 2009),
    "2010s": (2010, 2019),
    "2020s": (2020, 2029),
}

NBA_POSITIONS = ["C", "G", "F"]


# ── Helper: run a query and return a frozenset of player names ────────────────

def _query_set(conn, sql, params=()):
    try:
        rows = conn.execute(sql, params).fetchall()
        return frozenset(r[0] for r in rows if r[0])
    except Exception:
        return frozenset()


# ── Category pickers and player resolvers ─────────────────────────────────────

def _pick_position(conn, current_players=None):
    return random.choice(NBA_POSITIONS)


def _players_position(conn, value):
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nba_stats WHERE pos = ?",
        (value,),
    )


def _pick_team(conn, current_players=None):
    codes = list(NBA_TEAM_NAMES.keys())
    random.shuffle(codes)
    return NBA_TEAM_NAMES[codes[0]]


def _players_team(conn, value):
    code = NBA_TEAM_NAME_TO_CODE.get(value)
    if not code:
        return frozenset()
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nba_stats WHERE team = ?",
        (code,),
    )


def _pick_college(conn, current_players=None):
    rows = conn.execute(
        """SELECT college, COUNT(*) as cnt FROM nba_draft
           WHERE college IS NOT NULL AND college != ''
           GROUP BY college HAVING cnt >= 3
           ORDER BY RANDOM() LIMIT 1"""
    ).fetchall()
    if rows:
        return rows[0][0]
    return None


def _players_college(conn, value):
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nba_draft WHERE college = ?",
        (value,),
    )


def _pick_era(conn, current_players=None):
    return random.choice(list(ERA_RANGES.keys()))


def _players_era(conn, value):
    rng = ERA_RANGES.get(value)
    if not rng:
        return frozenset()
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nba_stats WHERE season BETWEEN ? AND ?",
        (rng[0], rng[1]),
    )


def _pick_conference(conn, current_players=None):
    return random.choice(["East", "West"])


def _players_conference(conn, value):
    if value == "East":
        teams = list(EAST_TEAMS)
    else:
        teams = list(WEST_TEAMS)
    placeholders = ",".join("?" * len(teams))
    return _query_set(
        conn,
        f"SELECT DISTINCT player FROM nba_stats WHERE team IN ({placeholders})",
        teams,
    )


def _pick_division(conn, current_players=None):
    return random.choice(list(DIVISIONS.keys()))


def _players_division(conn, value):
    teams = list(DIVISIONS.get(value, set()))
    if not teams:
        return frozenset()
    placeholders = ",".join("?" * len(teams))
    return _query_set(
        conn,
        f"SELECT DISTINCT player FROM nba_stats WHERE team IN ({placeholders})",
        teams,
    )


def _pick_static(conn, current_players=None):
    return ""


def _players_first_round(conn, value):
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nba_draft WHERE CAST(draft_pick AS INTEGER) <= 30",
    )


def _players_top10(conn, value):
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nba_draft WHERE CAST(draft_pick AS INTEGER) <= 10",
    )


def _pick_pts_season(conn, current_players=None):
    return str(random.choice([20, 25]))


def _players_pts_season(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nba_stats WHERE pts_pg >= ?",
        (threshold,),
    )


def _pick_reb_season(conn, current_players=None):
    return str(random.choice([8, 10]))


def _players_reb_season(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nba_stats WHERE trb_pg >= ?",
        (threshold,),
    )


def _pick_ast_season(conn, current_players=None):
    return str(random.choice([7, 10]))


def _players_ast_season(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nba_stats WHERE ast_pg >= ?",
        (threshold,),
    )


def _pick_allstar_count(conn, current_players=None):
    return str(random.choice([1, 3, 5, 10]))


def _players_allstar_count(conn, value):
    threshold = int(value)
    return _query_set(
        conn,
        "SELECT player FROM nba_allstars WHERE selections >= ?",
        (threshold,),
    )


def _pick_teammate(conn, current_players=None):
    if not current_players:
        return None
    players_list = list(current_players)
    random.shuffle(players_list)
    for candidate in players_list[:10]:
        row = conn.execute(
            """SELECT s2.player FROM nba_stats s1
               JOIN nba_stats s2 ON s1.team=s2.team AND s1.season=s2.season
               WHERE s1.player=? AND s2.player!=?
               LIMIT 1""",
            (candidate, candidate),
        ).fetchone()
        if row:
            return candidate
    return None


def _players_teammate(conn, value):
    if not value:
        return frozenset()
    return _query_set(
        conn,
        """SELECT DISTINCT s2.player FROM nba_stats s1
           JOIN nba_stats s2 ON s1.team=s2.team AND s1.season=s2.season
           WHERE s1.player=? AND s2.player!=?""",
        (value, value),
    )


# ── CATEGORIES list ───────────────────────────────────────────────────────────

CATEGORIES = [
    {
        "id": "position",
        "label": "Is a {value}",
        "pick": _pick_position,
        "players": _players_position,
        "is_teammate": False,
    },
    {
        "id": "team",
        "label": "Played for the {value}",
        "pick": _pick_team,
        "players": _players_team,
        "is_teammate": False,
    },
    {
        "id": "college",
        "label": "Went to {value}",
        "pick": _pick_college,
        "players": _players_college,
        "is_teammate": False,
    },
    {
        "id": "era",
        "label": "Played in the {value}",
        "pick": _pick_era,
        "players": _players_era,
        "is_teammate": False,
    },
    {
        "id": "conference",
        "label": "Played for a {value} Conference team",
        "pick": _pick_conference,
        "players": _players_conference,
        "is_teammate": False,
    },
    {
        "id": "division",
        "label": "Played for a {value} Division team",
        "pick": _pick_division,
        "players": _players_division,
        "is_teammate": False,
    },
    {
        "id": "first_round",
        "label": "Was a 1st round draft pick",
        "pick": _pick_static,
        "players": _players_first_round,
        "is_teammate": False,
    },
    {
        "id": "top_10",
        "label": "Was a top-10 draft pick",
        "pick": _pick_static,
        "players": _players_top10,
        "is_teammate": False,
    },
    {
        "id": "pts_season",
        "label": "Averaged {value}+ PPG in a season",
        "pick": _pick_pts_season,
        "players": _players_pts_season,
        "is_teammate": False,
    },
    {
        "id": "reb_season",
        "label": "Averaged {value}+ RPG in a season",
        "pick": _pick_reb_season,
        "players": _players_reb_season,
        "is_teammate": False,
    },
    {
        "id": "ast_season",
        "label": "Averaged {value}+ APG in a season",
        "pick": _pick_ast_season,
        "players": _players_ast_season,
        "is_teammate": False,
    },
    {
        "id": "teammate",
        "label": "Was a teammate of {value}",
        "pick": _pick_teammate,
        "players": _players_teammate,
        "is_teammate": True,
    },
    {
        "id": "allstar_count",
        "label": "Made {value}+ NBA All-Star appearances",
        "pick": _pick_allstar_count,
        "players": _players_allstar_count,
        "is_teammate": False,
    },
]

# Index for fast lookup
_CAT_BY_ID = {c["id"]: c for c in CATEGORIES}

# ── Conflict groups ──────────────────────────────────────────────────────────
_CONFLICT_GROUPS = [
    {"first_round", "top_10"},    # top-10 picks are all 1st round picks
    {"team", "division"},          # knowing the team tells you the division
    {"team", "conference"},        # knowing the team tells you the conference
    {"division", "conference"},    # knowing the division tells you the conference
]


def _expand_excluded(existing_ids):
    """Expand a set of excluded IDs to also exclude conflicting categories."""
    expanded = set(existing_ids)
    for group in _CONFLICT_GROUPS:
        if expanded & group:
            expanded |= group
    return expanded


def _format_label(cat, value):
    """Return the display label for a category with its value substituted."""
    if value:
        return cat["label"].replace("{value}", str(value))
    return cat["label"]


# ── Public API ────────────────────────────────────────────────────────────────

def get_players_for_chain(conn, chain):
    """Return frozenset of player names valid for the entire chain."""
    result = None
    for link in chain:
        cat = _CAT_BY_ID.get(link["id"])
        if not cat:
            continue
        s = cat["players"](conn, link.get("value", ""))
        if result is None:
            result = s
        else:
            result = result & s
    return result if result is not None else frozenset()


def get_start_category(conn):
    """Pick a starting category with >= 10 valid players. No teammate cats."""
    exclude_start = {"teammate"}
    candidates = [c for c in CATEGORIES if c["id"] not in exclude_start]
    random.shuffle(candidates)

    for cat in candidates:
        for _ in range(5):
            value = cat["pick"](conn, None)
            if value is None:
                continue
            players = cat["players"](conn, value)
            if len(players) >= 10:
                return {
                    "id": cat["id"],
                    "value": value,
                    "label": _format_label(cat, value),
                    "valid_count": len(players),
                }
    return None


def get_chain_category(conn, current_players, exclude_ids=None):
    """
    Pick the next chain category.

    Only picks categories where the intersection with current_players >= 2.
    Returns a dict with id/value/label/valid_count, or None if none found.
    """
    exclude_ids = _expand_excluded(exclude_ids or [])
    candidates = [c for c in CATEGORIES if c["id"] not in exclude_ids]
    random.shuffle(candidates)

    best = None  # fallback: intersect >= 1

    for cat in candidates:
        attempts = 5 if "{value}" in cat["label"] else 1
        for _ in range(attempts):
            value = cat["pick"](conn, current_players)
            if value is None:
                continue
            new_players = cat["players"](conn, value)
            intersection = current_players & new_players
            count = len(intersection)
            if count >= 2:
                return {
                    "id": cat["id"],
                    "value": value,
                    "label": _format_label(cat, value),
                    "valid_count": count,
                }
            elif count >= 1 and best is None:
                best = {
                    "id": cat["id"],
                    "value": value,
                    "label": _format_label(cat, value),
                    "valid_count": count,
                }

    return best


def search_players(conn, term):
    """Search player names across NBA tables."""
    like = f"%{term}%"
    rows = conn.execute(
        """SELECT DISTINCT player FROM nba_stats WHERE player LIKE ?
           UNION
           SELECT DISTINCT player FROM nba_draft WHERE player LIKE ?
           ORDER BY player LIMIT 20""",
        (like, like),
    ).fetchall()
    return [r[0] for r in rows]


def check_player_against_chain(conn, player, chain):
    """Return per-link pass/fail for a player against a chain."""
    results = []
    for link in chain:
        cat = _CAT_BY_ID.get(link["id"])
        if not cat:
            results.append({"label": link.get("label", link["id"]), "passed": False})
            continue
        players = cat["players"](conn, link.get("value", ""))
        results.append({
            "label": _format_label(cat, link.get("value", "")),
            "passed": player in players,
        })
    return results


def get_teammate_category(conn, player):
    """Build a 'teammate of X' starting category for a given player."""
    cat = _CAT_BY_ID.get("teammate")
    if not cat:
        return None
    players = cat["players"](conn, player)
    if not players:
        return None
    return {
        "id": "teammate",
        "value": player,
        "label": f"Was a teammate of {player}",
        "valid_count": len(players),
    }
