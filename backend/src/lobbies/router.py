"""FastAPI lobby routes for the strangler backend."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.lobbies import service
from src.lobbies.schemas import (
    ClaimSeatRequest,
    CreateLobbyRequest,
    LeaveSeatRequest,
    LobbyGameStateResponse,
    LobbyResponse,
    RematchRequest,
    SeatMetaRequest,
    StartLobbyRequest,
)


router = APIRouter(prefix="/lobbies", tags=["lobbies"])


@router.get("/games")
def supported_games():
    return {"games": service.list_supported_games()}


@router.post("/create", response_model=LobbyResponse)
def create_lobby(payload: CreateLobbyRequest) -> LobbyResponse:
    return LobbyResponse.model_validate(service.create_lobby(payload.game_type, payload.player_name, payload.token))


@router.get("/{room_id}", response_model=LobbyResponse)
def lobby_state(room_id: str, token: str = Query(default="")) -> LobbyResponse:
    return LobbyResponse.model_validate(service.get_lobby(room_id, token))


@router.post("/{room_id}/claim-seat", response_model=LobbyResponse)
def claim_seat(room_id: str, payload: ClaimSeatRequest) -> LobbyResponse:
    return LobbyResponse.model_validate(service.claim_lobby_seat(room_id, payload.token, payload.player_name, payload.seat_number))


@router.post("/{room_id}/leave-seat", response_model=LobbyResponse)
def leave_seat(room_id: str, payload: LeaveSeatRequest) -> LobbyResponse:
    return LobbyResponse.model_validate(service.leave_lobby_seat(room_id, payload.token))


@router.post("/{room_id}/seat-meta", response_model=LobbyResponse)
def seat_meta(room_id: str, payload: SeatMetaRequest) -> LobbyResponse:
    return LobbyResponse.model_validate(service.update_lobby_seat_meta(room_id, payload.token, payload.meta.model_dump(exclude_unset=True)))


@router.post("/{room_id}/start", response_model=LobbyResponse)
def start_lobby(room_id: str, payload: StartLobbyRequest) -> LobbyResponse:
    return LobbyResponse.model_validate(service.start_lobby(room_id, payload.token))


@router.post("/{room_id}/rematch", response_model=LobbyResponse)
def rematch_lobby(room_id: str, payload: RematchRequest) -> LobbyResponse:
    return LobbyResponse.model_validate(service.rematch_lobby(room_id, payload.token))


@router.get("/{room_id}/game-state", response_model=LobbyGameStateResponse)
def game_state(room_id: str, token: str = Query(default="")) -> LobbyGameStateResponse:
    return LobbyGameStateResponse.model_validate(service.lobby_game_state(room_id, token))
