import uuid

import chain_categories as nfl_cc
import nba_chain_categories as nba_cc
from session_store import GameStore


_GAMES = GameStore("chain_game", ttl_seconds=14400)

_SPORT_MODS = {
    "nfl": nfl_cc,
    "nba": nba_cc,
}


def _cc_for(sport: str):
    return _SPORT_MODS["nba" if sport == "nba" else "nfl"]


def _fresh_chain(conn, sport: str, used_players: set):
    cc = _cc_for(sport)
    attempts = 8
    while attempts > 0:
        attempts -= 1
        cat = cc.get_start_category(conn)
        if not cat:
            return None
        valid = cc.get_players_for_chain(conn, [{"id": cat["id"], "value": cat.get("value", "")}]) - used_players
        if valid:
            cat = dict(cat)
            cat["valid_count"] = len(valid)
            return cat
    return None


def _teammate_chain(conn, sport: str, player_name: str, used_players: set):
    cc = _cc_for(sport)
    cat = cc.get_teammate_category(conn, player_name)
    if not cat:
        return _fresh_chain(conn, sport, used_players)
    valid = cc.get_players_for_chain(conn, [{"id": cat["id"], "value": cat.get("value", "")}]) - used_players
    if not valid:
        return _fresh_chain(conn, sport, used_players)
    cat = dict(cat)
    cat["valid_count"] = len(valid)
    return cat


def _new_comp_player(name: str, token: str | None, chain: dict):
    return {
        "name": name,
        "token": token,
        "score": 0,
        "lives_left": 2,
        "eliminated": False,
        "chain": [chain] if chain else [],
        "validCount": chain["valid_count"] if chain else 0,
        "chainGuesses": [],
    }


def _new_coop_player(name: str, token: str | None):
    return {
        "name": name,
        "token": token,
        "score": 0,
    }


def _current_player(state: dict):
    return state["players"][state["currentPlayer"]]


def _is_over(state: dict) -> bool:
    if state["mode"] == "coop":
        return state.get("lives_left", 0) <= 0
    return all(player.get("eliminated") for player in state["players"])


def _advance_turn(state: dict):
    n_players = len(state["players"])
    next_idx = state["currentPlayer"]
    for _ in range(n_players):
        next_idx = (next_idx + 1) % n_players
        if state["mode"] == "coop" or not state["players"][next_idx].get("eliminated"):
            state["currentPlayer"] = next_idx
            return


def _winner_payload(state: dict):
    scores = [player.get("score", 0) for player in state["players"]]
    max_score = max(scores) if scores else 0
    winners = [idx for idx, score in enumerate(scores) if score == max_score]
    return {
        "scores": scores,
        "winner_indices": winners,
        "winner_names": [state["players"][idx]["name"] for idx in winners],
    }


def _finalize_if_needed(state: dict):
    if _is_over(state):
        state["done"] = True
        state["winner"] = _winner_payload(state)


def start_game(conn, player_names: list, player_tokens: list | None = None, sport: str = "nfl", mode: str = "coop") -> tuple:
    if not 2 <= len(player_names) <= 4:
        raise ValueError("Need 2-4 players")
    if player_tokens and len(player_tokens) != len(player_names):
        raise ValueError("Player token count mismatch")
    if mode == "comp" and len(player_names) != 2:
        raise ValueError("Competitive Chain requires exactly 2 players")

    used_players = set()
    players = []
    if mode == "coop":
        for idx, name in enumerate(player_names):
            players.append(_new_coop_player((name or f"Player {idx + 1}").strip() or f"Player {idx + 1}", player_tokens[idx] if player_tokens else None))
        first_chain = _fresh_chain(conn, sport, used_players)
        if not first_chain:
            raise ValueError("Could not create starting chain")
        state = {
            "game_id": str(uuid.uuid4())[:8],
            "sport": sport,
            "mode": mode,
            "players": players,
            "currentPlayer": 0,
            "lives_left": 3,
            "chain": [first_chain],
            "validCount": first_chain["valid_count"],
            "usedPlayers": [],
            "chainGuesses": [],
            "feedback": None,
            "done": False,
            "winner": None,
        }
    else:
        for idx, name in enumerate(player_names):
            chain = _fresh_chain(conn, sport, used_players)
            if not chain:
                raise ValueError("Could not create starting chain")
            players.append(_new_comp_player((name or f"Player {idx + 1}").strip() or f"Player {idx + 1}", player_tokens[idx] if player_tokens else None, chain))
        state = {
            "game_id": str(uuid.uuid4())[:8],
            "sport": sport,
            "mode": mode,
            "players": players,
            "currentPlayer": 0,
            "usedPlayers": [],
            "feedback": None,
            "done": False,
            "winner": None,
        }
    _GAMES[state["game_id"]] = state
    return state["game_id"], state


def get_game(game_id: str) -> dict | None:
    return _GAMES.get(game_id)


