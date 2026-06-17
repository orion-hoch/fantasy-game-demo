"""
chain_categories.py
Defines all 18 category types for the Chain Game, plus helper functions.
"""
import random
import sqlite3

# ── Team code → full name ─────────────────────────────────────────────────────
TEAM_NAMES = {
    "NWE": "New England Patriots", "NYJ": "New York Jets",
    "BUF": "Buffalo Bills", "MIA": "Miami Dolphins",
    "BAL": "Baltimore Ravens", "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns", "PIT": "Pittsburgh Steelers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars", "TEN": "Tennessee Titans",
    "DEN": "Denver Broncos", "KAN": "Kansas City Chiefs",
    "LVR": "Las Vegas Raiders", "LAC": "Los Angeles Chargers",
    "DAL": "Dallas Cowboys", "NYG": "New York Giants",
    "PHI": "Philadelphia Eagles", "WAS": "Washington Commanders",
    "CHI": "Chicago Bears", "DET": "Detroit Lions",
    "GNB": "Green Bay Packers", "MIN": "Minnesota Vikings",
    "ATL": "Atlanta Falcons", "CAR": "Carolina Panthers",
    "NOR": "New Orleans Saints", "TAM": "Tampa Bay Buccaneers",
    "ARI": "Arizona Cardinals", "LAR": "Los Angeles Rams",
    "SEA": "Seattle Seahawks", "SFO": "San Francisco 49ers",
}
TEAM_NAME_TO_CODE = {v: k for k, v in TEAM_NAMES.items()}

AFC_TEAMS = {"NWE", "NYJ", "BUF", "MIA", "BAL", "CIN", "CLE", "PIT",
             "HOU", "IND", "JAX", "TEN", "DEN", "KAN", "LVR", "LAC"}
NFC_TEAMS = {"DAL", "NYG", "PHI", "WAS", "CHI", "DET", "GNB", "MIN",
             "ATL", "CAR", "NOR", "TAM", "ARI", "LAR", "SEA", "SFO"}

DIVISIONS = {
    "AFC East": {"NWE", "NYJ", "BUF", "MIA"},
    "AFC North": {"BAL", "CIN", "CLE", "PIT"},
    "AFC South": {"HOU", "IND", "JAX", "TEN"},
    "AFC West": {"DEN", "KAN", "LVR", "LAC"},
    "NFC East": {"DAL", "NYG", "PHI", "WAS"},
    "NFC North": {"CHI", "DET", "GNB", "MIN"},
    "NFC South": {"ATL", "CAR", "NOR", "TAM"},
    "NFC West": {"ARI", "LAR", "SEA", "SFO"},
}

# Extended team name mapping for Super Bowl/Championship teams (including historical)
SB_TEAM_NAME_TO_CODE = {
    "Arizona Cardinals": "ARI", "St. Louis Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GNB",
    "Houston Texans": "HOU", "Houston Oilers": "TEN",
    "Indianapolis Colts": "IND", "Baltimore Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KAN",
    "Los Angeles Chargers": "LAC", "San Diego Chargers": "LAC",
    "Los Angeles Rams": "LAR", "St. Louis Rams": "LAR",
    "Las Vegas Raiders": "LVR", "Oakland Raiders": "LVR", "Los Angeles Raiders": "LVR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NWE",
    "New Orleans Saints": "NOR",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "Seattle Seahawks": "SEA",
    "San Francisco 49ers": "SFO",
    "Tampa Bay Buccaneers": "TAM",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS", "Washington Redskins": "WAS",
    "Washington Football Team": "WAS",
}

# NFL award code → display label mapping
_NFL_AWARD_OPTIONS = [
    ("NFL_MVP", "the NFL MVP Award"),
    ("AP_DPOY", "the Defensive Player of the Year"),
    ("AP_OPOY", "the Offensive Player of the Year"),
    ("SB_MVP", "the Super Bowl MVP"),
    ("AP_OROY", "the Offensive Rookie of the Year"),
    ("AP_DROY", "the Defensive Rookie of the Year"),
    ("Comeback", "the Comeback Player of the Year"),
]
_NFL_AWARD_DISPLAY_TO_CODE = {display: code for code, display in _NFL_AWARD_OPTIONS}

