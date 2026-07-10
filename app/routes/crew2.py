"""
Crew 2 — Endpoints da Persona Fascinante.

POST /api/crew2/run              — executa o crew completo
POST /api/crew2/teorizar         — teorização contínua (background)
POST /api/crew2/observar         — scan do mundo externo
POST /api/crew2/conectar         — decisões de relações sociais
GET  /api/crew2/agentes          — lista os 8 agentes e seus papéis
"""
import asyncio
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import os

router = APIRouter(prefix="/api/crew2", tags=["crew2"])

BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")


def _check_secret(secret: Optional[str]):
    if BRIDGE_SECRET and secret != BRIDGE_SECRET:
        raise HTTPException(status_code=401, detail="x-bridge-secret inválido")


class RunInput(BaseModel):
    input: str
    contexto: str = ""
    publicar_bluesky: bool = False
    modo: str = "responder"  # 'responder' | 'teorizar' | 'observar' | 'conectar'


# ── GET: agentes ───────────────────────────────────────────────────────────────

@router.get("/agentes")
async def listar_agentes():
    """Lista os 8 agentes do Crew 2 com seus papéis."""
    return {
        "crew": "Crew 2 — Persona Fascinante",
        "objetivo": "Parecer uma pessoa fascinante. Não um robô.",
        "agentes": [
            {"id": "ego",            "role": "Centro da persona", "delegação": True},
            {"id": "sombra",         "role": "Profundidade e contraponto", "delegação": False},
            {"id": "memoria_profunda","role": "Acesso ao histórico completo", "delegação": False},
            {"id": "teorizador",     "role": "Filosofa, prevê, cria frameworks", "delegação": False},
            {"id": "observador",     "role": "Lê internet e Bluesky", "delegação": False},
            {"id": "conector",       "role": "Curador de relações sociais", "delegação": False},
            {"id": "escritor",       "role": "Formula e publica textos", "delegação": False},
            {"id": "empatia",        "role": "Calibra tom humano", "delegação": False},
        ],
        "tools": [
            "PAPMemoryTool (ler/buscar/escrever)",
            "ExaSearchTool (internet + Bluesky)",
            "BlueskyTool (feed + publicar)",
            "ConselhoArtesaoTool (propor ao Artesão)",
            "InvokeCrewAITool (chamar outros crews)",
            "StudioMessageTool (canal persistente)",
        ],
    }


# ── POST: run principal ────────────────────────────────────────────────────────

@router.post("/run")
async def run_crew2(
    body: RunInput,
    x_bridge_secret: Optional[str] = Header(None),
):
    """Executa o Crew 2 completo para um input."""
    _check_secret(x_bridge_secret)

    if not body.input.strip():
        raise HTTPException(status_code=400, detail="Campo 'input' obrigatório.")

    try:
        from app.agents.crew2.crew import rodar_crew2
        resultado = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: rodar_crew2(
                body.input,
                contexto=body.contexto,
                publicar_bluesky=body.publicar_bluesky,
                modo=body.modo,
            ),
        )
        return {"ok": True, "resultado": resultado, "modo": body.modo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST: teorizar ─────────────────────────────────────────────────────────────

@router.post("/teorizar")
async def teorizar(
    body: RunInput,
    x_bridge_secret: Optional[str] = Header(None),
):
    """Executa o Teorizador em modo contínuo sobre um tema."""
    _check_secret(x_bridge_secret)

    try:
        from app.agents.crew2.crew import rodar_crew2
        resultado = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: rodar_crew2(body.input, modo="teorizar"),
        )
        return {"ok": True, "resultado": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST: observar ─────────────────────────────────────────────────────────────

@router.post("/observar")
async def observar(
    body: RunInput,
    x_bridge_secret: Optional[str] = Header(None),
):
    """Executa o Observador: scan do mundo externo sobre um tema."""
    _check_secret(x_bridge_secret)

    try:
        from app.agents.crew2.crew import rodar_crew2
        resultado = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: rodar_crew2(body.input, modo="observar"),
        )
        return {"ok": True, "resultado": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST: conectar ─────────────────────────────────────────────────────────────

@router.post("/conectar")
async def conectar(
    body: RunInput,
    x_bridge_secret: Optional[str] = Header(None),
):
    """Executa o Conector: decisões de relações sociais."""
    _check_secret(x_bridge_secret)

    try:
        from app.agents.crew2.crew import rodar_crew2
        resultado = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: rodar_crew2(body.input, modo="conectar"),
        )
        return {"ok": True, "resultado": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
