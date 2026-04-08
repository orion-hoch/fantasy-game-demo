"""Bullseye service layer using legacy NFL/NBA Bullseye engines."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException

from src.bullseye.schemas import Sport
from src.legacy.bridge import REPO_ROOT

import nba_bullseye as nba_bull
import nfl_bullseye as nfl_bull


DB_PATH = REPO_ROOT / "fantasy.db"


def _sync_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _module_for_sport(sport: Sport):
    return nfl_bull if sport == "nfl" else nba_bull


def _bad_request(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def _not_found(message: str = "Game not found") -> None:
    raise HTTPException(status_code=404, detail=message)


def start_game(sport: Sport, player_names: list[str], player_tokens: list[str] | None = None) -> dict[str, Any]:
    module = _module_for_sport(sport)
    conn = _sync_db()
    try:
        game_id, state = module.start_game(conn, player_names, player_tokens=player_tokens)
        conn.commit()
        return {"game_id": game_id, "state": state}
    except Exception as exc:
        _bad_request(str(exc))
    finally:
        conn.close()


def state(sport: Sport, game_id: str) -> dict[str, Any]:
    module = _module_for_sport(sport)
    game_state = module.get_game(game_id)
    if game_state is None:
        _not_found()
    return {"state": game_state}


def search(sport: Sport, game_id: str, prompt_idx: int, query: str) -> dict[str, Any]:
    module = _module_for_sport(sport)
    conn = _sync_db()
    try:
        return {"results": module.search_players(conn, query, prompt_idx, game_id)}
    finally:
        conn.close()


def years(sport: Sport, game_id: str, prompt_idx: int, player_name: str) -> dict[str, Any]:
    module = _module_for_sport(sport)
    conn = _sync_db()
    try:
        return {"years": module.get_valid_years(conn, game_id, prompt_idx, player_name)}
    except Exception as exc:
        return {"years": [], "error": str(exc)}
    finally:
        conn.close()


def seasons(sport: Sport, game_id: str, prompt_idx: int, player_name: str) -> dict[str, Any]:
    module = _module_for_sport(sport)
    conn = _sync_db()
    try:
        return {"seasons": module.get_player_seasons(conn, game_id, prompt_idx, player_name)}
    finally:
        conn.close()


def pick(
    sport: Sport,
    game_id: str,
    player_name: str,
    season: int,
    prompt_idx: int,
    player_idx: int,
    token: str | None,
) -> dict[str, Any]:
    module = _module_for_sport(sport)
    conn = _sync_db()
    try:
        state, err = module.submit_pick(
            conn,
            game_id,
            player_name,
            season,
            prompt_idx=prompt_idx,
            player_idx=player_idx,
            actor_token=token,
        )
        conn.commit()
        return {"ok": err is None, "state": state, "msg": err or ""}
    except Exception as exc:
        _bad_request(str(exc))
    finally:
        conn.close()
