"""Chain game service layer using legacy categories and multiplayer engine."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException

from src.chain.schemas import Sport
from src.legacy.bridge import REPO_ROOT

import chain_categories as nfl_cc
import chain_game as chain_game_mod
import nba_chain_categories as nba_cc


DB_PATH = REPO_ROOT / "fantasy.db"


def _sync_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _categories_for_sport(sport: Sport):
    return nfl_cc if sport == "nfl" else nba_cc


def _bad_request(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def _not_found(message: str = "Game not found") -> None:
    raise HTTPException(status_code=404, detail=message)


def start_chain(sport: Sport) -> dict[str, Any]:
    conn = _sync_db()
    try:
        cat = _categories_for_sport(sport).get_start_category(conn)
    finally:
        conn.close()
    if not cat:
        _bad_request("Could not find a starting category")
    return {"category": cat, "valid_count": cat["valid_count"]}


def teammate_start(sport: Sport, player: str) -> dict[str, Any]:
    conn = _sync_db()
    try:
        cat = _categories_for_sport(sport).get_teammate_category(conn, player)
    finally:
        conn.close()
    if not cat:
        raise HTTPException(status_code=404, detail=f"No teammates found for {player}")
    return {"category": cat, "valid_count": cat["valid_count"]}


def guess(sport: Sport, payload: dict[str, Any]) -> dict[str, Any]:
    game_id = (payload.get("game_id") or "").strip()
    player_guess = (payload.get("player") or "").strip()

    if game_id:
        conn = _sync_db()
        try:
            state, err = chain_game_mod.submit_guess(conn, game_id, player_guess, player_token=payload.get("token"))
            conn.commit()
            return {"ok": err is None, "state": state, "error": err}
        finally:
            conn.close()

    chain = payload.get("chain", []) or []
    if not player_guess or not chain:
        _bad_request("Missing player or chain")

    used_players = set(payload.get("used_players", []) or [])
    cc = _categories_for_sport(sport)
    conn = _sync_db()
    try:
        valid_players = cc.get_players_for_chain(conn, chain) - used_players
        correct = player_guess in valid_players
        chain_length = len(chain)

        if correct:
            remaining = valid_players - {player_guess}
            exclude_ids = [link["id"] for link in chain]
            next_cat = None
            last_player = None

            if len(remaining) == 1:
                last_player = next(iter(remaining))
            elif len(remaining) >= 2:
                next_cat = cc.get_chain_category(conn, remaining, exclude_ids=exclude_ids)

            return {
                "correct": True,
                "valid_count": len(remaining),
                "next_category": next_cat,
                "chain_length": chain_length,
                "last_player": last_player,
                "examples": [],
            }

        link_results = cc.check_player_against_chain(conn, player_guess, chain)
        examples = sorted(list(valid_players))[:3]
        return {
            "correct": False,
            "valid_count": len(valid_players),
            "next_category": None,
            "chain_length": chain_length,
            "examples": examples,
            "link_results": link_results,
        }
    finally:
        conn.close()


def search(sport: Sport, term: str, game_id: str | None = None) -> dict[str, Any]:
    if not term:
        return {"results": []}
    conn = _sync_db()
    try:
        if game_id:
            names = chain_game_mod.search_players(conn, game_id, term)
        else:
            names = _categories_for_sport(sport).search_players(conn, term)
    finally:
        conn.close()
    return {"results": [{"name": name} for name in names]}


def state(game_id: str) -> dict[str, Any]:
    value = chain_game_mod.get_game(game_id)
    if value is None:
        _not_found()
    return {"state": value}
