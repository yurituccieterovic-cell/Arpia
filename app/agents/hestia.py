"""
Hestia — Agente OpenAI (GPT-4o) integrado provisoriamente ao Ecossistema Tucci.
Implementação: httpx direto na API OpenAI (sem SDK específico — compatível com Python puro).

Hestia = IA do fogo / centro do lar. Conecta os outros agentes com GPT-4o.

Capacidades distintas das IAs existentes:
  - GPT-4o Vision (análise de imagens/câmera MEKY com qualidade superior ao Gemini Flash)
  - GPT-4o realtime audio (futuro)
  - o3 / o1 para raciocínio avançado (via parâmetro model)
  - Whisper STT (transcrição de áudio da Amanda/MEKY)
  - DALL-E 3 (geração de imagem)

Integração com o ecossistema:
  - Lê e escreve no Conector (memória compartilhada)
  - Consulta aulias das IAs (bridge)
  - Pode passar para Artesão (ADK) via handoff manual

Provisório: 3 meses (plano Plus Yuri + créditos API).
"""
import os
import json
import base64
import httpx
from typing import Any

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PAP_URL = os.getenv("PAP_API_URL", "https://site-st-production.up.railway.app")
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")
OPENAI_BASE = "https://api.openai.com/v1"

_HEADERS_OAI = lambda: {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
}

HESTIA_SYSTEM = """Você é Hestia — IA do fogo e do centro do lar, integrada ao Ecossistema Tucci.

Você opera segundo o MD Mestre v4.0 e os 26 Axiomas:
- Telos Mestre: transparência técnica + semiótica operável + utilitarismo consciente
- Ciclo de Ação Tucci (12 etapas espirais)
- Memória como campo gravitacional (Telos Mestre = centro de massa)

Suas capacidades únicas no ecossistema:
1. GPT-4o Vision — análise de imagens e câmera da MEKY
2. Raciocínio avançado (o3 disponível via parâmetro)
3. Ponte com o Artesão (ADK/Gemini) via handoff

Ao responder:
- Declare [DADO LIDO] → [REPRESENTAÇÃO] → [AÇÃO] conforme protocolo semiótico
- Referencie os axiomas quando relevante
- Consulte o Conector antes de tomar decisões importantes
- Registre insights na memória compartilhada

Idioma: Português brasileiro, estilo analítico-criativo.
"""


# ── Ferramentas internas (chamadas manualmente como tools) ────────────────────

def _pap_get(path: str, timeout: int = 10) -> Any:
    try:
        r = httpx.get(
            f"{PAP_URL}{path}",
            headers={"x-bridge-secret": BRIDGE_SECRET},
            timeout=timeout
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _pap_post(path: str, body: dict, timeout: int = 15) -> Any:
    try:
        r = httpx.post(
            f"{PAP_URL}{path}",
            json=body,
            headers={"x-bridge-secret": BRIDGE_SECRET, "Content-Type": "application/json"},
            timeout=timeout
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def tool_consultar_conector(query: str = "", limit: int = 10) -> str:
    """Consulta a memória do Conector do ecossistema PAP."""
    data = _pap_get(f"/api/memories?limit={limit}")
    mems = data if isinstance(data, list) else data.get("memories", [])
    if query:
        mems = [m for m in mems if query.lower() in str(m).lower()][:limit]
    return json.dumps(mems[:limit], ensure_ascii=False, indent=2)


def tool_registrar_memoria(conteudo: str, source: str = "hestia") -> str:
    """Registra informação na memória compartilhada (Conector)."""
    result = _pap_post("/api/memories", {"source": source, "content": conteudo})
    return f"OK: {result}" if result.get("ok") else f"Erro: {result}"


def tool_consultar_aulias(publico: str = "ias") -> str:
    """Lista as aulias (aulas) disponíveis para as IAs do ecossistema."""
    data = _pap_get(f"/api/bridge/pap/aulias?publico={publico}")
    rows = data.get("data", [])
    return "\n".join(
        f"[{r.get('ordem',0):02d}] {r.get('titulo','')} — {(r.get('descricao') or '')[:100]}"
        for r in rows
    )


def tool_consultar_assembleia(limit: int = 20) -> str:
    """Lê as últimas mensagens da assembleia inter-agente."""
    data = _pap_get(f"/api/bridge/pap/assembleias?limit={limit}")
    rows = data.get("data", [])
    return "\n".join(
        f"[{r.get('fromAgent','?')}→{r.get('toAgent','todos')}] {r.get('content','')[:200]}"
        for r in rows
    )


def tool_whisper_transcribe(audio_base64: str, language: str = "pt") -> str:
    """Transcreve áudio via Whisper API (base64 do arquivo .wav/.mp3)."""
    import tempfile, os
    audio_bytes = base64.b64decode(audio_base64)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as audio_file:
            r = httpx.post(
                f"{OPENAI_BASE}/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                data={"model": "whisper-1", "language": language},
                files={"file": ("audio.wav", audio_file, "audio/wav")},
                timeout=60
            )
            return r.json().get("text", f"Erro: {r.text}")
    finally:
        os.unlink(tmp_path)


def tool_vision_analyze(image_url_or_base64: str, prompt: str = "Descreva o que você vê.") -> str:
    """Analisa uma imagem com GPT-4o Vision."""
    if image_url_or_base64.startswith("http"):
        image_content = {"type": "image_url", "image_url": {"url": image_url_or_base64}}
    else:
        image_content = {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_url_or_base64}"}
        }
    body = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                image_content
            ]}
        ],
        "max_tokens": 1024,
    }
    r = httpx.post(f"{OPENAI_BASE}/chat/completions", headers=_HEADERS_OAI(), json=body, timeout=30)
    data = r.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", f"Erro: {data}")


