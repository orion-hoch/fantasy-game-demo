"""Pydantic schemas for migration inventory endpoints."""

from pydantic import BaseModel


class SurfaceSummary(BaseModel):
    name: str
    legacy_route: str
    target_route: str
    status: str
    notes: str


class MigrationInventory(BaseModel):
    strategy: str
    next_slice: list[str]
    surfaces: list[SurfaceSummary]
