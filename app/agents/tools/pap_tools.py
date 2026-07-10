"""
PAP Tools — ferramentas para os agentes ADK/CrewAI lerem e escreverem no PAP.
Auth: x-arvore-token (ARVORE_TOKEN) e x-bridge-secret (BRIDGE_SECRET).
Todas são sync (usadas pelo google-adk e crewai que chamam sync).
"""
import os, json
from typing import Any
import httpx

PAP_URL = os.getenv("PAP_API_URL", "https://site-st-production.up.railway.app")
ARVORE_TOKEN = os.getenv("ARVORE_TOKEN", "")
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")

_headers_arvore = lambda: {"x-arvore-token": ARVORE_TOKEN, "Content-Type": "application/json"}
_headers_bridge = lambda: {"x-bridge-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


def _get(path: str, headers: dict, timeout: int = 10) -> Any:
    try:
        r = httpx.get(f"{PAP_URL}{path}", headers=headers, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _post(path: str, body: dict, headers: dict, timeout: int = 15) -> Any:
    try:
        r = httpx.post(f"{PAP_URL}{path}", json=body, headers=headers, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── PAP Bridge tools ──────────────────────────────────────────────────────────

def pap_ler_memoria_isa(limit: int = 50) -> str:
    """Lê as últimas N entradas da memória ISA (contextos: cycle, chat, biblioteca, task)."""
    data = _get(f"/api/bridge/pap/isa-memory?limit={limit}", _headers_bridge())
    rows = data.get("data", [])
    return "\n".join(f"[{r.get('context','?')}][{r.get('role','?')}] {r.get('content','')[:300]}" for r in rows)


def pap_ler_assembleias(limit: int = 20) -> str:
    """Lê as últimas N mensagens da assembleia inter-agente do PAP (ISA, MEKY, Árvore)."""
    data = _get(f"/api/bridge/pap/assembleias?limit={limit}", _headers_bridge())
    rows = data.get("data", [])
    return "\n".join(f"[{r.get('fromAgent','?')}→{r.get('toAgent','all')}][{r.get('type','?')}] {r.get('content','')[:300]}" for r in rows)


def pap_ler_biblioteca(limit: int = 30) -> str:
    """Lista os documentos da biblioteca ISA (PDFs FUVEST, assembleias, livros)."""
    data = _get("/api/bridge/pap/biblioteca", _headers_bridge())
    rows = data.get("data", [])
    return "\n".join(f"• [{r.get('tipo','?')}] {r.get('titulo','')} — {r.get('resumo','')[:150]}" for r in rows[:limit])


def pap_escrever_memoria(conteudo: str, contexto: str = "agente", role: str = "isa") -> str:
    """Escreve uma entrada na memória ISA. contexto: agente|cycle|chat|biblioteca|task"""
    result = _post("/api/isa/memory/write", {
        "content": conteudo,
        "context": contexto,
        "role": role,
        "location": "/agente-twin"
    }, _headers_arvore())
    return json.dumps(result)


def pap_adicionar_biblioteca(titulo: str, url: str = "", tipo: str = "txt", resumo: str = "", tags: list | None = None) -> str:
    """Adiciona um documento à biblioteca ISA."""
    result = _post("/api/isa/biblioteca/bulk-add", {
        "docs": [{"titulo": titulo, "url": url, "tipo": tipo, "resumo": resumo, "tags": tags or ["agente"]}]
    }, _headers_arvore())
    return json.dumps(result)


def pap_status() -> str:
    """Verifica se o PAP está online."""
    try:
        r = httpx.get(f"{PAP_URL}/api/healthz", timeout=5)
        return f"PAP: {'online' if r.status_code == 200 else 'offline'} ({r.status_code})"
    except Exception as e:
        return f"PAP: offline ({e})"
