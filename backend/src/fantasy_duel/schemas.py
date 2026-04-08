"""Pydantic schemas for Fantasy Duel routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Sport = Literal["nfl", "nba"]


class FantasyDuelStartRequest(BaseModel):
    player_names: list[str] = Field(min_length=2, max_length=5)
    player_tokens: list[str] | None = None


class FantasyDuelPickRequest(BaseModel):
    game_id: str = Field(min_length=1)
    player_name: str = Field(min_length=1)
    season: int
    token: str | None = None


class FantasyDuelPassRequest(BaseModel):
    game_id: str = Field(min_length=1)
    token: str | None = None


class FantasyDuelStartResponse(BaseModel):
    game_id: str
    state: dict[str, Any]


class FantasyDuelStateResponse(BaseModel):
    state: dict[str, Any]


class FantasyDuelSearchResponse(BaseModel):
    results: list[str]


class FantasyDuelYearsResponse(BaseModel):
    years: list[int]


class FantasyDuelPickResponse(BaseModel):
    ok: bool
    state: dict[str, Any] | None = None
    msg: str = ""
