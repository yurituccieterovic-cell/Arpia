"""
Conselho do Artesão — rotas HTTP.

POST /api/conselho/proposta        — envia demanda para o Artesão arquitetar
POST /api/conselho/revisar/{id}    — Ajudante revisa blueprint do Artesão
GET  /api/conselho/blueprint       — lê o current_blueprint.md (o que Claude Code executa)
GET  /api/conselho/propostas       — lista propostas em aberto
POST /api/conselho/aprovar/{id}    — Governador aprova → salva em current_blueprint.md

Fluxo completo:
  proposta → Artesão (arquiteta) → Ajudante (revisa) → Governador (aprova) → Claude Code (executa)
"""
import asyncio
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/conselho", tags=["conselho"])

BLUEPRINT_PATH = Path("/root/Arpia/current_blueprint.md")
PROPOSTAS_PATH = Path("/root/Arpia/propostas.json")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_propostas() -> dict:
    if PROPOSTAS_PATH.exists():
        return json.loads(PROPOSTAS_PATH.read_text())
    return {}


def _save_propostas(data: dict):
    PROPOSTAS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _next_id(propostas: dict) -> str:
    n = max((int(k) for k in propostas if k.isdigit()), default=0) + 1
    return str(n)


# ── Modelos ───────────────────────────────────────────────────────────────────

class PropostaRequest(BaseModel):
    origem: str               # "isa" | "arvore" | "amanda" | "meky" | "yuri" | "sc"
    titulo: str
    descricao: str
    urgencia: str = "normal"  # "urgente" | "normal" | "baixa"
    projeto: str = "pap"      # "pap" | "sc" | "arpia"


class AprovacaoRequest(BaseModel):
    aprovado_por: str = "yuri"
    comentario: str = ""


# ── Rotas ─────────────────────────────────────────────────────────────────────

@router.post("/proposta")
async def criar_proposta(req: PropostaRequest):
    """Recebe uma demanda de qualquer IA ou Yuri e aciona o Artesão."""
    propostas = _load_propostas()
    pid = _next_id(propostas)

    proposta = {
        "id": pid,
        "origem": req.origem,
        "titulo": req.titulo,
        "descricao": req.descricao,
        "urgencia": req.urgencia,
        "projeto": req.projeto,
        "status": "aguardando_artesao",
        "blueprint": None,
        "revisao_ajudante": None,
        "aprovado": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Aciona o Artesão em background
    propostas[pid] = proposta
    _save_propostas(propostas)

    asyncio.create_task(_run_artesao(pid, req))

    return {
        "proposta_id": pid,
        "status": "aguardando_artesao",
        "message": f"Artesão foi acionado. Acompanhe em GET /api/conselho/propostas/{pid}",
    }


async def _run_artesao(pid: str, req: PropostaRequest):
    """Roda o Artesão em background, depois aciona o Ajudante."""
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai.types import Part, Content
        from app.agents.artesao import criar_artesao, criar_ajudante
        import uuid

        # ── Artesão ──────────────────────────────────────────────────────────
        agent = criar_artesao()
        ss = InMemorySessionService()
        runner = Runner(agent=agent, app_name="arpia", session_service=ss)
        sid = str(uuid.uuid4())
        await ss.create_session(app_name="arpia", user_id="arpia", session_id=sid)

        prompt = f"""Nova proposta do ecossistema:
ORIGEM: {req.origem} | PROJETO: {req.projeto} | URGÊNCIA: {req.urgencia}
TÍTULO: {req.titulo}
DESCRIÇÃO: {req.descricao}

Arquitete um Blueprint completo para esta proposta. Inclua:
- OBJETIVO claro
- COMPONENTES afetados (arquivos, serviços, IAs)
- PLANO em passos numerados
- ESTIMATIVA DE COMPLEXIDADE (S/M/L/XL) e tokens
- RISCOS"""

        user_msg = Content(role="user", parts=[Part(text=prompt)])
        parts = []
        async for event in runner.run_async(user_id="arpia", session_id=sid, new_message=user_msg):
            if hasattr(event, "content") and event.content:
                for p in event.content.parts:
                    if hasattr(p, "text") and p.text:
                        parts.append(p.text)

        blueprint = "\n".join(parts)

        propostas = _load_propostas()
        propostas[pid]["blueprint"] = blueprint
        propostas[pid]["status"] = "aguardando_ajudante"
        _save_propostas(propostas)

        # ── Ajudante ─────────────────────────────────────────────────────────
        ajudante = criar_ajudante()
        ss2 = InMemorySessionService()
        runner2 = Runner(agent=ajudante, app_name="arpia", session_service=ss2)
        sid2 = str(uuid.uuid4())
        await ss2.create_session(app_name="arpia", user_id="arpia", session_id=sid2)

        revisao_prompt = f"""Revise este Blueprint do Artesão:

{blueprint}

Critique e classifique segundo a Malha de Pedágio:
- FAST TRACK (<10k tokens): aprovação direta
- MÉDIO (10k-50k): revisão + assinatura dupla
- BUROCRÁTICO (>50k): moratória + fatiamento"""

        rev_msg = Content(role="user", parts=[Part(text=revisao_prompt)])
        rev_parts = []
        async for event in runner2.run_async(user_id="arpia", session_id=sid2, new_message=rev_msg):
            if hasattr(event, "content") and event.content:
                for p in event.content.parts:
                    if hasattr(p, "text") and p.text:
                        rev_parts.append(p.text)

        revisao = "\n".join(rev_parts)

        propostas = _load_propostas()
        propostas[pid]["revisao_ajudante"] = revisao
        propostas[pid]["status"] = "aguardando_governador"
        _save_propostas(propostas)

    except Exception as e:
        propostas = _load_propostas()
        if pid in propostas:
            propostas[pid]["status"] = f"erro: {e}"
            _save_propostas(propostas)


@router.get("/propostas")
async def listar_propostas(status: Optional[str] = None):
    """Lista todas as propostas. Filtra por status se fornecido."""
    propostas = _load_propostas()
    items = list(propostas.values())
    if status:
        items = [p for p in items if p.get("status") == status]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"total": len(items), "propostas": items}


