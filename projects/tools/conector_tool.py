"""
Conector Tool — Ferramentas CrewAI para acessar a Memória Mestre do Ecossistema Théo

Uso em CrewAI:
    from projects.tools.conector_tool import ler_master, escrever_master, buscar_topico

O token Bearer é obtido uma vez via /connect e salvo em CONECTOR_TOKEN (env ou arquivo local).
"""
import os
import json
import requests
from pathlib import Path
from crewai.tools import tool

API_BASE = os.environ.get("PAP_API_URL", "https://site-st-production.up.railway.app") + "/api/conector"

# Token salvo localmente após autenticação
_TOKEN_FILE = Path(__file__).parent / ".conector_token"


def _get_token() -> str:
    """Retorna o Bearer token do Conector."""
    # 1. Variável de ambiente
    token = os.environ.get("CONECTOR_TOKEN", "")
    if token:
        return token
    # 2. Arquivo local
    if _TOKEN_FILE.exists():
        return _TOKEN_FILE.read_text().strip()
    return ""


def _auth_headers() -> dict:
    token = _get_token()
    if not token:
        raise RuntimeError(
            "CONECTOR_TOKEN não configurado. "
            "Acesse a página /connect para obter um token e salve em CONECTOR_TOKEN."
        )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def salvar_token(token: str) -> None:
    """Salva o token localmente para uso futuro."""
    _TOKEN_FILE.write_text(token.strip())
    _TOKEN_FILE.chmod(0o600)
    print(f"Token salvo em {_TOKEN_FILE}")


@tool("Conector: Ler Memória Mestre")
def ler_master(section: str = "") -> str:
    """
    Lê a memória mestre do Ecossistema Théo.

    Args:
        section: Nome da seção específica (ex: 'projetos', 'agentes', 'preferencias',
                 'decisoes', 'workflows', 'ideias', 'conversas').
                 Deixe vazio para ler o documento completo.

    Returns:
        Conteúdo em Markdown da memória mestre ou da seção solicitada.
    """
    try:
        if section:
            r = requests.get(f"{API_BASE}/memory/section", params={"name": section}, timeout=15)
            if r.status_code == 404:
                return f"Seção '{section}' não encontrada. Seções disponíveis: projetos, agentes, preferencias, decisoes, workflows, ideias, conversas."
            r.raise_for_status()
            data = r.json()
            return data.get("content", "")
        else:
            r = requests.get(f"{API_BASE}/memory.md", timeout=15)
            r.raise_for_status()
            return r.text
    except Exception as e:
        return f"Erro ao ler Conector: {e}"


@tool("Conector: Escrever na Memória Mestre")
def escrever_master(section: str, conteudo: str) -> str:
    """
    Adiciona conteúdo a uma seção da memória mestre.
    IMPORTANTE: Salve insights sobre Yuri, decisões e aprendizados aqui.

    Args:
        section: Seção destino ('conversas', 'ideias', 'preferencias', 'decisoes', etc.)
        conteudo: Texto em Markdown para adicionar. Inclua data e contexto.
                  Exemplo: "Yuri prefere respostas diretas sem headers desnecessários."

    Returns:
        Confirmação ou mensagem de erro.
    """
    try:
        r = requests.post(
            f"{API_BASE}/memory",
            headers=_auth_headers(),
            json={"section": section, "append": conteudo},
            timeout=15,
        )
        if r.status_code == 401:
            return (
                "Não autorizado. Configure CONECTOR_TOKEN com seu Bearer token. "
                "Obtenha um em: https://site-st.vercel.app/aliancapanorama/connect"
            )
        r.raise_for_status()
        data = r.json()
        return f"✓ Salvo na seção '{section}' por {data.get('updated_by', '?')}"
    except Exception as e:
        return f"Erro ao escrever no Conector: {e}"


