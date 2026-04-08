"""FastAPI routes for Balatro, plus compatibility legacy pages and aliases."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

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
compat_router = APIRouter(tags=["balatro-compat"])


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


@compat_router.get("/legacy-balatro/{sport}", response_class=HTMLResponse)
def legacy_balatro_page(sport: Sport):
    return HTMLResponse(service.legacy_page_html(sport))


def _compat_prefix(sport: Sport) -> str:
    return f"/{sport}_balatro" if sport == "nba" else "/nfl_balatro"


@compat_router.post("/api/nfl_balatro/start")
def compat_nfl_start(payload: BalatroStartRequest):
    return service.start_game("nfl", payload.mode)


@compat_router.post("/api/nfl_balatro/play_hand")
def compat_nfl_play_hand(payload: BalatroCardsRequest):
    return service.play_hand("nfl", payload.game_id, payload.card_ids)


@compat_router.post("/api/nfl_balatro/discard")
def compat_nfl_discard(payload: BalatroCardsRequest):
    return service.discard("nfl", payload.game_id, payload.card_ids)


@compat_router.post("/api/nfl_balatro/select_joker")
def compat_nfl_select_joker(payload: BalatroSelectJokerRequest):
    return service.select_joker("nfl", payload.game_id, payload.joker_id)


@compat_router.post("/api/nfl_balatro/preview")
def compat_nfl_preview(payload: BalatroCardsRequest):
    return service.preview("nfl", payload.game_id, payload.card_ids)


@compat_router.post("/api/nfl_balatro/leave_shop")
def compat_nfl_leave_shop(payload: BalatroGameIdRequest):
    return service.leave_shop("nfl", payload.game_id)


@compat_router.post("/api/nfl_balatro/buy_item")
def compat_nfl_buy_item(payload: BalatroBuyItemRequest):
    return service.buy_item("nfl", payload.model_dump())


@compat_router.post("/api/nfl_balatro/get_pool")
def compat_nfl_get_pool(payload: BalatroGameIdRequest):
    return service.get_pool("nfl", payload.game_id)


@compat_router.get("/api/nfl_balatro/player_seasons")
def compat_nfl_player_seasons(game_id: str = Query(min_length=1), card_id: str = Query(min_length=1)):
    return service.player_seasons("nfl", game_id, card_id)


@compat_router.get("/api/nfl_balatro/card_stats")
def compat_nfl_card_stats(player: str = Query(default=""), season: str = Query(default="")):
    return service.card_stats("nfl", player, season)


@compat_router.post("/api/nfl_balatro/sell_joker")
def compat_nfl_sell_joker(payload: BalatroSelectJokerRequest):
    return service.sell_joker("nfl", payload.game_id, payload.joker_id)


@compat_router.post("/api/nfl_balatro/restock_shop")
def compat_nfl_restock_shop(payload: BalatroGameIdRequest):
    return service.restock_shop("nfl", payload.game_id)


@compat_router.post("/api/nfl_balatro/open_pack")
def compat_nfl_open_pack(payload: BalatroPackRequest):
    return service.open_pack("nfl", payload.game_id, payload.pack_id)


@compat_router.post("/api/nfl_balatro/confirm_pack_picks")
def compat_nfl_confirm_pack_picks(payload: BalatroPackPicksRequest):
    return service.confirm_pack_picks("nfl", payload.game_id, payload.selected_ids)


@compat_router.post("/api/nfl_balatro/advance_fight")
def compat_nfl_advance_fight(payload: BalatroGameIdRequest):
    return service.advance_fight("nfl", payload.game_id)


@compat_router.post("/api/nfl_balatro/claim_reward")
def compat_nfl_claim_reward(payload: BalatroClaimRewardRequest):
    return service.claim_reward("nfl", payload.game_id, payload.choice, payload.joker_id)


@compat_router.post("/api/nfl_balatro/apply_division_sticker")
def compat_nfl_division_sticker(payload: BalatroDivisionStickerRequest):
    return service.apply_division_sticker("nfl", payload.game_id, payload.card_id, payload.new_division)


@compat_router.post("/api/nfl_balatro/start_infinity")
def compat_nfl_start_infinity(payload: BalatroGameIdRequest):
    return service.start_infinity("nfl", payload.game_id)


@compat_router.post("/api/nba_balatro/start")
def compat_nba_start(payload: BalatroStartRequest):
    return service.start_game("nba", payload.mode)


@compat_router.post("/api/nba_balatro/play_hand")
def compat_nba_play_hand(payload: BalatroCardsRequest):
    return service.play_hand("nba", payload.game_id, payload.card_ids)


@compat_router.post("/api/nba_balatro/discard")
def compat_nba_discard(payload: BalatroCardsRequest):
    return service.discard("nba", payload.game_id, payload.card_ids)


@compat_router.post("/api/nba_balatro/select_joker")
def compat_nba_select_joker(payload: BalatroSelectJokerRequest):
    return service.select_joker("nba", payload.game_id, payload.joker_id)


@compat_router.post("/api/nba_balatro/preview")
def compat_nba_preview(payload: BalatroCardsRequest):
    return service.preview("nba", payload.game_id, payload.card_ids)


@compat_router.post("/api/nba_balatro/leave_shop")
def compat_nba_leave_shop(payload: BalatroGameIdRequest):
    return service.leave_shop("nba", payload.game_id)


@compat_router.post("/api/nba_balatro/buy_item")
def compat_nba_buy_item(payload: BalatroBuyItemRequest):
    return service.buy_item("nba", payload.model_dump())


@compat_router.post("/api/nba_balatro/use_held_item")
def compat_nba_use_held_item(payload: BalatroUseHeldItemRequest):
    return service.use_held_item("nba", payload.model_dump())


@compat_router.post("/api/nba_balatro/get_pool")
def compat_nba_get_pool(payload: BalatroGameIdRequest):
    return service.get_pool("nba", payload.game_id)


@compat_router.get("/api/nba_balatro/player_seasons")
def compat_nba_player_seasons(game_id: str = Query(min_length=1), card_id: str = Query(min_length=1)):
    return service.player_seasons("nba", game_id, card_id)


@compat_router.get("/api/nba_balatro/card_stats")
def compat_nba_card_stats(player: str = Query(default=""), season: str = Query(default="")):
    return service.card_stats("nba", player, season)


@compat_router.post("/api/nba_balatro/sell_joker")
def compat_nba_sell_joker(payload: BalatroSelectJokerRequest):
    return service.sell_joker("nba", payload.game_id, payload.joker_id)


@compat_router.post("/api/nba_balatro/restock_shop")
def compat_nba_restock_shop(payload: BalatroGameIdRequest):
    return service.restock_shop("nba", payload.game_id)


@compat_router.post("/api/nba_balatro/open_pack")
def compat_nba_open_pack(payload: BalatroPackRequest):
    return service.open_pack("nba", payload.game_id, payload.pack_id)


@compat_router.post("/api/nba_balatro/confirm_pack_picks")
def compat_nba_confirm_pack_picks(payload: BalatroPackPicksRequest):
    return service.confirm_pack_picks("nba", payload.game_id, payload.selected_ids)


@compat_router.post("/api/nba_balatro/advance_fight")
def compat_nba_advance_fight(payload: BalatroGameIdRequest):
    return service.advance_fight("nba", payload.game_id)


@compat_router.post("/api/nba_balatro/claim_reward")
def compat_nba_claim_reward(payload: BalatroClaimRewardRequest):
    return service.claim_reward("nba", payload.game_id, payload.choice, payload.joker_id)


@compat_router.post("/api/nba_balatro/apply_division_sticker")
def compat_nba_division_sticker(payload: BalatroDivisionStickerRequest):
    return service.apply_division_sticker("nba", payload.game_id, payload.card_id, payload.new_division)


@compat_router.post("/api/nba_balatro/start_infinity")
def compat_nba_start_infinity(payload: BalatroGameIdRequest):
    return service.start_infinity("nba", payload.game_id)
