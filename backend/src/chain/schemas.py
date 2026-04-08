"""Pydantic schemas for Chain routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Sport = Literal["nfl", "nba"]


class ChainGuessRequest(BaseModel):
    game_id: str | None = None
    player: str = Field(default="")
    token: str | None = None
    chain: list[dict[str, Any]] = Field(default_factory=list)
    used_players: list[str] = Field(default_factory=list)


class ChainTeammateRequest(BaseModel):
    player: str = Field(min_length=1)


class ChainStateResponse(BaseModel):
    state: dict[str, Any]


class ChainSearchResponse(BaseModel):
    results: list[dict[str, str]]
