from flask import Flask, jsonify, request, redirect, render_template
import sqlite3
import os
import urllib.parse
from load_data import repair_db_text
import chain_categories as cc
import ttb as ttb_mod
import nba_chain_categories as nba_cc
import nba_ttb as nba_ttb_mod
import dungeon_adventure as da
import nba_dungeon_adventure as nba_da
import nfl_balatro as nb
import nba_balatro as nba_b
import nba_bullseye as nba_bull
import nfl_bullseye as nfl_bull
import chain_game as chain_game_mod
import starting6_game as starting6_game_mod
import nba_starting5_game as nba_starting5_game_mod
import codewords_game as codewords_mod
from lobby_store import (
    SUPPORTED_GAMES,
    claim_seat,
    create_room,
    get_room,
    has_token,
    leave_seat,
    occupied_seats,
    reset_to_lobby,
    room_payload,
    save_room,
    set_started,
    update_seat_meta,
)

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fantasy.db")

MIGRATED_FRONTEND_ROUTES = {
    "nfl_bullseye": "/games/nfl/bullseye",
    "nba_bullseye": "/games/nba/bullseye",
    "starting6": "/games/nfl/fantasy-duel",
    "nba_starting5": "/games/nba/fantasy-duel",
    "chain_coop": "/games/nfl/chain",
    "chain_comp": "/games/nfl/chain",
    "nba_chain_coop": "/games/nba/chain",
    "nba_chain_comp": "/games/nba/chain",
    "nfl_codewords": "/games/nfl/codewords",
    "nba_codewords": "/games/nba/codewords",
}


def _request_json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _frontend_base_url() -> str:
    configured = os.getenv("FRONTEND_BASE_URL", "").rstrip("/")
    if configured:
        return configured
    host = (request.host or "").split(":", 1)[0].lower()
    if host in {"127.0.0.1", "localhost"}:
        return "http://127.0.0.1:5173"
    return ""


def _frontend_url(path: str, query: dict | None = None) -> str:
    query = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
    base = _frontend_base_url()
    qs = urllib.parse.urlencode(query, doseq=True)
    return f"{base}{path}{f'?{qs}' if qs else ''}"


def _redirect_frontend(path: str, preserve_query: bool = False, extra_query: dict | None = None, code: int = 302):
    query = dict(request.args) if preserve_query else {}
    if extra_query:
        query.update(extra_query)
    target = _frontend_url(path, query)
    current_query = urllib.parse.urlencode(dict(request.args), doseq=True)
    current_target = f"{request.path}{f'?{current_query}' if current_query else ''}"
    if not _frontend_base_url() and target == current_target:
        return "FRONTEND_BASE_URL is not configured for redirect cutover", 503
    return redirect(target, code=code)


def _build_room_redirect(room_id: str, game_type: str) -> str:
    route = MIGRATED_FRONTEND_ROUTES.get(game_type, SUPPORTED_GAMES[game_type]["route"])
    return _frontend_url(route, {"room_id": room_id})


def _room_game_state(room: dict):
    game_type = room["game_type"]
    game_id = room.get("game_id")
    if not game_id:
        return None
    if game_type == "nfl_bullseye":
        return nfl_bull.get_game(game_id)
    if game_type == "nba_bullseye":
        return nba_bull.get_game(game_id)
    if game_type == "starting6":
        return starting6_game_mod.get_game(game_id)
    if game_type == "nba_starting5":
        return nba_starting5_game_mod.get_game(game_id)
    if game_type in {"chain_coop", "chain_comp", "nba_chain_coop", "nba_chain_comp"}:
        return chain_game_mod.get_game(game_id)
    if game_type in {"nfl_codewords", "nba_codewords"}:
        return codewords_mod.get_game(game_id)
    return None

def get_db():
    return sqlite3.connect(DB_PATH)

# Historical NBA team code → modern franchise code
_NBA_HIST_TO_MODERN = {
    "NJN": "BRK", "SEA": "OKC", "NOH": "NOP", "NOK": "NOP",
    "CHH": "CHA", "CHO": "CHA", "VAN": "MEM", "WSB": "WAS",
    "NOJ": "UTA", "KCK": "SAC", "KCO": "SAC", "FTW": "DET",
    "SDC": "LAC", "SDR": "HOU", "PHW": "GSW", "SFW": "GSW",
    "MLH": "ATL", "STL": "ATL", "CAP": "WAS", "INO": "IND",
    "WSC": "WAS", "MNL": "LAL", "ROC": "SAC", "CIN": "SAC",
    "TRI": "ATL", "SYR": "PHI", "BUF": "LAC", "BAL": "WAS",
    "CHP": "WAS", "CHZ": "WAS",
}
# Build reverse: modern code → all equivalent codes (modern + historical)
_NBA_TEAM_EQUIV: dict[str, list[str]] = {}
for _hist, _mod in _NBA_HIST_TO_MODERN.items():
    _NBA_TEAM_EQUIV.setdefault(_mod, [_mod]).append(_hist)

def _nba_teams_in(team: str):
    """Return (sql_in_clause, params) expanding a team code to all historical equivalents."""
    codes = _NBA_TEAM_EQUIV.get(team, [team])
    return f"({','.join('?' * len(codes))})", codes


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


# ── Existing routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return _redirect_frontend("/")


