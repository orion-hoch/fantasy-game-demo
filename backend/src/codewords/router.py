"""FastAPI routes for Code Words."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

import codewords_game as codewords_mod

from src.codewords import service
from src.codewords.schemas import (
    CodewordsActionResponse,
    CodewordsClueRequest,
    CodewordsEndTurnRequest,
    CodewordsGuessRequest,
    CodewordsStateResponse,
)


router = APIRouter(prefix="/codewords", tags=["codewords"])


@router.get("/state", response_model=CodewordsStateResponse)
def state(game_id: str = Query(min_length=1), token: str = Query(default="")) -> CodewordsStateResponse:
    return CodewordsStateResponse.model_validate(service.state(game_id, token))


@router.post("/clue", response_model=CodewordsActionResponse)
def clue(payload: CodewordsClueRequest) -> CodewordsActionResponse:
    result = service.clue(payload.game_id, payload.token, payload.clue, payload.number)
    if result["error"]:
        return JSONResponse({"error": result["error"], "state": codewords_mod.view_state(result["state"], result["token"] )}, status_code=400)
    return CodewordsActionResponse.model_validate({"state": codewords_mod.view_state(result["state"], result["token"])})


@router.post("/guess", response_model=CodewordsActionResponse)
def guess(payload: CodewordsGuessRequest) -> CodewordsActionResponse:
    result = service.guess(payload.game_id, payload.token, payload.index)
    if result["error"]:
        return JSONResponse({"error": result["error"], "state": codewords_mod.view_state(result["state"], result["token"] )}, status_code=400)
    return CodewordsActionResponse.model_validate({"state": codewords_mod.view_state(result["state"], result["token"])})


@router.post("/end_turn", response_model=CodewordsActionResponse)
def end_turn(payload: CodewordsEndTurnRequest) -> CodewordsActionResponse:
    result = service.end_turn(payload.game_id, payload.token)
    if result["error"]:
        return JSONResponse({"error": result["error"], "state": codewords_mod.view_state(result["state"], result["token"] )}, status_code=400)
    return CodewordsActionResponse.model_validate({"state": codewords_mod.view_state(result["state"], result["token"])})