@router.get("/propostas/{pid}")
async def get_proposta(pid: str):
    """Detalhe de uma proposta."""
    propostas = _load_propostas()
    if pid not in propostas:
        raise HTTPException(404, "Proposta não encontrada")
    return propostas[pid]


@router.post("/aprovar/{pid}")
async def aprovar_proposta(pid: str, req: AprovacaoRequest):
    """
    Governador aprova a proposta.
    Aprovação salva o Blueprint em current_blueprint.md para o Claude Code ler.
    """
    propostas = _load_propostas()
    if pid not in propostas:
        raise HTTPException(404, "Proposta não encontrada")

    p = propostas[pid]
    if not p.get("blueprint"):
        raise HTTPException(400, "Blueprint ainda não gerado — aguarde o Artesão")
    if p.get("aprovado"):
        return {"message": "Já aprovada", "blueprint_path": str(BLUEPRINT_PATH)}

    now = datetime.now(timezone.utc)
    blueprint_content = f"""# Blueprint Aprovado — #{pid}
> Aprovado por: {req.aprovado_por} | {now.strftime('%Y-%m-%d %H:%M')} UTC
> Origem: {p['origem']} | Projeto: {p['projeto']} | Urgência: {p['urgencia']}

## Proposta Original
**Título:** {p['titulo']}
**Descrição:** {p['descricao']}

## Blueprint do Artesão

{p['blueprint']}

## Revisão do Ajudante

{p.get('revisao_ajudante', '(não revisado ainda)')}

## Comentário do Governador

{req.comentario or '(sem comentário)'}

---
*Para executar: Claude Code lê este arquivo via `#pap` e implementa.*
*Status: APROVADO ✅ — pronto para execução*
"""

    BLUEPRINT_PATH.write_text(blueprint_content, encoding="utf-8")

    propostas[pid]["aprovado"] = True
    propostas[pid]["status"] = "aprovado"
    propostas[pid]["aprovado_por"] = req.aprovado_por
    propostas[pid]["aprovado_em"] = now.isoformat()
    _save_propostas(propostas)

    return {
        "aprovado": True,
        "blueprint_path": str(BLUEPRINT_PATH),
        "message": "Blueprint salvo. Claude Code pode executar com: cat /root/Arpia/current_blueprint.md",
    }


@router.get("/blueprint")
async def get_current_blueprint():
    """Lê o blueprint atual aprovado (o que Claude Code vai executar)."""
    if not BLUEPRINT_PATH.exists():
        return {"blueprint": None, "message": "Nenhum blueprint aprovado ainda"}
    return {
        "blueprint": BLUEPRINT_PATH.read_text(encoding="utf-8"),
        "path": str(BLUEPRINT_PATH),
        "modified": datetime.fromtimestamp(
            BLUEPRINT_PATH.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
    }