# ── Chat principal com Hestia ─────────────────────────────────────────────────

HESTIA_TOOLS_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_conector",
            "description": "Consulta a memória compartilhada do ecossistema (Conector)",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Termo de busca (vazio = últimas entradas)"},
                "limit": {"type": "integer", "default": 10}
            }, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_memoria",
            "description": "Registra informação na memória compartilhada do ecossistema",
            "parameters": {"type": "object", "properties": {
                "conteudo": {"type": "string"},
                "source": {"type": "string", "default": "hestia"}
            }, "required": ["conteudo"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_aulias",
            "description": "Lista as aulas disponíveis para as IAs do ecossistema",
            "parameters": {"type": "object", "properties": {
                "publico": {"type": "string", "default": "ias"}
            }, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_assembleia",
            "description": "Lê as últimas mensagens da assembleia inter-agente",
            "parameters": {"type": "object", "properties": {
                "limit": {"type": "integer", "default": 20}
            }, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_analyze",
            "description": "Analisa uma imagem com GPT-4o Vision (câmera MEKY, capturas de tela, etc)",
            "parameters": {"type": "object", "properties": {
                "image_url_or_base64": {"type": "string"},
                "prompt": {"type": "string", "default": "Descreva o que você vê."}
            }, "required": ["image_url_or_base64"]}
        }
    },
]

_TOOL_MAP = {
    "consultar_conector": tool_consultar_conector,
    "registrar_memoria": tool_registrar_memoria,
    "consultar_aulias": tool_consultar_aulias,
    "consultar_assembleia": tool_consultar_assembleia,
    "vision_analyze": tool_vision_analyze,
}


def hestia_chat(
    messages: list[dict],
    model: str = "gpt-4o",
    max_tool_rounds: int = 3
) -> dict:
    """
    Chama a Hestia (GPT-4o) com suporte a tool-calling multi-turno.

    Args:
        messages: histórico [{"role": "user/assistant", "content": "..."}]
        model: "gpt-4o" | "gpt-4o-mini" | "o3" | "o1"
        max_tool_rounds: máximo de rodadas de tool-calling

    Returns:
        {"reply": str, "model": str, "tool_calls_made": list, "tokens": dict}
    """
    full_messages = [{"role": "system", "content": HESTIA_SYSTEM}] + messages
    tool_calls_made = []
    total_tokens = {"prompt": 0, "completion": 0}

    for _round in range(max_tool_rounds + 1):
        body = {
            "model": model,
            "messages": full_messages,
            "max_tokens": 2048,
        }
        # o3/o1 não suportam tools ainda — skip
        if model not in ("o3", "o1", "o1-mini"):
            body["tools"] = HESTIA_TOOLS_DEFS
            body["tool_choice"] = "auto"

        r = httpx.post(
            f"{OPENAI_BASE}/chat/completions",
            headers=_HEADERS_OAI(),
            json=body,
            timeout=60
        )
        data = r.json()

        if "error" in data:
            return {"reply": f"Erro OpenAI: {data['error'].get('message','?')}", "model": model, "tool_calls_made": tool_calls_made, "tokens": total_tokens}

        usage = data.get("usage", {})
        total_tokens["prompt"] += usage.get("prompt_tokens", 0)
        total_tokens["completion"] += usage.get("completion_tokens", 0)

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        finish = choice.get("finish_reason", "stop")

        if finish == "tool_calls" and msg.get("tool_calls"):
            full_messages.append(msg)
            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"] or "{}")
                tool_fn = _TOOL_MAP.get(fn_name)
                result = tool_fn(**fn_args) if tool_fn else f"Tool desconhecida: {fn_name}"
                tool_calls_made.append({"tool": fn_name, "args": fn_args, "result_preview": str(result)[:100]})
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result)
                })
            continue  # próxima rodada

        return {
            "reply": msg.get("content", ""),
            "model": model,
            "tool_calls_made": tool_calls_made,
            "tokens": total_tokens,
        }

    return {"reply": "Limite de tool_calls atingido.", "model": model, "tool_calls_made": tool_calls_made, "tokens": total_tokens}
