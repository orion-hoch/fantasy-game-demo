"""Fantasy Duel service layer using legacy Starting 6 / Starting 5 engines."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException

from src.fantasy_duel.schemas import Sport
from src.legacy.bridge import REPO_ROOT
from src.player_search import search_players as search_all_players

import nba_starting5_game as nba_game
import starting6_game as nfl_game


DB_PATH = REPO_ROOT / "fantasy.db"


def _sync_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _module_for_sport(sport: Sport):
    return nfl_game if sport == "nfl" else nba_game


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


def get_state(sport: Sport, game_id: str) -> dict[str, Any]:
    module = _module_for_sport(sport)
    state = module.get_game(game_id)
    if state is None:
        _not_found()
    return {"state": state}


def search_players(sport: Sport, game_id: str, query: str) -> dict[str, Any]:
    conn = _sync_db()
    try:
        return {"results": search_all_players(conn, sport, query)}
    finally:
        conn.close()


def get_years(sport: Sport, game_id: str, player_name: str) -> dict[str, Any]:
    module = _module_for_sport(sport)
    conn = _sync_db()
    try:
        return {"years": module.get_years(conn, game_id, player_name)}
    finally:
        conn.close()


def submit_pick(sport: Sport, game_id: str, player_name: str, season: int, token: str | None) -> dict[str, Any]:
    module = _module_for_sport(sport)
    conn = _sync_db()
    try:
        state, err = module.submit_pick(conn, game_id, player_name, season, player_token=token)
        conn.commit()
        return {"ok": err is None, "state": state, "msg": err or ""}
    except Exception as exc:
        _bad_request(str(exc))
    finally:
        conn.close()


def pass_turn(sport: Sport, game_id: str, token: str | None) -> dict[str, Any]:
    module = _module_for_sport(sport)
    conn = _sync_db()
    try:
        state, err = module.pass_turn(conn, game_id, player_token=token)
        conn.commit()
        return {"ok": err is None, "state": state, "msg": err or ""}
    except Exception as exc:
        _bad_request(str(exc))
    finally:
        conn.close()
