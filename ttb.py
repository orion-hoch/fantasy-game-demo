"""
ttb.py  —  Ticking Time Bomb game logic
"""
import uuid
import random

_games: dict = {}
MAX_WRONG = 5


# ── DB helpers ────────────────────────────────────────────────────────────────

def _pick_classic_player(conn, min_draft_year=None):
    """Active player (season >= 2022, PPR >= 50, games >= 5)."""
    extra = ""
    params = []
    if min_draft_year:
        extra = " AND EXISTS (SELECT 1 FROM draft d WHERE d.player = stats.player AND CAST(d.draft_year AS REAL) >= ?)"
        params = [min_draft_year]
    row = conn.execute(
        f"""
        SELECT player, pos FROM stats
        WHERE season >= 2022 AND games >= 5 AND fantasy_ppr >= 50{extra}
        ORDER BY RANDOM() LIMIT 1
        """,
        params,
    ).fetchone()
    return {"player": row[0], "pos": row[1]} if row else None


_DEF_POS_SET = {"CB", "S", "LB", "DE", "DT"}

_DEF_DRAFT_NORM = {
    "CB": "CB", "DB": "CB",
    "S": "S", "SS": "S", "FS": "S",
    "LB": "LB", "OLB": "LB", "ILB": "LB", "MLB": "LB",
    "RILB": "LB", "LILB": "LB", "ROLB": "LB", "LOLB": "LB",
    "DE": "DE", "EDGE": "DE",
    "DT": "DT", "NT": "DT", "MG": "DT",
}


def _pick_defense_player(conn, min_draft_year=None):
    """Pro Bowl defensive player with at least 3 Pro Bowl offensive teammates."""
    extra = ""
    if min_draft_year:
        extra = f"  AND CAST(d.draft_year AS REAL) >= {int(min_draft_year)}\n"
    row = conn.execute(
        f"""
        SELECT d.player, d.pos FROM draft d
        WHERE CAST(d.pro_bowls AS REAL) >= 1
          AND d.player IN (SELECT DISTINCT player FROM def_stats)
{extra}          AND (
            SELECT COUNT(DISTINCT s2.player)
            FROM def_stats ds1
            JOIN stats s2 ON ds1.team = s2.team AND ds1.season = s2.season
            LEFT JOIN draft d2 ON d2.player = s2.player
            WHERE ds1.player = d.player AND s2.player != d.player
              AND CAST(d2.pro_bowls AS REAL) >= 1
          ) >= 3
        ORDER BY RANDOM() LIMIT 1
        """,
    ).fetchone()
    if not row:
        return None
    raw_pos = row[1] if row[1] else "LB"
    pos = _DEF_DRAFT_NORM.get(raw_pos.split("/")[0].strip(), raw_pos)
    # If pos didn't normalize to a known def position, fall back to LB
    if pos not in _DEF_POS_SET:
        pos = "LB"
    return {"player": row[0], "pos": pos}


def _pick_vintage_player(conn, min_draft_year=None):
    """Non-active Pro Bowl player with at least 3 Pro Bowl teammates."""
    extra = ""
    params = []
    if min_draft_year:
        extra = f"  AND CAST(d.draft_year AS REAL) >= {int(min_draft_year)}\n"
    row = conn.execute(
        f"""
        SELECT d.player, d.pos FROM draft d
        WHERE CAST(d.pro_bowls AS REAL) >= 1
          AND d.player NOT IN (SELECT DISTINCT player FROM stats WHERE season >= 2022)
          AND d.player IN (SELECT DISTINCT player FROM stats)
{extra}          AND (
            SELECT COUNT(DISTINCT s2.player)
            FROM stats s1
            JOIN stats s2 ON s1.team = s2.team AND s1.season = s2.season
            LEFT JOIN draft d2 ON d2.player = s2.player
            WHERE s1.player = d.player AND s2.player != d.player
              AND CAST(d2.pro_bowls AS REAL) >= 1
          ) >= 3
          AND d.pos IN ('QB','RB','WR','TE','FL','HB','FB','E','SE')
        ORDER BY RANDOM() LIMIT 1
        """,
        params,
    ).fetchone()
    if not row:
        return None
    # Normalise old position names to modern ones
    pos_map = {"FL": "WR", "SE": "WR", "E": "TE", "HB": "RB", "FB": "RB"}
    pos = pos_map.get(row[1], row[1])
    return {"player": row[0], "pos": pos}


