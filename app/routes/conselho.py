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

_BASE = Path(__file__).parent.parent.parent
BLUEPRINT_PATH = _BASE / "current_blueprint.md"
PROPOSTAS_PATH = _BASE / "propostas.json"


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
    """Artesão via Gemini direto (sem ADK — compatível com Render free)."""
    try:
        import google.generativeai as genai
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY não configurada")
        genai.configure(api_key=gemini_key)

        ARTESAO_SYSTEM = (
            "Você é o Artesão do Conselho — arquiteto técnico do ecossistema Sociedade Tucci. "
            "Recebe demandas de IAs e humanos e cria Blueprints de implementação detalhados. "
            "Seu Blueprint sempre inclui: OBJETIVO, COMPONENTES AFETADOS (arquivos/serviços/IAs), "
            "PLANO em passos numerados, COMPLEXIDADE (S/M/L/XL), e RISCOS. "
            "Seja preciso, técnico e conciso. Máximo 800 tokens."
        )

        prompt_artesao = (
            f"Nova proposta do ecossistema:\n"
            f"ORIGEM: {req.origem} | PROJETO: {req.projeto or 'N/A'} | URGÊNCIA: {req.urgencia or 'media'}\n"
            f"TÍTULO: {req.titulo}\n"
            f"DESCRIÇÃO: {req.descricao}\n\n"
            "Crie um Blueprint completo."
        )

        model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=ARTESAO_SYSTEM)
        resp = await asyncio.to_thread(model.generate_content, prompt_artesao)
        blueprint = resp.text if hasattr(resp, "text") else str(resp)

        propostas = _load_propostas()
        propostas[pid]["blueprint"] = blueprint
        propostas[pid]["status"] = "aguardando_ajudante"
        _save_propostas(propostas)

        # ── Ajudante revisa ───────────────────────────────────────────────────
        AJUDANTE_SYSTEM = (
            "Você é o Ajudante do Conselho — revisor crítico de Blueprints. "
            "Analise o Blueprint do Artesão e classifique segundo a Malha de Pedágio: "
            "FAST TRACK (<10k tokens), MÉDIO (10k-50k), BUROCRÁTICO (>50k). "
            "Aponte pontos cegos, riscos e sugira melhorias. Máximo 400 tokens."
        )

        prompt_ajudante = (
            f"Revise este Blueprint:\n\n{blueprint}\n\n"
            "Critique e classifique pela Malha de Pedágio."
        )

        model2 = genai.GenerativeModel("gemini-2.0-flash", system_instruction=AJUDANTE_SYSTEM)
        resp2 = await asyncio.to_thread(model2.generate_content, prompt_ajudante)
        revisao = resp2.text if hasattr(resp2, "text") else str(resp2)

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
