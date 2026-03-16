from flask import Flask, jsonify, request, render_template
import sqlite3
import os
from load_data import build_db
from questions import QUESTIONS

app = Flask(__name__)
DB_PATH = "fantasy.db"

# --- Point this at your data folders ---
DATA_FOLDERS = [
    "/Users/orionhoch/fantasy_stats/QB_Fantasy",
    "/Users/orionhoch/fantasy_stats/WR_Fantasy",
    "/Users/orionhoch/fantasy_stats/TE_Fantasy",
    "/Users/orionhoch/fantasy_stats/RB_Fantasy",
]


def get_db():
    return sqlite3.connect(DB_PATH)


@app.route("/")
def index():
    return render_template("index.html", questions=QUESTIONS)


@app.route("/api/question/<int:qid>/answers")
def get_answers(qid):
    question = next((q for q in QUESTIONS if q["id"] == qid), None)
    if not question:
        return jsonify({"error": "Not found"}), 404
    conn = get_db()
    rows = conn.execute(question["query"]).fetchall()
    conn.close()
    return jsonify({"answers": [r[0] for r in rows], "count": len(rows)})


@app.route("/api/search")
def search():
    term = request.args.get("q", "").strip()
    qid = request.args.get("qid", type=int)
    if not term or not qid:
        return jsonify({"results": []})

    question = next((q for q in QUESTIONS if q["id"] == qid), None)
    if not question:
        return jsonify({"results": []})

    conn = get_db()
    # Get valid answer set for this question
    valid = {r[0] for r in conn.execute(question["query"]).fetchall()}
    # Search all players matching the term
    rows = conn.execute(
        "SELECT DISTINCT player FROM stats WHERE player LIKE ? ORDER BY player LIMIT 20",
        (f"%{term}%",)
    ).fetchall()
    conn.close()

    results = [
        {"name": r[0], "valid": r[0] in valid}
        for r in rows
    ]
    return jsonify({"results": results})


@app.route("/starting6")
def starting6():
    return render_template("starting6.html")


@app.route("/api/starting6/random-team")
def random_team():
    conn = get_db()
    row = conn.execute(
        "SELECT team FROM stats WHERE team IS NOT NULL AND team != '' ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    conn.close()
    return jsonify({"team": row[0] if row else None})


@app.route("/api/starting6/years")
def starting6_years():
    player = request.args.get("player", "").strip()
    team = request.args.get("team", "").strip()
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT season FROM stats WHERE player = ? AND team = ? AND fantasy_ppr IS NOT NULL ORDER BY season DESC",
        (player, team),
    ).fetchall()
    conn.close()
    return jsonify({"years": [r[0] for r in rows]})


@app.route("/api/starting6/search")
def starting6_search():
    term = request.args.get("q", "").strip()
    if not term:
        return jsonify({"results": []})
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT player FROM stats WHERE player LIKE ? ORDER BY player LIMIT 20",
        (f"%{term}%",),
    ).fetchall()
    conn.close()
    return jsonify({"results": [r[0] for r in rows]})


@app.route("/api/starting6/validate")
def starting6_validate():
    player = request.args.get("player", "").strip()
    team = request.args.get("team", "").strip()
    season = request.args.get("season", "").strip()
    conn = get_db()
    if season:
        row = conn.execute(
            "SELECT player, pos, fantasy_ppr, season, team FROM stats WHERE player = ? AND team = ? AND season = ?",
            (player, team, int(season)),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT player, pos, fantasy_ppr, season, team FROM stats
               WHERE player = ? AND team = ? AND fantasy_ppr IS NOT NULL
               ORDER BY fantasy_ppr DESC LIMIT 1""",
            (player, team),
        ).fetchone()
    conn.close()
    if row:
        return jsonify({"valid": True, "player": row[0], "pos": row[1], "ppr": row[2], "season": row[3], "team": row[4]})
    return jsonify({"valid": False})


@app.route("/api/starting6/players")
def get_team_players():
    team = request.args.get("team", "")
    positions = request.args.getlist("pos")
    conn = get_db()
    if positions:
        placeholders = ",".join("?" * len(positions))
        rows = conn.execute(
            f"""SELECT player, season, pos, fantasy_ppr, team
                FROM stats
                WHERE team = ? AND pos IN ({placeholders}) AND fantasy_ppr IS NOT NULL
                ORDER BY fantasy_ppr DESC""",
            [team] + positions,
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT player, season, pos, fantasy_ppr, team
               FROM stats WHERE team = ? AND fantasy_ppr IS NOT NULL
               ORDER BY fantasy_ppr DESC""",
            (team,),
        ).fetchall()
    conn.close()
    return jsonify({"players": [
        {"player": r[0], "season": r[1], "pos": r[2], "ppr": r[3], "team": r[4]}
        for r in rows
    ]})


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("Building database...")
        build_db(DATA_FOLDERS, DB_PATH)
    else:
        print("Database already exists, skipping load. Delete fantasy.db to reload.")
    app.run(debug=True)
