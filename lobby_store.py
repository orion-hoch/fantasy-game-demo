import random
import string
import time

from session_store import GameStore


_ROOMS = GameStore("multiplayer_lobbies", ttl_seconds=86400)


SUPPORTED_GAMES = {
    "nfl_bullseye": {
        "label": "NFL Bullseye",
        "route": "/nfl_bullseye",
        "min_players": 2,
        "max_players": 4,
    },
    "nba_bullseye": {
        "label": "NBA Bullseye",
        "route": "/nba_bullseye",
        "min_players": 2,
        "max_players": 4,
    },
    "starting6": {
        "label": "Fantasy Duel (NFL)",
        "route": "/starting6",
        "min_players": 2,
        "max_players": 4,
    },
    "nba_starting5": {
        "label": "Fantasy Duel (NBA)",
        "route": "/nba_starting5",
        "min_players": 2,
        "max_players": 4,
    },
    "chain": {
        "label": "Chain Game",
        "route": "/chain",
        "min_players": 2,
        "max_players": 4,
    },
}


def _now() -> int:
    return int(time.time())


def _new_room_id() -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        room_id = "".join(random.choice(alphabet) for _ in range(6))
        if get_room(room_id) is None:
            return room_id


def _seat_map() -> dict:
    return {str(idx): None for idx in range(1, 5)}


def create_room(game_type: str, host_name: str, host_token: str) -> dict:
    if game_type not in SUPPORTED_GAMES:
        raise ValueError("Unsupported game type")
    if not host_token:
        raise ValueError("Missing host token")

    room_id = _new_room_id()
    host_name = (host_name or "Host").strip() or "Host"
    now = _now()
    room = {
        "room_id": room_id,
        "game_type": game_type,
        "status": "lobby",
        "host_token": host_token,
        "created_at": now,
        "updated_at": now,
        "game_id": None,
        "redirect_url": None,
        "seats": _seat_map(),
    }
    room["seats"]["1"] = {"name": host_name, "token": host_token}
    _ROOMS[room_id] = room
    return room


def get_room(room_id: str) -> dict | None:
    return _ROOMS.get(room_id)


def save_room(room: dict) -> dict:
    room["updated_at"] = _now()
    _ROOMS[room["room_id"]] = room
    return room


def occupied_seats(room: dict) -> list:
    filled = []
    for seat_no in range(1, 5):
        seat = room["seats"].get(str(seat_no))
        if seat:
            filled.append((seat_no, seat))
    return filled


def token_seat(room: dict, token: str) -> tuple[int | None, dict | None]:
    for seat_no in range(1, 5):
        seat = room["seats"].get(str(seat_no))
        if seat and seat.get("token") == token:
            return seat_no, seat
    return None, None


def has_token(room: dict, token: str) -> bool:
    if not token:
        return False
    if room.get("host_token") == token:
        return True
    seat_no, _ = token_seat(room, token)
    return seat_no is not None


def claim_seat(room_id: str, token: str, player_name: str, seat_number: int) -> dict:
    room = get_room(room_id)
    if room is None:
        raise ValueError("Room not found")
    if room["status"] != "lobby":
        raise ValueError("Game has already started")
    if not token:
        raise ValueError("Missing player token")
    seat_key = str(int(seat_number))
    if seat_key not in room["seats"]:
        raise ValueError("Invalid seat")
    if room["seats"][seat_key] is not None and room["seats"][seat_key].get("token") != token:
        raise ValueError("Seat is already taken")

    current_seat, _ = token_seat(room, token)
    if current_seat is not None and str(current_seat) != seat_key:
        room["seats"][str(current_seat)] = None

    room["seats"][seat_key] = {
        "name": (player_name or f"Player {seat_key}").strip() or f"Player {seat_key}",
        "token": token,
    }
    return save_room(room)


def leave_seat(room_id: str, token: str) -> dict:
    room = get_room(room_id)
    if room is None:
        raise ValueError("Room not found")
    if room["status"] != "lobby":
        raise ValueError("Game has already started")
    seat_no, _ = token_seat(room, token)
    if seat_no is None:
        return room
    room["seats"][str(seat_no)] = None
    return save_room(room)


def set_started(room_id: str, game_id: str, redirect_url: str) -> dict:
    room = get_room(room_id)
    if room is None:
        raise ValueError("Room not found")
    room["status"] = "in_game"
    room["game_id"] = game_id
    room["redirect_url"] = redirect_url
    return save_room(room)


def reset_to_lobby(room_id: str) -> dict:
    room = get_room(room_id)
    if room is None:
        raise ValueError("Room not found")
    room["status"] = "lobby"
    room["game_id"] = None
    room["redirect_url"] = None
    return save_room(room)


def room_payload(room: dict, token: str | None = None) -> dict:
    payload = dict(room)
    payload["seats"] = {
        seat_no: ({"name": seat["name"]} if seat else None)
        for seat_no, seat in room["seats"].items()
    }
    payload["game_label"] = SUPPORTED_GAMES[room["game_type"]]["label"]
    payload["my_seat"] = token_seat(room, token)[0] if token else None
    payload["is_host"] = bool(token and token == room.get("host_token"))
    payload["filled_seat_count"] = len(occupied_seats(room))
    return payload
