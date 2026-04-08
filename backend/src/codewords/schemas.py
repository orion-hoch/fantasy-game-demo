"""Pydantic schemas for Code Words routes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CodewordsStateResponse(BaseModel):
    state: dict[str, Any]


class CodewordsClueRequest(BaseModel):
    game_id: str = Field(min_length=1)
    token: str = Field(min_length=1)
    clue: str = Field(default="")
    number: int


class CodewordsGuessRequest(BaseModel):
    game_id: str = Field(min_length=1)
    token: str = Field(min_length=1)
    index: int


class CodewordsEndTurnRequest(BaseModel):
    game_id: str = Field(min_length=1)
    token: str = Field(min_length=1)


class CodewordsActionResponse(BaseModel):
    state: dict[str, Any] | None = None
    error: str | None = None
