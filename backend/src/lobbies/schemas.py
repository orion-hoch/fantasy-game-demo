"""Pydantic schemas for multiplayer lobby routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SeatMetaUpdate(BaseModel):
    team: str | None = None
    role: str | None = None


class CreateLobbyRequest(BaseModel):
    game_type: str = Field(min_length=1)
    player_name: str = Field(default="Host")
    token: str = Field(min_length=1)


class ClaimSeatRequest(BaseModel):
    token: str = Field(min_length=1)
    player_name: str = Field(default="Player")
    seat_number: int = Field(ge=1, le=4)


class LeaveSeatRequest(BaseModel):
    token: str = Field(min_length=1)


class SeatMetaRequest(BaseModel):
    token: str = Field(min_length=1)
    meta: SeatMetaUpdate


class StartLobbyRequest(BaseModel):
    token: str = Field(min_length=1)


class RematchRequest(BaseModel):
    token: str = Field(min_length=1)


class RoomSeatPayload(BaseModel):
    name: str
    meta: dict[str, Any] = Field(default_factory=dict)


class RoomPayload(BaseModel):
    room_id: str
    game_type: str
    game_label: str
    status: Literal["lobby", "in_game"]
    created_at: int
    updated_at: int
    game_id: str | None = None
    redirect_url: str | None = None
    min_players: int
    max_players: int
    my_seat: int | None = None
    is_host: bool = False
    filled_seat_count: int
    seats: dict[str, RoomSeatPayload | None]


class LobbyResponse(BaseModel):
    room: RoomPayload
    room_url: str | None = None


class LobbyGameStateResponse(BaseModel):
    room: RoomPayload
    state: dict[str, Any] | None = None
