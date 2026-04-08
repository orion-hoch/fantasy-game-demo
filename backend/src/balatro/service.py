"""Balatro service layer using legacy NFL/NBA Balatro engines."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import HTTPException

import nba_balatro as nba_b
import nfl_balatro as nfl_b
from src.balatro.schemas import Sport
from src.legacy.bridge import REPO_ROOT


DB_PATH = REPO_ROOT / "fantasy.db"
TEMPLATE_DIR = REPO_ROOT / "templates"


def _sync_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _module_for_sport(sport: Sport):
    return nfl_b if sport == "nfl" else nba_b


def _bad_request(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def _not_found(message: str = "Game not found") -> None:
    raise HTTPException(status_code=404, detail=message)


def _serialize_start(sport: Sport, game_id: str, state: dict) -> dict:
    payload = {
        "game_id": game_id,
        "mode": state.get("mode", "normal"),
        "floor": state["floor"],
        "round": state.get("round", 1),
        "fight": state.get("fight", 1),
        "boss_effect": state.get("boss_effect"),
        "level_name": state["level_name"],
        "target_score": state["target_score"],
        "hands_remaining": state["hands_remaining"],
        "discards_remaining": state["discards_remaining"],
        "hand": state["hand"],
        "jokers": [],
        "coins": state["coins"],
        "skill_levels": state["skill_levels"],
        "combo_boosts": state["combo_boosts"],
        "card_effects": state["card_effects"],
        "status": state["status"],
        "max_hand_size": state.get("max_hand_size", 7),
        "base_discards": state.get("base_discards", 3),
        "max_jokers": state.get("max_jokers", 5),
        "joker_state": state.get("joker_state", {}),
        "deck_cards": state.get("deck", []),
        "fight_discards": state.get("fight_discards", []),
        "fight_played": state.get("fight_played", []),
    }
    if sport == "nfl":
        payload["held_cards"] = state.get("held_cards", [])
    else:
        payload["held_items"] = state.get("held_items", [])
        payload["deck_pool"] = state.get("deck_pool", [])
    return payload


def start_game(sport: Sport, mode: str = "normal") -> dict:
    module = _module_for_sport(sport)
    module.cleanup_old_games()
    conn = _sync_db()
    try:
        if sport == "nfl":
            game_id, state = module.start_game(conn, mode=mode)
        else:
            game_id, state = module.start_game(conn)
    finally:
        conn.close()
    return _serialize_start(sport, game_id, state)


def play_hand(sport: Sport, game_id: str, card_ids: list[str]) -> dict:
    module = _module_for_sport(sport)
    result, err = module.play_hand(game_id, card_ids)
    if err:
        _bad_request(err)
    if sport == "nfl":
        g = module.get_state(game_id)
        if g:
            result["hand"] = g["hand"]
    return result


def discard(sport: Sport, game_id: str, card_ids: list[str]) -> dict:
    result, err = _module_for_sport(sport).discard_cards(game_id, card_ids)
    if err:
        _bad_request(err)
    return result


def select_joker(sport: Sport, game_id: str, joker_id: str) -> dict:
    module = _module_for_sport(sport)
    result, err = module.select_joker(game_id, joker_id)
    if err:
        _bad_request(err)
    if sport == "nfl":
        conn = _sync_db()
        try:
            shop_items = module.generate_shop_for_game(game_id, conn)
        finally:
            conn.close()
        result["shop_items"] = shop_items or []
    return result


def preview(sport: Sport, game_id: str, card_ids: list[str]) -> dict:
    module = _module_for_sport(sport)
    g = module.get_state(game_id)
    if not g:
        _not_found()
    played = [c for c in g["hand"] if c["id"] in set(card_ids)]
    return module.get_score_preview(
        played,
        g["jokers"],
        skill_levels=g.get("skill_levels", {}),
        combo_boosts=g.get("combo_boosts", {}),
        card_effects=g.get("card_effects", {}),
        joker_state=g.get("joker_state", {}),
        floor=g.get("floor", 1),
        joker_enhancements=g.get("joker_enhancements", {}),
    )


def leave_shop(sport: Sport, game_id: str) -> dict:
    result, err = _module_for_sport(sport).leave_shop(game_id)
    if err:
        _bad_request(err)
    return result


def buy_item(sport: Sport, payload: dict) -> dict:
    module = _module_for_sport(sport)
    conn = _sync_db()
    try:
        if sport == "nfl":
            result, err = module.buy_shop_item(
                payload["game_id"],
                payload["item_type"],
                payload["shop_id"],
                target_card_id=payload.get("target_card_id"),
                target_year=payload.get("target_year"),
                conn=conn,
                new_pos=payload.get("new_pos"),
            )
        else:
            result, err = module.buy_shop_item(
                payload["game_id"],
                payload["item_type"],
                payload["shop_id"],
                target_card_id=payload.get("target_card_id"),
                target_year=payload.get("target_year"),
                conn=conn,
            )
    finally:
        conn.close()
    if err:
        _bad_request(err)
    return result


def use_held_item(sport: Sport, payload: dict) -> dict:
    if sport != "nba":
        _bad_request("Held items are only available in NBA Balatro")
    conn = _sync_db()
    try:
        result, err = nba_b.use_held_item(
            payload["game_id"],
            payload["held_id"],
            payload.get("target_card_id"),
            payload.get("target_year"),
            conn,
            payload.get("discard_only", False),
            new_pos=payload.get("new_pos"),
        )
    finally:
        conn.close()
    if err:
        _bad_request(err)
    return result


def get_pool(sport: Sport, game_id: str) -> dict:
    result, err = _module_for_sport(sport).get_pool(game_id)
    if err:
        raise HTTPException(status_code=404 if sport == "nfl" else 400, detail=err)
    return result


def player_seasons(sport: Sport, game_id: str, card_id: str) -> dict:
    module = _module_for_sport(sport)
    g = module.get_state(game_id)
    if not g:
        _not_found()
    card = next((c for c in g["deck_pool"] if c["id"] == card_id), None)
    if not card:
        _not_found("Card not found")
    conn = _sync_db()
    try:
        seasons = module.get_player_seasons(conn, card["player"])
    finally:
        conn.close()
    return {"seasons": seasons, "current_season": card["season"]}


def card_stats(sport: Sport, player: str, season: str) -> dict:
    if not player or not season:
        _bad_request("Missing params")
    conn = _sync_db()
    try:
        stats = _module_for_sport(sport).get_card_stats(conn, player, season)
    finally:
        conn.close()
    return stats or {}


def sell_joker(sport: Sport, game_id: str, joker_id: str) -> dict:
    result, err = _module_for_sport(sport).sell_joker(game_id, joker_id)
    if err:
        _bad_request(err)
    return result


def restock_shop(sport: Sport, game_id: str) -> dict:
    conn = _sync_db()
    try:
        result, err = _module_for_sport(sport).restock_shop(game_id, conn)
    finally:
        conn.close()
    if err:
        _bad_request(err)
    return result


def open_pack(sport: Sport, game_id: str, pack_id: str) -> dict:
    conn = _sync_db()
    try:
        result, err = _module_for_sport(sport).open_pack(game_id, pack_id, conn)
    finally:
        conn.close()
    if err:
        _bad_request(err)
    return result


def confirm_pack_picks(sport: Sport, game_id: str, selected_ids: list[str]) -> dict:
    result, err = _module_for_sport(sport).confirm_pack_picks(game_id, selected_ids)
    if err:
        _bad_request(err)
    return result


def advance_fight(sport: Sport, game_id: str) -> dict:
    result, err = _module_for_sport(sport).advance_fight(game_id)
    if err:
        _bad_request(err)
    return result


def claim_reward(sport: Sport, game_id: str, choice: str, joker_id: str | None = None) -> dict:
    conn = _sync_db()
    try:
        result, err = _module_for_sport(sport).claim_fight_reward(game_id, choice, joker_id, conn)
    finally:
        conn.close()
    if err:
        _bad_request(err)
    return result


def apply_division_sticker(sport: Sport, game_id: str, card_id: str, new_division: str) -> dict:
    return _module_for_sport(sport).apply_division_sticker(game_id, card_id, new_division)


def start_infinity(sport: Sport, game_id: str) -> dict:
    result, err = _module_for_sport(sport).start_infinity_mode(game_id)
    if err:
        _bad_request(err)
    return result


def legacy_page_html(sport: Sport) -> str:
    template_name = "nfl_balatro.html" if sport == "nfl" else "nba_balatro.html"
    html = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    html = html.replace('href="/?tab=nfl" class="back-link">&#8592; Back</a>', 'href="#" class="back-link" onclick="window.top.history.back(); return false;">&#8592; Back</a>')
    html = html.replace('href="/?tab=nba" class="back-link">&#8592; Back</a>', 'href="#" class="back-link" onclick="window.top.history.back(); return false;">&#8592; Back</a>')
    return html