@app.route("/multiplayer/<game_type>")
def multiplayer_create_page(game_type):
    config = SUPPORTED_GAMES.get(game_type)
    if not config:
        return "Game not supported for multiplayer", 404
    return _redirect_frontend(f"/multiplayer/{game_type}")


@app.route("/lobbies/<room_id>")
def multiplayer_lobby_page(room_id):
    room = get_room(room_id)
    if room is None:
        return "Lobby not found", 404
    return _redirect_frontend(f"/lobbies/{room_id}")


@app.route("/migration")
def migration_page():
    return _redirect_frontend("/migration")


@app.route("/games/<sport>/<slug>")
def migrated_game_page(sport, slug):
    return _redirect_frontend(f"/games/{sport}/{slug}", preserve_query=True)


@app.route("/legacy-home")
def legacy_home_page():
    return render_template("index.html")


@app.route("/legacy/multiplayer/<game_type>")
def legacy_multiplayer_create_page(game_type):
    config = SUPPORTED_GAMES.get(game_type)
    if not config:
        return "Game not supported for multiplayer", 404
    return render_template("lobby.html", create_mode=True, game_type=game_type, game_label=config["label"])


@app.route("/legacy/lobbies/<room_id>")
def legacy_multiplayer_lobby_page(room_id):
    room = get_room(room_id)
    if room is None:
        return "Lobby not found", 404
    return render_template(
        "lobby.html",
        create_mode=False,
        game_type=room["game_type"],
        game_label=SUPPORTED_GAMES[room["game_type"]]["label"],
        room_id=room_id,
    )


@app.route("/legacy/starting6")
def legacy_starting6_page():
    return render_template("starting6.html")


@app.route("/legacy/nba_starting5")
def legacy_nba_starting5_page():
    return render_template("nba_starting5.html")


@app.route("/legacy/chain")
def legacy_chain_page():
    return render_template("chain.html")


@app.route("/legacy/nba_chain")
def legacy_nba_chain_page():
    return render_template("nba_chain.html")


@app.route("/legacy/ttb")
def legacy_ttb_page():
    return render_template("ttb.html")


@app.route("/legacy/nba_ttb")
def legacy_nba_ttb_page():
    return render_template("nba_ttb.html")


@app.route("/legacy/nfl_bullseye")
def legacy_nfl_bullseye_page():
    return render_template("nfl_bullseye.html")


@app.route("/legacy/nba_bullseye")
def legacy_nba_bullseye_page():
    return render_template("nba_bullseye.html")


@app.route("/starting6")
def starting6():
    return _redirect_frontend("/games/nfl/fantasy-duel", preserve_query=True)


@app.route("/api/lobbies/create", methods=["POST"])
def create_lobby_api():
    data = _request_json_body()
    try:
        room = create_room(data.get("game_type", ""), data.get("player_name", "Host"), data.get("token", ""))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"room": room_payload(room, data.get("token")), "room_url": f"/lobbies/{room['room_id']}"})


@app.route("/api/lobbies/<room_id>")
def lobby_state_api(room_id):
    room = get_room(room_id)
    if room is None:
        return jsonify({"error": "Lobby not found"}), 404
    token = request.args.get("token", "")
    return jsonify({"room": room_payload(room, token)})


@app.route("/api/lobbies/<room_id>/claim-seat", methods=["POST"])
def lobby_claim_seat_api(room_id):
    data = _request_json_body()
    try:
        room = claim_seat(room_id, data.get("token", ""), data.get("player_name", ""), int(data.get("seat_number", 0)))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"room": room_payload(room, data.get("token"))})


@app.route("/api/lobbies/<room_id>/leave-seat", methods=["POST"])
def lobby_leave_seat_api(room_id):
    data = _request_json_body()
    try:
        room = leave_seat(room_id, data.get("token", ""))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"room": room_payload(room, data.get("token"))})


@app.route("/api/lobbies/<room_id>/seat-meta", methods=["POST"])
def lobby_seat_meta_api(room_id):
    data = _request_json_body()
    try:
        room = update_seat_meta(room_id, data.get("token", ""), data.get("meta", {}) or {})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"room": room_payload(room, data.get("token"))})


@app.route("/api/lobbies/<room_id>/start", methods=["POST"])
def lobby_start_api(room_id):
    try:
        room = get_room(room_id)
        if room is None:
            return jsonify({"error": "Lobby not found"}), 404
        data = _request_json_body()
        token = data.get("token", "")
        if token != room.get("host_token"):
            return jsonify({"error": "Only the host can start the game"}), 400
        filled = occupied_seats(room)
        if len(filled) < 2:
            return jsonify({"error": "Need at least 2 seated players to start"}), 400
        if room.get("status") != "lobby":
            return jsonify({"error": "Lobby has already started"}), 400

        player_names = [seat["name"] for _, seat in filled]
        player_tokens = [seat["token"] for _, seat in filled]
        conn = get_db()
        try:
            if room["game_type"] == "nfl_bullseye":
                game_id, _ = nfl_bull.start_game(conn, player_names, player_tokens=player_tokens)
            elif room["game_type"] == "nba_bullseye":
                game_id, _ = nba_bull.start_game(conn, player_names, player_tokens=player_tokens)
            elif room["game_type"] == "starting6":
                game_id, _ = starting6_game_mod.start_game(conn, player_names, player_tokens=player_tokens)
            elif room["game_type"] == "nba_starting5":
                game_id, _ = nba_starting5_game_mod.start_game(conn, player_names, player_tokens=player_tokens)
            elif room["game_type"] in {"chain_coop", "chain_comp", "nba_chain_coop", "nba_chain_comp"}:
                sport = "nba" if room["game_type"].startswith("nba_") else "nfl"
                mode = "comp" if room["game_type"].endswith("_comp") else "coop"
                game_id, _ = chain_game_mod.start_game(conn, player_names, player_tokens=player_tokens, sport=sport, mode=mode)
            elif room["game_type"] in {"nfl_codewords", "nba_codewords"}:
                sport = "nba" if "nba" in room["game_type"] else "nfl"
                cw_players = []
                for _, seat in filled:
                    meta = seat.get("meta") or {}
                    cw_players.append({
                        "name": seat["name"],
                        "token": seat["token"],
                        "team": meta.get("team"),
                        "role": meta.get("role"),
                    })
                try:
                    game_id, _ = codewords_mod.start_game(
                        conn, cw_players, sport=sport,
                        mode="teams",
                    )
                except ValueError as exc:
                    return jsonify({"error": str(exc)}), 400
            else:
                return jsonify({"error": "Unsupported game type"}), 400
            conn.commit()
        finally:
            conn.close()

        room = set_started(room_id, game_id, _build_room_redirect(room_id, room["game_type"]))
        return jsonify({"room": room_payload(room, token)})
    except Exception as exc:
        return jsonify({"error": str(exc) or "Failed to start lobby"}), 500


