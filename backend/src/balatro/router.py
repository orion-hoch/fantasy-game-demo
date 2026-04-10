"""FastAPI routes for Balatro."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.balatro import service
from src.balatro.schemas import (
    BalatroBuyItemRequest,
    BalatroCardLookupRequest,
    BalatroCardStatsQuery,
    BalatroCardsRequest,
    BalatroClaimRewardRequest,
    BalatroDivisionStickerRequest,
    BalatroGameIdRequest,
    BalatroPackPicksRequest,
    BalatroPackRequest,
    BalatroSelectJokerRequest,
    BalatroStartRequest,
    BalatroUseHeldItemRequest,
    Sport,
)


router = APIRouter(prefix="/balatro", tags=["balatro"])


@router.post("/{sport}/start")
def start_game(sport: Sport, payload: BalatroStartRequest):
    return service.start_game(sport, payload.mode)


@router.post("/{sport}/play_hand")
def play_hand(sport: Sport, payload: BalatroCardsRequest):
    return service.play_hand(sport, payload.game_id, payload.card_ids)


@router.post("/{sport}/discard")
def discard(sport: Sport, payload: BalatroCardsRequest):
    return service.discard(sport, payload.game_id, payload.card_ids)


@router.post("/{sport}/select_joker")
def select_joker(sport: Sport, payload: BalatroSelectJokerRequest):
    return service.select_joker(sport, payload.game_id, payload.joker_id)


@router.post("/{sport}/preview")
def preview(sport: Sport, payload: BalatroCardsRequest):
    return service.preview(sport, payload.game_id, payload.card_ids)


@router.post("/{sport}/leave_shop")
def leave_shop(sport: Sport, payload: BalatroGameIdRequest):
    return service.leave_shop(sport, payload.game_id)


@router.post("/{sport}/buy_item")
def buy_item(sport: Sport, payload: BalatroBuyItemRequest):
    return service.buy_item(sport, payload.model_dump())


@router.post("/{sport}/use_held_item")
def use_held_item(sport: Sport, payload: BalatroUseHeldItemRequest):
    return service.use_held_item(sport, payload.model_dump())


@router.post("/{sport}/get_pool")
def get_pool(sport: Sport, payload: BalatroGameIdRequest):
    return service.get_pool(sport, payload.game_id)


@router.get("/{sport}/player_seasons")
def player_seasons(sport: Sport, game_id: str = Query(min_length=1), card_id: str = Query(min_length=1)):
    return service.player_seasons(sport, game_id, card_id)


@router.get("/{sport}/card_stats")
def card_stats(sport: Sport, player: str = Query(default=""), season: str = Query(default="")):
    return service.card_stats(sport, player, season)


@router.post("/{sport}/sell_joker")
def sell_joker(sport: Sport, payload: BalatroSelectJokerRequest):
    return service.sell_joker(sport, payload.game_id, payload.joker_id)


@router.post("/{sport}/restock_shop")
def restock_shop(sport: Sport, payload: BalatroGameIdRequest):
    return service.restock_shop(sport, payload.game_id)


@router.post("/{sport}/open_pack")
def open_pack(sport: Sport, payload: BalatroPackRequest):
    return service.open_pack(sport, payload.game_id, payload.pack_id)


@router.post("/{sport}/confirm_pack_picks")
def confirm_pack_picks(sport: Sport, payload: BalatroPackPicksRequest):
    return service.confirm_pack_picks(sport, payload.game_id, payload.selected_ids)


@router.post("/{sport}/advance_fight")
def advance_fight(sport: Sport, payload: BalatroGameIdRequest):
    return service.advance_fight(sport, payload.game_id)


@router.post("/{sport}/claim_reward")
def claim_reward(sport: Sport, payload: BalatroClaimRewardRequest):
    return service.claim_reward(sport, payload.game_id, payload.choice, payload.joker_id)


@router.post("/{sport}/apply_division_sticker")
def apply_division_sticker(sport: Sport, payload: BalatroDivisionStickerRequest):
    return service.apply_division_sticker(sport, payload.game_id, payload.card_id, payload.new_division)


@router.post("/{sport}/start_infinity")
def start_infinity(sport: Sport, payload: BalatroGameIdRequest):
    return service.start_infinity(sport, payload.game_id)


