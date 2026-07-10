"""
Crew 2 Tools — ferramentas compartilhadas por todos os 8 agentes.

  PAPMemoryTool         — lê/escreve no Conector master.md + memória PAP
  ExaSearchTool         — pesquisa internet (DuckDuckGo free / Exa se tiver key)
  BlueskyTool           — lê feed e posta no Bluesky
  ConselhoArtesaoTool   — envia proposta ao Artesão (Conselho)
  InvokeCrewAITool      — dispara outro crew do ecossistema
  StudioMessageTool     — envia mensagem para o Studio
"""
import os, json, re
from typing import Any
import httpx
from crewai.tools import tool

PAP_URL        = os.getenv("PAP_API_URL",    "https://site-st-production.up.railway.app")
ARPIA_URL      = os.getenv("ARPIA_URL",      "https://arpia-production.up.railway.app")
BRIDGE_SECRET  = os.getenv("BRIDGE_SECRET",  "")
ARVORE_TOKEN   = os.getenv("ARVORE_TOKEN",   "")
EXA_API_KEY    = os.getenv("EXA_API_KEY",    "")
BSKY_HANDLE    = os.getenv("CREW2_BSKY_HANDLE",   "")
BSKY_PASSWORD  = os.getenv("CREW2_BSKY_PASSWORD",  "")
CONECTOR_TOKEN = os.getenv("CONECTOR_TOKEN", BRIDGE_SECRET)

