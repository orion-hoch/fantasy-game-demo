"""
ttb.py  —  Ticking Time Bomb game logic
"""
import uuid

_games: dict = {}
MAX_WRONG = 5


# ── DB helpers ────────────────────────────────────────────────────────────────

def _pick_active_player(conn):
    row = conn.execute(
        """
        SELECT player, pos FROM stats
        WHERE season >= 2022 AND games >= 5 AND fantasy_ppr >= 50
        ORDER BY RANDOM() LIMIT 1
        """
    ).fetchone()
    return {"player": row[0], "pos": row[1]} if row else None


def _build_teammate_chain(conn, player):
    """One teammate per team the player played for (oldest team first).
    Prefers recognisable teammates (PPR >= 50). Pads to 5 if needed."""
    teams = conn.execute(
        "SELECT team, MIN(season) AS first FROM stats WHERE player = ? GROUP BY team ORDER BY first",
        (player,),
    ).fetchall()
    if not teams:
        return []

    used = set()
    clues = []

    def pick(team):
        seasons = [r[0] for r in conn.execute(
            "SELECT DISTINCT season FROM stats WHERE player = ? AND team = ?",
            (player, team),
        ).fetchall()]
        if not seasons:
            return None
        ph = ",".join("?" * len(seasons))
        row = conn.execute(
            f"""SELECT DISTINCT s.player FROM stats s
                WHERE s.team = ? AND s.season IN ({ph}) AND s.player != ?
                  AND EXISTS (SELECT 1 FROM stats s2 WHERE s2.player = s.player AND s2.fantasy_ppr >= 50)
                ORDER BY RANDOM() LIMIT 1""",
            [team] + seasons + [player],
        ).fetchone()
        if not row:
            row = conn.execute(
                f"SELECT DISTINCT player FROM stats WHERE team = ? AND season IN ({ph}) AND player != ? ORDER BY RANDOM() LIMIT 1",
                [team] + seasons + [player],
            ).fetchone()
        return row[0] if row else None

    for team, _ in teams:
        if len(clues) >= 5:
            break
        tm = pick(team)
        if tm and tm not in used:
            used.add(tm)
            clues.append({"icon": "🤝", "label": "Teammate", "text": tm})

    # Pad from any overlapping season
    if len(clues) < 5:
        extras = conn.execute(
            """SELECT DISTINCT s2.player FROM stats s1
               JOIN stats s2 ON s1.team = s2.team AND s1.season = s2.season
               WHERE s1.player = ? AND s2.player != ?
                 AND EXISTS (SELECT 1 FROM stats s3 WHERE s3.player = s2.player AND s3.fantasy_ppr >= 50)
               ORDER BY RANDOM() LIMIT 40""",
            (player, player),
        ).fetchall()
        for row in extras:
            if len(clues) >= 5:
                break
            if row[0] not in used:
                used.add(row[0])
                clues.append({"icon": "🤝", "label": "Teammate", "text": row[0]})

    return clues[:5]


def _build_hints(conn, player, pos):
    """Return 5 bio hints ordered from vague → specific."""
    hints = []

    # 1 — Position
    hints.append({"icon": "🏈", "label": "Position", "text": f"Plays {pos}"})

    # 2 — Career length
    row = conn.execute(
        "SELECT COUNT(DISTINCT season) FROM stats WHERE player = ?", (player,)
    ).fetchone()
    seasons = int(row[0]) if row else 1
    hints.append({
        "icon": "📅",
        "label": "Experience",
        "text": f"{seasons} season{'s' if seasons != 1 else ''} of NFL experience",
    })

    # 3 — College
    draft = conn.execute(
        "SELECT college, draft_round, draft_year FROM draft WHERE player = ? LIMIT 1",
        (player,),
    ).fetchone()
    if draft and draft[0]:
        hints.append({"icon": "🎓", "label": "College", "text": f"Attended {draft[0]}"})
    else:
        hints.append({"icon": "🎓", "label": "College", "text": "College not on record"})

    # 4 — Draft round + year
    if draft and draft[1] is not None and draft[2] is not None:
        rnd = int(float(draft[1]))
        yr  = int(float(draft[2]))
        sfx = {1: "st", 2: "nd", 3: "rd"}.get(rnd, "th")
        hints.append({"icon": "📋", "label": "Draft", "text": f"{rnd}{sfx}-round pick, {yr} NFL Draft"})
    else:
        hints.append({"icon": "📋", "label": "Draft", "text": "Undrafted or draft data not on record"})

    # 5 — Best season stat
    col   = {"QB": "pass_yds", "RB": "rush_yds"}.get(pos, "rec_yds")
    label = {"QB": "passing yards", "RB": "rushing yards"}.get(pos, "receiving yards")
    stat_text = None
    try:
        row = conn.execute(
            f"SELECT MAX(CAST({col} AS REAL)) FROM season_stats WHERE player = ?", (player,)
        ).fetchone()
        if row and row[0] and float(row[0]) >= 100:
            floored = (int(float(row[0])) // 100) * 100
            stat_text = f"{floored:,}+ {label} in a single season"
    except Exception:
        pass
    if not stat_text:
        try:
            row = conn.execute(
                "SELECT MAX(fantasy_ppr) FROM stats WHERE player = ?", (player,)
            ).fetchone()
            if row and row[0]:
                stat_text = f"{int(float(row[0]))}+ PPR fantasy points in a single season"
        except Exception:
            pass
    hints.append({"icon": "📊", "label": "Career Stat", "text": stat_text or "Stat data unavailable"})

    return hints


# ── Public API ────────────────────────────────────────────────────────────────

def start_game(conn):
    """Returns (game_id, first_clue_list, all_hints) or (None, [], [])."""
    p = _pick_active_player(conn)
    if not p:
        return None, [], []
    player, pos = p["player"], p["pos"]
    clues = _build_teammate_chain(conn, player)
    if not clues:
        return None, [], []
    hints = _build_hints(conn, player, pos)
    gid = str(uuid.uuid4())
    _games[gid] = {
        "player": player,
        "pos": pos,
        "clues": clues,
        "revealed": 1,
        "wrong": 0,
        "over": False,
    }
    return gid, [clues[0]], hints


def check_guess(game_id, guess, skip=False):
    """
    skip=True counts as a wrong (fuse burns) without checking the answer.
    Returns one of:
      { correct: True,  player }
      { correct: False, new_clue, wrong, skipped }
      { correct: False, exploded: True, player, wrong, skipped }
    """
    game = _games.get(game_id)
    if not game or game["over"]:
        return {"error": "Game not found or already over"}

    if not skip and guess.strip().lower() == game["player"].strip().lower():
        game["over"] = True
        return {"correct": True, "player": game["player"]}

    game["wrong"] += 1
    wrong = game["wrong"]

    if wrong >= MAX_WRONG:
        game["over"] = True
        return {"correct": False, "exploded": True, "player": game["player"],
                "wrong": wrong, "skipped": skip}

    idx = game["revealed"]
    new_clue = game["clues"][idx] if idx < len(game["clues"]) else None
    game["revealed"] = min(idx + 1, len(game["clues"]))
    return {"correct": False, "new_clue": new_clue, "wrong": wrong, "skipped": skip}


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
