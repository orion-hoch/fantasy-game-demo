"""Service layer for the selected_quizzes (Sporcle-style) game."""

from __future__ import annotations

import json
import re
import secrets
import time
import unicodedata
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from session_store import GameStore
from src.legacy.bridge import REPO_ROOT
from src.selected_quizzes.schemas import Sport


QUIZZES_ROOT = REPO_ROOT / "quizzes"

_store = GameStore("selected_quizzes", ttl_seconds=4 * 60 * 60)

# quiz_id -> (mtime, parsed_quiz_dict)
_quiz_cache: dict[str, tuple[float, dict[str, Any]]] = {}

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.lower()
    folded = _PUNCT_RE.sub(" ", folded)
    folded = _WS_RE.sub(" ", folded).strip()
    return folded


def _quiz_path(sport: Sport, quiz_id: str) -> Path:
    if "/" in quiz_id or "\\" in quiz_id or quiz_id.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid quiz id")
    return QUIZZES_ROOT / sport / f"{quiz_id}.json"


def _load_quiz_file(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    answers = raw.get("answers") or []
    parsed_answers = []
    lookup: dict[str, int] = {}
    hint_keys: set[str] = set()
    for entry in answers:
        if isinstance(entry, str):
            canonical = entry
            aliases: list[str] = []
            hints: dict[str, str] | None = None
        else:
            canonical = str(entry.get("canonical", "")).strip()
            aliases = [str(a).strip() for a in (entry.get("aliases") or []) if str(a).strip()]
            raw_hints = entry.get("hints") or None
            hints = (
                {str(k): str(v) for k, v in raw_hints.items() if v is not None}
                if isinstance(raw_hints, dict) and raw_hints
                else None
            )
        if hints:
            hint_keys.update(hints.keys())
        if not canonical:
            continue
        idx = len(parsed_answers)
        parsed_answers.append({"canonical": canonical, "aliases": aliases, "hints": hints})
        for label in (canonical, *aliases):
            key = _normalize(label)
            if key and key not in lookup:
                lookup[key] = idx
    raw_default_order_hint = str(raw.get("default_order_hint_key") or "").strip()
    default_order_hint = raw_default_order_hint if raw_default_order_hint in hint_keys else None

    raw_default_order_direction = str(raw.get("default_order_direction") or "low").strip().lower()
    default_order_direction = raw_default_order_direction if raw_default_order_direction in {"low", "high"} else "low"

    return {
        "id": str(raw.get("id") or path.stem),
        "title": str(raw.get("title") or path.stem),
        "prompt": str(raw.get("prompt") or ""),
        "time_limit_seconds": int(raw.get("time_limit_seconds") or 180),
        "default_order_hint_key": default_order_hint,
        "default_order_direction": default_order_direction,
        "answers": parsed_answers,
        "lookup": lookup,
    }


def _get_quiz(sport: Sport, quiz_id: str) -> dict[str, Any]:
    path = _quiz_path(sport, quiz_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Quiz not found")
    cache_key = f"{sport}/{quiz_id}"
    mtime = path.stat().st_mtime
    cached = _quiz_cache.get(cache_key)
    if cached and cached[0] == mtime:
        return cached[1]
    quiz = _load_quiz_file(path)
    _quiz_cache[cache_key] = (mtime, quiz)
    return quiz


def list_quizzes(sport: Sport) -> list[dict[str, Any]]:
    sport_dir = QUIZZES_ROOT / sport
    if not sport_dir.exists():
        return []
    summaries = []
    for path in sorted(sport_dir.glob("*.json")):
        try:
            quiz = _get_quiz(sport, path.stem)
        except (HTTPException, json.JSONDecodeError, OSError):
            continue
        summaries.append({
            "id": quiz["id"],
            "title": quiz["title"],
            "prompt": quiz["prompt"],
            "time_limit_seconds": quiz["time_limit_seconds"],
            "total_answers": len(quiz["answers"]),
        })
    return summaries


def start(sport: Sport, quiz_id: str) -> dict[str, Any]:
    quiz = _get_quiz(sport, quiz_id)
    now = time.time()
    deadline = now + quiz["time_limit_seconds"]
    game_id = secrets.token_urlsafe(12)
    _store[game_id] = {
        "sport": sport,
        "quiz_id": quiz["id"],
        "started_at": now,
        "deadline": deadline,
        "found": [],
        "finished": False,
    }
    return {
        "game_id": game_id,
        "quiz_id": quiz["id"],
        "title": quiz["title"],
        "prompt": quiz["prompt"],
        "time_limit_seconds": quiz["time_limit_seconds"],
        "total_answers": len(quiz["answers"]),
        "deadline_ms": int(deadline * 1000),
        "slots": [{"hints": ans.get("hints")} for ans in quiz["answers"]],
        "default_order_hint_key": quiz.get("default_order_hint_key"),
        "default_order_direction": quiz.get("default_order_direction") or "low",
    }


def _load_session(game_id: str) -> dict[str, Any]:
    state = _store.get(game_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game not found")
    return state


def guess(sport: Sport, game_id: str, raw_guess: str) -> dict[str, Any]:
    state = _load_session(game_id)
    if state.get("sport") != sport:
        raise HTTPException(status_code=400, detail="Sport mismatch")
    quiz = _get_quiz(sport, state["quiz_id"])
    total = len(quiz["answers"])
    now = time.time()
    deadline = float(state.get("deadline", now))
    time_left = max(0, int(deadline - now))
    found: list[str] = list(state.get("found") or [])
    finished = bool(state.get("finished")) or now >= deadline or len(found) >= total

    matched: str | None = None
    matched_index: int | None = None
    duplicate = False

    if not finished:
        key = _normalize(raw_guess)
        if key:
            idx = quiz["lookup"].get(key)
            if idx is not None:
                canonical = quiz["answers"][idx]["canonical"]
                if canonical in found:
                    duplicate = True
                else:
                    matched = canonical
                    matched_index = idx
                    found.append(canonical)

    if len(found) >= total or now >= deadline:
        finished = True

    state["found"] = found
    state["finished"] = finished
    _store[game_id] = state

    return {
        "matched": matched,
        "matched_index": matched_index,
        "duplicate": duplicate,
        "found_count": len(found),
        "total_answers": total,
        "time_left_seconds": time_left,
        "finished": finished,
    }


def finish(sport: Sport, game_id: str) -> dict[str, Any]:
    state = _load_session(game_id)
    if state.get("sport") != sport:
        raise HTTPException(status_code=400, detail="Sport mismatch")
    quiz = _get_quiz(sport, state["quiz_id"])
    found = set(state.get("found") or [])
    started_at = float(state.get("started_at", time.time()))
    elapsed = max(0, int(time.time() - started_at))
    elapsed = min(elapsed, quiz["time_limit_seconds"])
    state["finished"] = True
    _store[game_id] = state
    return {
        "quiz_id": quiz["id"],
        "title": quiz["title"],
        "prompt": quiz["prompt"],
        "answers": [
            {
                "canonical": ans["canonical"],
                "found": ans["canonical"] in found,
                "hints": ans.get("hints"),
            }
            for ans in quiz["answers"]
        ],
        "found_count": len(found),
        "total_answers": len(quiz["answers"]),
        "elapsed_seconds": elapsed,
        "time_limit_seconds": quiz["time_limit_seconds"],
    }
