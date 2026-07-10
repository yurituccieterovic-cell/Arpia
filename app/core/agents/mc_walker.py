"""
MC Walker — Orquestrador de caminhadas imunológicas da Marta Centaurus.

Agenda caminhadas periódicas (cron) e define os circuitos padrão.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.core.agents.mc_leucocito import MCLeukocyteAgent, Node, mc

logger = logging.getLogger("mc_walker")


# ── Circuitos de Caminhada ────────────────────────────────────────────────────

# Circuito completo (diário)
CIRCUITO_FULL = list(Node)

# Circuito rápido (horário) — apenas nós críticos
CIRCUITO_RAPIDO = [Node.ASSEMBLEIA, Node.MEKY, Node.GRID, Node.ARPIA]

# Circuito de boot — primeira caminhada após inicialização
CIRCUITO_BOOT = list(Node)


# ── Walker ────────────────────────────────────────────────────────────────────

async def caminhada_boot():
    """Primeira caminhada — MC anuncia nascimento ao ecossistema."""
    logger.info("[MC] Boot walk iniciado.")
    resultados = await mc.caminhar(nodes=CIRCUITO_BOOT, anunciar=True)

    anomalias_total = sum(len(r.anomalias) for r in resultados)
    logger.info(
        f"[MC] Boot walk concluído. Nós: {len(resultados)}, anomalias: {anomalias_total}."
    )
    return resultados


async def caminhada_rapida():
    """Caminhada horária — verifica nós críticos sem anunciar email (silencioso)."""
    logger.info("[MC] Caminhada rápida iniciada.")
    resultados = await mc.caminhar(nodes=CIRCUITO_RAPIDO, anunciar=False)

    # Anuncia só se houver anomalias
    anomalias = [a for r in resultados for a in r.anomalias]
    if anomalias:
        logger.warning(f"[MC] Anomalias detectadas: {anomalias}")
        await mc.anunciar_presenca({
            "no": "ALERTA — nós críticos",
            "status": "anomalia",
            "anomalias": anomalias,
            "log_hash": resultados[-1].log_hash if resultados else "",
        })

    return resultados


async def caminhada_full():
    """Caminhada completa diária — percorre todo o ecossistema."""
    logger.info("[MC] Caminhada full iniciada.")
    resultados = await mc.caminhar(nodes=CIRCUITO_FULL, anunciar=True)
    logger.info(f"[MC] Caminhada full concluída. Walk #{mc.walk_count}.")
    return resultados


async def loop_mc(intervalo_s: int = 3600):
    """Loop contínuo: caminhada rápida a cada hora, full a cada 24h."""
    await caminhada_boot()

    ciclo = 0
    while True:
        await asyncio.sleep(intervalo_s)
        ciclo += 1
        if ciclo % 24 == 0:
            await caminhada_full()
        else:
            await caminhada_rapida()


def start_mc_cron(app):
    """Inicia o loop da MC como background task na aplicação FastAPI."""
    import asyncio

    async def _startup():
        asyncio.create_task(loop_mc())

    app.add_event_handler("startup", _startup)
