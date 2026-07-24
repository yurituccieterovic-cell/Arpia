"""
Arpia — API FastAPI (ponto de entrada)
Conecta: Manga (PostgreSQL) | Socoboy (Telegram bot) | PAP Site | MEKY

Deploy: Railway → Procfile web process
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.routes import health, auth, chat, clube, semiotics, tasks, view, hardware, mc, governance, fractal, agents, conselho, crew2, hestia, arpia, animador as animador_route
from app.agents.animador import iniciar_loop, parar_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    await init_db()
    animador_task = asyncio.create_task(iniciar_loop())
    yield
    parar_loop()
    animador_task.cancel()
    await close_db()


def create_app() -> FastAPI:
    cfg = get_settings()

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.app_version,
        docs_url="/docs" if cfg.debug else None,   # docs só em debug
        redoc_url=None,
        lifespan=lifespan,
    )

    # ── CORS — permite o PAP site e o Socoboy ─────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Rotas ─────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(clube.router)
    app.include_router(semiotics.router)
    app.include_router(tasks.router)
    app.include_router(view.router)
    app.include_router(hardware.router)
    app.include_router(mc.router)
    app.include_router(governance.router)
    app.include_router(fractal.router)
    app.include_router(agents.router)
    app.include_router(conselho.router)
    app.include_router(crew2.router)
    app.include_router(hestia.router, prefix="/api")
    app.include_router(arpia.router)
    app.include_router(animador_route.router)

    @app.get("/")
    async def root():
        return {"arpia": cfg.app_version, "manga": "online"}

    return app


app = create_app()
