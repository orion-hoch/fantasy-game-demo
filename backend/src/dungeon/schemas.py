"""Pydantic schemas for Dungeon Adventure routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Sport = Literal["nfl", "nba"]


class DungeonRewardsRequest(BaseModel):
    floor: int = Field(default=1, ge=1)
    items: list[dict[str, Any]] = Field(default_factory=list)


class DungeonEncounterRequest(BaseModel):
    floor: int = Field(default=1, ge=1)
    items: list[dict[str, Any]] = Field(default_factory=list)
    used_questions: list[str] = Field(default_factory=list)


class DungeonAnswerRequest(BaseModel):
    question: dict[str, Any] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(default_factory=list)
    answer: str = Field(default="")


class DungeonSearchRequest(BaseModel):
    query: str = Field(default="")
    items: list[dict[str, Any]] = Field(default_factory=list)
    question: dict[str, Any] | None = None


class DungeonRewardsResponse(BaseModel):
    rewards: list[dict[str, Any]]


class DungeonSearchResponse(BaseModel):
    results: list[str]
