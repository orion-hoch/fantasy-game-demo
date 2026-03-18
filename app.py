from flask import Flask, jsonify, request, render_template
import sqlite3
import os
from load_data import repair_db_text
import chain_categories as cc
import ttb as ttb_mod
import nba_chain_categories as nba_cc
import nba_ttb as nba_ttb_mod
import dungeon_adventure as da
import nba_dungeon_adventure as nba_da

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fantasy.db")

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


@app.route("/dungeon_adventure")
def dungeon_adventure_page():
    return render_template(
        "dungeon_adventure.html",
        page_title="Dungeon Adventure",
        game_title="Dungeon Adventure",
        sport_label="NFL",
        api_prefix="/api/dungeon",
    )


@app.route("/nba_dungeon_adventure")
def nba_dungeon_adventure_page():
    return render_template(
        "dungeon_adventure.html",
        page_title="NBA Dungeon Adventure",
        game_title="NBA Dungeon Adventure",
        sport_label="NBA",
        api_prefix="/api/nba_dungeon",
    )


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


@app.route("/api/dungeon/rewards", methods=["POST"])
def dungeon_rewards():
    data = request.get_json(force=True) or {}
    floor = max(1, int(data.get("floor", 1)))
    items = data.get("items", [])
    conn = get_db()
    rewards = da.get_reward_options(conn, floor, items)
    conn.close()
    return jsonify({"rewards": rewards})


@app.route("/api/dungeon/encounter", methods=["POST"])
def dungeon_encounter():
    data = request.get_json(force=True) or {}
    floor = max(1, int(data.get("floor", 1)))
    items = data.get("items", [])
    used_questions = data.get("used_questions", [])
    conn = get_db()
    encounter = da.get_encounter(conn, floor, items, used_questions=used_questions)
    conn.close()
    if not encounter:
        return jsonify({"error": "Could not build an encounter"}), 500
    return jsonify(encounter)


@app.route("/api/dungeon/answer", methods=["POST"])
def dungeon_answer():
    data = request.get_json(force=True) or {}
    question = data.get("question") or {}
    items = data.get("items", [])
    answer = (data.get("answer") or "").strip()
    if not answer:
        return jsonify({"error": "Missing answer"}), 400
    conn = get_db()
    result = da.check_answer(conn, question, items, answer)
    conn.close()
    return jsonify(result)


@app.route("/api/dungeon/search", methods=["POST"])
def dungeon_search():
    data = request.get_json(force=True) or {}
    query = (data.get("query") or "").strip()
    items = data.get("items", [])
    question = data.get("question")
    if not query:
        return jsonify({"results": []})
    conn = get_db()
    results = da.search_answers(conn, query, items, question=question)
    conn.close()
    return jsonify({"results": results})


@app.route("/api/nba_dungeon/rewards", methods=["POST"])
def nba_dungeon_rewards():
    data = request.get_json(force=True) or {}
    floor = max(1, int(data.get("floor", 1)))
    items = data.get("items", [])
    conn = get_db()
    rewards = nba_da.get_reward_options(conn, floor, items)
    conn.close()
    return jsonify({"rewards": rewards})


@app.route("/api/nba_dungeon/encounter", methods=["POST"])
def nba_dungeon_encounter():
    data = request.get_json(force=True) or {}
    floor = max(1, int(data.get("floor", 1)))
    items = data.get("items", [])
    used_questions = data.get("used_questions", [])
    conn = get_db()
    encounter = nba_da.get_encounter(conn, floor, items, used_questions=used_questions)
    conn.close()
    if not encounter:
        return jsonify({"error": "Could not build an encounter"}), 500
    return jsonify(encounter)


@app.route("/api/nba_dungeon/answer", methods=["POST"])
def nba_dungeon_answer():
    data = request.get_json(force=True) or {}
    question = data.get("question") or {}
    items = data.get("items", [])
    answer = (data.get("answer") or "").strip()
    if not answer:
        return jsonify({"error": "Missing answer"}), 400
    conn = get_db()
    result = nba_da.check_answer(conn, question, items, answer)
    conn.close()
    return jsonify(result)


@app.route("/api/nba_dungeon/search", methods=["POST"])
def nba_dungeon_search():
    data = request.get_json(force=True) or {}
    query = (data.get("query") or "").strip()
    items = data.get("items", [])
    question = data.get("question")
    if not query:
        return jsonify({"results": []})
    conn = get_db()
    results = nba_da.search_answers(conn, query, items, question=question)
    conn.close()
    return jsonify({"results": results})


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