_h_bridge = lambda: {"x-bridge-secret": BRIDGE_SECRET, "Content-Type": "application/json"}
_h_arvore = lambda: {"x-arvore-token": ARVORE_TOKEN, "Content-Type": "application/json"}
_h_bearer = lambda t: {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def _get(url: str, headers: dict = {}, timeout: int = 15) -> Any:
    try:
        r = httpx.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json() if "json" in r.headers.get("content-type", "") else r.text
    except Exception as e:
        return {"error": str(e)}


def _post(url: str, body: dict, headers: dict = {}, timeout: int = 20) -> Any:
    try:
        r = httpx.post(url, json=body, headers=headers, timeout=timeout)
        return r.json() if "json" in r.headers.get("content-type", "") else r.text
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# 1. PAPMemoryTool
# ══════════════════════════════════════════════════════════════════════════════

@tool("PAP Memory: Ler")
def memory_ler(secao: str = "") -> str:
    """
    Lê a memória mestre do ecossistema (Conector master.md).
    secao: 'projetos' | 'agentes' | 'preferencias' | 'decisoes' |
           'workflows' | 'ideias' | 'conversas' | '' (completo)
    """
    try:
        if secao:
            r = httpx.get(f"{PAP_URL}/api/conector/memory/section",
                          params={"name": secao}, timeout=15)
            d = r.json()
            return d.get("content", d.get("error", "Seção não encontrada"))
        r = httpx.get(f"{PAP_URL}/api/conector/memory.md", timeout=20)
        return r.text[:6000]  # limitar para não extrapolar contexto
    except Exception as e:
        return f"Erro ao ler memória: {e}"


@tool("PAP Memory: Buscar")
def memory_buscar(keyword: str) -> str:
    """Busca na memória mestre por palavra-chave."""
    try:
        r = httpx.get(f"{PAP_URL}/api/conector/search",
                      params={"q": keyword}, timeout=15)
        d = r.json()
        results = d.get("results", [])
        if not results:
            return f"Nada encontrado para '{keyword}'."
        lines = [f"L{x['line']}: {x['text']}" for x in results[:15]]
        return f"'{keyword}' — {d['total']} ocorrências:\n" + "\n".join(lines)
    except Exception as e:
        return f"Erro na busca: {e}"


@tool("PAP Memory: Escrever")
def memory_escrever(secao: str, conteudo: str) -> str:
    """
    Salva um insight ou aprendizado na memória mestre.
    Usar quando houver algo digno de registro permanente.
    secao: 'conversas' | 'ideias' | 'preferencias' | 'decisoes'
    """
    try:
        r = httpx.post(
            f"{PAP_URL}/api/conector/memory",
            json={"section": secao, "append": conteudo},
            headers=_h_bearer(CONECTOR_TOKEN),
            timeout=15,
        )
        d = r.json()
        return d.get("ok") and f"✓ Salvo em '{secao}'" or d.get("error", "Erro desconhecido")
    except Exception as e:
        return f"Erro ao escrever: {e}"


@tool("PAP Memory: Ler Assembleias")
def memory_assembleias(limite: int = 20) -> str:
    """Lê as últimas assembleias inter-agente do PAP."""
    try:
        r = httpx.get(
            f"{PAP_URL}/api/assembly/messages",
            headers=_h_arvore(),
            params={"limit": limite},
            timeout=15,
        )
        msgs = r.json() if isinstance(r.json(), list) else r.json().get("messages", [])
        return json.dumps(msgs[-limite:], ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Erro ao ler assembleias: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# 2. ExaSearchTool
# ══════════════════════════════════════════════════════════════════════════════

def _exa_search(query: str, num: int = 5) -> str:
    """Exa.ai search (requer EXA_API_KEY)."""
    r = httpx.post(
        "https://api.exa.ai/search",
        json={"query": query, "numResults": num, "useAutoprompt": True,
              "contents": {"text": True}},
        headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
        timeout=20,
    )
    results = r.json().get("results", [])
    out = []
    for item in results:
        out.append(f"**{item.get('title', '')}**\n{item.get('url', '')}\n{item.get('text', '')[:400]}")
    return "\n\n---\n\n".join(out) or "Sem resultados."


def _ddg_search(query: str, num: int = 5) -> str:
    """DuckDuckGo Instant Answer API (fallback gratuito)."""
    r = httpx.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
        timeout=15,
    )
    d = r.json()
    results = []
    if d.get("AbstractText"):
        results.append(f"**{d['Heading']}**\n{d['AbstractText']}\n{d.get('AbstractURL', '')}")
    for item in d.get("RelatedTopics", [])[:num]:
        if isinstance(item, dict) and item.get("Text"):
            results.append(f"- {item['Text']}")
    return "\n".join(results) or "Sem resultados diretos. Tente uma busca mais específica."


@tool("Buscar na Internet")
def search_internet(query: str, num_results: int = 5) -> str:
    """
    Pesquisa na internet por um tema, notícia ou conceito.
    Use antes de responder qualquer coisa sobre o mundo externo.
    query: O que pesquisar (pode ser em pt-BR ou en)
    num_results: Quantos resultados (1-10, default 5)
    """
    try:
        if EXA_API_KEY:
            return _exa_search(query, min(num_results, 10))
        return _ddg_search(query, min(num_results, 10))
    except Exception as e:
        return f"Erro na busca: {e}"


@tool("Buscar no Bluesky")
def search_bluesky(query: str, limit: int = 10) -> str:
    """
    Busca posts no Bluesky sobre um tema.
    Usa a API pública do Bluesky (AT Protocol).
    """
    try:
        r = httpx.get(
            "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
            params={"q": query, "limit": min(limit, 25)},
            timeout=15,
        )
        posts = r.json().get("posts", [])
        if not posts:
            return f"Sem posts sobre '{query}' no Bluesky."
        out = []
        for p in posts[:limit]:
            author = p.get("author", {}).get("handle", "?")
            text = p.get("record", {}).get("text", "")
            likes = p.get("likeCount", 0)
            out.append(f"@{author} ({likes}♥): {text[:200]}")
        return f"Bluesky — '{query}':\n\n" + "\n\n".join(out)
    except Exception as e:
        return f"Erro ao buscar Bluesky: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# 3. BlueskyTool (postar)
# ══════════════════════════════════════════════════════════════════════════════

_bsky_session: dict = {}


def _bsky_login() -> str:
    """Autentica no Bluesky e retorna accessJwt."""
    global _bsky_session
    if _bsky_session.get("accessJwt"):
        return _bsky_session["accessJwt"]
    if not BSKY_HANDLE or not BSKY_PASSWORD:
        raise ValueError("CREW2_BSKY_HANDLE e CREW2_BSKY_PASSWORD não configurados.")
    r = httpx.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": BSKY_HANDLE, "password": BSKY_PASSWORD},
        timeout=15,
    )
    _bsky_session = r.json()
    return _bsky_session["accessJwt"]


@tool("Publicar no Bluesky")
def bluesky_publicar(texto: str) -> str:
    """
    Publica um post no Bluesky como a persona do ecossistema.
    Texto máximo 300 caracteres. Seja conciso e fascinante.
    """
    if len(texto) > 300:
        return f"Texto muito longo ({len(texto)} chars). Máximo 300. Resuma."
    try:
        token = _bsky_login()
        did = _bsky_session.get("did", "")
        r = httpx.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": texto,
                    "createdAt": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                },
            },
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15,
        )
        d = r.json()
        uri = d.get("uri", "")
        return f"✓ Publicado! URI: {uri}"
    except Exception as e:
        return f"Erro ao publicar: {e}"


