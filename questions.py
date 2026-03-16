QUESTIONS = [
    {
        "id": 1,
        "title": "300+ PPR Points — Any Season",
        "description": "Name a player who scored 300 or more PPR fantasy points in a single season.",
        "query": "SELECT DISTINCT player FROM stats WHERE fantasy_ppr >= 300 ORDER BY player",
    },
    {
        "id": 2,
        "title": "400+ PPR Points — QB",
        "description": "Name a QB who scored 400 or more PPR fantasy points in a single season.",
        "query": "SELECT DISTINCT player FROM stats WHERE fantasy_ppr >= 400 AND pos = 'QB' ORDER BY player",
    },
    {
        "id": 3,
        "title": "200+ PPR Points — TE",
        "description": "Name a Tight End who scored 200 or more PPR fantasy points in a single season.",
        "query": "SELECT DISTINCT player FROM stats WHERE fantasy_ppr >= 200 AND pos = 'TE' ORDER BY player",
    },
    {
        "id": 4,
        "title": "250+ PPR Points — WR",
        "description": "Name a Wide Receiver who scored 250 or more PPR fantasy points in a single season.",
        "query": "SELECT DISTINCT player FROM stats WHERE fantasy_ppr >= 250 AND pos = 'WR' ORDER BY player",
    },
    {
        "id": 5,
        "title": "20+ PPR Per Game",
        "description": "Name a player who averaged 20 or more PPR fantasy points per game in a season (min 8 games).",
        "query": "SELECT DISTINCT player FROM stats WHERE ppr_per_game >= 20 AND games >= 8 ORDER BY player",
    },
    {
        "id": 6,
        "title": "Multi-Season 300+ PPR",
        "description": "Name a player who scored 300+ PPR fantasy points in more than one season.",
        "query": """
            SELECT player FROM stats WHERE fantasy_ppr >= 300
            GROUP BY player HAVING COUNT(*) > 1 ORDER BY player
        """,
    },
]
