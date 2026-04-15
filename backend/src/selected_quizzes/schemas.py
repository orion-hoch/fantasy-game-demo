"""Pydantic schemas for the selected_quizzes routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Sport = Literal["nfl", "nba"]


class QuizSlot(BaseModel):
    hints: dict[str, str] | None = None


class QuizSummary(BaseModel):
    id: str
    title: str
    prompt: str
    time_limit_seconds: int
    total_answers: int


class QuizListResponse(BaseModel):
    quizzes: list[QuizSummary]


class QuizStartResponse(BaseModel):
    game_id: str
    quiz_id: str
    title: str
    prompt: str
    time_limit_seconds: int
    total_answers: int
    deadline_ms: int
    slots: list[QuizSlot]


class QuizGuessRequest(BaseModel):
    game_id: str = Field(min_length=1)
    guess: str = Field(default="")


class QuizGuessResponse(BaseModel):
    matched: str | None
    matched_index: int | None
    duplicate: bool
    found_count: int
    total_answers: int
    time_left_seconds: int
    finished: bool


class QuizAnswerStatus(BaseModel):
    canonical: str
    found: bool
    hints: dict[str, str] | None = None


class QuizFinishResponse(BaseModel):
    quiz_id: str
    title: str
    prompt: str
    answers: list[QuizAnswerStatus]
    found_count: int
    total_answers: int
    elapsed_seconds: int
    time_limit_seconds: int
