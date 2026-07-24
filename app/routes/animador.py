"""
Rotas do IA Animador — /api/animador/*
"""

from fastapi import APIRouter, HTTPException
from app.agents.animador import executar_ciclo, state

router = APIRouter(prefix="/api/animador", tags=["animador"])


@router.get("/status")
async def status():
    """Estado atual do Animador (ciclos, última execução, próximo email)."""
    return state.to_dict()


@router.post("/ciclo")
async def ciclo_manual():
    """Dispara um ciclo do Animador manualmente (sem esperar os 45 min)."""
    result = await executar_ciclo()
    return result


@router.get("/log")
async def log():
    """Últimos 20 relatórios de ciclo."""
    return {"log": state.log}


@router.get("/filosofias")
async def filosofias():
    """Filosofias acumuladas pelo Animador."""
    return {"total": len(state.filosofias), "filosofias": state.filosofias[-10:]}
