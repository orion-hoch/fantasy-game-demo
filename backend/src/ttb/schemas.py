"""Pydantic schemas for TTB routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Sport = Literal["nfl", "nba"]


class TTBStartRequest(BaseModel):
    mode: str = Field(default="classic")
    include_defense: bool = False
    hard_mode: bool = False
    min_draft_year: int | None = None


class TTBGuessRequest(BaseModel):
    game_id: str = Field(min_length=1)
    guess: str = Field(default="")
    reveal: bool = False
    skip: bool = False


class TTBStartResponse(BaseModel):
    game_id: str
    clues: list[dict[str, Any]]
    hints: list[dict[str, Any]]


class TTBSearchResponse(BaseModel):
    results: list[dict[str, str]]
