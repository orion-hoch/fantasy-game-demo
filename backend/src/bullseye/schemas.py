"""Pydantic schemas for Bullseye routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Sport = Literal["nfl", "nba"]


class BullseyeStartRequest(BaseModel):
    player_names: list[str] = Field(min_length=1, max_length=4)
    player_tokens: list[str] | None = None


class BullseyePickRequest(BaseModel):
    game_id: str = Field(min_length=1)
    player_name: str = Field(min_length=1)
    season: int
    prompt_idx: int = Field(ge=0, le=4)
    player_idx: int = Field(ge=0, le=3)
    token: str | None = None


class BullseyeStartResponse(BaseModel):
    game_id: str
    state: dict[str, Any]


class BullseyeStateResponse(BaseModel):
    state: dict[str, Any]


class BullseyeSearchResponse(BaseModel):
    results: list[dict[str, Any]]


class BullseyeYearsResponse(BaseModel):
    years: list[int]
    error: str | None = None


class BullseyeSeasonsResponse(BaseModel):
    seasons: list[dict[str, Any]]


class BullseyePickResponse(BaseModel):
    ok: bool
    state: dict[str, Any] | None = None
    msg: str = ""
