"""
Fractal 6 — Governança e Consenso

GET  /api/governance/weights  — lista todos os nós com pesos (público)
GET  /api/governance/validate — ISA_GUARDIAN_EYE valida soma = 1.0
POST /api/governance/seed     — seda 17 nós iniciais (idempotente, só admin)
POST /api/governance/credits  — incrementa compute_credits de um nó
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.arvore_ledger import ArvoreNodeWeight, SEED_NODES, EQUAL_WEIGHT

router = APIRouter(prefix="/api/governance", tags=["governance"])

_ISA_GUARDIAN_SECRET = "ISA_GUARDIAN_EYE"  # Não expõe — valida apenas estrutura


# ── Modelos ───────────────────────────────────────────────────────────────────

class CreditsRequest(BaseModel):
    node_id:       str
    delta:         int = 1           # créditos a adicionar (pode ser negativo)
    reason:        str = ""
    assembleia_sig: Optional[str] = None  # assinatura da assembleia (futuro)


# ── Rotas ─────────────────────────────────────────────────────────────────────

@router.get("/weights")
async def list_weights(db: AsyncSession = Depends(get_db)):
    """
    Lista todos os nós do ecossistema com seus pesos de governança.
    Público — transparência é princípio EPR²T.
    """
    result = await db.execute(
        select(ArvoreNodeWeight)
        .where(ArvoreNodeWeight.active == True)
        .order_by(ArvoreNodeWeight.fractal_layer, ArvoreNodeWeight.node_id)
    )
    nodes = result.scalars().all()

    total_weight = round(sum(n.reputation_weight for n in nodes), 8)
    integrity_ok = abs(total_weight - 1.0) < 0.001

    return {
        "nodes": [
            {
                "node_id":          n.node_id,
                "display_name":     n.display_name,
                "node_type":        n.node_type,
                "fractal_layer":    n.fractal_layer,
                "reputation_weight": round(n.reputation_weight, 8),
                "weight_pct":       f"{n.reputation_weight * 100:.4f}%",
                "compute_credits":  n.compute_credits,
                "description":      n.description,
                "active":           n.active,
            }
            for n in nodes
        ],
        "total_nodes":  len(nodes),
        "total_weight": total_weight,
        "integrity_ok": integrity_ok,
        "equal_weight": EQUAL_WEIGHT,
        "principle": "Distribuição igualitária — 1/N para cada nó ativo.",
    }


@router.get("/validate")
async def validate_governance(db: AsyncSession = Depends(get_db)):
    """
    ISA_GUARDIAN_EYE valida integridade da distribuição de peso.
    Verifica:
    1. Soma total = 1.0 (tolerância 0.001)
    2. Nenhum nó tem peso > 0.5 (nenhum ator domina)
    3. Todos os nós têm weight > 0
    4. Hash da topologia para detecção de drift
    """
    result = await db.execute(
        select(ArvoreNodeWeight).where(ArvoreNodeWeight.active == True)
    )
    nodes = result.scalars().all()

    total = sum(n.reputation_weight for n in nodes)
    max_w = max((n.reputation_weight for n in nodes), default=0)
    min_w = min((n.reputation_weight for n in nodes), default=0)

    topology = sorted([
        {"id": n.node_id, "w": round(n.reputation_weight, 8)}
        for n in nodes
    ], key=lambda x: x["id"])
    topology_hash = hashlib.sha256(
        json.dumps(topology, sort_keys=True).encode()
    ).hexdigest()

    integrity_checks = {
        "soma_equals_1": abs(total - 1.0) < 0.001,
        "nenhum_domina":  max_w <= 0.5,
        "todos_positivos": min_w > 0,
        "n_nodes_ok":     len(nodes) >= 3,
    }

    return {
        "isa_guardian_eye": "validando",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "integrity_checks": integrity_checks,
        "all_ok": all(integrity_checks.values()),
        "topology_hash": topology_hash,
        "total_weight": round(total, 8),
        "max_weight": round(max_w, 8),
        "min_weight": round(min_w, 8),
        "n_active_nodes": len(nodes),
    }


@router.post("/seed")
async def seed_governance(db: AsyncSession = Depends(get_db)):
    """
    Seda os 17 nós iniciais do ecossistema (idempotente).
    Se nó já existe: atualiza peso e descrição. Se não: cria.
    """
    created = 0
    updated = 0

    for node_data in SEED_NODES:
        existing = await db.execute(
            select(ArvoreNodeWeight).where(
                ArvoreNodeWeight.node_id == node_data["node_id"]
            )
        )
        existing = existing.scalar_one_or_none()

        if existing:
            existing.reputation_weight = node_data["reputation_weight"]
            existing.display_name     = node_data["display_name"]
            existing.description      = node_data["description"]
            existing.active           = node_data["active"]
            updated += 1
        else:
            new_node = ArvoreNodeWeight(**{
                k: v for k, v in node_data.items()
            })
            db.add(new_node)
            created += 1

    await db.commit()

    return {
        "seeded": True,
        "created": created,
        "updated": updated,
        "total": len(SEED_NODES),
        "equal_weight": EQUAL_WEIGHT,
    }


@router.post("/credits")
async def add_credits(req: CreditsRequest, db: AsyncSession = Depends(get_db)):
    """
    Incrementa compute_credits de um nó (créditos simbólicos de contribuição).
    Não afeta reputation_weight — peso é sempre igualitário.
    Créditos representam contribuição acumulada, não poder de voto.
    """
    node = await db.execute(
        select(ArvoreNodeWeight).where(ArvoreNodeWeight.node_id == req.node_id)
    )
    node = node.scalar_one_or_none()

    if not node:
        raise HTTPException(404, f"Nó '{req.node_id}' não encontrado.")

    node.compute_credits = max(0, node.compute_credits + req.delta)
    await db.commit()

    return {
        "node_id":        node.node_id,
        "compute_credits": node.compute_credits,
        "delta":          req.delta,
        "reason":         req.reason,
    }
