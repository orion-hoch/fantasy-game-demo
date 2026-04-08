"""Migration inventory routes."""

from fastapi import APIRouter

from src.migration.schemas import MigrationInventory
from src.migration.service import get_inventory


router = APIRouter(prefix="/migration", tags=["migration"])


@router.get("/inventory", response_model=MigrationInventory)
async def migration_inventory() -> MigrationInventory:
    return get_inventory()
