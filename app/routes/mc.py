"""
MC — Marta Centaurus: rotas HTTP do Leucócito Digital

GET  /api/mc/status      — relátorio da MC (walks, anomalias)
POST /api/mc/walk        — dispara caminhada manual
POST /api/mc/alert       — quimiotaxia: alerta de anomalia → MC vai até o nó
POST /api/mc/neutralize  — fagocitose: neutraliza anomalia específica
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.agents.mc_leucocito import mc, Node

router = APIRouter(prefix="/api/mc", tags=["mc"])


class WalkRequest(BaseModel):
    nodes: Optional[list[str]] = None  # nomes de Node enum; None = todos
    anunciar: bool = True


class AlertRequest(BaseModel):
    node_target: str  # Node enum value
    severity: str = "MEDIA"
    descricao: str = ""


class NeutralizeRequest(BaseModel):
    anomaly_id: str
    raw_data: str = ""


@router.get("/status")
async def mc_status():
    return {"mc": mc.relatorio(), "assinatura": "Marta Centaurus — Leucócito Digital"}


@router.post("/walk")
async def mc_walk(req: WalkRequest):
    if req.nodes:
        try:
            node_list = [Node(n) for n in req.nodes]
        except ValueError as e:
            raise HTTPException(400, f"Nó inválido: {e}. Válidos: {[n.value for n in Node]}")
    else:
        node_list = None

    resultados = await mc.caminhar(nodes=node_list, anunciar=req.anunciar)
    return {
        "walk_n": mc.walk_count,
        "resultados": [r.to_dict() for r in resultados],
    }


@router.post("/alert")
async def mc_alert(req: AlertRequest):
    try:
        node = Node(req.node_target)
    except ValueError:
        raise HTTPException(400, f"Nó inválido: {req.node_target}")

    result = await mc.responder_alerta(node, req.severity, req.descricao)
    return {"quimiotaxia": result}


@router.post("/neutralize")
async def mc_neutralize(req: NeutralizeRequest):
    result = await mc.neutralizar(req.anomaly_id, req.raw_data)
    return {"fagocitose": result.to_dict()}