CONFERENCE_SCHOOLS = {
    "SEC": {
        "Alabama", "Georgia", "LSU", "Florida", "Tennessee", "Auburn",
        "Mississippi", "Mississippi St.", "Arkansas", "South Carolina",
        "Missouri", "Kentucky", "Vanderbilt", "Texas A&M", "Texas", "Oklahoma",
    },
    "Big Ten": {
        "Ohio St.", "Michigan", "Penn St.", "Wisconsin", "Iowa", "Minnesota",
        "Nebraska", "Illinois", "Northwestern", "Indiana", "Purdue",
        "Michigan St.", "Maryland", "Rutgers", "Oregon", "Washington",
        "UCLA", "USC",
    },
    "ACC": {
        "Florida St.", "Clemson", "Miami (FL)", "Virginia Tech",
        "North Carolina", "North Carolina St.", "Boston Col.", "Pittsburgh",
        "Syracuse", "Wake Forest", "Louisville", "Georgia Tech", "Duke",
        "Virginia", "SMU", "Stanford", "California",
    },
    "Big 12": {
        "Oklahoma St.", "Kansas St.", "Baylor", "TCU", "West Virginia",
        "Kansas", "Texas Tech", "BYU", "Cincinnati", "Houston",
        "Central Florida", "Utah", "Colorado", "Arizona", "Arizona St.",
    },
}

ERA_RANGES = {
    "1980s": (1980, 1989),
    "1990s": (1990, 1999),
    "2000s": (2000, 2009),
    "2010s": (2010, 2019),
    "2020s": (2020, 2029),
}


# ── Helper: run a query and return a frozenset of player names ────────────────

def _query_set(conn, sql, params=()):
    try:
        rows = conn.execute(sql, params).fetchall()
        return frozenset(r[0] for r in rows if r[0])
    except Exception:
        return frozenset()


# ── Category definitions ───────────────────────────────────────────────────────

_OFF_POSITIONS = ["QB", "RB", "WR", "TE"]
_DEF_POSITIONS = ["CB", "S", "LB", "DE", "DT"]


def _pick_position(conn, current_players=None):
    return random.choice(_OFF_POSITIONS + _DEF_POSITIONS)


def _players_position(conn, value):
    if value in _DEF_POSITIONS:
        return _query_set(
            conn,
            "SELECT DISTINCT player FROM def_stats WHERE pos = ?",
            (value,),
        )
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM stats WHERE pos = ?",
        (value,),
    )


def _pick_team(conn, current_players=None):
    codes = list(TEAM_NAMES.keys())
    random.shuffle(codes)
    return TEAM_NAMES[codes[0]]


def _players_team(conn, value):
    code = TEAM_NAME_TO_CODE.get(value)
    if not code:
        return frozenset()
    return _query_set(
        conn,
        """SELECT DISTINCT player FROM stats WHERE team = ?
           UNION
           SELECT DISTINCT player FROM def_stats WHERE team = ?""",
        (code, code),
    )


def _pick_college(conn, current_players=None):
    rows = conn.execute(
        """SELECT college, COUNT(*) as cnt FROM draft
           WHERE college IS NOT NULL AND college != ''
           GROUP BY college HAVING cnt >= 5
           ORDER BY RANDOM() LIMIT 1"""
    ).fetchall()
    if rows:
        return rows[0][0]
    return None


def _players_college(conn, value):
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM draft WHERE college = ?",
        (value,),
    )


def _pick_conference(conn, current_players=None):
    conf = random.choice(list(CONFERENCE_SCHOOLS.keys()))
    return conf


def _players_conference(conn, value):
    schools = list(CONFERENCE_SCHOOLS.get(value, set()))
    if not schools:
        return frozenset()
    placeholders = ",".join("?" * len(schools))
    return _query_set(
        conn,
        f"SELECT DISTINCT player FROM draft WHERE college IN ({placeholders})",
        schools,
    )


def _pick_static(conn, current_players=None):
    return ""


