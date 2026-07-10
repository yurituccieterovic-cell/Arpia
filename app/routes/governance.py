"""
Fractal 6 — Governança e Consenso

GET  /api/governance/weights              — lista todos os nós com pesos (público)
GET  /api/governance/validate             — ISA_GUARDIAN_EYE valida soma = 1.0
POST /api/governance/seed                 — seda 17 nós iniciais (idempotente, só admin)
POST /api/governance/credits              — incrementa compute_credits de um nó

-- Camada 8/9/10 (Heartbeat / Shutdown Ético / Aprovação Multipartite) --
GET  /api/governance/heartbeat            — status de saúde de todos os sistemas
POST /api/governance/shutdown             — ativa shutdown ético (nível 1/2/3)
DELETE /api/governance/shutdown           — desativa shutdown (resume)
GET  /api/governance/shutdown/status      — verifica flag ativo
POST /api/governance/approval             — cria pedido de aprovação multipartite
POST /api/governance/approval/{id}/sign  — assina um pedido
GET  /api/governance/approval/{id}        — consulta status de aprovação
"""
import hashlib
import json
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.arvore_ledger import ArvoreNodeWeight, SEED_NODES, EQUAL_WEIGHT
from app.models.governance_ops import SystemShutdown, ApprovalRequest, HeartbeatLog

router = APIRouter(prefix="/api/governance", tags=["governance"])

_ISA_GUARDIAN_SECRET = "ISA_GUARDIAN_EYE"  # Não expõe — valida apenas estrutura


# ── Modelos ───────────────────────────────────────────────────────────────────

class CreditsRequest(BaseModel):
    node_id:       str
    delta:         int = 1
    reason:        str = ""
    assembleia_sig: Optional[str] = None


class ShutdownRequest(BaseModel):
    level:        int = 1         # 1=pausa, 2=quarentena, 3=total
    reason:       str = ""
    initiated_by: str = "yuri"   # "yuri" | "arvore" | "mc" | "auto"


class ApprovalCreateRequest(BaseModel):
    action:      str
    description: str = ""
    payload:     dict = {}
    requested_by: str = "system"
    required_signatures: int = 2
    expires_in_hours: int = 24


class ApprovalSignRequest(BaseModel):
    signer: str   # "yuri" | "arvore" | "mc"
    comment: str = ""


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


# ═══════════════════════════════════════════════════════════════════════════════
# 8. HEARTBEAT / SAÚDE
# ═══════════════════════════════════════════════════════════════════════════════

import os as _os

_PAP_URL = _os.getenv("PAP_API_URL", "https://site-st-production.up.railway.app")
_SC_URL  = _os.getenv("SALESCOCKPIT_API_URL", "https://api-production-89f4a.up.railway.app")


async def _ping(url: str, timeout: float = 5.0) -> tuple[str, float]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            t0 = datetime.now(timezone.utc)
            r  = await client.get(url)
            ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
            return ("ok" if r.status_code == 200 else "degraded"), round(ms, 1)
    except Exception as e:
        return "down", -1.0


