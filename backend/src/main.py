"""FastAPI strangler backend entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.legacy.bridge import REPO_ROOT  # must be first — adds repo root to sys.path

from src.balatro.router import compat_router as balatro_compat_router
from src.balatro.router import router as balatro_router
from src.bullseye.router import router as bullseye_router
from src.chain.router import router as chain_router
from src.codewords.router import router as codewords_router
from src.dungeon.router import router as dungeon_router
from src.fantasy_duel.router import router as fantasy_duel_router
from src.lobbies.router import router as lobbies_router
from src.migration.router import router as migration_router
from src.ttb.router import router as ttb_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hook for the strangler backend."""
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(migration_router, prefix=settings.api_prefix)
app.include_router(lobbies_router, prefix=settings.api_prefix)
app.include_router(balatro_router, prefix=settings.api_prefix)
app.include_router(bullseye_router, prefix=settings.api_prefix)
app.include_router(fantasy_duel_router, prefix=settings.api_prefix)
app.include_router(chain_router, prefix=settings.api_prefix)
app.include_router(codewords_router, prefix=settings.api_prefix)
app.include_router(ttb_router, prefix=settings.api_prefix)
app.include_router(dungeon_router, prefix=settings.api_prefix)
app.include_router(balatro_compat_router)
app.mount("/static", StaticFiles(directory=str(REPO_ROOT / "static")), name="legacy-static-root")
app.mount("/legacy-static", StaticFiles(directory=str(REPO_ROOT / "static")), name="legacy-static")


@app.get("/")
async def root():
    return {"status": "ok", "app": settings.app_name, "mode": "strangler"}


@app.get("/health")
async def health():
    return {"status": "healthy", "mode": "strangler", "api_prefix": settings.api_prefix}
