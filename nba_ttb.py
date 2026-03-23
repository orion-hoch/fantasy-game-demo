"""
nba_ttb.py  —  NBA Ticking Time Bomb game logic
"""
import uuid
import random

from session_store import GameStore

_games = GameStore("nba_ttb", ttl_seconds=43200)
MAX_WRONG = 5


# ── DB helpers ────────────────────────────────────────────────────────────────

def _pick_classic_player(conn):
    """Recent NBA player, season >= 2021, games >= 10, fantasy_score >= 1500."""
    row = conn.execute(
        """
        SELECT player, pos FROM nba_stats
        WHERE season >= 2021 AND games >= 10 AND fantasy_score >= 1500
        ORDER BY RANDOM() LIMIT 1
        """
    ).fetchone()
    return {"player": row[0], "pos": row[1]} if row else None


def _pick_vintage_player(conn):
    """Notable past NBA player from nba_draft with win_shares >= 30,
    max season in nba_stats < 2021, at least 3 teammates in nba_stats."""
    row = conn.execute(
        """
        SELECT d.player FROM nba_draft d
        WHERE CAST(d.win_shares AS REAL) >= 30
          AND d.player IN (SELECT DISTINCT player FROM nba_stats)
          AND (SELECT MAX(CAST(season AS INTEGER)) FROM nba_stats WHERE player = d.player) < 2021
          AND (
            SELECT COUNT(DISTINCT s2.player)
            FROM nba_stats s1
            JOIN nba_stats s2 ON s1.team = s2.team AND s1.season = s2.season
            WHERE s1.player = d.player AND s2.player != d.player
          ) >= 3
        ORDER BY RANDOM() LIMIT 1
        """
    ).fetchone()
    if not row:
        return None
    player = row[0]
    # Get position from nba_stats (most common)
    pos_row = conn.execute(
        """SELECT pos FROM nba_stats WHERE player = ?
           GROUP BY pos ORDER BY COUNT(*) DESC LIMIT 1""",
        (player,),
    ).fetchone()
    pos = pos_row[0] if pos_row else "F"
    return {"player": player, "pos": pos}


# ── Teammate chain builders ───────────────────────────────────────────────────