def _players_pro_bowl(conn, value):
    return _query_set(conn, "SELECT DISTINCT player FROM draft WHERE pro_bowls >= 1")


def _players_all_pro(conn, value):
    return _query_set(conn, "SELECT DISTINCT player FROM draft WHERE all_pro >= 1")


def _players_round1(conn, value):
    return _query_set(conn, "SELECT DISTINCT player FROM draft WHERE draft_round = 1")


def _players_top10(conn, value):
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM draft WHERE CAST(draft_pick AS INTEGER) <= 10"
    )


def _pick_pass_yds(conn, current_players=None):
    return str(random.choice([3500, 4000]))


def _players_pass_yds(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM season_stats WHERE pass_yds >= ?",
        (threshold,),
    )


def _pick_pass_td(conn, current_players=None):
    return str(random.choice([25, 30]))


def _players_pass_td(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM season_stats WHERE pass_td >= ?",
        (threshold,),
    )


def _pick_rush_yds(conn, current_players=None):
    return str(random.choice([750, 1000]))


def _players_rush_yds(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM season_stats WHERE rush_yds >= ?",
        (threshold,),
    )


def _pick_rec_yds(conn, current_players=None):
    return str(random.choice([750, 1000]))


def _players_rec_yds(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM season_stats WHERE rec_yds >= ?",
        (threshold,),
    )


def _players_rec_100(conn, value):
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM season_stats WHERE rec_rec >= 100"
    )


def _pick_era(conn, current_players=None):
    return random.choice(list(ERA_RANGES.keys()))


def _players_era(conn, value):
    rng = ERA_RANGES.get(value)
    if not rng:
        return frozenset()
    return _query_set(
        conn,
        """SELECT DISTINCT player FROM stats WHERE season BETWEEN ? AND ?
           UNION
           SELECT DISTINCT player FROM def_stats WHERE season BETWEEN ? AND ?""",
        (rng[0], rng[1], rng[0], rng[1]),
    )


def _pick_afc_nfc(conn, current_players=None):
    return random.choice(["AFC", "NFC"])


def _players_afc_nfc(conn, value):
    if value == "AFC":
        teams = list(AFC_TEAMS)
    else:
        teams = list(NFC_TEAMS)
    placeholders = ",".join("?" * len(teams))
    return _query_set(
        conn,
        f"""SELECT DISTINCT player FROM stats WHERE team IN ({placeholders})
            UNION
            SELECT DISTINCT player FROM def_stats WHERE team IN ({placeholders})""",
        teams + teams,
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
        f"""SELECT DISTINCT player FROM stats WHERE team IN ({placeholders})
            UNION
            SELECT DISTINCT player FROM def_stats WHERE team IN ({placeholders})""",
        teams + teams,
    )


