import uuid

from session_store import GameStore
import chain_categories as cc


_GAMES = GameStore("chain_game", ttl_seconds=14400)


def _player_scores(state: dict) -> list:
    return [player.get("score", 0) for player in state["players"]]


def _next_player(state: dict):
    state["currentPlayer"] = (state["currentPlayer"] + 1) % len(state["players"])


def _fresh_chain(conn, used_players: set):
    cat = cc.get_start_category(conn)
    if not cat:
        return None
    valid = cc.get_players_for_chain(conn, [{"id": cat["id"], "value": cat.get("value", "")}]) - used_players
    if not valid:
        return None
    cat = dict(cat)
    cat["valid_count"] = len(valid)
    return cat


def start_game(conn, player_names: list, player_tokens: list | None = None) -> tuple:
    if not 2 <= len(player_names) <= 4:
        raise ValueError("Need 2-4 players")
    if player_tokens and len(player_tokens) != len(player_names):
        raise ValueError("Player token count mismatch")

    used_players = set()
    first_cat = _fresh_chain(conn, used_players)
    if not first_cat:
        raise ValueError("Could not create starting chain")

    players = []
    for idx, name in enumerate(player_names):
        players.append({
            "name": (name or f"Player {idx + 1}").strip() or f"Player {idx + 1}",
            "token": player_tokens[idx] if player_tokens else None,
            "score": 0,
        })

    state = {
        "game_id": str(uuid.uuid4())[:8],
        "players": players,
        "currentPlayer": 0,
        "chain": [first_cat],
        "validCount": first_cat["valid_count"],
        "usedPlayers": [],
        "chainGuesses": [],
        "feedback": None,
        "mode": "multiplayer",
    }
    _GAMES[state["game_id"]] = state
    return state["game_id"], state


def get_game(game_id: str) -> dict | None:
    return _GAMES.get(game_id)


def _validate_actor(state: dict, player_token: str | None):
    if not player_token:
        return None
    current = state["players"][state["currentPlayer"]]
    if current.get("token") and current["token"] != player_token:
        return "It is not your turn"
    return None


def search_players(conn, game_id: str, term: str) -> list:
    state = get_game(game_id)
    if state is None:
        return []
    names = cc.search_players(conn, term)
    used = set(state.get("usedPlayers") or [])
    return [name for name in names if name not in used]


def submit_guess(conn, game_id: str, player_guess: str, player_token: str | None = None) -> tuple:
    state = get_game(game_id)
    if state is None:
        return None, "Game not found"
    actor_err = _validate_actor(state, player_token)
    if actor_err:
        return state, actor_err
    if not player_guess or not state.get("chain"):
        return state, "Missing player or chain"

    player_guess = player_guess.strip()
    used_players = set(state.get("usedPlayers") or [])
    if player_guess in used_players:
        return state, f"{player_guess} has already been used"

    chain = state["chain"]
    valid_players = cc.get_players_for_chain(conn, chain) - used_players
    current_idx = state["currentPlayer"]
    current_player = state["players"][current_idx]

    if player_guess in valid_players:
        pts = len(chain)
        current_player["score"] += pts
        used_players.add(player_guess)
        state["usedPlayers"] = list(used_players)
        state["chainGuesses"].append({
            "player": player_guess,
            "pts": pts,
            "by": current_player["name"],
        })
        remaining = valid_players - {player_guess}
        exclude_ids = [link["id"] for link in chain]
        feedback = f"{current_player['name']} is correct with {player_guess} (+{pts})"

        if len(remaining) >= 2:
            next_cat = cc.get_chain_category(conn, remaining, exclude_ids=exclude_ids)
            if next_cat:
                state["chain"].append(next_cat)
                state["validCount"] = next_cat["valid_count"]
            else:
                state["validCount"] = len(remaining)
        elif len(remaining) == 1:
            state["validCount"] = 1
        else:
            fresh = _fresh_chain(conn, used_players)
            if fresh:
                state["chain"] = [fresh]
                state["validCount"] = fresh["valid_count"]
                state["chainGuesses"] = []
                feedback = f"{current_player['name']} cleared the chain with {player_guess}. New chain!"
            else:
                state["validCount"] = 0
                feedback = f"{current_player['name']} used the last valid answer with {player_guess}."

        _next_player(state)
        state["feedback"] = {"type": "correct", "message": feedback}
        _GAMES[state["game_id"]] = state
        return state, None

    link_results = cc.check_player_against_chain(conn, player_guess, chain)
    examples = sorted(list(valid_players))[:3]
    state["feedback"] = {
        "type": "wrong",
        "message": f"{current_player['name']} missed with {player_guess}",
        "examples": examples,
        "link_results": link_results,
    }
    _next_player(state)
    _GAMES[state["game_id"]] = state
    return state, None