def _build_classic_chain(conn, player):
    """Find 5 notable teammates. One per team. Notable = career pts_pg >= 12 in nba_draft."""
    teams = conn.execute(
        "SELECT team, MIN(season) FROM nba_stats WHERE player = ? GROUP BY team ORDER BY MIN(season)",
        (player,),
    ).fetchall()
    if not teams:
        return []

    used = set()
    clues = []

    def pick(team):
        seasons = [r[0] for r in conn.execute(
            "SELECT DISTINCT season FROM nba_stats WHERE player = ? AND team = ?",
            (player, team),
        ).fetchall()]
        if not seasons:
            return None
        ph = ",".join("?" * len(seasons))
        # Prefer notable teammates (pts_pg >= 12 in nba_draft)
        notable = [r[0] for r in conn.execute(
            f"""SELECT DISTINCT s.player FROM nba_stats s
                LEFT JOIN nba_draft d ON d.player = s.player
                WHERE s.team = ? AND s.season IN ({ph}) AND s.player != ?
                  AND CAST(d.pts_pg AS REAL) >= 12
                ORDER BY RANDOM() LIMIT 20""",
            [team] + seasons + [player],
        ).fetchall()]
        if notable:
            return random.choice(notable)
        # Fallback: any teammate
        row = conn.execute(
            f"SELECT DISTINCT player FROM nba_stats WHERE team=? AND season IN ({ph}) AND player!=? ORDER BY RANDOM() LIMIT 1",
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

    if len(clues) < 5:
        # Pad with more notable teammates
        extras = conn.execute(
            """SELECT DISTINCT s2.player FROM nba_stats s1
               JOIN nba_stats s2 ON s1.team=s2.team AND s1.season=s2.season
               LEFT JOIN nba_draft d ON d.player = s2.player
               WHERE s1.player=? AND s2.player!=?
                 AND CAST(d.pts_pg AS REAL) >= 12
               ORDER BY RANDOM() LIMIT 40""",
            (player, player),
        ).fetchall()
        if len(extras) < 5:
            extras += conn.execute(
                """SELECT DISTINCT s2.player FROM nba_stats s1
                   JOIN nba_stats s2 ON s1.team=s2.team AND s1.season=s2.season
                   WHERE s1.player=? AND s2.player!=?
                   ORDER BY RANDOM() LIMIT 40""",
                (player, player),
            ).fetchall()
        pool = [r[0] for r in extras]
        random.shuffle(pool)
        for name in pool:
            if len(clues) >= 5:
                break
            if name not in used:
                used.add(name)
                clues.append({"icon": "🤝", "label": "Teammate", "text": name})

    return clues[:5]


def _build_vintage_chain(conn, player):
    """Similar to classic but prefer win_shares >= 10 teammates."""
    teams = conn.execute(
        "SELECT team, MIN(season) FROM nba_stats WHERE player = ? GROUP BY team ORDER BY MIN(season)",
        (player,),
    ).fetchall()
    if not teams:
        return []

    used = set()
    clues = []

    def pick_teammate(team):
        seasons = [r[0] for r in conn.execute(
            "SELECT DISTINCT season FROM nba_stats WHERE player = ? AND team = ?",
            (player, team),
        ).fetchall()]
        if not seasons:
            return None
        ph = ",".join("?" * len(seasons))
        notable = [r[0] for r in conn.execute(
            f"""SELECT DISTINCT s.player FROM nba_stats s
                LEFT JOIN nba_draft d ON d.player = s.player
                WHERE s.team = ? AND s.season IN ({ph}) AND s.player != ?
                  AND CAST(d.win_shares AS REAL) >= 10
                ORDER BY CAST(d.win_shares AS REAL) DESC, RANDOM() LIMIT 20""",
            [team] + seasons + [player],
        ).fetchall()]
        if notable:
            return random.choice(notable)
        # Fallback: any teammate
        row = conn.execute(
            f"SELECT DISTINCT player FROM nba_stats WHERE team=? AND season IN ({ph}) AND player!=? ORDER BY RANDOM() LIMIT 1",
            [team] + seasons + [player],
        ).fetchone()
        return row[0] if row else None

    for team, _ in teams:
        if len(clues) >= 5:
            break
        tm = pick_teammate(team)
        if tm and tm not in used:
            used.add(tm)
            clues.append({"icon": "🤝", "label": "Teammate", "text": tm})

    if len(clues) < 5:
        extras = conn.execute(
            """SELECT DISTINCT s2.player FROM nba_stats s1
               JOIN nba_stats s2 ON s1.team=s2.team AND s1.season=s2.season
               LEFT JOIN nba_draft d ON d.player = s2.player
               WHERE s1.player=? AND s2.player!=?
                 AND CAST(d.win_shares AS REAL) >= 10
               ORDER BY CAST(d.win_shares AS REAL) DESC, RANDOM() LIMIT 40""",
            (player, player),
        ).fetchall()
        if len(extras) < 5:
            extras += conn.execute(
                """SELECT DISTINCT s2.player FROM nba_stats s1
                   JOIN nba_stats s2 ON s1.team=s2.team AND s1.season=s2.season
                   WHERE s1.player=? AND s2.player!=?
                   ORDER BY RANDOM() LIMIT 40""",
                (player, player),
            ).fetchall()
        pool = [r[0] for r in extras]
        random.shuffle(pool)
        for name in pool:
            if len(clues) >= 5:
                break
            if name not in used:
                used.add(name)
                clues.append({"icon": "🤝", "label": "Teammate", "text": name})

    return clues[:5]


# ── Hints ─────────────────────────────────────────────────────────────────────

def _build_hints(conn, player, pos):
    hints = []

    hints.append({"icon": "🏀", "label": "Position", "text": f"Plays {pos}"})

    row = conn.execute(
        "SELECT COUNT(DISTINCT season) FROM nba_stats WHERE player = ?", (player,)
    ).fetchone()
    seasons = int(row[0]) if row else 1
    hints.append({
        "icon": "📅", "label": "Experience",
        "text": f"{seasons} season{'s' if seasons != 1 else ''} of NBA experience",
    })

    draft = conn.execute(
        "SELECT college, draft_pick, pts_pg FROM nba_draft WHERE player = ? LIMIT 1",
        (player,),
    ).fetchone()

    if draft and draft[0]:
        hints.append({"icon": "🎓", "label": "College", "text": f"Attended {draft[0]}"})
    else:
        hints.append({"icon": "🎓", "label": "College", "text": "College not on record"})

    if draft and draft[1] is not None:
        try:
            pick = int(float(draft[1]))
            sfx = {1: "st", 2: "nd", 3: "rd"}.get(pick if pick <= 20 else 0, "th")
            hints.append({"icon": "📋", "label": "Draft", "text": f"{pick}{sfx} pick, NBA Draft"})
        except (ValueError, TypeError):
            hints.append({"icon": "📋", "label": "Draft", "text": "Undrafted"})
    else:
        hints.append({"icon": "📋", "label": "Draft", "text": "Undrafted"})

    stat_text = None
    try:
        row = conn.execute(
            "SELECT MAX(CAST(pts_pg AS REAL)) FROM nba_stats WHERE player = ?", (player,)
        ).fetchone()
        if row and row[0] and float(row[0]) >= 1:
            floored = int(float(row[0]))
            stat_text = f"Averaged {floored}+ PPG in a season"
    except Exception:
        pass
    if not stat_text:
        try:
            row = conn.execute(
                "SELECT MAX(CAST(fantasy_score AS REAL)) FROM nba_stats WHERE player = ?", (player,)
            ).fetchone()
            if row and row[0]:
                stat_text = f"{int(float(row[0]))}+ fantasy pts in a season"
        except Exception:
            pass

    allstar = conn.execute(
        "SELECT selections FROM nba_allstars WHERE player = ? LIMIT 1", (player,)
    ).fetchone()
    if allstar and allstar[0]:
        count = int(allstar[0])
        sfx_word = "time" if count == 1 else "times"
        hints.append({"icon": "⭐", "label": "All-Star", "text": f"Named an NBA All-Star {count} {sfx_word}"})
    else:
        hints.append({"icon": "📊", "label": "Career Stat", "text": stat_text or "Stat data unavailable"})
        return hints

    hints.append({"icon": "📊", "label": "Career Stat", "text": stat_text or "Stat data unavailable"})
    return hints


# ── Public API ────────────────────────────────────────────────────────────────

def start_game(conn, mode="classic"):
    if mode == "vintage":
        p = _pick_vintage_player(conn)
        chain_fn = _build_vintage_chain
    else:
        p = _pick_classic_player(conn)
        chain_fn = _build_classic_chain

    if not p:
        return None, [], []

    player, pos = p["player"], p["pos"]
    clues = chain_fn(conn, player)
    if not clues:
        return None, [], []

    hints = _build_hints(conn, player, pos)
    gid = str(uuid.uuid4())
    _games[gid] = {
        "player":   player,
        "pos":      pos,
        "mode":     mode,
        "clues":    clues,
        "revealed": 1,
        "wrong":    0,
        "over":     False,
    }
    return gid, [clues[0]], hints


def check_guess(game_id, guess, skip=False):
    game = _games.get(game_id)
    if not game or game["over"]:
        return {"error": "Game not found or already over"}

    if not skip and guess.strip().lower() == game["player"].strip().lower():
        game["over"] = True
        _games[game_id] = game
        return {"correct": True, "player": game["player"]}

    game["wrong"] += 1
    wrong = game["wrong"]

    if wrong >= MAX_WRONG:
        game["over"] = True
        _games[game_id] = game
        return {"correct": False, "exploded": True, "player": game["player"],
                "wrong": wrong, "skipped": skip}

    idx = game["revealed"]
    new_clue = game["clues"][idx] if idx < len(game["clues"]) else None
    game["revealed"] = min(idx + 1, len(game["clues"]))
    _games[game_id] = game
    return {"correct": False, "new_clue": new_clue, "wrong": wrong, "skipped": skip}


def reveal_answer(game_id):
    game = _games.get(game_id)
    if not game:
        return {"error": "Game not found"}
    game["over"] = True
    _games[game_id] = game
    return {"player": game["player"]}


def cleanup_old_games(max_size=2000):
    _games.cleanup_to_size(max_size)
