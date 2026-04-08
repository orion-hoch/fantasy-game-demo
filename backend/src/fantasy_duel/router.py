"""FastAPI routes for Fantasy Duel."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.fantasy_duel import service
from src.fantasy_duel.schemas import (
    FantasyDuelPassRequest,
    FantasyDuelPickRequest,
    FantasyDuelPickResponse,
    FantasyDuelSearchResponse,
    FantasyDuelStartRequest,
    FantasyDuelStartResponse,
    FantasyDuelStateResponse,
    FantasyDuelYearsResponse,
    Sport,
)


router = APIRouter(prefix="/fantasy-duel", tags=["fantasy-duel"])


@router.post("/{sport}/start", response_model=FantasyDuelStartResponse)
def start_game(sport: Sport, payload: FantasyDuelStartRequest) -> FantasyDuelStartResponse:
    return FantasyDuelStartResponse.model_validate(service.start_game(sport, payload.player_names, payload.player_tokens))


@router.get("/{sport}/state", response_model=FantasyDuelStateResponse)
def get_state(sport: Sport, game_id: str = Query(min_length=1)) -> FantasyDuelStateResponse:
    return FantasyDuelStateResponse.model_validate(service.get_state(sport, game_id))


@router.get("/{sport}/search", response_model=FantasyDuelSearchResponse)
def search_players(sport: Sport, game_id: str = Query(min_length=1), q: str = Query(default="")) -> FantasyDuelSearchResponse:
    return FantasyDuelSearchResponse.model_validate(service.search_players(sport, game_id, q.strip()))


@router.get("/{sport}/years", response_model=FantasyDuelYearsResponse)
def get_years(sport: Sport, game_id: str = Query(min_length=1), player: str = Query(min_length=1)) -> FantasyDuelYearsResponse:
    return FantasyDuelYearsResponse.model_validate(service.get_years(sport, game_id, player.strip()))


@router.post("/{sport}/pick", response_model=FantasyDuelPickResponse)
def submit_pick(sport: Sport, payload: FantasyDuelPickRequest) -> FantasyDuelPickResponse:
    return FantasyDuelPickResponse.model_validate(service.submit_pick(sport, payload.game_id, payload.player_name, payload.season, payload.token))


@router.post("/{sport}/pass", response_model=FantasyDuelPickResponse)
def pass_turn(sport: Sport, payload: FantasyDuelPassRequest) -> FantasyDuelPickResponse:
    return FantasyDuelPickResponse.model_validate(service.pass_turn(sport, payload.game_id, payload.token))
