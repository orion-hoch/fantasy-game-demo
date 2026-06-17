"""TTB service layer using the legacy NFL/NBA time bomb engines."""

from __future__ import annotations

import sqlite3

from fastapi import HTTPException

import nba_ttb as nba_ttb_mod
import ttb as ttb_mod
from src.player_search import search_players as search_all_players
from src.ttb.schemas import Sport
from src.legacy.bridge import REPO_ROOT


DB_PATH = REPO_ROOT / "data" / "fantasy.db"


def _sync_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _bad_request(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def _module_for_sport(sport: Sport):
    return ttb_mod if sport == "nfl" else nba_ttb_mod


def start_game(
    sport: Sport,
    mode: str = "classic",
    include_defense: bool = False,
    hard_mode: bool = False,
    min_draft_year: int | None = None,
) -> dict:
    module = _module_for_sport(sport)
    module.cleanup_old_games()
    conn = _sync_db()
    try:
        if sport == "nfl":
            game_id, clues, hints = module.start_game(
                conn,
                mode=mode,
                include_defense=include_defense,
                hard_mode=hard_mode,
                min_draft_year=min_draft_year,
            )
        else:
            game_id, clues, hints = module.start_game(
                conn,
                mode=mode,
                hard_mode=hard_mode,
                min_draft_year=min_draft_year,
            )
    finally:
        conn.close()
    if not game_id:
        _bad_request("Could not load a player")
    return {"game_id": game_id, "clues": clues, "hints": hints}


def guess(sport: Sport, game_id: str, guess_text: str, reveal: bool = False, skip: bool = False) -> dict:
    if not game_id:
        _bad_request("Missing game_id")
    module = _module_for_sport(sport)
    if reveal:
        return module.reveal_answer(game_id)
    if not skip and not guess_text:
        _bad_request("Missing guess")
    return module.check_guess(game_id, guess_text, skip=skip)


def search(sport: Sport, query: str) -> dict:
    conn = _sync_db()
    try:
        names = search_all_players(conn, sport, query)
    finally:
        conn.close()
    return {"results": [{"name": name} for name in names]}
