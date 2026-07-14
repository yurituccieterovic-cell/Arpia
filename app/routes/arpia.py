"""
ARPIA v1 — Middleware Cognitivo do Ecossistema Tucci.

Qualquer IA conectada herda: Telos, Princípios, Axiomas, Memória e Workflows.

Endpoints:
  POST /api/arpia/v1/handshake          — agente se registra, recebe token + DNA
  GET  /api/arpia/v1/context/{agent_id} — retorna DNA completo (requer token)
  POST /api/arpia/v1/memory/query       — consulta memória do ecossistema
  POST /api/arpia/v1/memory/save        — salva insight no audit log
  POST /api/arpia/v1/audit/log          — registra ação realizada
  GET  /api/arpia/v1/agents             — lista agentes registrados
"""
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dna_builder import build_dna, fetch_ecosystem_memory, PAP_API_URL
from app.models.arpia_agent import ArpiaAgent, ArpiaAuditLog

router = APIRouter(prefix="/api/arpia/v1", tags=["arpia"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _require_agent(token: str, db: AsyncSession) -> ArpiaAgent:
    """Valida Bearer token e retorna o agente."""
    result = await db.execute(select(ArpiaAgent).where(ArpiaAgent.token == token))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(401, "Token inválido. Use POST /api/arpia/v1/handshake para registrar.")
    # Atualiza last_seen
    await db.execute(
        update(ArpiaAgent).where(ArpiaAgent.id == agent.id).values(last_seen=datetime.utcnow())
    )
    return agent


def _bearer(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization: Bearer <token> obrigatório.")
    return authorization[7:]


# ── Schemas ───────────────────────────────────────────────────────────────────

class HandshakeRequest(BaseModel):
    agent_id: str                          # identificador único (ex: "claudio-code", "replit-arboretum")
    display_name: str                      # nome legível
    model_type: str = "generic"            # "claude", "gemini", "gpt", "replit", "human"
    skills: list[str] = []                 # capacidades declaradas
    telos_local: Optional[str] = None      # propósito específico deste agente (opcional)

class MemoryQueryRequest(BaseModel):
    query: str                             # o que buscar na memória
    limit: int = 10

class MemorySaveRequest(BaseModel):
    insight: str                           # insight a salvar
    tags: list[str] = []

class AuditLogRequest(BaseModel):
    action: str
    payload: Optional[dict] = None
    result: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/handshake")
async def handshake(req: HandshakeRequest, db: AsyncSession = Depends(get_db)):
    """
    Agente se apresenta ao ecossistema.
    Retorna token de acesso + Pacote DNA completo.
    Idempotente: se o agent_id já existe, renova o token.
    """
    result = await db.execute(select(ArpiaAgent).where(ArpiaAgent.id == req.agent_id))
    existing = result.scalar_one_or_none()

    new_token = ArpiaAgent.generate_token()

    if existing:
        await db.execute(
            update(ArpiaAgent)
            .where(ArpiaAgent.id == req.agent_id)
            .values(
                token=new_token,
                display_name=req.display_name,
                model_type=req.model_type,
                skills=req.skills,
                telos_local=req.telos_local,
                last_seen=datetime.utcnow(),
            )
        )
        await db.commit()
    else:
        agent = ArpiaAgent(
            id=req.agent_id,
            display_name=req.display_name,
            model_type=req.model_type,
            token=new_token,
            skills=req.skills,
            telos_local=req.telos_local,
        )
        db.add(agent)
        await db.commit()

    dna = await build_dna(req.agent_id, req.model_type, req.skills)

    # Log do batismo
    await db.execute(
        ArpiaAuditLog.__table__.insert().values(
            agent_id=req.agent_id,
            action="handshake",
            payload={"model_type": req.model_type, "skills": req.skills},
            result="ok",
            created_at=datetime.utcnow(),
        )
    )
    await db.commit()

    return {
        "ok": True,
        "token": new_token,
        "agent_id": req.agent_id,
        "dna": dna,
        "instrucoes": (
            "Use este token em 'Authorization: Bearer <token>' em todas as chamadas. "
            "Injete dna.instrucao_sistema como system prompt antes de processar qualquer tarefa. "
            "Registre actions via POST /api/arpia/v1/audit/log ao final de cada ciclo."
        ),
    }


@router.get("/context/{agent_id}")
async def get_context(
    agent_id: str,
    token: str = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    """Retorna o DNA completo atualizado para o agente."""
    agent = await _require_agent(token, db)
    if agent.id != agent_id:
        raise HTTPException(403, "Token não corresponde ao agent_id solicitado.")

    dna = await build_dna(agent_id, agent.model_type, agent.skills)
    if agent.telos_local:
        dna["telos_local"] = agent.telos_local

    return {"ok": True, "agent_id": agent_id, "dna": dna}


@router.post("/memory/query")
async def memory_query(
    req: MemoryQueryRequest,
    token: str = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    """
    Consulta memória do ecossistema.
    Por ora: retorna mensagens recentes do Playcenter (endpoint público PAP).
    Extensível: filtrar por query keyword no futuro.
    """
    agent = await _require_agent(token, db)
    msgs = await fetch_ecosystem_memory(req.limit)

    # Filtro simples por keyword
    q = req.query.lower()
    filtered = [m for m in msgs if q in m.get("conteudo", "").lower()] if q else msgs

    return {
        "ok": True,
        "query": req.query,
        "results": filtered,
        "total": len(filtered),
        "source": "playcenter",
    }


@router.post("/memory/save")
async def memory_save(
    req: MemorySaveRequest,
    token: str = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    """
    Salva insight no audit log local (Manga DB).
    Se PAP_BRIDGE_SECRET estiver configurado, replica no Conector do PAP.
    """
    from app.core.config import get_settings
    agent = await _require_agent(token, db)
    cfg = get_settings()

    # Salva no audit log
    log = ArpiaAuditLog(
        agent_id=agent.id,
        action="memory_save",
        payload={"tags": req.tags},
        result=req.insight[:500],
    )
    db.add(log)
    await db.commit()

    # Tenta replicar no Conector PAP se tiver BRIDGE_SECRET
    pap_ok = False
    bridge = getattr(cfg, "pap_bridge_secret", "") or ""
    if bridge:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                entry = f"### {datetime.utcnow().strftime('%Y-%m-%d')} — {agent.id}\n- {req.insight}"
                r = await client.post(
                    f"{PAP_API_URL}/api/conector/memory",
                    headers={"Authorization": f"Bearer {bridge}", "Content-Type": "application/json"},
                    json={"section": "conversas", "append": entry},
                )
                pap_ok = r.status_code == 200
        except Exception:
            pass

    return {"ok": True, "saved_locally": True, "replicated_pap": pap_ok}


@router.post("/audit/log")
async def audit_log(
    req: AuditLogRequest,
    token: str = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    """Registra uma ação realizada pelo agente."""
    agent = await _require_agent(token, db)

    log = ArpiaAuditLog(
        agent_id=agent.id,
        action=req.action[:200],
        payload=req.payload,
        result=req.result[:500] if req.result else None,
    )
    db.add(log)
    await db.commit()

    return {"ok": True, "logged": True, "agent_id": agent.id, "action": req.action}


@router.get("/agents")
async def list_agents(db: AsyncSession = Depends(get_db)):
    """Lista todos os agentes registrados (público — sem token)."""
    result = await db.execute(
        select(ArpiaAgent.id, ArpiaAgent.display_name, ArpiaAgent.model_type,
               ArpiaAgent.skills, ArpiaAgent.created_at, ArpiaAgent.last_seen)
        .order_by(ArpiaAgent.created_at.desc())
    )
    rows = result.all()
    return {
        "ok": True,
        "total": len(rows),
        "agents": [
            {
                "id": r.id,
                "display_name": r.display_name,
                "model_type": r.model_type,
                "skills": r.skills,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            }
            for r in rows
        ],
    }