# ── Ticking Time Bomb routes ─────────────────────────────────────────────────

@app.route("/ttb")
def ttb_page():
    return render_template("ttb.html")


@app.route("/api/ttb/start", methods=["POST"])
def ttb_start():
    ttb_mod.cleanup_old_games()
    data = request.get_json(force=True) or {}
    mode = data.get("mode", "classic")
    include_defense = bool(data.get("include_defense", False))
    hard_mode = bool(data.get("hard_mode", False))
    min_draft_year = data.get("min_draft_year") or None
    if min_draft_year:
        min_draft_year = int(min_draft_year)
    conn = get_db()
    gid, clues, hints = ttb_mod.start_game(conn, mode=mode, include_defense=include_defense, hard_mode=hard_mode, min_draft_year=min_draft_year)
    conn.close()
    if not gid:
        return jsonify({"error": "Could not load a player"}), 500
    return jsonify({"game_id": gid, "clues": clues, "hints": hints})


@app.route("/api/ttb/guess", methods=["POST"])
def ttb_guess():
    data = request.get_json(force=True)
    gid = (data.get("game_id") or "").strip()
    guess = (data.get("guess") or "").strip()
    reveal = bool(data.get("reveal", False))
    skip   = bool(data.get("skip",   False))

    if not gid:
        return jsonify({"error": "Missing game_id"}), 400

    if reveal:
        return jsonify(ttb_mod.reveal_answer(gid))

    if not skip and not guess:
        return jsonify({"error": "Missing guess"}), 400

    return jsonify(ttb_mod.check_guess(gid, guess, skip=skip))


@app.route("/api/ttb/search")
def ttb_search():
    term = request.args.get("q", "").strip()
    if not term:
        return jsonify({"results": []})
    conn = get_db()
    names = cc.search_players(conn, term)
    conn.close()
    return jsonify({"results": [{"name": n} for n in names]})


# ── Startup ───────────────────────────────────────────────────────────────────

@app.route("/nba_chain")
def nba_chain_game():
    return render_template("nba_chain.html")


@app.route("/nba_ttb")
def nba_ttb_page():
    return render_template("nba_ttb.html")


@app.route("/nba_starting5")
def nba_starting5_page():
    return render_template("nba_starting5.html")


# ── NBA Chain Game routes ─────────────────────────────────────────────────────

@app.route("/api/nba_chain/start", methods=["POST"])
def nba_chain_start():
    conn = get_db()
    cat = nba_cc.get_start_category(conn)
    conn.close()
    if not cat:
        return jsonify({"error": "Could not find a starting category"}), 500
    return jsonify({"category": cat, "valid_count": cat["valid_count"]})


@app.route("/api/nba_chain/guess", methods=["POST"])
def nba_chain_guess():
    data = request.get_json(force=True)
    player_guess = (data.get("player") or "").strip()
    chain = data.get("chain", [])

    if not player_guess or not chain:
        return jsonify({"error": "Missing player or chain"}), 400

    used_players = set(data.get("used_players", []))

    conn = get_db()
    valid_players = nba_cc.get_players_for_chain(conn, chain) - used_players
    correct = player_guess in valid_players
    chain_length = len(chain)

    if correct:
        remaining = valid_players - {player_guess}
        exclude_ids = [link["id"] for link in chain]
        next_cat = None
        last_player = None

        if len(remaining) == 1:
            last_player = next(iter(remaining))
        elif len(remaining) >= 2:
            next_cat = nba_cc.get_chain_category(conn, remaining, exclude_ids=exclude_ids)

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
        link_results = nba_cc.check_player_against_chain(conn, player_guess, chain)
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


@app.route("/api/nba_chain/teammate_start", methods=["POST"])
def nba_chain_teammate_start():
    data = request.get_json(force=True)
    player = (data.get("player") or "").strip()
    if not player:
        return jsonify({"error": "Missing player"}), 400
    conn = get_db()
    cat = nba_cc.get_teammate_category(conn, player)
    conn.close()
    if not cat:
        return jsonify({"error": f"No teammates found for {player}"}), 404
    return jsonify({"category": cat, "valid_count": cat["valid_count"]})


@app.route("/api/nba_chain/search")
def nba_chain_search():
    term = request.args.get("q", "").strip()
    if not term:
        return jsonify({"results": []})
    conn = get_db()
    names = nba_cc.search_players(conn, term)
    conn.close()
    return jsonify({"results": [{"name": n} for n in names]})


# ── NBA TTB routes ────────────────────────────────────────────────────────────

