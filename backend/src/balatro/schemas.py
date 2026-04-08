"""Pydantic schemas for Balatro routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Sport = Literal["nfl", "nba"]


class BalatroStartRequest(BaseModel):
    mode: str = Field(default="normal")


class BalatroGameIdRequest(BaseModel):
    game_id: str = Field(min_length=1)


class BalatroCardsRequest(BaseModel):
    game_id: str = Field(min_length=1)
    card_ids: list[str] = Field(default_factory=list)


class BalatroSelectJokerRequest(BaseModel):
    game_id: str = Field(min_length=1)
    joker_id: str = Field(default="skip")


class BalatroBuyItemRequest(BaseModel):
    game_id: str = Field(min_length=1)
    shop_id: str = Field(default="")
    item_type: str = Field(default="")
    target_card_id: str | None = None
    target_year: int | None = None
    new_pos: str | None = None


class BalatroUseHeldItemRequest(BaseModel):
    game_id: str = Field(min_length=1)
    held_id: str = Field(default="")
    target_card_id: str | None = None
    target_year: int | None = None
    discard_only: bool = False
    new_pos: str | None = None


class BalatroPackRequest(BaseModel):
    game_id: str = Field(min_length=1)
    pack_id: str = Field(default="")


class BalatroPackPicksRequest(BaseModel):
    game_id: str = Field(min_length=1)
    selected_ids: list[str] = Field(default_factory=list)


class BalatroClaimRewardRequest(BaseModel):
    game_id: str = Field(min_length=1)
    choice: str = Field(default="")
    joker_id: str | None = None


class BalatroCardLookupRequest(BaseModel):
    game_id: str = Field(min_length=1)
    card_id: str = Field(min_length=1)


class BalatroCardStatsQuery(BaseModel):
    player: str
    season: str


class BalatroDivisionStickerRequest(BaseModel):
    game_id: str = Field(min_length=1)
    card_id: str = Field(min_length=1)
    new_division: str = Field(min_length=1)
