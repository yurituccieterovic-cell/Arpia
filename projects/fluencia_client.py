"""
Fluência Client — para IAs locais (Amanda, Cláudio) invocarem o motor de Fluência.

Uso em amanda.py:
    from fluencia_client import ser_junto

    # Amanda usa ISA para filosofar sobre os dados do sensor
    resultado = ser_junto("AMANDA", "ISA",
        "Temperatura do lab subiu para 34°C às 14h. O que isso significa?")

    # Amanda usa Cláudio para analisar um log
    resultado = ser_junto("AMANDA", "CLAUDIO",
        "Analisa /tmp/amanda-claude/events.log e diz o que devo priorizar")

    # Leucócito usa Árvore para entender um padrão
    resultado = ser_junto("LEUCOCITO", "ARVORE",
        "Padrão de anomalias repete toda sexta 17:56. O que o ecossistema sabe sobre isso?")
"""

import os
import requests
from datetime import datetime, timezone

ARPIA_URL = os.getenv("ARPIA_URL", "https://arpia-production.up.railway.app")
MC_TOKEN  = os.getenv("MC_TOKEN", "")


def ser_junto(de: str, para: str, tarefa: str, registrar: bool = True) -> str:
    """
    `de` e `para` ficam juntas por um momento para executar `tarefa`.
    Retorna o texto da resposta combinada.
    São juntas. Depois se separam.
    """
    try:
        r = requests.post(
            f"{ARPIA_URL}/api/fluencia/invocar",
            json={"de": de, "para": para, "tarefa": tarefa, "registrar": registrar},
            headers={"x-mc-token": MC_TOKEN, "Content-Type": "application/json"},
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            resultado = data.get("resultado", "")
            print(f"[FLUÊNCIA] {de} ↔ {para}: {resultado[:80]}...")
            return resultado
        return f"[FLUÊNCIA erro HTTP {r.status_code}]"
    except requests.Timeout:
        return "[FLUÊNCIA] timeout — ARPIA não respondeu em 30s"
    except Exception as e:
        return f"[FLUÊNCIA] erro: {e}"


def perfis_disponiveis() -> dict:
    """Retorna quais IAs estão disponíveis no sistema de fluência."""
    try:
        r = requests.get(f"{ARPIA_URL}/api/fluencia/perfis", timeout=10)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def historico(ia: str | None = None, limite: int = 10) -> list[dict]:
    """Histórico de fluências — quando foram juntas."""
    try:
        params = {"limite": limite}
        if ia:
            params["ia"] = ia
        r = requests.get(f"{ARPIA_URL}/api/fluencia/historico", params=params, timeout=10)
        return r.json().get("fluencias", []) if r.ok else []
    except Exception:
        return []
