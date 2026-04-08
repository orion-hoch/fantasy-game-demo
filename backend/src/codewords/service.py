"""Code Words service layer using the legacy multiplayer engine."""

from __future__ import annotations

from fastapi import HTTPException

import codewords_game as codewords_mod


def _not_found(message: str = "Game not found") -> None:
    raise HTTPException(status_code=404, detail=message)


def _bad_request(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def state(game_id: str, token: str) -> dict:
    state_value = codewords_mod.get_game(game_id)
    if state_value is None:
        _not_found()
    return {"state": codewords_mod.view_state(state_value, token)}


def clue(game_id: str, token: str, clue_text: str, number: int) -> dict:
    state_value, err = codewords_mod.submit_clue(game_id, token, clue_text, number)
    if state_value is None:
        _not_found(err or "Game not found")
    return {"state": state_value, "error": err, "token": token}


def guess(game_id: str, token: str, index: int) -> dict:
    state_value, err = codewords_mod.submit_guess(game_id, token, index)
    if state_value is None:
        _not_found(err or "Game not found")
    return {"state": state_value, "error": err, "token": token}


def end_turn(game_id: str, token: str) -> dict:
    state_value, err = codewords_mod.end_turn(game_id, token)
    if state_value is None:
        _not_found(err or "Game not found")
    return {"state": state_value, "error": err, "token": token}
