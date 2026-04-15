"""FastAPI routes for selected_quizzes."""

from __future__ import annotations

from fastapi import APIRouter

from src.selected_quizzes import service
from src.selected_quizzes.schemas import (
    QuizFinishResponse,
    QuizGuessRequest,
    QuizGuessResponse,
    QuizListResponse,
    QuizStartResponse,
    Sport,
)


router = APIRouter(prefix="/selected-quizzes", tags=["selected-quizzes"])


@router.get("/{sport}", response_model=QuizListResponse)
def list_quizzes(sport: Sport) -> QuizListResponse:
    return QuizListResponse(quizzes=service.list_quizzes(sport))


@router.post("/{sport}/{quiz_id}/start", response_model=QuizStartResponse)
def start_quiz(sport: Sport, quiz_id: str) -> QuizStartResponse:
    return QuizStartResponse.model_validate(service.start(sport, quiz_id))


@router.post("/{sport}/{quiz_id}/guess", response_model=QuizGuessResponse)
def guess(sport: Sport, quiz_id: str, payload: QuizGuessRequest) -> QuizGuessResponse:
    return QuizGuessResponse.model_validate(service.guess(sport, payload.game_id, payload.guess))


@router.post("/{sport}/{quiz_id}/finish", response_model=QuizFinishResponse)
def finish(sport: Sport, quiz_id: str, payload: QuizGuessRequest) -> QuizFinishResponse:
    return QuizFinishResponse.model_validate(service.finish(sport, payload.game_id))