def _pick_teammate(conn, current_players=None):
    if not current_players:
        return None
    players_list = list(current_players)
    random.shuffle(players_list)
    # Pick a player who actually has teammates in season_stats
    for candidate in players_list[:10]:
        row = conn.execute(
            """SELECT s2.player FROM season_stats s1
               JOIN season_stats s2 ON s1.team=s2.team AND s1.season=s2.season
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
        """SELECT DISTINCT s2.player FROM season_stats s1
           JOIN season_stats s2 ON s1.team=s2.team AND s1.season=s2.season
           WHERE s1.player=? AND s2.player!=?""",
        (value, value),
    )


def _pick_sacks(conn, current_players=None):
    return str(random.choice([10, 12, 15]))


def _players_sacks(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM def_stats WHERE sacks >= ?",
        (threshold,),
    )


def _pick_ints(conn, current_players=None):
    return str(random.choice([5, 8]))


def _players_ints(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM def_stats WHERE interceptions >= ?",
        (threshold,),
    )


def _pick_high_ppr(conn, current_players=None):
    return str(random.choice([250, 300, 350]))


def _players_high_ppr(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM stats WHERE fantasy_ppr >= ?",
        (threshold,),
    )


def _players_hof(conn, value):
    return _query_set(conn, "SELECT DISTINCT player FROM nfl_hof")


def _get_sb_team_seasons(conn, include_loser=False):
    """Return set of (team_code, season) tuples for Super Bowl participants."""
    rows = conn.execute(
        "SELECT winner, loser, year FROM nfl_superbowl WHERE game_type='Super Bowl'"
    ).fetchall()
    pairs = set()
    for (winner, loser, year) in rows:
        season = year - 1
        for name in ([winner, loser] if include_loser else [winner]):
            code = SB_TEAM_NAME_TO_CODE.get(name)
            if code:
                pairs.add((code, season))
    return pairs


def _players_sb_champion(conn, value):
    pairs = _get_sb_team_seasons(conn, include_loser=False)
    results = set()
    for (code, season) in pairs:
        players = _query_set(
            conn,
            """SELECT DISTINCT player FROM stats WHERE team=? AND season=?
               UNION
               SELECT DISTINCT player FROM def_stats WHERE team=? AND season=?""",
            (code, season, code, season),
        )
        results |= players
    return frozenset(results)


def _players_sb_appearance(conn, value):
    pairs = _get_sb_team_seasons(conn, include_loser=True)
    results = set()
    for (code, season) in pairs:
        players = _query_set(
            conn,
            """SELECT DISTINCT player FROM stats WHERE team=? AND season=?
               UNION
               SELECT DISTINCT player FROM def_stats WHERE team=? AND season=?""",
            (code, season, code, season),
        )
        results |= players
    return frozenset(results)


def _pick_nfl_award(conn, current_players=None):
    _, display = random.choice(_NFL_AWARD_OPTIONS)
    return display


def _players_nfl_award(conn, value):
    code = _NFL_AWARD_DISPLAY_TO_CODE.get(value)
    if not code:
        return frozenset()
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nfl_awards WHERE award=?",
        (code,),
    )


def _players_all_rookie_nfl(conn, value):
    return _query_set(conn, "SELECT DISTINCT player FROM nfl_allrookie")


def _pick_kicker_fg(conn, current_players=None):
    return str(random.choice([85, 88, 90]))


def _players_kicker_fg(conn, value):
    threshold = float(value)
    return _query_set(
        conn,
        "SELECT DISTINCT player FROM nfl_kicking WHERE fg_pct >= ?",
        (threshold,),
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
        "id": "conference",
        "label": "Attended a {value} school",
        "pick": _pick_conference,
        "players": _players_conference,
        "is_teammate": False,
    },
    {
        "id": "pro_bowl",
        "label": "Made the Pro Bowl",
        "pick": _pick_static,
        "players": _players_pro_bowl,
        "is_teammate": False,
    },
    {
        "id": "all_pro",
        "label": "Was an All-Pro selection",
        "pick": _pick_static,
        "players": _players_all_pro,
        "is_teammate": False,
    },
    {
        "id": "round_1",
        "label": "Was a 1st round draft pick",
        "pick": _pick_static,
        "players": _players_round1,
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
        "id": "pass_yds",
        "label": "Threw for {value}+ yards in a season",
        "pick": _pick_pass_yds,
        "players": _players_pass_yds,
        "is_teammate": False,
    },
    {
        "id": "pass_td",
        "label": "Threw {value}+ TD passes in a season",
        "pick": _pick_pass_td,
        "players": _players_pass_td,
        "is_teammate": False,
    },
    {
        "id": "rush_yds",
        "label": "Rushed for {value}+ yards in a season",
        "pick": _pick_rush_yds,
        "players": _players_rush_yds,
        "is_teammate": False,
    },
    {
        "id": "rec_yds",
        "label": "Had {value}+ receiving yards in a season",
        "pick": _pick_rec_yds,
        "players": _players_rec_yds,
        "is_teammate": False,
    },
    {
        "id": "rec_100",
        "label": "Had 100+ receptions in a season",
        "pick": _pick_static,
        "players": _players_rec_100,
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
        "id": "afc_nfc",
        "label": "Played for an {value} team",
        "pick": _pick_afc_nfc,
        "players": _players_afc_nfc,
        "is_teammate": False,
    },
    {
        "id": "division",
        "label": "Played for an {value} team",
        "pick": _pick_division,
        "players": _players_division,
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
        "id": "high_ppr",
        "label": "Scored {value}+ PPR fantasy points in a season",
        "pick": _pick_high_ppr,
        "players": _players_high_ppr,
        "is_teammate": False,
    },
    {
        "id": "sacks",
        "label": "Had {value}+ sacks in a season",
        "pick": _pick_sacks,
        "players": _players_sacks,
        "is_teammate": False,
    },
    {
        "id": "interceptions",
        "label": "Had {value}+ interceptions in a season",
        "pick": _pick_ints,
        "players": _players_ints,
        "is_teammate": False,
    },
    {
        "id": "hof",
        "label": "Is in the Pro Football Hall of Fame",
        "pick": _pick_static,
        "players": _players_hof,
        "is_teammate": False,
    },
    {
        "id": "sb_champion",
        "label": "Won a Super Bowl",
        "pick": _pick_static,
        "players": _players_sb_champion,
        "is_teammate": False,
    },
    {
        "id": "sb_appearance",
        "label": "Played in a Super Bowl",
        "pick": _pick_static,
        "players": _players_sb_appearance,
        "is_teammate": False,
    },
    {
        "id": "nfl_award",
        "label": "Won {value}",
        "pick": _pick_nfl_award,
        "players": _players_nfl_award,
        "is_teammate": False,
    },
    {
        "id": "all_rookie_nfl",
        "label": "Made the NFL All-Rookie Team",
        "pick": _pick_static,
        "players": _players_all_rookie_nfl,
        "is_teammate": False,
    },
    {
        "id": "kicker_fg",
        "label": "Made {value}%+ of field goals in a season",
        "pick": _pick_kicker_fg,
        "players": _players_kicker_fg,
        "is_teammate": False,
    },
]

# Index for fast lookup
_CAT_BY_ID = {c["id"]: c for c in CATEGORIES}

# ── Conflict groups ──────────────────────────────────────────────────────────
# Categories in the same group are redundant with each other (one implies the
# other). If any member is already in the chain, exclude all others in the group.
_CONFLICT_GROUPS = [
    {"round_1", "top_10"},       # top-10 picks are all 1st round picks
    {"team", "division"},         # knowing the team tells you the division
    {"team", "afc_nfc"},          # knowing the team tells you AFC/NFC
    {"division", "afc_nfc"},      # knowing the division tells you AFC/NFC
    {"college", "conference"},    # knowing the college tells you the conference
    {"sb_champion", "sb_appearance"},  # champion implies appeared in SB
]


def _expand_excluded(existing_ids):
    """Expand a set of excluded IDs to also exclude conflicting categories."""
    expanded = set(existing_ids)
    for group in _CONFLICT_GROUPS:
        if expanded & group:          # any member already excluded/used?
            expanded |= group         # block all members of the group
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
    """Pick a starting category with >= 10 valid players. No teammate/rare cats."""
    exclude_start = {"teammate"}
    candidates = [c for c in CATEGORIES if c["id"] not in exclude_start]
    random.shuffle(candidates)

    for cat in candidates:
        # Try up to 5 values per category
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
        # Try up to 5 values for variable-value categories
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

    return best  # may be None


def search_players(conn, term):
    """Search player names across all tables, with normalized matching."""
    from name_utils import normalize_name
    key = normalize_name(term)
    if not key:
        return []
    rows = conn.execute(
        """SELECT DISTINCT player FROM stats
           UNION
           SELECT DISTINCT player FROM season_stats
           UNION
           SELECT DISTINCT player FROM draft
           UNION
           SELECT DISTINCT player FROM def_stats
           ORDER BY player"""
    ).fetchall()
    starts, contains = [], []
    for (name,) in rows:
        nk = normalize_name(name)
        if nk.startswith(key):
            starts.append(name)
        elif key in nk:
            contains.append(name)
    return (starts + contains)[:20]


def check_player_against_chain(conn, player, chain):
    """Return per-link pass/fail for a player against a chain.

    Returns a list of dicts: [{label, passed}, ...]
    """
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