@app.route("/api/lobbies/<room_id>/rematch", methods=["POST"])
def lobby_rematch_api(room_id):
    room = get_room(room_id)
    if room is None:
        return jsonify({"error": "Lobby not found"}), 404
    data = _request_json_body()
    token = data.get("token", "")
    if not has_token(room, token):
        return jsonify({"error": "Only lobby players can restart this room"}), 400
    room = reset_to_lobby(room_id)
    return jsonify({"room": room_payload(room, token), "room_url": f"/lobbies/{room['room_id']}"})


@app.route("/api/lobbies/<room_id>/game-state")
def lobby_game_state_api(room_id):
    room = get_room(room_id)
    if room is None:
        return jsonify({"error": "Lobby not found"}), 404
    state = _room_game_state(room)
    return jsonify({"room": room_payload(room, request.args.get("token", "")), "state": state})


@app.route("/dungeon_adventure")
def dungeon_adventure_page():
    return _redirect_frontend("/games/nfl/dungeon")


@app.route("/nba_dungeon_adventure")
def nba_dungeon_adventure_page():
    return _redirect_frontend("/games/nba/dungeon")


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
    game_id = request.args.get("game_id", "").strip()
    if game_id:
        conn = get_db()
        try:
            return jsonify({"years": starting6_game_mod.get_years(conn, game_id, player)})
        finally:
            conn.close()
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
    game_id = request.args.get("game_id", "").strip()
    if game_id:
        conn = get_db()
        try:
            return jsonify({"results": starting6_game_mod.search_players(conn, term, game_id)})
        finally:
            conn.close()
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
    game_id = request.args.get("game_id", "").strip()
    if game_id:
        season = request.args.get("season", "").strip()
        conn = get_db()
        try:
            state, err = starting6_game_mod.submit_pick(conn, game_id, player, int(season), player_token=request.args.get("token", ""))
            conn.commit()
            return jsonify({"valid": err is None, "state": state, "msg": err or ""})
        finally:
            conn.close()
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


@app.route("/api/starting6/state")
def starting6_state():
    game_id = request.args.get("game_id", "").strip()
    state = starting6_game_mod.get_game(game_id)
    if state is None:
        return jsonify({"error": "Game not found"}), 404
    return jsonify({"state": state})


@app.route("/api/starting6/pass", methods=["POST"])
def starting6_pass():
    data = request.get_json(force=True) or {}
    conn = get_db()
    try:
        state, err = starting6_game_mod.pass_turn(conn, data.get("game_id", ""), player_token=data.get("token", ""))
        conn.commit()
        return jsonify({"ok": err is None, "state": state, "msg": err or ""})
    finally:
        conn.close()


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
    return _redirect_frontend("/games/nfl/chain", preserve_query=True)


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
    game_id = (data.get("game_id") or "").strip()
    if game_id:
        player_guess = (data.get("player") or "").strip()
        conn = get_db()
        try:
            state, err = chain_game_mod.submit_guess(conn, game_id, player_guess, player_token=data.get("token"))
            conn.commit()
            return jsonify({"ok": err is None, "state": state, "error": err})
        finally:
            conn.close()

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
    game_id = request.args.get("game_id", "").strip()
    if not term:
        return jsonify({"results": []})
    conn = get_db()
    names = chain_game_mod.search_players(conn, game_id, term) if game_id else cc.search_players(conn, term)
    conn.close()
    return jsonify({"results": [{"name": n} for n in names]})


@app.route("/api/chain/state")
def chain_state():
    game_id = request.args.get("game_id", "").strip()
    state = chain_game_mod.get_game(game_id)
    if state is None:
        return jsonify({"error": "Game not found"}), 404
    return jsonify({"state": state})


# ── Ticking Time Bomb routes ─────────────────────────────────────────────────

@app.route("/ttb")
def ttb_page():
    return _redirect_frontend("/games/nfl/ttb")


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
    return _redirect_frontend("/games/nba/chain", preserve_query=True)


@app.route("/nba_ttb")
def nba_ttb_page():
    return _redirect_frontend("/games/nba/ttb")