@app.route("/api/nba_ttb/start", methods=["POST"])
def nba_ttb_start():
    nba_ttb_mod.cleanup_old_games()
    data = request.get_json(force=True) or {}
    mode = data.get("mode", "classic")
    conn = get_db()
    gid, clues, hints = nba_ttb_mod.start_game(conn, mode=mode)
    conn.close()
    if not gid:
        return jsonify({"error": "Could not load a player"}), 500
    return jsonify({"game_id": gid, "clues": clues, "hints": hints})


@app.route("/api/nba_ttb/guess", methods=["POST"])
def nba_ttb_guess():
    data = request.get_json(force=True)
    gid = (data.get("game_id") or "").strip()
    guess = (data.get("guess") or "").strip()
    reveal = bool(data.get("reveal", False))
    skip   = bool(data.get("skip",   False))

    if not gid:
        return jsonify({"error": "Missing game_id"}), 400

    if reveal:
        return jsonify(nba_ttb_mod.reveal_answer(gid))

    if not skip and not guess:
        return jsonify({"error": "Missing guess"}), 400

    return jsonify(nba_ttb_mod.check_guess(gid, guess, skip=skip))


@app.route("/api/nba_ttb/search")
def nba_ttb_search():
    term = request.args.get("q", "").strip()
    if not term:
        return jsonify({"results": []})
    conn = get_db()
    names = nba_cc.search_players(conn, term)
    conn.close()
    return jsonify({"results": [{"name": n} for n in names]})


# ── NBA Starting 5 routes ─────────────────────────────────────────────────────

@app.route("/api/nba_starting5/random-team")
def nba_random_team():
    conn = get_db()
    row = conn.execute(
        "SELECT team FROM nba_stats WHERE team IS NOT NULL AND team != '' ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    conn.close()
    return jsonify({"team": row[0] if row else None})


@app.route("/api/nba_starting5/search")
def nba_starting5_search():
    term = request.args.get("q", "").strip()
    if not term:
        return jsonify({"results": []})
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT player FROM nba_stats WHERE player LIKE ? ORDER BY player LIMIT 20",
        (f"%{term}%",),
    ).fetchall()
    conn.close()
    return jsonify({"results": [r[0] for r in rows]})


@app.route("/api/nba_starting5/years")
def nba_starting5_years():
    player = request.args.get("player", "").strip()
    team = request.args.get("team", "").strip()
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT season FROM nba_stats WHERE player = ? AND team = ? AND fantasy_score IS NOT NULL ORDER BY season DESC",
        (player, team),
    ).fetchall()
    conn.close()
    return jsonify({"years": [r[0] for r in rows]})


@app.route("/api/nba_starting5/validate")
def nba_starting5_validate():
    player = request.args.get("player", "").strip()
    team = request.args.get("team", "").strip()
    season = request.args.get("season", "").strip()
    conn = get_db()
    if season:
        row = conn.execute(
            "SELECT player, pos, fantasy_score, season, team FROM nba_stats WHERE player = ? AND team = ? AND season = ?",
            (player, team, int(season)),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT player, pos, fantasy_score, season, team FROM nba_stats
               WHERE player = ? AND team = ? AND fantasy_score IS NOT NULL
               ORDER BY fantasy_score DESC LIMIT 1""",
            (player, team),
        ).fetchone()
    conn.close()
    if row:
        return jsonify({"valid": True, "player": row[0], "pos": row[1], "ppr": row[2], "season": row[3], "team": row[4]})
    return jsonify({"valid": False})


@app.route("/api/nba_starting5/players")
def nba_get_team_players():
    team = request.args.get("team", "")
    positions = request.args.getlist("pos")
    conn = get_db()
    if positions:
        placeholders = ",".join("?" * len(positions))
        rows = conn.execute(
            f"""SELECT player, season, pos, fantasy_score, team
                FROM nba_stats
                WHERE team = ? AND pos IN ({placeholders}) AND fantasy_score IS NOT NULL
                ORDER BY fantasy_score DESC""",
            [team] + positions,
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT player, season, pos, fantasy_score, team
               FROM nba_stats WHERE team = ? AND fantasy_score IS NOT NULL
               ORDER BY fantasy_score DESC""",
            (team,),
        ).fetchall()
    conn.close()
    return jsonify({"players": [
        {"player": r[0], "season": r[1], "pos": r[2], "ppr": r[3], "team": r[4]}
        for r in rows
    ]})


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Missing consolidated database at {DB_PATH}. Restore or recreate fantasy.db before starting the app."
        )

    print("Repairing text encoding issues...")
    repair_db_text(DB_PATH)

    app.run(debug=True)
