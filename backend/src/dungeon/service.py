"""Dungeon Adventure service layer using the legacy NFL/NBA engines."""

from __future__ import annotations

import sqlite3

from fastapi import HTTPException

import dungeon_adventure as nfl_dungeon
import nba_dungeon_adventure as nba_dungeon
from src.dungeon.schemas import Sport
from src.legacy.bridge import REPO_ROOT


DB_PATH = REPO_ROOT / "fantasy.db"


def _sync_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _module_for_sport(sport: Sport):
    return nfl_dungeon if sport == "nfl" else nba_dungeon


def _bad_request(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def rewards(sport: Sport, floor: int, items: list[dict]) -> dict:
    conn = _sync_db()
    try:
        data = _module_for_sport(sport).get_reward_options(conn, max(1, int(floor)), items)
    finally:
        conn.close()
    return {"rewards": data}


def encounter(sport: Sport, floor: int, items: list[dict], used_questions: list[str]) -> dict:
    conn = _sync_db()
    try:
        data = _module_for_sport(sport).get_encounter(conn, max(1, int(floor)), items, used_questions=used_questions)
    finally:
        conn.close()
    if not data:
        _bad_request("Could not build an encounter")
    return data


def answer(sport: Sport, question: dict, items: list[dict], answer_text: str) -> dict:
    if not answer_text.strip():
        _bad_request("Missing answer")
    conn = _sync_db()
    try:
        data = _module_for_sport(sport).check_answer(conn, question or {}, items, answer_text.strip())
    finally:
        conn.close()
    return data


def search(sport: Sport, query: str, items: list[dict], question: dict | None) -> dict:
    if not query.strip():
        return {"results": []}
    conn = _sync_db()
    try:
        data = _module_for_sport(sport).search_answers(conn, query.strip(), items, question=question)
    finally:
        conn.close()
    return {"results": data}