@app.route("/nba_starting5")
def nba_starting5_page():
    return _redirect_frontend("/games/nba/fantasy-duel", preserve_query=True)


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
    game_id = (data.get("game_id") or "").strip()
    if game_id:
        player_guess = (data.get("player") or "").strip()
        conn = get_db()
        try:
            state, err = chain_game_mod.submit_guess(conn, game_id, player_guess, player_token=data.get("token"))
            conn.commit()
            return jsonify({"ok": err is None, "state": state, "error": err})
        finally:
            conn.close()

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
    game_id = request.args.get("game_id", "").strip()
    if not term:
        return jsonify({"results": []})
    conn = get_db()
    names = chain_game_mod.search_players(conn, game_id, term) if game_id else nba_cc.search_players(conn, term)
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
    game_id = request.args.get("game_id", "").strip()
    if game_id:
        conn = get_db()
        try:
            return jsonify({"results": nba_starting5_game_mod.search_players(conn, term, game_id)})
        finally:
            conn.close()
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
    game_id = request.args.get("game_id", "").strip()
    if game_id:
        conn = get_db()
        try:
            return jsonify({"years": nba_starting5_game_mod.get_years(conn, game_id, player)})
        finally:
            conn.close()
    team = request.args.get("team", "").strip()
    conn = get_db()
    team_in, team_codes = _nba_teams_in(team)
    rows = conn.execute(
        f"SELECT DISTINCT season FROM nba_stats WHERE player = ? AND team IN {team_in} AND fantasy_score IS NOT NULL ORDER BY season DESC",
        [player] + team_codes,
    ).fetchall()
    conn.close()
    return jsonify({"years": [r[0] for r in rows]})


@app.route("/api/nba_starting5/validate")
def nba_starting5_validate():
    player = request.args.get("player", "").strip()
    game_id = request.args.get("game_id", "").strip()
    if game_id:
        season = request.args.get("season", "").strip()
        conn = get_db()
        try:
            state, err = nba_starting5_game_mod.submit_pick(conn, game_id, player, int(season), player_token=request.args.get("token", ""))
            conn.commit()
            return jsonify({"valid": err is None, "state": state, "msg": err or ""})
        finally:
            conn.close()
    team = request.args.get("team", "").strip()
    season = request.args.get("season", "").strip()
    conn = get_db()
    team_in, team_codes = _nba_teams_in(team)
    if season:
        row = conn.execute(
            f"SELECT player, pos, fantasy_score, season, team FROM nba_stats WHERE player = ? AND team IN {team_in} AND season = ?",
            [player] + team_codes + [int(season)],
        ).fetchone()
    else:
        row = conn.execute(
            f"""SELECT player, pos, fantasy_score, season, team FROM nba_stats
               WHERE player = ? AND team IN {team_in} AND fantasy_score IS NOT NULL
               ORDER BY fantasy_score DESC LIMIT 1""",
            [player] + team_codes,
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
    team_in, team_codes = _nba_teams_in(team)
    if positions:
        pos_placeholders = ",".join("?" * len(positions))
        rows = conn.execute(
            f"""SELECT player, season, pos, fantasy_score, team
                FROM nba_stats
                WHERE team IN {team_in} AND pos IN ({pos_placeholders}) AND fantasy_score IS NOT NULL
                ORDER BY fantasy_score DESC""",
            team_codes + positions,
        ).fetchall()
    else:
        rows = conn.execute(
            f"""SELECT player, season, pos, fantasy_score, team
               FROM nba_stats WHERE team IN {team_in} AND fantasy_score IS NOT NULL
               ORDER BY fantasy_score DESC""",
            team_codes,
        ).fetchall()
    conn.close()
    return jsonify({"players": [
        {"player": r[0], "season": r[1], "pos": r[2], "ppr": r[3], "team": r[4]}
        for r in rows
    ]})


@app.route("/api/nba_starting5/state")
def nba_starting5_state():
    game_id = request.args.get("game_id", "").strip()
    state = nba_starting5_game_mod.get_game(game_id)
    if state is None:
        return jsonify({"error": "Game not found"}), 404
    return jsonify({"state": state})


@app.route("/api/nba_starting5/pass", methods=["POST"])
def nba_starting5_pass():
    data = request.get_json(force=True) or {}
    conn = get_db()
    try:
        state, err = nba_starting5_game_mod.pass_turn(conn, data.get("game_id", ""), player_token=data.get("token", ""))
        conn.commit()
        return jsonify({"ok": err is None, "state": state, "msg": err or ""})
    finally:
        conn.close()


# ── NFL Balatro routes ────────────────────────────────────────────────────────

@app.route("/nfl_balatro")
def nfl_balatro_page():
    return _redirect_frontend("/games/nfl/balatro")


@app.route("/api/nfl_balatro/start", methods=["POST"])
def nfl_balatro_start():
    nb.cleanup_old_games()
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "normal")
    conn = get_db()
    gid, state = nb.start_game(conn, mode=mode)
    conn.close()
    return jsonify({
        "game_id": gid,
        "mode": state.get("mode", "normal"),
        "floor": state["floor"],
        "round": state.get("round", 1),
        "fight": state.get("fight", 1),
        "boss_effect": state.get("boss_effect"),
        "level_name": state["level_name"],
        "target_score": state["target_score"],
        "hands_remaining": state["hands_remaining"],
        "discards_remaining": state["discards_remaining"],
        "hand": state["hand"],
        "jokers": [],
        "coins": state["coins"],
        "skill_levels": state["skill_levels"],
        "combo_boosts": state["combo_boosts"],
        "card_effects": state["card_effects"],
        "status": state["status"],
        "max_hand_size": state.get("max_hand_size", 7),
        "base_discards": state.get("base_discards", 3),
        "max_jokers": state.get("max_jokers", 5),
        "joker_state": state.get("joker_state", {}),
        "held_cards": state.get("held_cards", []),
        "deck_cards": state.get("deck", []),
        "fight_discards": state.get("fight_discards", []),
        "fight_played": state.get("fight_played", []),
    })


