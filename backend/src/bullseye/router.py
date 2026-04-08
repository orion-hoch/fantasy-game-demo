"""FastAPI Bullseye routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.bullseye import service
from src.bullseye.schemas import (
    BullseyePickRequest,
    BullseyePickResponse,
    BullseyeSearchResponse,
    BullseyeSeasonsResponse,
    BullseyeStartRequest,
    BullseyeStartResponse,
    BullseyeStateResponse,
    BullseyeYearsResponse,
    Sport,
)


router = APIRouter(prefix="/bullseye", tags=["bullseye"])


@router.post("/{sport}/start", response_model=BullseyeStartResponse)
def start_game(sport: Sport, payload: BullseyeStartRequest) -> BullseyeStartResponse:
    return BullseyeStartResponse.model_validate(service.start_game(sport, payload.player_names, payload.player_tokens))


@router.get("/{sport}/state", response_model=BullseyeStateResponse)
def state(sport: Sport, game_id: str = Query(min_length=1)) -> BullseyeStateResponse:
    return BullseyeStateResponse.model_validate(service.state(sport, game_id))


@router.get("/{sport}/search", response_model=BullseyeSearchResponse)
def search(
    sport: Sport,
    game_id: str = Query(min_length=1),
    prompt_idx: int = Query(ge=0, le=4),
    q: str = Query(default=""),
) -> BullseyeSearchResponse:
    return BullseyeSearchResponse.model_validate(service.search(sport, game_id, prompt_idx, q.strip()))


@router.get("/{sport}/years", response_model=BullseyeYearsResponse)
def years(
    sport: Sport,
    game_id: str = Query(min_length=1),
    prompt_idx: int = Query(ge=0, le=4),
    player: str = Query(min_length=1),
) -> BullseyeYearsResponse:
    return BullseyeYearsResponse.model_validate(service.years(sport, game_id, prompt_idx, player.strip()))


@router.get("/{sport}/seasons", response_model=BullseyeSeasonsResponse)
def seasons(
    sport: Sport,
    game_id: str = Query(min_length=1),
    prompt_idx: int = Query(ge=0, le=4),
    player: str = Query(min_length=1),
) -> BullseyeSeasonsResponse:
    return BullseyeSeasonsResponse.model_validate(service.seasons(sport, game_id, prompt_idx, player.strip()))


@router.post("/{sport}/pick", response_model=BullseyePickResponse)
def pick(sport: Sport, payload: BullseyePickRequest) -> BullseyePickResponse:
    return BullseyePickResponse.model_validate(
        service.pick(
            sport,
            payload.game_id,
            payload.player_name,
            payload.season,
            payload.prompt_idx,
            payload.player_idx,
            payload.token,
        )
    )