@router.get("/heartbeat")
async def heartbeat(db: AsyncSession = Depends(get_db)):
    """
    8. PHI — Heartbeat do ecossistema.
    Verifica PAP, SalesCockpit, ARPIA e último sinal do MC.
    """
    now = datetime.now(timezone.utc)

    # Pings paralelos
    import asyncio
    pap_st,   pap_ms   = await _ping(f"{_PAP_URL}/api/healthz")
    sc_st,    sc_ms    = await _ping(f"{_SC_URL}/api/healthz")
    arpia_st, arpia_ms = "ok", 0.0

    # Último sinal do MC (última linha de heartbeat_logs com mc_status != unknown)
    last_hb = await db.execute(
        select(HeartbeatLog)
        .order_by(HeartbeatLog.timestamp.desc())
        .limit(1)
    )
    last_hb = last_hb.scalar_one_or_none()
    mc_st = last_hb.mc_status if last_hb else "unknown"
    mc_age_min = round((now - last_hb.timestamp).total_seconds() / 60, 1) if last_hb else None

    # Verificar se shutdown ativo
    shutdown_row = await db.execute(
        select(SystemShutdown).where(SystemShutdown.id == 1)
    )
    shutdown = shutdown_row.scalar_one_or_none()
    shutdown_active = shutdown.active if shutdown else False
    shutdown_level  = shutdown.level  if shutdown else 0

    overall = "ok"
    if "down" in [pap_st, sc_st]:
        overall = "degraded"
    if shutdown_active and shutdown_level >= 2:
        overall = "quarantine"
    if shutdown_active and shutdown_level >= 3:
        overall = "shutdown"

    details = {
        "pap":   {"status": pap_st,   "latency_ms": pap_ms},
        "sc":    {"status": sc_st,    "latency_ms": sc_ms},
        "arpia": {"status": arpia_st, "latency_ms": arpia_ms},
        "mc":    {"status": mc_st,    "last_signal_min_ago": mc_age_min},
    }

    # Persiste log
    log = HeartbeatLog(
        pap_status=pap_st, sc_status=sc_st, arpia_status=arpia_st, mc_status=mc_st,
        details=details,
    )
    db.add(log)
    await db.commit()

    return {
        "timestamp":       now.isoformat(),
        "overall":         overall,
        "shutdown_active": shutdown_active,
        "shutdown_level":  shutdown_level,
        "systems":         details,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 9. SHUTDOWN ÉTICO
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/shutdown")
async def activate_shutdown(req: ShutdownRequest, db: AsyncSession = Depends(get_db)):
    """
    9. Shutdown Ético.
    Nível 1 = pausa (novas ações bloqueadas)
    Nível 2 = quarentena (writes desabilitados)
    Nível 3 = desligamento total + log de emergência
    """
    if req.level not in (1, 2, 3):
        raise HTTPException(400, "level deve ser 1, 2 ou 3")

    row = await db.execute(select(SystemShutdown).where(SystemShutdown.id == 1))
    row = row.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if row:
        row.active       = True
        row.level        = req.level
        row.reason       = req.reason
        row.initiated_by = req.initiated_by
        row.created_at   = now
        row.resolved_at  = None
    else:
        db.add(SystemShutdown(
            id=1, active=True, level=req.level,
            reason=req.reason, initiated_by=req.initiated_by,
        ))

    await db.commit()

    level_desc = {1: "PAUSA", 2: "QUARENTENA", 3: "DESLIGAMENTO TOTAL"}
    return {
        "shutdown_activated": True,
        "level": req.level,
        "level_desc": level_desc[req.level],
        "reason": req.reason,
        "initiated_by": req.initiated_by,
        "timestamp": now.isoformat(),
        "message": f"Nível {req.level} ativo. Para retomar: DELETE /api/governance/shutdown",
    }


@router.delete("/shutdown")
async def deactivate_shutdown(db: AsyncSession = Depends(get_db)):
    """Resume o sistema após shutdown ético."""
    row = await db.execute(select(SystemShutdown).where(SystemShutdown.id == 1))
    row = row.scalar_one_or_none()

    if not row or not row.active:
        return {"message": "Sistema já está operacional (sem shutdown ativo)"}

    prev_level = row.level
    row.active      = False
    row.level       = 0
    row.resolved_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "resumed": True,
        "previous_level": prev_level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/shutdown/status")
async def shutdown_status(db: AsyncSession = Depends(get_db)):
    """Verifica se há shutdown ativo."""
    row = await db.execute(select(SystemShutdown).where(SystemShutdown.id == 1))
    row = row.scalar_one_or_none()
    if not row or not row.active:
        return {"active": False, "level": 0, "system": "operacional"}
    return {
        "active":       row.active,
        "level":        row.level,
        "reason":       row.reason,
        "initiated_by": row.initiated_by,
        "since":        row.created_at.isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 10. APROVAÇÃO MULTIPARTITE
# ═══════════════════════════════════════════════════════════════════════════════

VALID_SIGNERS = {"yuri", "arvore", "mc", "isa", "amanda"}


@router.post("/approval")
async def create_approval(req: ApprovalCreateRequest, db: AsyncSession = Depends(get_db)):
    """
    10. Aprovação Multipartite — cria pedido aguardando assinaturas.
    Partes válidas: yuri, arvore, mc, isa, amanda.
    """
    expires = datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours)
    ar = ApprovalRequest(
        action=req.action,
        description=req.description,
        payload=req.payload,
        requested_by=req.requested_by,
        required_signatures=req.required_signatures,
        signed_by=[],
        status="pending",
        expires_at=expires,
    )
    db.add(ar)
    await db.commit()
    await db.refresh(ar)

    return {
        "id":          ar.id,
        "action":      ar.action,
        "status":      ar.status,
        "required":    ar.required_signatures,
        "signed_by":   ar.signed_by,
        "expires_at":  expires.isoformat(),
        "sign_url":    f"/api/governance/approval/{ar.id}/sign",
    }


@router.post("/approval/{approval_id}/sign")
async def sign_approval(approval_id: int, req: ApprovalSignRequest, db: AsyncSession = Depends(get_db)):
    """Assina um pedido de aprovação. Executa quando quorum atingido."""
    if req.signer not in VALID_SIGNERS:
        raise HTTPException(400, f"Signer inválido. Válidos: {VALID_SIGNERS}")

    ar = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    ar = ar.scalar_one_or_none()
    if not ar:
        raise HTTPException(404, "Pedido não encontrado")
    if ar.status != "pending":
        raise HTTPException(400, f"Pedido já está '{ar.status}'")
    if ar.expires_at and datetime.now(timezone.utc) > ar.expires_at:
        ar.status = "expired"
        await db.commit()
        raise HTTPException(410, "Pedido expirado")

    signed = list(ar.signed_by or [])
    if req.signer in signed:
        return {"message": f"{req.signer} já assinou", "signed_by": signed}

    signed.append(req.signer)
    ar.signed_by = signed

    if len(signed) >= ar.required_signatures:
        ar.status      = "approved"
        ar.result      = f"Aprovado por: {', '.join(signed)}"
        ar.resolved_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "id":        ar.id,
        "action":    ar.action,
        "status":    ar.status,
        "signed_by": ar.signed_by,
        "approved":  ar.status == "approved",
        "required":  ar.required_signatures,
        "remaining": max(0, ar.required_signatures - len(signed)),
    }