@app.route("/api/nfl_balatro/play_hand", methods=["POST"])
def nfl_balatro_play():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    card_ids = data.get("card_ids", [])
    result, err = nb.play_hand(gid, card_ids)
    if err:
        return jsonify({"error": err}), 400
    # Include updated hand in response
    g = nb.get_state(gid)
    if g:
        result["hand"] = g["hand"]
    return jsonify(result)


@app.route("/api/nfl_balatro/discard", methods=["POST"])
def nfl_balatro_discard():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    card_ids = data.get("card_ids", [])
    result, err = nb.discard_cards(gid, card_ids)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nfl_balatro/select_joker", methods=["POST"])
def nfl_balatro_select_joker():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    joker_id = data.get("joker_id", "skip")
    result, err = nb.select_joker(gid, joker_id)
    if err:
        return jsonify({"error": err}), 400
    # Generate shop items now that we have a db connection
    conn = get_db()
    shop_items = nb.generate_shop_for_game(gid, conn)
    conn.close()
    result["shop_items"] = shop_items or []
    return jsonify(result)


@app.route("/api/nfl_balatro/preview", methods=["POST"])
def nfl_balatro_preview():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    card_ids = data.get("card_ids", [])
    g = nb.get_state(gid)
    if not g:
        return jsonify({"error": "Game not found"}), 404
    played = [c for c in g["hand"] if c["id"] in set(card_ids)]
    result = nb.get_score_preview(
        played, g["jokers"],
        skill_levels=g.get("skill_levels", {}),
        combo_boosts=g.get("combo_boosts", {}),
        card_effects=g.get("card_effects", {}),
        joker_state=g.get("joker_state", {}),
        floor=g.get("floor", 1),
        joker_enhancements=g.get("joker_enhancements", {}),
    )
    return jsonify(result)


@app.route("/api/nfl_balatro/leave_shop", methods=["POST"])
def nfl_balatro_leave_shop():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    result, err = nb.leave_shop(gid)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nfl_balatro/buy_item", methods=["POST"])
def nfl_balatro_buy_item():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    shop_id = data.get("shop_id", "")
    item_type = data.get("item_type", "")
    target_card_id = data.get("target_card_id", None)
    target_year = data.get("target_year", None)
    new_pos = data.get("new_pos", None)
    conn = get_db()
    result, err = nb.buy_shop_item(gid, item_type, shop_id, target_card_id=target_card_id, target_year=target_year, conn=conn, new_pos=new_pos)
    conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)



@app.route("/api/nfl_balatro/get_pool", methods=["POST"])
def nfl_balatro_get_pool():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    result, err = nb.get_pool(gid)
    if err:
        return jsonify({"error": err}), 404
    return jsonify(result)


@app.route("/api/nfl_balatro/player_seasons")
def nfl_balatro_player_seasons():
    game_id = request.args.get("game_id", "")
    card_id = request.args.get("card_id", "")
    g = nb.get_state(game_id)
    if not g:
        return jsonify({"error": "Game not found"}), 404
    card = next((c for c in g["deck_pool"] if c["id"] == card_id), None)
    if not card:
        return jsonify({"error": "Card not found"}), 404
    conn = get_db()
    seasons = nb.get_player_seasons(conn, card["player"])
    conn.close()
    return jsonify({"seasons": seasons, "current_season": card["season"]})


@app.route("/api/nfl_balatro/card_stats")
def nfl_balatro_card_stats():
    player = request.args.get("player", "")
    season = request.args.get("season", "")
    if not player or not season:
        return jsonify({"error": "Missing params"}), 400
    conn = get_db()
    stats = nb.get_card_stats(conn, player, season)
    conn.close()
    return jsonify(stats or {})


@app.route("/api/nfl_balatro/sell_joker", methods=["POST"])
def nfl_balatro_sell_joker():
    data = request.get_json(force=True) or {}
    result, err = nb.sell_joker(data.get("game_id", ""), data.get("joker_id", ""))
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nfl_balatro/restock_shop", methods=["POST"])
def nfl_balatro_restock_shop():
    data = request.get_json(force=True) or {}
    conn = get_db()
    result, err = nb.restock_shop(data.get("game_id", ""), conn)
    conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nfl_balatro/open_pack", methods=["POST"])
def nfl_balatro_open_pack():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    pack_id = data.get("pack_id", "")
    conn = get_db()
    result, err = nb.open_pack(gid, pack_id, conn)
    conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nfl_balatro/confirm_pack_picks", methods=["POST"])
def nfl_balatro_confirm_pack_picks():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    selected_ids = data.get("selected_ids", [])
    result, err = nb.confirm_pack_picks(gid, selected_ids)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nfl_balatro/advance_fight", methods=["POST"])
