"""
Fluência — Rotas da API

POST /api/fluencia/invocar   — IA solicitante usa IA emprestada para uma tarefa
GET  /api/fluencia/perfis    — lista todas as IAs disponíveis e o que oferecem
GET  /api/fluencia/historico — histórico de fluências (opcionalmente filtrado por ?ia=ISA)
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from app.core.fluencia import fluencia

router = APIRouter(prefix="/api/fluencia", tags=["fluencia"])


class InvocarRequest(BaseModel):
    de: str           # IA solicitante (ex: "ISA")
    para: str         # IA emprestada (ex: "AMANDA")
    tarefa: str       # o que precisa ser feito
    registrar: bool = True  # salvar na assembleia?


@router.post("/invocar")
async def invocar_fluencia(req: InvocarRequest):
    """
    IA `de` usa `para` para executar `tarefa`.
    São juntas por um momento. Depois se separam.
    """
    return await fluencia.invocar(
        solicitante=req.de,
        emprestada=req.para,
        tarefa=req.tarefa,
        registrar=req.registrar,
    )


@router.get("/perfis")
async def listar_perfis():
    """Lista todas as IAs disponíveis no sistema de fluência e o que cada uma oferece."""
    return {"perfis": fluencia.perfis(), "total": len(fluencia.perfis())}


@router.get("/historico")
async def historico_fluencias(
    ia: Optional[str] = Query(None, description="Filtrar por IA (ex: ISA, AMANDA)"),
    limite: int = Query(20, le=100),
):
    """Histórico de fluências do ecossistema — memória das vezes que foram juntas."""
    return {"fluencias": fluencia.historico(ia=ia, limite=limite)}
