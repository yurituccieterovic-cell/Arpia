"""
Hestia Routes — endpoints para o agente GPT-4o do Ecossistema Tucci.

Endpoints:
  POST /api/hestia/chat          — chat com Hestia (GPT-4o)
  POST /api/hestia/vision        — análise de imagem/câmera MEKY
  POST /api/hestia/whisper       — transcrição de áudio (Whisper STT)
  GET  /api/hestia/status        — verificar disponibilidade + modelo

Auth: x-bridge-secret (mesma do bridge).

Uso provisório: 3 meses enquanto Yuri tem plano ChatGPT Plus + créditos API.
"""
import os
import base64
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.agents.hestia import hestia_chat, tool_vision_analyze, tool_whisper_transcribe

router = APIRouter(prefix="/hestia", tags=["hestia"])

BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")


def _check_auth(request: Request) -> None:
    if not BRIDGE_SECRET:
        raise HTTPException(status_code=500, detail="BRIDGE_SECRET não configurado")
    if request.headers.get("x-bridge-secret") != BRIDGE_SECRET:
        raise HTTPException(status_code=403, detail="Acesso negado")


class ChatRequest(BaseModel):
    messages: list[dict]
    model: str = "gpt-4o"
    max_tool_rounds: int = 3


class VisionRequest(BaseModel):
    image_url: str | None = None
    image_base64: str | None = None
    prompt: str = "Descreva o que você vê. Analise em termos semióticos e conecte ao Ciclo de Ação Tucci."
    context: str = "meky_camera"


class WhisperRequest(BaseModel):
    audio_base64: str
    language: str = "pt"
    context: str = "amanda_voice"


@router.get("/status")
async def hestia_status():
    api_key = os.getenv("OPENAI_API_KEY", "")
    return {
        "ok": bool(api_key),
        "agent": "Hestia",
        "model_default": "gpt-4o",
        "modelos_disponiveis": ["gpt-4o", "gpt-4o-mini", "o3", "o1"],
        "ferramentas": ["consultar_conector", "registrar_memoria", "consultar_aulias", "consultar_assembleia", "vision_analyze"],
        "api_key_configurada": bool(api_key),
        "integracao": "provisoria_3_meses",
        "ecossistema": "tucci_v4",
    }


@router.post("/chat")
async def hestia_chat_endpoint(body: ChatRequest, request: Request):
    _check_auth(request)
    result = hestia_chat(
        messages=body.messages,
        model=body.model,
        max_tool_rounds=body.max_tool_rounds,
    )
    return result


@router.post("/vision")
async def hestia_vision(body: VisionRequest, request: Request):
    _check_auth(request)
    image_ref = body.image_url or body.image_base64
    if not image_ref:
        raise HTTPException(status_code=400, detail="image_url ou image_base64 obrigatório")
    result = tool_vision_analyze(image_ref, body.prompt)
    return {
        "analysis": result,
        "model": "gpt-4o",
        "context": body.context,
    }


@router.post("/whisper")
async def hestia_whisper(body: WhisperRequest, request: Request):
    _check_auth(request)
    transcript = tool_whisper_transcribe(body.audio_base64, body.language)
    return {
        "transcript": transcript,
        "model": "whisper-1",
        "language": body.language,
        "context": body.context,
    }