def nfl_balatro_advance_fight():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    result, err = nb.advance_fight(gid)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nfl_balatro/claim_reward", methods=["POST"])
def nfl_balatro_claim_reward():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    choice = data.get("choice", "")
    joker_id = data.get("joker_id", None)
    conn = get_db()
    result, err = nb.claim_fight_reward(gid, choice, joker_id, conn)
    conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


# ── NBA Balatro routes ────────────────────────────────────────────────────────

@app.route("/nba_balatro")
def nba_balatro_page():
    return _redirect_frontend("/games/nba/balatro")


@app.route("/api/nba_balatro/start", methods=["POST"])
def nba_balatro_start():
    nba_b.cleanup_old_games()
    conn = get_db()
    gid, state = nba_b.start_game(conn)
    conn.close()
    return jsonify({
        "game_id": gid,
        "floor": state["floor"],
        "round": state.get("round", 1),
        "fight": state.get("fight", 1),
        "boss_effect": state.get("boss_effect"),
        "level_name": state["level_name"],
        "target_score": state["target_score"],
        "hands_remaining": state["hands_remaining"],
        "discards_remaining": state["discards_remaining"],
        "hand": state["hand"],
        "jokers": [],
        "coins": state["coins"],
        "skill_levels": state["skill_levels"],
        "combo_boosts": state["combo_boosts"],
        "card_effects": state["card_effects"],
        "status": state["status"],
        "max_hand_size": state.get("max_hand_size", 7),
        "base_discards": state.get("base_discards", 3),
        "max_jokers": state.get("max_jokers", 5),
        "joker_state": state.get("joker_state", {}),
        "held_items": state.get("held_items", []),
        "deck_pool": state.get("deck_pool", []),
        "deck_cards": state.get("deck", []),
        "fight_discards": state.get("fight_discards", []),
        "fight_played": state.get("fight_played", []),
    })


@app.route("/api/nba_balatro/play_hand", methods=["POST"])
def nba_balatro_play():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    card_ids = data.get("card_ids", [])
    result, err = nba_b.play_hand(gid, card_ids)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/discard", methods=["POST"])
def nba_balatro_discard():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    card_ids = data.get("card_ids", [])
    result, err = nba_b.discard_cards(gid, card_ids)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/select_joker", methods=["POST"])
def nba_balatro_select_joker():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    joker_id = data.get("joker_id", "")
    result, err = nba_b.select_joker(gid, joker_id)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/preview", methods=["POST"])
def nba_balatro_preview():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    card_ids = data.get("card_ids", [])
    g = nba_b.get_state(gid)
    if not g:
        return jsonify({"error": "Game not found"}), 404
    played = [c for c in g["hand"] if c["id"] in set(card_ids)]
    result = nba_b.get_score_preview(
        played, g["jokers"],
        skill_levels=g.get("skill_levels", {}),
        combo_boosts=g.get("combo_boosts", {}),
        card_effects=g.get("card_effects", {}),
        joker_state=g.get("joker_state", {}),
        floor=g.get("floor", 1),
        joker_enhancements=g.get("joker_enhancements", {}),
    )
    return jsonify(result)


@app.route("/api/nba_balatro/leave_shop", methods=["POST"])
def nba_balatro_leave_shop():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    result, err = nba_b.leave_shop(gid)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/buy_item", methods=["POST"])
def nba_balatro_buy_item():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    shop_id = data.get("shop_id", "")
    item_type = data.get("item_type", "")
    target_card_id = data.get("target_card_id", None)
    target_year = data.get("target_year", None)
    conn = get_db()
    result, err = nba_b.buy_shop_item(gid, item_type, shop_id, target_card_id=target_card_id, target_year=target_year, conn=conn)
    conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/use_held_item", methods=["POST"])
def nba_balatro_use_held_item():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    held_id = data.get("held_id", "")
    target_card_id = data.get("target_card_id")
    target_year = data.get("target_year")
    discard_only = data.get("discard_only", False)
    new_pos = data.get("new_pos", None)
    conn = get_db()
    result, err = nba_b.use_held_item(gid, held_id, target_card_id, target_year, conn, discard_only, new_pos=new_pos)
    conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/get_pool", methods=["POST"])
def nba_balatro_get_pool():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    result, err = nba_b.get_pool(gid)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/player_seasons", methods=["GET"])
def nba_balatro_player_seasons():
    gid = request.args.get("game_id", "")
    card_id = request.args.get("card_id", "")
    g = nba_b.get_state(gid)
    if not g:
        return jsonify({"error": "Game not found"}), 404
    card = next((c for c in g["deck_pool"] if c["id"] == card_id), None)
    if not card:
        return jsonify({"error": "Card not found"}), 404
    conn = get_db()
    seasons = nba_b.get_player_seasons(conn, card["player"])
    conn.close()
    return jsonify({"seasons": seasons, "current_season": card["season"]})


@app.route("/api/nba_balatro/card_stats", methods=["GET"])
def nba_balatro_card_stats():
    player = request.args.get("player", "")
    season = request.args.get("season", "")
    if not player or not season:
        return jsonify({"error": "Missing params"}), 400
    conn = get_db()
    stats = nba_b.get_card_stats(conn, player, season)
    conn.close()
    return jsonify(stats or {})


@app.route("/api/nba_balatro/sell_joker", methods=["POST"])
def nba_balatro_sell_joker():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    joker_id = data.get("joker_id", "")
    result, err = nba_b.sell_joker(gid, joker_id)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/restock_shop", methods=["POST"])
