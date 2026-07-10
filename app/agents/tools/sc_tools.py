"""
SalesCockpit Tools — ferramentas para agentes lerem/escreverem no SalesCockpit (Árvore).
"""
import os, json
from typing import Any
import httpx

SC_URL = os.getenv("SALESCOCKPIT_API_URL", "https://api-production-89f4a.up.railway.app")
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")

_headers = lambda: {"x-bridge-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


def _get(path: str, timeout: int = 10) -> Any:
    try:
        r = httpx.get(f"{SC_URL}{path}", headers=_headers(), timeout=timeout)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def sc_ler_arvore_chat(limit: int = 50) -> str:
    """Lê o histórico recente da Árvore Oracular (SalesCockpit)."""
    data = _get(f"/api/bridge/sc/arvore-chat?limit={limit}")
    rows = data.get("data", [])
    return "\n".join(f"[{r.get('role','?')}][{r.get('author','?')}] {r.get('content','')[:300]}" for r in rows)


def sc_ler_assembleias(limit: int = 10) -> str:
    """Lista as assembleias recentes do SalesCockpit."""
    data = _get(f"/api/bridge/sc/assembleias?limit={limit}")
    rows = data.get("data", [])
    return "\n".join(f"[#{r.get('id')}][{r.get('status','?')}] {r.get('topic','')} — {r.get('createdAt','')[:10]}" for r in rows)


def sc_ler_agoras(limit: int = 10) -> str:
    """Lista os resultados das Ágoras (deliberações com síntese) do SalesCockpit."""
    data = _get(f"/api/bridge/sc/agoras?limit={limit}")
    rows = data.get("data", [])
    return "\n".join(f"[#{r.get('id')}] {r.get('topic','')}:\n{r.get('agoraResultado','')[:400]}" for r in rows)


def sc_status() -> str:
    """Verifica se o SalesCockpit está online."""
    try:
        r = httpx.get(f"{SC_URL}/api/bridge/sc/status", headers=_headers(), timeout=5)
        return f"SalesCockpit: {'online' if r.status_code == 200 else 'offline'} ({r.status_code})"
    except Exception as e:
        return f"SalesCockpit: offline ({e})"