# ── Teammate chain builders ───────────────────────────────────────────────────

def _build_classic_chain(conn, player, hard_mode=False):
    """One notable teammate per team; pad if needed."""
    teams = conn.execute(
        "SELECT team, MIN(season) FROM stats WHERE player = ? GROUP BY team ORDER BY MIN(season)",
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
        if hard_mode:
            pool = [r[0] for r in conn.execute(
                f"""SELECT player FROM (
                    SELECT player FROM stats WHERE team=? AND season IN ({ph}) AND player!=?
                    UNION
                    SELECT player FROM def_stats WHERE team=? AND season IN ({ph}) AND player!=?
                ) ORDER BY RANDOM() LIMIT 30""",
                [team] + seasons + [player, team] + seasons + [player],
            ).fetchall()]
        else:
            off = [r[0] for r in conn.execute(
                f"""SELECT DISTINCT s.player FROM stats s
                    WHERE s.team = ? AND s.season IN ({ph}) AND s.player != ?
                      AND EXISTS (SELECT 1 FROM stats s2 WHERE s2.player = s.player AND s2.fantasy_ppr >= 50)
                    ORDER BY RANDOM() LIMIT 20""",
                [team] + seasons + [player],
            ).fetchall()]
            dfn = [r[0] for r in conn.execute(
                f"""SELECT DISTINCT ds.player FROM def_stats ds
                    LEFT JOIN draft d ON d.player = ds.player
                    WHERE ds.team = ? AND ds.season IN ({ph}) AND ds.player != ?
                      AND CAST(d.pro_bowls AS REAL) >= 1
                    ORDER BY RANDOM() LIMIT 10""",
                [team] + seasons + [player],
            ).fetchall()]
            pool = off + dfn
        if pool:
            return random.choice(pool)
        row = conn.execute(
            f"SELECT DISTINCT player FROM stats WHERE team=? AND season IN ({ph}) AND player!=? ORDER BY RANDOM() LIMIT 1",
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
        if hard_mode:
            extras = conn.execute(
                """SELECT player FROM (
                   SELECT s2.player AS player FROM stats s1
                   JOIN stats s2 ON s1.team=s2.team AND s1.season=s2.season
                   WHERE s1.player=? AND s2.player!=?
                   UNION
                   SELECT ds.player FROM stats s1
                   JOIN def_stats ds ON s1.team=ds.team AND s1.season=ds.season
                   WHERE s1.player=? AND ds.player!=?
                ) ORDER BY RANDOM() LIMIT 60""",
                (player, player, player, player),
            ).fetchall()
        else:
            off_extras = conn.execute(
                """SELECT DISTINCT s2.player FROM stats s1
                   JOIN stats s2 ON s1.team=s2.team AND s1.season=s2.season
                   WHERE s1.player=? AND s2.player!=?
                     AND EXISTS (SELECT 1 FROM stats s3 WHERE s3.player=s2.player AND s3.fantasy_ppr>=50)
                   ORDER BY RANDOM() LIMIT 40""",
                (player, player),
            ).fetchall()
            dfn_extras = conn.execute(
                """SELECT DISTINCT ds2.player FROM stats s1
                   JOIN def_stats ds2 ON s1.team=ds2.team AND s1.season=ds2.season
                   LEFT JOIN draft d ON d.player=ds2.player
                   WHERE s1.player=? AND ds2.player!=?
                     AND CAST(d.pro_bowls AS REAL) >= 1
                   ORDER BY RANDOM() LIMIT 20""",
                (player, player),
            ).fetchall()
            extras = off_extras + dfn_extras
        pool = [r[0] for r in extras]
        random.shuffle(pool)
        for name in pool:
            if len(clues) >= 5:
                break
            if name not in used:
                used.add(name)
                clues.append({"icon": "🤝", "label": "Teammate", "text": name})

    return clues[:5]


def _build_vintage_chain(conn, player, hard_mode=False):
    """One Pro Bowl teammate (offensive or defensive) per team; pad with more."""
    teams = conn.execute(
        "SELECT team, MIN(season) FROM stats WHERE player = ? GROUP BY team ORDER BY MIN(season)",
        (player,),
    ).fetchall()
    if not teams:
        return []

    used = set()
    clues = []

    def pick_teammate(team):
        seasons = [r[0] for r in conn.execute(
            "SELECT DISTINCT season FROM stats WHERE player = ? AND team = ?",
            (player, team),
        ).fetchall()]
        if not seasons:
            return None
        ph = ",".join("?" * len(seasons))
        if hard_mode:
            pool = [r[0] for r in conn.execute(
                f"""SELECT player FROM (
                    SELECT player FROM stats WHERE team=? AND season IN ({ph}) AND player!=?
                    UNION
                    SELECT player FROM def_stats WHERE team=? AND season IN ({ph}) AND player!=?
                ) ORDER BY RANDOM() LIMIT 30""",
                [team] + seasons + [player, team] + seasons + [player],
            ).fetchall()]
        else:
            off = [r[0] for r in conn.execute(
                f"""SELECT DISTINCT s.player FROM stats s
                    LEFT JOIN draft d ON d.player = s.player
                    WHERE s.team=? AND s.season IN ({ph}) AND s.player!=?
                      AND CAST(d.pro_bowls AS REAL) >= 1
                    ORDER BY CAST(d.pro_bowls AS REAL) DESC, RANDOM() LIMIT 10""",
                [team] + seasons + [player],
            ).fetchall()]
            dfn = [r[0] for r in conn.execute(
                f"""SELECT DISTINCT ds.player FROM def_stats ds
                    LEFT JOIN draft d ON d.player = ds.player
                    WHERE ds.team=? AND ds.season IN ({ph}) AND ds.player!=?
                      AND CAST(d.pro_bowls AS REAL) >= 1
                    ORDER BY CAST(d.pro_bowls AS REAL) DESC, RANDOM() LIMIT 10""",
                [team] + seasons + [player],
            ).fetchall()]
            pool = off + dfn
        return random.choice(pool) if pool else None

    for team, _ in teams:
        if len(clues) >= 5:
            break
        tm = pick_teammate(team)
        if tm and tm not in used:
            used.add(tm)
            clues.append({"icon": "🏆", "label": "Teammate", "text": tm})

    if len(clues) < 5:
        if hard_mode:
            extras = conn.execute(
                """SELECT player FROM (
                   SELECT s2.player AS player FROM stats s1
                   JOIN stats s2 ON s1.team=s2.team AND s1.season=s2.season
                   WHERE s1.player=? AND s2.player!=?
                   UNION
                   SELECT ds.player FROM stats s1
                   JOIN def_stats ds ON s1.team=ds.team AND s1.season=ds.season
                   WHERE s1.player=? AND ds.player!=?
                ) ORDER BY RANDOM() LIMIT 60""",
                (player, player, player, player),
            ).fetchall()
        else:
            off_extras = conn.execute(
                """SELECT DISTINCT s2.player FROM stats s1
                   JOIN stats s2 ON s1.team=s2.team AND s1.season=s2.season
                   LEFT JOIN draft d ON d.player=s2.player
                   WHERE s1.player=? AND s2.player!=?
                     AND CAST(d.pro_bowls AS REAL) >= 1
                   ORDER BY CAST(d.pro_bowls AS REAL) DESC, RANDOM() LIMIT 40""",
                (player, player),
            ).fetchall()
            dfn_extras = conn.execute(
                """SELECT DISTINCT ds2.player FROM stats s1
                   JOIN def_stats ds2 ON s1.team=ds2.team AND s1.season=ds2.season
                   LEFT JOIN draft d ON d.player=ds2.player
                   WHERE s1.player=? AND ds2.player!=?
                     AND CAST(d.pro_bowls AS REAL) >= 1
                   ORDER BY CAST(d.pro_bowls AS REAL) DESC, RANDOM() LIMIT 20""",
                (player, player),
            ).fetchall()
            extras = off_extras + dfn_extras
        pool = [r[0] for r in extras]
        random.shuffle(pool)
        for name in pool:
            if len(clues) >= 5:
                break
            if name not in used:
                used.add(name)
                clues.append({"icon": "🏆", "label": "Teammate", "text": name})

    return clues[:5]


def _build_defense_chain(conn, player, hard_mode=False):
    """Offensive (and optionally defensive) teammates of the mystery defender, one per team."""
    teams = conn.execute(
        "SELECT team, MIN(season) FROM def_stats WHERE player = ? GROUP BY team ORDER BY MIN(season)",
        (player,),
    ).fetchall()
    if not teams:
        return []

    used = set()
    clues = []

    def pick_teammate(team):
        seasons = [r[0] for r in conn.execute(
            "SELECT DISTINCT season FROM def_stats WHERE player = ? AND team = ?",
            (player, team),
        ).fetchall()]
        if not seasons:
            return None
        ph = ",".join("?" * len(seasons))
        if hard_mode:
            pool = [r[0] for r in conn.execute(
                f"""SELECT player FROM (
                    SELECT player FROM stats WHERE team=? AND season IN ({ph}) AND player!=?
                    UNION
                    SELECT player FROM def_stats WHERE team=? AND season IN ({ph}) AND player!=?
                ) ORDER BY RANDOM() LIMIT 30""",
                [team] + seasons + [player, team] + seasons + [player],
            ).fetchall()]
            return random.choice(pool) if pool else None
        # Normal: prefer offensive Pro Bowlers, fall back to any offensive teammate
        row = conn.execute(
            f"""SELECT DISTINCT s.player FROM stats s
                LEFT JOIN draft d ON d.player = s.player
                WHERE s.team=? AND s.season IN ({ph}) AND s.player!=?
                  AND CAST(d.pro_bowls AS REAL) >= 1
                ORDER BY CAST(d.pro_bowls AS REAL) DESC, RANDOM() LIMIT 1""",
            [team] + seasons + [player],
        ).fetchone()
        if row:
            return row[0]
        row = conn.execute(
            f"SELECT DISTINCT player FROM stats WHERE team=? AND season IN ({ph}) AND player!=? ORDER BY RANDOM() LIMIT 1",
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
        if hard_mode:
            extras = conn.execute(
                """SELECT player FROM (
                   SELECT s2.player AS player FROM def_stats ds
                   JOIN stats s2 ON ds.team=s2.team AND ds.season=s2.season
                   WHERE ds.player=? AND s2.player!=?
                   UNION
                   SELECT ds2.player FROM def_stats ds
                   JOIN def_stats ds2 ON ds.team=ds2.team AND ds.season=ds2.season
                   WHERE ds.player=? AND ds2.player!=?
                ) ORDER BY RANDOM() LIMIT 60""",
                (player, player, player, player),
            ).fetchall()
        else:
            extras = conn.execute(
                """SELECT DISTINCT s2.player FROM def_stats ds
                   JOIN stats s2 ON ds.team=s2.team AND ds.season=s2.season
                   LEFT JOIN draft d ON d.player=s2.player
                   WHERE ds.player=? AND s2.player!=?
                     AND CAST(d.pro_bowls AS REAL) >= 1
                   ORDER BY CAST(d.pro_bowls AS REAL) DESC, RANDOM() LIMIT 40""",
                (player, player),
            ).fetchall()
            if len(extras) < 5:
                extras += conn.execute(
                    """SELECT DISTINCT s2.player FROM def_stats ds
                       JOIN stats s2 ON ds.team=s2.team AND ds.season=s2.season
                       WHERE ds.player=? AND s2.player!=?
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
    is_def = pos in _DEF_POS_SET

    hints.append({"icon": "🏈", "label": "Position", "text": f"Plays {pos}"})

    season_table = "def_stats" if is_def else "stats"
    row = conn.execute(
        f"SELECT COUNT(DISTINCT season) FROM {season_table} WHERE player = ?", (player,)
    ).fetchone()
    seasons = int(row[0]) if row else 1
    hints.append({
        "icon": "📅", "label": "Experience",
        "text": f"{seasons} season{'s' if seasons != 1 else ''} of NFL experience",
    })

    draft = conn.execute(
        "SELECT college, draft_round, draft_year, all_pro, pro_bowls FROM draft WHERE player = ? LIMIT 1",
        (player,),
    ).fetchone()

    if draft and draft[0]:
        hints.append({"icon": "🎓", "label": "College", "text": f"Attended {draft[0]}"})
    else:
        hints.append({"icon": "🎓", "label": "College", "text": "College not on record"})

    if draft and draft[1] is not None and draft[2] is not None:
        rnd = int(float(draft[1]))
        yr  = int(float(draft[2]))
        sfx = {1: "st", 2: "nd", 3: "rd"}.get(rnd, "th")
        hints.append({"icon": "📋", "label": "Draft", "text": f"{rnd}{sfx}-round pick, {yr} NFL Draft"})
    else:
        hints.append({"icon": "📋", "label": "Draft", "text": "Undrafted or draft data not on record"})

    stat_text = None
    if is_def:
        if pos in ("DE", "DT", "LB"):
            try:
                row = conn.execute(
                    "SELECT MAX(CAST(sacks AS REAL)) FROM def_stats WHERE player = ?", (player,)
                ).fetchone()
                if row and row[0] and float(row[0]) >= 1:
                    stat_text = f"{int(float(row[0]))}+ sacks in a single season"
            except Exception:
                pass
        if not stat_text and pos in ("CB", "S", "LB"):
            try:
                row = conn.execute(
                    "SELECT MAX(CAST(interceptions AS REAL)) FROM def_stats WHERE player = ?", (player,)
                ).fetchone()
                if row and row[0] and float(row[0]) >= 1:
                    stat_text = f"{int(float(row[0]))}+ interceptions in a single season"
            except Exception:
                pass
    else:
        col   = {"QB": "pass_yds", "RB": "rush_yds"}.get(pos, "rec_yds")
        label = {"QB": "passing yards", "RB": "rushing yards"}.get(pos, "receiving yards")
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

def start_game(conn, mode="classic", include_defense=False, hard_mode=False, min_draft_year=None):
    use_defense = include_defense and random.random() < 0.5

    if mode == "vintage":
        if use_defense:
            p = _pick_defense_player(conn, min_draft_year=min_draft_year)
            chain_fn = lambda c, pl: _build_defense_chain(c, pl, hard_mode=hard_mode)
        else:
            p = _pick_vintage_player(conn, min_draft_year=min_draft_year)
            chain_fn = lambda c, pl: _build_vintage_chain(c, pl, hard_mode=hard_mode)
    else:
        if use_defense:
            p = _pick_defense_player(conn, min_draft_year=min_draft_year)
            chain_fn = lambda c, pl: _build_defense_chain(c, pl, hard_mode=hard_mode)
        else:
            p = _pick_classic_player(conn, min_draft_year=min_draft_year)
            chain_fn = lambda c, pl: _build_classic_chain(c, pl, hard_mode=hard_mode)

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
