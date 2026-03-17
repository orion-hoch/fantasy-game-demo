from flask import Flask, jsonify, request, render_template
import sqlite3
import os
from load_data import build_db, load_total_stats
import chain_categories as cc

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fantasy.db")

DATA_FOLDERS = [
    os.path.join(BASE_DIR, "fantasy_stats", "QB_Fantasy"),
    os.path.join(BASE_DIR, "fantasy_stats", "WR_Fantasy"),
    os.path.join(BASE_DIR, "fantasy_stats", "TE_Fantasy"),
    os.path.join(BASE_DIR, "fantasy_stats", "RB_Fantasy"),
]


def get_db():
    return sqlite3.connect(DB_PATH)


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


# ── Existing routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


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


# ── Chain Game routes ─────────────────────────────────────────────────────────

@app.route("/chain")
def chain_game():
    return render_template("chain.html")


@app.route("/api/chain/start", methods=["POST"])
def chain_start():
    conn = get_db()
    cat = cc.get_start_category(conn)
    conn.close()
    if not cat:
        return jsonify({"error": "Could not find a starting category"}), 500
    return jsonify({"category": cat, "valid_count": cat["valid_count"]})


@app.route("/api/chain/guess", methods=["POST"])
def chain_guess():
    data = request.get_json(force=True)
    player_guess = (data.get("player") or "").strip()
    chain = data.get("chain", [])  # list of {id, value}

    if not player_guess or not chain:
        return jsonify({"error": "Missing player or chain"}), 400

    used_players = set(data.get("used_players", []))

    conn = get_db()
    valid_players = cc.get_players_for_chain(conn, chain) - used_players
    correct = player_guess in valid_players
    chain_length = len(chain)

    if correct:
        remaining = valid_players - {player_guess}
        exclude_ids = [link["id"] for link in chain]
        next_cat = None
        last_player = None

        if len(remaining) == 1:
            # Last player standing — return who they are for the bonus chain
            last_player = next(iter(remaining))
        elif len(remaining) >= 2:
            next_cat = cc.get_chain_category(conn, remaining, exclude_ids=exclude_ids)

        conn.close()
        return jsonify({
            "correct": True,
            "valid_count": len(remaining),
            "next_category": next_cat,
            "chain_length": chain_length,
            "last_player": last_player,
            "examples": [],
        })
    else:
        link_results = cc.check_player_against_chain(conn, player_guess, chain)
        examples = sorted(list(valid_players))[:3]
        conn.close()
        return jsonify({
            "correct": False,
            "valid_count": len(valid_players),
            "next_category": None,
            "chain_length": chain_length,
            "examples": examples,
            "link_results": link_results,
        })


@app.route("/api/chain/teammate_start", methods=["POST"])
def chain_teammate_start():
    data = request.get_json(force=True)
    player = (data.get("player") or "").strip()
    if not player:
        return jsonify({"error": "Missing player"}), 400
    conn = get_db()
    cat = cc.get_teammate_category(conn, player)
    conn.close()
    if not cat:
        return jsonify({"error": f"No teammates found for {player}"}), 404
    return jsonify({"category": cat, "valid_count": cat["valid_count"]})


@app.route("/api/chain/search")
def chain_search():
    term = request.args.get("q", "").strip()
    if not term:
        return jsonify({"results": []})
    conn = get_db()
    names = cc.search_players(conn, term)
    conn.close()
    return jsonify({"results": [{"name": n} for n in names]})


# ── Startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("Building database...")
        build_db(DATA_FOLDERS, DB_PATH)
    else:
        print("Database already exists, skipping fantasy stats load.")

    # Load total_stats tables if they don't exist yet
    _conn = get_db()
    _needs_load = not _table_exists(_conn, "season_stats") or not _table_exists(_conn, "draft")
    _conn.close()
    if _needs_load:
        print("Loading total_stats tables...")
        load_total_stats(BASE_DIR, DB_PATH)
    else:
        print("season_stats and draft tables already exist.")

    app.run(debug=True)