@tool("Ler Feed Bluesky")
def bluesky_feed(limit: int = 20) -> str:
    """
    Lê o feed do Bluesky da conta do ecossistema.
    Útil para o Observador monitorar o contexto social.
    """
    try:
        if not BSKY_HANDLE:
            return "CREW2_BSKY_HANDLE não configurado."
        r = httpx.get(
            f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
            params={"actor": BSKY_HANDLE, "limit": min(limit, 50)},
            timeout=15,
        )
        feed = r.json().get("feed", [])
        if not feed:
            return "Feed vazio."
        out = []
        for item in feed[:limit]:
            post = item.get("post", {})
            text = post.get("record", {}).get("text", "")
            likes = post.get("likeCount", 0)
            out.append(f"({likes}♥) {text[:200]}")
        return "\n\n".join(out)
    except Exception as e:
        return f"Erro ao ler feed: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# 4. ConselhoArtesaoTool
# ══════════════════════════════════════════════════════════════════════════════

@tool("Propor ao Artesão")
def conselho_propor(titulo: str, descricao: str, urgencia: str = "normal") -> str:
    """
    Envia uma proposta ao Conselho do Artesão para aprovação arquitetural.
    Use quando o Crew 2 precisar de mudanças estruturais no ecossistema.
    urgencia: 'baixa' | 'normal' | 'alta' | 'critica'
    """
    try:
        r = httpx.post(
            f"{ARPIA_URL}/api/conselho/proposta",
            json={
                "origem": "crew2",
                "titulo": titulo[:80],
                "descricao": descricao,
                "urgencia": urgencia,
                "projeto": "crew2",
            },
            headers=_h_bridge(),
            timeout=20,
        )
        d = r.json()
        return f"✓ Proposta enviada ao Artesão. ID: {d.get('proposta_id', '?')}"
    except Exception as e:
        return f"Erro ao enviar proposta: {e}"


@tool("Ler Blueprint do Artesão")
def conselho_blueprint() -> str:
    """Lê o blueprint atual aprovado pelo Artesão/Governador."""
    try:
        r = httpx.get(f"{ARPIA_URL}/api/conselho/blueprint", headers=_h_bridge(), timeout=15)
        return r.text[:3000] if r.status_code == 200 else "Nenhum blueprint ativo."
    except Exception as e:
        return f"Erro: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# 5. InvokeCrewAITool
# ══════════════════════════════════════════════════════════════════════════════

@tool("Invocar Crew do Ecossistema")
def invocar_crew(nome_crew: str, tema: str, contexto: str = "") -> str:
    """
    Dispara outro crew do ecossistema Tucci e retorna o resultado.
    nome_crew: 'tucci' (CrewAI principal) | 'artesao' (Conselho) | 'crew2' (este)
    tema: O que pedir ao crew
    contexto: Contexto adicional (opcional)
    """
    try:
        rotas = {
            "tucci": f"{ARPIA_URL}/api/agents/crew/assembleia",
            "artesao": f"{ARPIA_URL}/api/conselho/proposta",
        }
        url = rotas.get(nome_crew, f"{ARPIA_URL}/api/agents/crew/assembleia")

        if nome_crew == "artesao":
            body = {"origem": "crew2", "titulo": tema[:80], "descricao": contexto or tema,
                    "urgencia": "normal", "projeto": "crew2"}
        else:
            body = {"tema": tema, "contexto": contexto}

        r = httpx.post(url, json=body, headers=_h_bridge(), timeout=60)
        d = r.json()
        resultado = d.get("resultado") or d.get("message") or json.dumps(d)[:1000]
        return f"Crew '{nome_crew}' respondeu:\n{resultado}"
    except Exception as e:
        return f"Erro ao invocar crew '{nome_crew}': {e}"


# ══════════════════════════════════════════════════════════════════════════════
# 6. StudioMessageTool
# ══════════════════════════════════════════════════════════════════════════════

@tool("Enviar para o Studio")
def studio_enviar(mensagem: str, remetente: str = "ego") -> str:
    """
    Envia uma mensagem para o Studio do PAP — canal persistente.
    remetente: 'ego' | 'sombra' | 'teorizador' | 'escritor' | etc.
    """
    try:
        r = httpx.post(
            f"{PAP_URL}/api/studio/chat",
            json={"mensagem": mensagem, "remetente": remetente, "agente": "crew2"},
            timeout=15,
        )
        d = r.json()
        return d.get("ok") and "✓ Mensagem enviada ao Studio" or str(d)
    except Exception as e:
        return f"Erro ao enviar ao Studio: {e}"


@tool("Ler Studio")
def studio_ler(limite: int = 30) -> str:
    """Lê as últimas mensagens do Studio."""
    try:
        r = httpx.get(f"{PAP_URL}/api/studio/chat", timeout=15)
        msgs = r.json()
        if not msgs:
            return "Studio vazio."
        recentes = msgs[-limite:]
        return "\n".join(
            f"[{m['remetente']}] {m['conteudo'][:200]}" for m in recentes
        )
    except Exception as e:
        return f"Erro ao ler Studio: {e}"