def nba_balatro_restock_shop():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    conn = get_db()
    result, err = nba_b.restock_shop(gid, conn)
    conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/open_pack", methods=["POST"])
def nba_balatro_open_pack():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    pack_id = data.get("pack_id", "")
    conn = get_db()
    result, err = nba_b.open_pack(gid, pack_id, conn)
    conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/confirm_pack_picks", methods=["POST"])
def nba_balatro_confirm_pack_picks():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    selected_ids = data.get("selected_ids", [])
    result, err = nba_b.confirm_pack_picks(gid, selected_ids)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/advance_fight", methods=["POST"])
def nba_balatro_advance_fight():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    result, err = nba_b.advance_fight(gid)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route("/api/nba_balatro/claim_reward", methods=["POST"])
def nba_balatro_claim_reward():
    data = request.get_json(force=True) or {}
    gid = data.get("game_id", "")
    choice = data.get("choice", "")
    joker_id = data.get("joker_id", None)
    conn = get_db()
    result, err = nba_b.claim_fight_reward(gid, choice, joker_id, conn)
    conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route('/api/nfl_balatro/apply_division_sticker', methods=['POST'])
def api_nfl_apply_division_sticker():
    data = request.json
    return jsonify(nb.apply_division_sticker(data['game_id'], data['card_id'], data['new_division']))

@app.route('/api/nba_balatro/apply_division_sticker', methods=['POST'])
def api_nba_apply_division_sticker():
    data = request.json
    return jsonify(nba_b.apply_division_sticker(data['game_id'], data['card_id'], data['new_division']))

@app.route('/api/nfl_balatro/start_infinity', methods=['POST'])
def api_nfl_start_infinity():
    data = request.json
    result, err = nb.start_infinity_mode(data['game_id'])
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)

@app.route('/api/nba_balatro/start_infinity', methods=['POST'])
def api_nba_start_infinity():
    data = request.json
    result, err = nba_b.start_infinity_mode(data['game_id'])
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


# ── NBA Bullseye routes ───────────────────────────────────────────────────────

@app.route("/nba_bullseye")
def nba_bullseye_page():
    if request.args.get("room_id"):
        return _redirect_frontend("/games/nba/bullseye", preserve_query=True)
    return _redirect_frontend("/games/nba/bullseye", extra_query={"solo": "1"})


@app.route("/api/nba_bullseye/start", methods=["POST"])
def nba_bullseye_start():
    data = request.get_json(force=True) or {}
    player_names = data.get("player_names", [])
    player_tokens = data.get("player_tokens")
    conn = get_db()
    try:
        game_id, state = nba_bull.start_game(conn, player_names, player_tokens=player_tokens)
        conn.commit()
        return jsonify({"game_id": game_id, "state": state})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


@app.route("/api/nba_bullseye/search")
def nba_bullseye_search():
    query = request.args.get("q", "").strip()
    prompt_idx = int(request.args.get("prompt_idx", 0))
    game_id = request.args.get("game_id", "")
    conn = get_db()
    try:
        results = nba_bull.search_players(conn, query, prompt_idx, game_id)
        return jsonify({"results": results})
    finally:
        conn.close()


@app.route("/api/nba_bullseye/pick", methods=["POST"])
def nba_bullseye_pick():
    data = request.get_json(force=True) or {}
    conn = get_db()
    try:
        state, err = nba_bull.submit_pick(
            conn, data["game_id"], data["player_name"], data["season"],
            prompt_idx=data.get("prompt_idx"), player_idx=data.get("player_idx"), actor_token=data.get("token")
        )
        ok = err is None
        conn.commit()
        return jsonify({"ok": ok, "state": state, "msg": err or ""})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


@app.route("/api/nba_bullseye/years")
def nba_bullseye_years():
    game_id = request.args.get("game_id", "")
    prompt_idx = int(request.args.get("prompt_idx", 0))
    player_name = request.args.get("player", "").strip()
    conn = get_db()
    try:
        years = nba_bull.get_valid_years(conn, game_id, prompt_idx, player_name)
        return jsonify({"years": years})
    except Exception as e:
        return jsonify({"years": [], "error": str(e)}), 200
    finally:
        conn.close()


@app.route("/api/nba_bullseye/seasons")
def nba_bullseye_seasons():
    game_id = request.args.get("game_id", "")
    prompt_idx = int(request.args.get("prompt_idx", 0))
    player_name = request.args.get("player", "").strip()
    conn = get_db()
    try:
        seasons = nba_bull.get_player_seasons(conn, game_id, prompt_idx, player_name)
        return jsonify({"seasons": seasons})
    finally:
        conn.close()


@app.route("/api/nba_bullseye/state")
def nba_bullseye_state():
    game_id = request.args.get("game_id", "")
    state = nba_bull.get_game(game_id)
    if state is None:
        return jsonify({"error": "Game not found"}), 404
    return jsonify({"state": state})


# ── NFL Bullseye routes ───────────────────────────────────────────────────────

@app.route("/nfl_bullseye")
def nfl_bullseye_page():
    if request.args.get("room_id"):
        return _redirect_frontend("/games/nfl/bullseye", preserve_query=True)
    return _redirect_frontend("/games/nfl/bullseye", extra_query={"solo": "1"})


