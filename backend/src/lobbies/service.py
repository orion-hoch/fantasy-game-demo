"""Service layer for multiplayer lobby operations.

This wraps the legacy lobby/game modules so the strangler FastAPI backend can
reuse existing server-side game logic without forking behavior.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException

from src.legacy.bridge import REPO_ROOT

import chain_game as chain_game_mod
import codewords_game as codewords_mod
import lobby_store
import nba_bullseye as nba_bull
import nba_starting5_game as nba_starting5_game_mod
import nfl_bullseye as nfl_bull
import starting6_game as starting6_game_mod


DB_PATH = REPO_ROOT / "fantasy.db"
MIGRATED_GAME_REDIRECTS = {
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


def room_url(room_id: str) -> str:
    return f"/lobbies/{room_id}"


def _build_room_redirect(room_id: str, game_type: str) -> str:
    route = MIGRATED_GAME_REDIRECTS.get(game_type, lobby_store.SUPPORTED_GAMES[game_type]["route"])
    return f"{route}?room_id={room_id}"


def _room_game_state(room: dict) -> dict[str, Any] | None:
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


def _sync_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _raise_not_found(message: str = "Lobby not found") -> None:
    raise HTTPException(status_code=404, detail=message)


def _raise_bad_request(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def list_supported_games() -> list[dict[str, Any]]:
    return [
        {
            "game_type": game_type,
            "label": config["label"],
            "route": config["route"],
            "min_players": config["min_players"],
            "max_players": config["max_players"],
        }
        for game_type, config in lobby_store.SUPPORTED_GAMES.items()
    ]


def create_lobby(game_type: str, player_name: str, token: str) -> dict[str, Any]:
    try:
        room = lobby_store.create_room(game_type, player_name, token)
    except Exception as exc:
        _raise_bad_request(str(exc))
    return {"room": lobby_store.room_payload(room, token), "room_url": room_url(room["room_id"])}


def get_lobby(room_id: str, token: str | None = None) -> dict[str, Any]:
    room = lobby_store.get_room(room_id)
    if room is None:
        _raise_not_found()
    return {"room": lobby_store.room_payload(room, token or "")}


def claim_lobby_seat(room_id: str, token: str, player_name: str, seat_number: int) -> dict[str, Any]:
    try:
        room = lobby_store.claim_seat(room_id, token, player_name, seat_number)
    except Exception as exc:
        _raise_bad_request(str(exc))
    return {"room": lobby_store.room_payload(room, token)}


def leave_lobby_seat(room_id: str, token: str) -> dict[str, Any]:
    try:
        room = lobby_store.leave_seat(room_id, token)
    except Exception as exc:
        _raise_bad_request(str(exc))
    return {"room": lobby_store.room_payload(room, token)}


def update_lobby_seat_meta(room_id: str, token: str, meta: dict[str, Any]) -> dict[str, Any]:
    try:
        room = lobby_store.update_seat_meta(room_id, token, meta)
    except Exception as exc:
        _raise_bad_request(str(exc))
    return {"room": lobby_store.room_payload(room, token)}


def start_lobby(room_id: str, token: str) -> dict[str, Any]:
    room = lobby_store.get_room(room_id)
    if room is None:
        _raise_not_found()
    if token != room.get("host_token"):
        _raise_bad_request("Only the host can start the game")
    filled = lobby_store.occupied_seats(room)
    if len(filled) < 2:
        _raise_bad_request("Need at least 2 seated players to start")
    if room.get("status") != "lobby":
        _raise_bad_request("Lobby has already started")

    player_names = [seat["name"] for _, seat in filled]
    player_tokens = [seat["token"] for _, seat in filled]
    conn = _sync_db()
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
            players = []
            for _, seat in filled:
                meta = seat.get("meta") or {}
                players.append(
                    {
                        "name": seat["name"],
                        "token": seat["token"],
                        "team": meta.get("team"),
                        "role": meta.get("role"),
                    }
                )
            try:
                game_id, _ = codewords_mod.start_game(conn, players, sport=sport, mode="teams")
            except ValueError as exc:
                _raise_bad_request(str(exc))
        else:
            _raise_bad_request("Unsupported game type")
        conn.commit()
    finally:
        conn.close()

    room = lobby_store.set_started(room_id, game_id, _build_room_redirect(room_id, room["game_type"]))
    return {"room": lobby_store.room_payload(room, token)}


def rematch_lobby(room_id: str, token: str) -> dict[str, Any]:
    room = lobby_store.get_room(room_id)
    if room is None:
        _raise_not_found()
    if not lobby_store.has_token(room, token):
        _raise_bad_request("Only lobby players can restart this room")
    room = lobby_store.reset_to_lobby(room_id)
    return {"room": lobby_store.room_payload(room, token), "room_url": room_url(room["room_id"])}


def start_chain_match(room_id: str, token: str) -> dict[str, Any]:
    room = lobby_store.get_room(room_id)
    if room is None:
        _raise_not_found()
    if room.get("status") != "in_game" or not room.get("game_id"):
        _raise_bad_request("Lobby is not in game state")
    if room["game_type"] not in {"chain_coop", "chain_comp", "nba_chain_coop", "nba_chain_comp"}:
        _raise_bad_request("Start button is only available for Chain lobbies")

    conn = _sync_db()
    try:
        state, err = chain_game_mod.start_match(conn, room["game_id"], player_token=token)
        conn.commit()
    finally:
        conn.close()

    if err:
        _raise_bad_request(err)

    return {
        "room": lobby_store.room_payload(room, token),
        "state": state,
    }


def lobby_game_state(room_id: str, token: str | None = None) -> dict[str, Any]:
    room = lobby_store.get_room(room_id)
    if room is None:
        _raise_not_found()
    return {"room": lobby_store.room_payload(room, token or ""), "state": _room_game_state(room)}
