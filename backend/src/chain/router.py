"""FastAPI routes for Chain."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.chain import service
from src.chain.schemas import ChainGuessRequest, ChainSearchResponse, ChainStateResponse, ChainTeammateRequest, Sport


router = APIRouter(prefix="/chain", tags=["chain"])


@router.post("/{sport}/start")
def start_chain(sport: Sport):
    return service.start_chain(sport)


@router.post("/{sport}/guess")
def guess_chain(sport: Sport, payload: ChainGuessRequest):
    return service.guess(sport, payload.model_dump())


@router.post("/{sport}/teammate_start")
def teammate_start(sport: Sport, payload: ChainTeammateRequest):
    return service.teammate_start(sport, payload.player.strip())


@router.get("/{sport}/search", response_model=ChainSearchResponse)
def search_chain(sport: Sport, q: str = Query(default=""), game_id: str = Query(default="")) -> ChainSearchResponse:
    return ChainSearchResponse.model_validate(service.search(sport, q.strip(), game_id.strip() or None))


@router.get("/{sport}/state", response_model=ChainStateResponse)
def state_chain(sport: Sport, game_id: str = Query(min_length=1)) -> ChainStateResponse:
    return ChainStateResponse.model_validate(service.state(game_id))