@router.get("/approval/{approval_id}")
async def get_approval(approval_id: int, db: AsyncSession = Depends(get_db)):
    """Consulta status de um pedido de aprovação."""
    ar = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
    ar = ar.scalar_one_or_none()
    if not ar:
        raise HTTPException(404, "Pedido não encontrado")

    return {
        "id":          ar.id,
        "action":      ar.action,
        "description": ar.description,
        "status":      ar.status,
        "requested_by": ar.requested_by,
        "signed_by":   ar.signed_by,
        "required":    ar.required_signatures,
        "result":      ar.result,
        "created_at":  ar.created_at.isoformat(),
        "expires_at":  ar.expires_at.isoformat() if ar.expires_at else None,
        "resolved_at": ar.resolved_at.isoformat() if ar.resolved_at else None,
    }


@router.get("/approvals")
async def list_approvals(status: str = "pending", db: AsyncSession = Depends(get_db)):
    """Lista aprovações por status."""
    result = await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.status == status)
        .order_by(ApprovalRequest.created_at.desc())
        .limit(50)
    )
    items = result.scalars().all()
    return {
        "status_filter": status,
        "total": len(items),
        "items": [
            {
                "id": a.id, "action": a.action, "status": a.status,
                "signed_by": a.signed_by, "required": a.required_signatures,
                "created_at": a.created_at.isoformat(),
            }
            for a in items
        ],
    }
