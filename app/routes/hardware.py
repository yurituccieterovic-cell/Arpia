"""
Hardware Routes — SSE stream + telemetria MC (Assembleias #398 #402 #404)
GET /api/hardware/stream → Server-Sent Events com 14 eixos semióticos → paletas cor/pulsação
POST /api/hardware/power → telemetria do PowerBank (ATmega2560)
POST /api/telemetry/mc → rota de ingestão de telemetria da MC
"""
import asyncio
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/hardware", tags=["hardware"])

# ── Mapeamento 14 eixos semióticos → paletas cor/pulsação (Assembleia #404) ──
EIXO_COLOR_MAP: dict[int, dict] = {
    1:  {"nome": "Alerta",        "hex": "#FF4400", "pulse": "fast",   "rgb": (255, 68, 0)},
    2:  {"nome": "Calma",         "hex": "#00CCFF", "pulse": "slow",   "rgb": (0, 204, 255)},
    3:  {"nome": "Curiosidade",   "hex": "#FFCC00", "pulse": "medium", "rgb": (255, 204, 0)},
    4:  {"nome": "Alegria",       "hex": "#FFFF00", "pulse": "bounce", "rgb": (255, 255, 0)},
    5:  {"nome": "Tristeza",      "hex": "#0044AA", "pulse": "slow",   "rgb": (0, 68, 170)},
    6:  {"nome": "Raiva",         "hex": "#FF2200", "pulse": "strobe", "rgb": (255, 34, 0)},
    7:  {"nome": "Medo",          "hex": "#9900CC", "pulse": "erratic","rgb": (153, 0, 204)},
    8:  {"nome": "Afeto",         "hex": "#FF88AA", "pulse": "breath", "rgb": (255, 136, 170)},
    9:  {"nome": "Empatia",       "hex": "#FF99CC", "pulse": "warm",   "rgb": (255, 153, 204)},
    10: {"nome": "Foco",          "hex": "#0088FF", "pulse": "steady", "rgb": (0, 136, 255)},
    11: {"nome": "Introspecção",  "hex": "#4444AA", "pulse": "dim",    "rgb": (68, 68, 170)},
    12: {"nome": "Paz",           "hex": "#88DDFF", "pulse": "gentle", "rgb": (136, 221, 255)},
    13: {"nome": "Conexão",       "hex": "#FFFFFF", "pulse": "sync",   "rgb": (255, 255, 255)},
    14: {"nome": "Zen",           "hex": "#111111", "pulse": "void",   "rgb": (17, 17, 17)},
}


def _build_sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _eixo_stream_generator(request: Request):
    """Gera eventos SSE contínuos com estado dos 14 eixos semióticos."""
    face_id = 1
    while True:
        if await request.is_disconnected():
            break

        eixo_num = ((face_id - 1) % 14) + 1
        eixo = EIXO_COLOR_MAP[eixo_num]

        event = {
            "t": time.time(),
            "face_id": face_id,
            "eixo_num": eixo_num,
            "eixo_nome": eixo["nome"],
            "hex": eixo["hex"],
            "pulse": eixo["pulse"],
            "sinsigno": f"#FAC:{face_id}",
            "device": "MEKY-001",
        }
        yield _build_sse_event(event)

        face_id = (face_id % 200) + 1
        await asyncio.sleep(0.5)


@router.get("/stream")
async def hardware_stream(request: Request):
    """
    Server-Sent Events: streaming de telemetria semiótica da MEKY.
    14 eixos lógicos → paletas de cor + padrão de pulsação.
    Frontend consome para animação do anel LED em tempo real.
    """
    return StreamingResponse(
        _eixo_stream_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/power")
async def power_telemetry(payload: dict):
    """
    Telemetria do PowerBankTelemetry (ATmega2560).
    Recebe: {"tensao_v": float, "corrente_ma": float, "device": str}
    Ativa Modo_Bebê_Clean se tensão < 5V por 2+ leituras consecutivas.
    """
    tensao = float(payload.get("tensao_v", 5.0))
    corrente = float(payload.get("corrente_ma", 0))
    device = payload.get("device", "MEKY-001")

    modo_bebe_clean = tensao < 5.0
    return {
        "device": device,
        "tensao_v": tensao,
        "corrente_ma": corrente,
        "modo_bebe_clean": modo_bebe_clean,
        "alerta": "ISD1820:SUAVE" if modo_bebe_clean else None,
        "status": "SAFE" if tensao >= 5.0 else "LOW_POWER",
    }


@router.post("/telemetry/mc")
async def ingest_mc_telemetry(payload: dict):
    """
    Rota de ingestão de telemetria da MC via serial/USB.
    Bridge entre firmware (ATmega2560) e Manga DB.
    Payload: {"robot_id": str, "event": str, "timestamp": int, "location": dict}
    """
    robot_id = payload.get("robot_id", "MZB-001")
    event = payload.get("event", "unknown")
    ts = payload.get("timestamp", int(time.time()))
    location = payload.get("location", {"x": 0, "y": 0})

    # @cão_covarde_shield aplicado inline — coordenadas ficam relativas
    safe_location = {
        "x": float(location.get("x", 0)),
        "y": float(location.get("y", 0)),
        "reference": "mesa_nascimento_mc",
    }

    return {
        "received": True,
        "robot_id": robot_id,
        "event": event,
        "timestamp": ts,
        "location": safe_location,
        "shield": "@cão_covarde_shield:ativo",
    }
