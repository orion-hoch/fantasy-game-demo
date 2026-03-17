"""
ttb.py  —  Ticking Time Bomb game logic
"""
import random
import uuid

# ── In-memory game state ──────────────────────────────────────────────────────
_games: dict = {}   # { game_id: { player, clues, revealed, wrong, over } }

MAX_WRONG = 5


# ── DB helpers ────────────────────────────────────────────────────────────────

def _pick_active_player(conn):
    row = conn.execute(
        """
        SELECT player, pos FROM stats
        WHERE season >= 2022 AND games >= 5 AND fantasy_ppr >= 30
        ORDER BY RANDOM() LIMIT 1
        """
    ).fetchone()
    return {"player": row[0], "pos": row[1]} if row else None


def _seasons_of_experience(conn, player):
    row = conn.execute(
        "SELECT COUNT(DISTINCT season) FROM stats WHERE player = ?", (player,)
    ).fetchone()
    return int(row[0]) if row else 1


def _early_teammate(conn, player):
    row = conn.execute(
        "SELECT MIN(season) FROM stats WHERE player = ?", (player,)
    ).fetchone()
    if not row or row[0] is None:
        return None
    first_season = row[0]
    team_row = conn.execute(
        "SELECT team FROM stats WHERE player = ? AND season = ? LIMIT 1",
        (player, first_season),
    ).fetchone()
    if not team_row:
        return None
    tmate = conn.execute(
        """
        SELECT player FROM stats
        WHERE team = ? AND season = ? AND player != ?
        ORDER BY RANDOM() LIMIT 1
        """,
        (team_row[0], first_season, player),
    ).fetchone()
    return tmate[0] if tmate else None


def _draft_info(conn, player):
    row = conn.execute(
        "SELECT college, draft_round, draft_year FROM draft WHERE player = ? LIMIT 1",
        (player,),
    ).fetchone()
    if not row:
        return None, None, None
    return row[0], row[1], row[2]


def _best_stat(conn, player, pos):
    col = {"QB": "pass_yds", "RB": "rush_yds"}.get(pos, "rec_yds")
    label = {"QB": "passing yards", "RB": "rushing yards"}.get(pos, "receiving yards")
    try:
        row = conn.execute(
            f"SELECT MAX(CAST({col} AS REAL)) FROM season_stats WHERE player = ?",
            (player,),
        ).fetchone()
        if row and row[0] and float(row[0]) >= 100:
            floored = (int(float(row[0])) // 100) * 100
            return f"{floored:,}+ {label} in a single season"
    except Exception:
        pass
    # Fallback: best PPR season
    try:
        row = conn.execute(
            "SELECT MAX(fantasy_ppr) FROM stats WHERE player = ?", (player,)
        ).fetchone()
        if row and row[0] and float(row[0]) >= 50:
            return f"{int(float(row[0]))}+ PPR fantasy points in a single season"
    except Exception:
        pass
    return "Stat data not available"


def _ordinal(n):
    n = int(n)
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd','th'][min(n % 10, 4)]}"


# ── Clue builder ──────────────────────────────────────────────────────────────

def _build_clues(conn, player, pos):
    clues = []

    # 1 — Position + experience
    seasons = _seasons_of_experience(conn, player)
    clues.append({
        "icon": "🏈",
        "label": "Position & Experience",
        "text": f"{pos} with {seasons} season{'s' if seasons != 1 else ''} of NFL experience",
    })

    # 2 — Early-career teammate
    tmate = _early_teammate(conn, player)
    if tmate:
        clues.append({
            "icon": "🤝",
            "label": "Early-Career Teammate",
            "text": f"Early in their career, played alongside {tmate}",
        })
    else:
        clues.append({
            "icon": "🤝",
            "label": "Early-Career Teammate",
            "text": "Teammate data not available",
        })

    # 3 — College
    college, draft_round, draft_year = _draft_info(conn, player)
    if college:
        clues.append({"icon": "🎓", "label": "College", "text": f"Attended {college}"})
    else:
        clues.append({"icon": "🎓", "label": "College", "text": "College not on record"})

    # 4 — Draft info
    if draft_round is not None and draft_year is not None:
        clues.append({
            "icon": "📋",
            "label": "Draft",
            "text": f"Selected in the {_ordinal(draft_round)} round of the {int(float(draft_year))} NFL Draft",
        })
    else:
        clues.append({
            "icon": "📋",
            "label": "Draft",
            "text": "Undrafted or draft data not on record",
        })

    # 5 — Best season stat
    clues.append({
        "icon": "📊",
        "label": "Career Stat",
        "text": _best_stat(conn, player, pos),
    })

    return clues


# ── Public API ────────────────────────────────────────────────────────────────

def start_game(conn):
    """
    Returns (game_id, [first_clue]) or (None, []) on error.
    """
    p = _pick_active_player(conn)
    if not p:
        return None, []
    player, pos = p["player"], p["pos"]
    clues = _build_clues(conn, player, pos)
    gid = str(uuid.uuid4())
    _games[gid] = {
        "player": player,
        "clues": clues,
        "revealed": 1,
        "wrong": 0,
        "over": False,
    }
    return gid, [clues[0]]


def check_guess(game_id, guess):
    """
    Returns one of:
      { correct: True,  player: str }
      { correct: False, new_clue: dict, wrong: int }
      { correct: False, exploded: True, player: str, wrong: int }
      { error: str }
    """
    game = _games.get(game_id)
    if not game or game["over"]:
        return {"error": "Game not found or already over"}

    if guess.strip().lower() == game["player"].strip().lower():
        game["over"] = True
        return {"correct": True, "player": game["player"]}

    game["wrong"] += 1
    wrong = game["wrong"]

    if wrong >= MAX_WRONG:
        game["over"] = True
        return {"correct": False, "exploded": True, "player": game["player"], "wrong": wrong}

    # Reveal next clue
    idx = game["revealed"]
    new_clue = game["clues"][idx] if idx < len(game["clues"]) else None
    game["revealed"] = min(idx + 1, len(game["clues"]))
    return {"correct": False, "new_clue": new_clue, "wrong": wrong}


def reveal_answer(game_id):
    game = _games.get(game_id)
    if not game:
        return {"error": "Game not found"}
    game["over"] = True
    return {"player": game["player"]}


def cleanup_old_games(max_size=2000):
    if len(_games) > max_size:
        for k in list(_games.keys())[: max_size // 2]:
            del _games[k]
