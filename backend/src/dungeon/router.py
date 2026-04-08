"""FastAPI routes for Dungeon Adventure."""

from __future__ import annotations

from fastapi import APIRouter

from src.dungeon import service
from src.dungeon.schemas import (
    DungeonAnswerRequest,
    DungeonEncounterRequest,
    DungeonRewardsRequest,
    DungeonRewardsResponse,
    DungeonSearchRequest,
    DungeonSearchResponse,
    Sport,
)


router = APIRouter(prefix="/dungeon", tags=["dungeon"])


@router.post("/{sport}/rewards", response_model=DungeonRewardsResponse)
def rewards(sport: Sport, payload: DungeonRewardsRequest) -> DungeonRewardsResponse:
    return DungeonRewardsResponse.model_validate(service.rewards(sport, payload.floor, payload.items))


@router.post("/{sport}/encounter")
def encounter(sport: Sport, payload: DungeonEncounterRequest):
    return service.encounter(sport, payload.floor, payload.items, payload.used_questions)


@router.post("/{sport}/answer")
def answer(sport: Sport, payload: DungeonAnswerRequest):
    return service.answer(sport, payload.question, payload.items, payload.answer)


@router.post("/{sport}/search", response_model=DungeonSearchResponse)
def search(sport: Sport, payload: DungeonSearchRequest) -> DungeonSearchResponse:
    return DungeonSearchResponse.model_validate(service.search(sport, payload.query, payload.items, payload.question))