def _validate_actor(state: dict, player_token: str | None):
    if not player_token:
        return None
    current = _current_player(state)
    if current.get("token") and current["token"] != player_token:
        return "It is not your turn"
    return None


def _current_chain(state: dict):
    if state["mode"] == "coop":
        return state.get("chain", [])
    return _current_player(state).get("chain", [])


def _current_valid_count(state: dict):
    if state["mode"] == "coop":
        return state.get("validCount", 0)
    return _current_player(state).get("validCount", 0)


def search_players(conn, game_id: str, term: str) -> list:
    state = get_game(game_id)
    if state is None:
        return []
    names = _cc_for(state["sport"]).search_players(conn, term)
    used = set(state.get("usedPlayers") or [])
    return [name for name in names if name not in used]


def _set_current_chain(state: dict, chain: list, valid_count: int, guesses: list | None = None):
    if state["mode"] == "coop":
        state["chain"] = chain
        state["validCount"] = valid_count
        if guesses is not None:
            state["chainGuesses"] = guesses
    else:
        player = _current_player(state)
        player["chain"] = chain
        player["validCount"] = valid_count
        if guesses is not None:
            player["chainGuesses"] = guesses


def submit_guess(conn, game_id: str, player_guess: str, player_token: str | None = None) -> tuple:
    state = get_game(game_id)
    if state is None:
        return None, "Game not found"
    if state.get("done"):
        return state, "Game is already complete"
    actor_err = _validate_actor(state, player_token)
    if actor_err:
        return state, actor_err
    player_guess = (player_guess or "").strip()
    if not player_guess:
        return state, "Missing player"

    used_players = set(state.get("usedPlayers") or [])
    if player_guess in used_players:
        return state, f"{player_guess} has already been used"

    cc = _cc_for(state["sport"])
    chain = _current_chain(state)
    if not chain:
        return state, "No active chain"
    valid_players = cc.get_players_for_chain(conn, chain) - used_players
    active_player = _current_player(state)

    if player_guess in valid_players:
        pts = len(chain)
        active_player["score"] += pts
        used_players.add(player_guess)
        state["usedPlayers"] = list(used_players)

        guess_entry = {"player": player_guess, "pts": pts, "by": active_player["name"]}
        guesses = list(state.get("chainGuesses", [])) if state["mode"] == "coop" else list(active_player.get("chainGuesses", []))
        guesses.append(guess_entry)

        remaining = valid_players - {player_guess}
        exclude_ids = [link["id"] for link in chain]
        feedback = {"type": "correct", "message": f"{active_player['name']} is correct with {player_guess} (+{pts})"}

        if len(remaining) >= 2:
            next_cat = cc.get_chain_category(conn, remaining, exclude_ids=exclude_ids)
            if next_cat:
                chain = list(chain) + [next_cat]
                _set_current_chain(state, chain, next_cat["valid_count"], guesses)
            else:
                fresh = _fresh_chain(conn, state["sport"], used_players)
                if fresh:
                    _set_current_chain(state, [fresh], fresh["valid_count"], [])
                    feedback = {"type": "correct", "message": f"{active_player['name']} cleared the chain with {player_guess}. New chain!"}
                else:
                    _set_current_chain(state, list(chain), len(remaining), guesses)
        else:
            fresh = _fresh_chain(conn, state["sport"], used_players)
            if fresh:
                _set_current_chain(state, [fresh], fresh["valid_count"], [])
                feedback = {"type": "correct", "message": f"{active_player['name']} used one of the last answers with {player_guess}. New chain!"}
            else:
                _set_current_chain(state, list(chain), len(remaining), guesses)

        state["feedback"] = feedback
        _advance_turn(state)
        _finalize_if_needed(state)
        _GAMES[state["game_id"]] = state
        return state, None

    link_results = cc.check_player_against_chain(conn, player_guess, chain)
    examples = sorted(list(valid_players))[:3]
    if state["mode"] == "coop":
        state["lives_left"] -= 1
        state["feedback"] = {
            "type": "wrong",
            "message": f"{active_player['name']} missed with {player_guess}. {state['lives_left']} lives left.",
            "examples": examples,
            "link_results": link_results,
        }
        _advance_turn(state)
        _finalize_if_needed(state)
    else:
        active_player["lives_left"] -= 1
        if active_player["lives_left"] <= 0:
            active_player["eliminated"] = True
            msg = f"{active_player['name']} is out after missing with {player_guess}."
        else:
            new_chain = _teammate_chain(conn, state["sport"], player_guess, used_players)
            if new_chain:
                active_player["chain"] = [new_chain]
                active_player["validCount"] = new_chain["valid_count"]
                active_player["chainGuesses"] = []
            msg = f"{active_player['name']} lost a life with {player_guess}. New chain started."
        state["feedback"] = {
            "type": "wrong",
            "message": msg,
            "examples": examples,
            "link_results": link_results,
        }
        _advance_turn(state)
        _finalize_if_needed(state)

    _GAMES[state["game_id"]] = state
    return state, None
