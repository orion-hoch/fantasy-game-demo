import random
import string
import time

from session_store import GameStore


_ROOMS = GameStore("multiplayer_lobbies", ttl_seconds=86400)

_CODEWORDS_TEAM_GAMES = {"nfl_codewords", "nba_codewords"}
_CODEWORDS_DUEL_GAMES = {"nfl_codewords_duel", "nba_codewords_duel"}
_CODEWORDS_GAMES = _CODEWORDS_TEAM_GAMES | _CODEWORDS_DUEL_GAMES
_VALID_CW_TEAMS = {"A", "B"}
_VALID_CW_ROLES = {"spymaster", "guesser"}


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
    "chain_coop": {
        "label": "Chain Game Co-op (NFL)",
        "route": "/chain",
        "min_players": 2,
        "max_players": 4,
    },
    "chain_comp": {
        "label": "Chain Game Comp (NFL)",
        "route": "/chain",
        "min_players": 2,
        "max_players": 2,
    },
    "nba_chain_coop": {
        "label": "Chain Game Co-op (NBA)",
        "route": "/nba_chain",
        "min_players": 2,
        "max_players": 4,
    },
    "nba_chain_comp": {
        "label": "Chain Game Comp (NBA)",
        "route": "/nba_chain",
        "min_players": 2,
        "max_players": 2,
    },
    "nfl_codewords": {
        "label": "NFL Code Words",
        "route": "/nfl_codewords",
        "min_players": 4,
        "max_players": 4,
    },
    "nba_codewords": {
        "label": "NBA Code Words",
        "route": "/nba_codewords",
        "min_players": 4,
        "max_players": 4,
    },
    "nfl_codewords_duel": {
        "label": "NFL Code Words Duel",
        "route": "/nfl_codewords",
        "min_players": 2,
        "max_players": 2,
    },
    "nba_codewords_duel": {
        "label": "NBA Code Words Duel",
        "route": "/nba_codewords",
        "min_players": 2,
        "max_players": 2,
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


def _is_codewords_game(game_type: str) -> bool:
    return game_type in _CODEWORDS_GAMES


def _is_codewords_duel(game_type: str) -> bool:
    return game_type in _CODEWORDS_DUEL_GAMES


def _cw_team_label(team: str) -> str:
    return "Red" if team == "A" else "Yellow"


def _cw_role_label(role: str) -> str:
    return "Clue Giver" if role == "spymaster" else "Guesser"


def _merge_meta(existing: dict, meta_updates: dict) -> dict:
    merged = dict(existing or {})
    for key, value in (meta_updates or {}).items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def _normalize_codewords_meta(room: dict, seat_no: int, seat: dict, meta_updates: dict) -> dict:
    existing = dict(seat.get("meta") or {})
    updates = dict(meta_updates or {})
    duel_mode = _is_codewords_duel(room["game_type"])

    if "team" in updates and updates["team"] is not None and updates["team"] not in _VALID_CW_TEAMS:
        raise ValueError("Invalid team")
    if "role" in updates and updates["role"] is not None and updates["role"] not in _VALID_CW_ROLES:
        raise ValueError("Invalid role")

    merged = _merge_meta(existing, updates)

    # Team switches should not carry the previous team role with them.
    if not duel_mode and "team" in updates and updates.get("team") != existing.get("team") and "role" not in updates:
        merged.pop("role", None)

    chosen_team = merged.get("team")
    chosen_role = merged.get("role")

    for other_seat_no, other_seat in occupied_seats(room):
        if other_seat_no == seat_no:
            continue
        other_meta = other_seat.get("meta") or {}
        if duel_mode:
            if chosen_team and other_meta.get("team") == chosen_team:
                raise ValueError(f"Team {_cw_team_label(chosen_team)} is already taken")
            continue
        if chosen_team and chosen_role and other_meta.get("team") == chosen_team and other_meta.get("role") == chosen_role:
            raise ValueError(f"{_cw_team_label(chosen_team)} {_cw_role_label(chosen_role)} is already taken")

    return merged


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
    max_players = SUPPORTED_GAMES[room["game_type"]]["max_players"]
    if seat_key not in room["seats"] or int(seat_key) > max_players:
        raise ValueError("Invalid seat")
    if room["seats"][seat_key] is not None and room["seats"][seat_key].get("token") != token:
        raise ValueError("Seat is already taken")

    current_seat, _ = token_seat(room, token)
    if current_seat is not None and str(current_seat) != seat_key:
        room["seats"][str(current_seat)] = None

    room["seats"][seat_key] = {
        "name": (player_name or f"Player {seat_key}").strip() or f"Player {seat_key}",
        "token": token,
        "meta": {},
    }
    return save_room(room)


def update_seat_meta(room_id: str, token: str, meta_updates: dict) -> dict:
    """Merge arbitrary metadata onto the seat owned by `token`.

    Used today by Code Words for picking team + role in the lobby. Other game
    types simply ignore the meta dict.
    """
    room = get_room(room_id)
    if room is None:
        raise ValueError("Room not found")
    if room["status"] != "lobby":
        raise ValueError("Game has already started")
    seat_no, seat = token_seat(room, token)
    if seat_no is None or seat is None:
        raise ValueError("You are not seated in this room")

    if _is_codewords_game(room["game_type"]):
        seat["meta"] = _normalize_codewords_meta(room, seat_no, seat, meta_updates)
    else:
        seat["meta"] = _merge_meta(seat.get("meta") or {}, meta_updates)

    room["seats"][str(seat_no)] = seat
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
        seat_no: (
            {"name": seat["name"], "meta": dict(seat.get("meta") or {})}
            if seat else None
        )
        for seat_no, seat in room["seats"].items()
    }
    payload["game_label"] = SUPPORTED_GAMES[room["game_type"]]["label"]
    payload["min_players"] = SUPPORTED_GAMES[room["game_type"]]["min_players"]
    payload["max_players"] = SUPPORTED_GAMES[room["game_type"]]["max_players"]
    payload["my_seat"] = token_seat(room, token)[0] if token else None
    payload["is_host"] = bool(token and token == room.get("host_token"))
    payload["filled_seat_count"] = len(occupied_seats(room))
    return payload