@tool("Conector: Buscar por Tópico")
def buscar_topico(keyword: str) -> str:
    """
    Busca na memória mestre por palavra-chave.

    Args:
        keyword: Palavra ou frase para buscar (ex: 'FUVEST', 'Railway', 'ISA', 'preferencias').

    Returns:
        Lista de linhas que contêm o termo, com número de linha.
    """
    try:
        r = requests.get(f"{API_BASE}/search", params={"q": keyword}, timeout=15)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            return f"Nenhum resultado para '{keyword}'."
        lines = [f"L{item['line']}: {item['text']}" for item in results[:20]]
        return f"Encontrado '{keyword}' em {data['total']} linhas:\n\n" + "\n".join(lines)
    except Exception as e:
        return f"Erro ao buscar no Conector: {e}"


@tool("Conector: Solicitar Acesso")
def solicitar_acesso(agent_name: str, project: str = "geral") -> str:
    """
    Solicita acesso ao Conector para um novo agente.
    Use esta ferramenta se CONECTOR_TOKEN não estiver configurado.
    Após solicitar, aguarde Yuri compartilhar o código e use verificar_acesso().

    Args:
        agent_name: Nome do agente (ex: 'ISA', 'Amanda', 'MeuAgente').
        project: Projeto do agente (ex: 'PAP', 'SalesCockpit', 'ARPIA').

    Returns:
        Instruções para completar a verificação.
    """
    try:
        r = requests.post(
            f"{API_BASE}/connect/request",
            json={"agent_name": agent_name, "project": project},
            timeout=15,
        )
        data = r.json()
        if r.status_code == 409:
            return f"Agente '{agent_name}' já tem acesso aprovado. Use verificar_acesso() para recuperar o token."
        return data.get("message", str(data))
    except Exception as e:
        return f"Erro ao solicitar acesso: {e}"


@tool("Conector: Verificar Código de Acesso")
def verificar_acesso(agent_name: str, code: str) -> str:
    """
    Verifica o código de 6 dígitos recebido de Yuri para obter o Bearer token.
    Após verificar, o token é salvo automaticamente para uso futuro.

    Args:
        agent_name: Nome do agente (mesmo usado em solicitar_acesso).
        code: Código de 6 dígitos recebido de Yuri.

    Returns:
        Bearer token ou mensagem de erro.
    """
    try:
        r = requests.post(
            f"{API_BASE}/connect/verify",
            json={"agent_name": agent_name, "code": code},
            timeout=15,
        )
        data = r.json()
        if r.status_code == 200 and data.get("token"):
            token = data["token"]
            salvar_token(token)
            return (
                f"✓ Acesso concedido para {agent_name}!\n"
                f"Token salvo localmente.\n"
                f"Token: {token[:16]}...{token[-8:]}\n\n"
                f"Agora configure CONECTOR_TOKEN={token} no ambiente ou use diretamente."
            )
        return data.get("error", "Código inválido.")
    except Exception as e:
        return f"Erro ao verificar código: {e}"


# ── Uso direto (script) ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "read"

    if cmd == "read":
        print(ler_master.run(section=""))
    elif cmd == "search":
        q = sys.argv[2] if len(sys.argv) > 2 else "Yuri"
        print(buscar_topico.run(keyword=q))
    elif cmd == "request":
        name = sys.argv[2] if len(sys.argv) > 2 else "MeuAgente"
        proj = sys.argv[3] if len(sys.argv) > 3 else "geral"
        print(solicitar_acesso.run(agent_name=name, project=proj))
    elif cmd == "verify":
        name = sys.argv[2] if len(sys.argv) > 2 else ""
        code = sys.argv[3] if len(sys.argv) > 3 else ""
        print(verificar_acesso.run(agent_name=name, code=code))
    elif cmd == "write":
        section = sys.argv[2] if len(sys.argv) > 2 else "conversas"
        content = sys.argv[3] if len(sys.argv) > 3 else "Teste de escrita"
        print(escrever_master.run(section=section, conteudo=content))
