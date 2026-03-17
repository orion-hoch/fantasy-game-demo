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
    """
    Return up to 5 distinct teammate clues.
    One teammate is drawn from each team the player has played for (oldest team
    first). If the player has fewer than 5 teams, remaining slots are filled
    with extra teammates from any team.
    Prefers recognisable teammates (PPR >= 50 in any season).
    """
    # Distinct teams in career order (first season on each team)
    teams = conn.execute(
        "SELECT team, MIN(season) AS first FROM stats WHERE player = ? GROUP BY team ORDER BY first",
        (player,),
    ).fetchall()

    if not teams:
        return []

    clues = []
    used = set()

    def pick_teammate(team):
        # Only from seasons the mystery player was actually on this team
        seasons = [r[0] for r in conn.execute(
            "SELECT DISTINCT season FROM stats WHERE player = ? AND team = ?",
            (player, team),
        ).fetchall()]
        if not seasons:
            return None
        ph = ",".join("?" * len(seasons))
        # Prefer recognisable teammate (PPR >= 50 in any season)
        row = conn.execute(
            f"""
            SELECT DISTINCT s.player FROM stats s
            WHERE s.team = ? AND s.season IN ({ph}) AND s.player != ?
              AND EXISTS (SELECT 1 FROM stats s2 WHERE s2.player = s.player AND s2.fantasy_ppr >= 50)
            ORDER BY RANDOM() LIMIT 1
            """,
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
        tm = pick_teammate(team)
        if tm and tm not in used:
            used.add(tm)
            clues.append({"icon": "🤝", "label": "Teammate", "text": tm})

    # Fill remaining slots from any overlapping season
    if len(clues) < 5:
        extras = conn.execute(
            """
            SELECT DISTINCT s2.player
            FROM stats s1
            JOIN stats s2 ON s1.team = s2.team AND s1.season = s2.season
            WHERE s1.player = ? AND s2.player != ?
              AND EXISTS (SELECT 1 FROM stats s3 WHERE s3.player = s2.player AND s3.fantasy_ppr >= 50)
            ORDER BY RANDOM() LIMIT 40
            """,
            (player, player),
        ).fetchall()
        for row in extras:
            if len(clues) >= 5:
                break
            if row[0] not in used:
                used.add(row[0])
                clues.append({"icon": "🤝", "label": "Teammate", "text": row[0]})

    return clues[:5]


# ── Public API ────────────────────────────────────────────────────────────────

def start_game(conn):
    p = _pick_active_player(conn)
    if not p:
        return None, []
    player, pos = p["player"], p["pos"]
    clues = _build_teammate_chain(conn, player)
    if not clues:
        return None, []
    gid = str(uuid.uuid4())
    _games[gid] = {
        "player": player,
        "pos": pos,
        "clues": clues,
        "revealed": 1,
        "wrong": 0,
        "over": False,
    }
    return gid, [clues[0]]


def check_guess(game_id, guess):
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
