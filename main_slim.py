"""
ARPIA — Entry point para Render.
Sobe o app completo mas com init_db não-fatal e sem travar o healthcheck.
"""
import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("arpia")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # init_db com timeout — não bloqueia o healthcheck
    try:
        await asyncio.wait_for(init_db(), timeout=10.0)
        logger.info("DB OK")
    except Exception as e:
        logger.error(f"init_db skipped: {e}")
    yield
    await close_db()


app = FastAPI(title="Arpia", lifespan=lifespan)
cfg = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.allowed_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# ── Health (sempre responde) ──────────────────────────────────────────────────
from app.routes import health as health_route
app.include_router(health_route.router)

# ── Rotas principais ─────────────────────────────────────────────────────────
ROUTES_TO_LOAD = [
    ("app.routes.conselho", "router"),
    ("app.routes.crew2", "router"),
    ("app.routes.auth", "router"),
    ("app.routes.chat", "router"),
    ("app.routes.arpia", "router"),
    ("app.routes.agents", "router"),
    ("app.routes.fluencia", "router"),
    ("app.routes.governance", "router"),
    ("app.routes.tasks", "router"),
    ("app.routes.semiotics", "router"),
    ("app.routes.fractal", "router"),
    ("app.routes.view", "router"),
    ("app.routes.hestia", "router"),
    ("app.routes.mc", "router"),
    ("app.routes.clube", "router"),
    ("app.routes.animador", "router"),
    ("app.routes.hardware", "router"),
]

for mod_path, attr in ROUTES_TO_LOAD:
    try:
        import importlib
        mod = importlib.import_module(mod_path)
        router = getattr(mod, attr)
        if mod_path == "app.routes.hestia":
            app.include_router(router, prefix="/api")
        else:
            app.include_router(router)
        logger.info(f"Loaded: {mod_path}")
    except Exception as e:
        logger.error(f"Skipped {mod_path}: {e}")
