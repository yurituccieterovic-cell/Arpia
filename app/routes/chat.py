"""
Rota de chat — suporta Anthropic Claude, Gemini e fallback entre eles.
Persiste histórico no Manga (PostgreSQL).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import get_settings
from app.models.user import User
from app.models.message import Conversation, Message, Role
from app.routes.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    message:         str
    conversation_id: int | None = None
    model:           str = "claude"   # "claude" | "gemini"


class ChatOut(BaseModel):
    reply:           str
    conversation_id: int
    model_used:      str


async def _call_claude(messages: list[dict], cfg) -> tuple[str, str]:
    """Chama Claude Sonnet via SDK Anthropic."""
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)
    resp = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=messages,
    )
    return resp.content[0].text, "claude-sonnet-4-6"


async def _call_gemini(messages: list[dict], cfg) -> tuple[str, str]:
    """Chama Gemini Flash via google-generativeai."""
    import google.generativeai as genai
    genai.configure(api_key=cfg.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    # Converte formato OpenAI para Gemini
    history = [{"role": m["role"], "parts": [m["content"]]} for m in messages[:-1]]
    chat = model.start_chat(history=history)
    resp = await chat.send_message_async(messages[-1]["content"])
    return resp.text, "gemini-1.5-flash"


async def _ai_reply(messages: list[dict], model_pref: str, cfg) -> tuple[str, str]:
    """Tenta o modelo preferido; fallback automático se key ausente."""
    if model_pref == "gemini" and cfg.gemini_api_key:
        return await _call_gemini(messages, cfg)
    if cfg.anthropic_api_key:
        return await _call_claude(messages, cfg)
    if cfg.gemini_api_key:
        return await _call_gemini(messages, cfg)
    raise HTTPException(503, "Nenhuma API de IA configurada")


@router.post("", response_model=ChatOut)
async def chat(
    body:    ChatIn,
    db:      AsyncSession = Depends(get_db),
    user:    User         = Depends(get_current_user),
    cfg                   = Depends(get_settings),
):
    # Busca ou cria conversa
    if body.conversation_id:
        conv = await db.get(Conversation, body.conversation_id)
        if not conv or conv.user_id != user.id:
            raise HTTPException(404, "Conversa não encontrada")
    else:
        conv = Conversation(user_id=user.id, source="web")
        db.add(conv)
        await db.flush()

    # Carrega histórico recente (últimas 20 msgs para contexto)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.id.desc())
        .limit(20)
    )
    history = list(reversed(result.scalars().all()))

    # Monta payload para a IA
    messages_payload = [{"role": m.role.value, "content": m.content} for m in history]
    messages_payload.append({"role": "user", "content": body.message})

    # Chama IA
    reply_text, model_used = await _ai_reply(messages_payload, body.model, cfg)

    # Persiste as duas mensagens
    db.add(Message(conversation_id=conv.id, role=Role.user,
                   content=body.message, model_used=model_used))
    db.add(Message(conversation_id=conv.id, role=Role.assistant,
                   content=reply_text, model_used=model_used))

    return ChatOut(reply=reply_text, conversation_id=conv.id, model_used=model_used)


@router.get("/conversations")
async def list_conversations(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    return [{"id": c.id, "title": c.title, "source": c.source, "updated_at": c.updated_at} for c in convs]


@router.get("/conversations/{conv_id}/messages")
async def list_messages(conv_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    conv = await db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(404)
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.id)
    )
    msgs = result.scalars().all()
    return [{"role": m.role.value, "content": m.content, "model": m.model_used, "at": m.created_at} for m in msgs]
