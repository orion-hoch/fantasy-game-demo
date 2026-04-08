"""FastAPI routes for TTB."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.ttb import service
from src.ttb.schemas import Sport, TTBGuessRequest, TTBSearchResponse, TTBStartRequest, TTBStartResponse


router = APIRouter(prefix="/ttb", tags=["ttb"])


@router.post("/{sport}/start", response_model=TTBStartResponse)
def start_game(sport: Sport, payload: TTBStartRequest) -> TTBStartResponse:
    return TTBStartResponse.model_validate(
        service.start_game(
            sport,
            mode=payload.mode,
            include_defense=payload.include_defense,
            hard_mode=payload.hard_mode,
            min_draft_year=payload.min_draft_year,
        )
    )


@router.post("/{sport}/guess")
def guess(sport: Sport, payload: TTBGuessRequest):
    return service.guess(sport, payload.game_id, payload.guess.strip(), reveal=payload.reveal, skip=payload.skip)


@router.get("/{sport}/search", response_model=TTBSearchResponse)
def search(sport: Sport, q: str = Query(default="")) -> TTBSearchResponse:
    return TTBSearchResponse.model_validate(service.search(sport, q.strip()))
