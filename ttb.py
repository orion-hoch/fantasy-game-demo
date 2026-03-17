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
    Return up to 5 distinct teammate clues, spread across the player's career
    (oldest first → newest last, closest to the bomb).
    Prefers teammates who are recognisable (have decent PPR stats themselves).
    """
    # All (season, team) pairs for this player, oldest first
    seasons = conn.execute(
        "SELECT DISTINCT season, team FROM stats WHERE player = ? ORDER BY season",
        (player,),
    ).fetchall()

    if not seasons:
        return []

    # Pick up to 5 evenly-spread season slots
    n = len(seasons)
    if n <= 5:
        slots = seasons
    else:
        indices = [int(round(i * (n - 1) / 4)) for i in range(5)]
        slots = [seasons[i] for i in indices]

    clues = []
    used = set()

    for season, team in slots:
        if len(clues) >= 5:
            break
        # Try to pick a recognisable teammate (PPR >= 50 in any season) first
        row = conn.execute(
            """
            SELECT DISTINCT s.player
            FROM stats s
            WHERE s.team = ? AND s.season = ? AND s.player != ?
              AND s.player NOT IN (SELECT value FROM (
                    SELECT player AS value FROM stats
                    WHERE player = ?
              ))
              AND EXISTS (
                    SELECT 1 FROM stats s2
                    WHERE s2.player = s.player AND s2.fantasy_ppr >= 50
              )
            ORDER BY RANDOM() LIMIT 1
            """,
            (team, season, player, player),
        ).fetchone()

        if not row:
            # Fallback: any teammate
            row = conn.execute(
                "SELECT DISTINCT player FROM stats WHERE team = ? AND season = ? AND player != ? ORDER BY RANDOM() LIMIT 1",
                (team, season, player),
            ).fetchone()

        if row and row[0] not in used:
            used.add(row[0])
            clues.append({
                "icon": "🤝",
                "label": f"{season} Teammate",
                "text": row[0],
            })

    # Pad to 5 if still short
    if len(clues) < 5:
        extras = conn.execute(
            """
            SELECT DISTINCT s2.player
            FROM stats s1
            JOIN stats s2 ON s1.team = s2.team AND s1.season = s2.season
            WHERE s1.player = ? AND s2.player != ?
            ORDER BY RANDOM() LIMIT 30
            """,
            (player, player),
        ).fetchall()
        for row in extras:
            if len(clues) >= 5:
                break
            if row[0] not in used:
                used.add(row[0])
                clues.append({
                    "icon": "🤝",
                    "label": "Teammate",
                    "text": row[0],
                })

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