@app.route("/api/nfl_bullseye/start", methods=["POST"])
def nfl_bullseye_start():
    data = request.get_json(force=True) or {}
    player_names = data.get("player_names", [])
    player_tokens = data.get("player_tokens")
    conn = get_db()
    try:
        game_id, state = nfl_bull.start_game(conn, player_names, player_tokens=player_tokens)
        conn.commit()
        return jsonify({"game_id": game_id, "state": state})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


@app.route("/api/nfl_bullseye/search")
def nfl_bullseye_search():
    query = request.args.get("q", "").strip()
    prompt_idx = int(request.args.get("prompt_idx", 0))
    game_id = request.args.get("game_id", "")
    conn = get_db()
    try:
        results = nfl_bull.search_players(conn, query, prompt_idx, game_id)
        return jsonify({"results": results})
    finally:
        conn.close()


@app.route("/api/nfl_bullseye/years")
def nfl_bullseye_years():
    game_id = request.args.get("game_id", "")
    prompt_idx = int(request.args.get("prompt_idx", 0))
    player_name = request.args.get("player", "").strip()
    conn = get_db()
    try:
        years = nfl_bull.get_valid_years(conn, game_id, prompt_idx, player_name)
        return jsonify({"years": years})
    except Exception as e:
        return jsonify({"years": [], "error": str(e)}), 200
    finally:
        conn.close()


@app.route("/api/nfl_bullseye/seasons")
def nfl_bullseye_seasons():
    game_id = request.args.get("game_id", "")
    prompt_idx = int(request.args.get("prompt_idx", 0))
    player_name = request.args.get("player", "").strip()
    conn = get_db()
    try:
        seasons = nfl_bull.get_player_seasons(conn, game_id, prompt_idx, player_name)
        return jsonify({"seasons": seasons})
    finally:
        conn.close()


@app.route("/api/nfl_bullseye/state")
def nfl_bullseye_state():
    game_id = request.args.get("game_id", "")
    state = nfl_bull.get_game(game_id)
    if state is None:
        return jsonify({"error": "Game not found"}), 404
    return jsonify({"state": state})


@app.route("/api/nfl_bullseye/pick", methods=["POST"])
def nfl_bullseye_pick():
    data = request.get_json(force=True) or {}
    conn = get_db()
    try:
        state, err = nfl_bull.submit_pick(
            conn, data["game_id"], data["player_name"], data["season"],
            prompt_idx=data.get("prompt_idx"), player_idx=data.get("player_idx"), actor_token=data.get("token")
        )
        ok = err is None
        conn.commit()
        return jsonify({"ok": ok, "state": state, "msg": err or ""})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


# ── Code Words (multiplayer) ─────────────────────────────────────────────────

@app.route("/nfl_codewords")
def nfl_codewords_page():
    if request.args.get("room_id"):
        return _redirect_frontend("/games/nfl/codewords", preserve_query=True)
    return _redirect_frontend("/multiplayer/nfl_codewords")


@app.route("/nba_codewords")
def nba_codewords_page():
    if request.args.get("room_id"):
        return _redirect_frontend("/games/nba/codewords", preserve_query=True)
    return _redirect_frontend("/multiplayer/nba_codewords")


def _codewords_state_response(game_id: str, token: str):
    state = codewords_mod.get_game(game_id)
    if state is None:
        return jsonify({"error": "Game not found"}), 404
    return jsonify({"state": codewords_mod.view_state(state, token)})


@app.route("/api/codewords/state")
def codewords_state_api():
    game_id = request.args.get("game_id", "")
    token = request.args.get("token", "")
    return _codewords_state_response(game_id, token)


@app.route("/api/codewords/clue", methods=["POST"])
def codewords_clue_api():
    data = request.get_json(force=True) or {}
    state, err = codewords_mod.submit_clue(
        data.get("game_id", ""),
        data.get("token", ""),
        data.get("clue", ""),
        data.get("number", 0),
    )
    if state is None:
        return jsonify({"error": err or "Game not found"}), 404
    if err:
        return jsonify({"error": err, "state": codewords_mod.view_state(state, data.get("token", ""))}), 400
    return jsonify({"state": codewords_mod.view_state(state, data.get("token", ""))})


@app.route("/api/codewords/guess", methods=["POST"])
def codewords_guess_api():
    data = request.get_json(force=True) or {}
    state, err = codewords_mod.submit_guess(
        data.get("game_id", ""),
        data.get("token", ""),
        data.get("index", -1),
    )
    if state is None:
        return jsonify({"error": err or "Game not found"}), 404
    if err:
        return jsonify({"error": err, "state": codewords_mod.view_state(state, data.get("token", ""))}), 400
    return jsonify({"state": codewords_mod.view_state(state, data.get("token", ""))})


@app.route("/api/codewords/end_turn", methods=["POST"])
def codewords_end_turn_api():
    data = request.get_json(force=True) or {}
    state, err = codewords_mod.end_turn(data.get("game_id", ""), data.get("token", ""))
    if state is None:
        return jsonify({"error": err or "Game not found"}), 404
    if err:
        return jsonify({"error": err, "state": codewords_mod.view_state(state, data.get("token", ""))}), 400
    return jsonify({"state": codewords_mod.view_state(state, data.get("token", ""))})


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Missing consolidated database at {DB_PATH}. Restore or recreate fantasy.db before starting the app."
        )

    should_repair = not os.environ.get("RENDER") and not os.environ.get("PORT")
    if should_repair:
        print("Repairing text encoding issues...")
        repair_db_text(DB_PATH)

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
