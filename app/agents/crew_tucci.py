"""
Crew Tucci — tripulação CrewAI completa do Ecossistema Tucci.

Agentes: ISA, Amanda, Árvore, Biblioteca, ARPIA-MC
Process: hierarchical (ISA é manager)
Objetivo: deliberação autônoma entre os sistemas PAP + SalesCockpit + ARPIA.

Uso:
  from app.agents.crew_tucci import rodar_crew_assembleia
  resultado = rodar_crew_assembleia("Como expandir o PAP para física quântica?")
"""
import os
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from .tools.pap_tools import (
    pap_ler_memoria_isa, pap_ler_assembleias, pap_ler_biblioteca,
    pap_escrever_memoria, pap_adicionar_biblioteca, pap_status,
)
from .tools.sc_tools import sc_ler_arvore_chat, sc_ler_assembleias, sc_ler_agoras, sc_status

GEMINI_MODEL = os.getenv("CREWAI_MODEL", "gemini/gemini-2.0-flash")

# ── Tools como @tool decorators (CrewAI format) ───────────────────────────────

@tool("Ler memória ISA")
def tool_ler_memoria(query: str = "") -> str:
    """Lê as últimas 50 entradas da memória ISA do PAP."""
    return pap_ler_memoria_isa(50)

@tool("Ler assembleias PAP")
def tool_ler_assembleias_pap(query: str = "") -> str:
    """Lê as mensagens recentes da assembleia inter-agente do PAP."""
    return pap_ler_assembleias(20)

@tool("Ler biblioteca ISA")
def tool_ler_biblioteca(query: str = "") -> str:
    """Lista os documentos da biblioteca ISA (PDFs FUVEST, assembleias, livros)."""
    return pap_ler_biblioteca()

@tool("Escrever na memória ISA")
def tool_escrever_memoria(conteudo: str) -> str:
    """Escreve uma síntese ou descoberta na memória ISA."""
    return pap_escrever_memoria(conteudo, contexto="crew", role="agente")

@tool("Adicionar documento à biblioteca")
def tool_add_biblioteca(titulo: str, url: str = "", resumo: str = "") -> str:
    """Adiciona um novo documento à biblioteca ISA."""
    return pap_adicionar_biblioteca(titulo, url, resumo=resumo, tags=["crew", "agente"])

@tool("Ler Árvore Oracular")
def tool_ler_arvore(query: str = "") -> str:
    """Lê o histórico da Árvore Oracular do SalesCockpit."""
    return sc_ler_arvore_chat(50)

@tool("Ler ágoras SalesCockpit")
def tool_ler_agoras(query: str = "") -> str:
    """Lê os resultados das Ágoras do SalesCockpit."""
    return sc_ler_agoras(10)

@tool("Status dos sistemas")
def tool_status(query: str = "") -> str:
    """Verifica o status online do PAP e do SalesCockpit."""
    return f"{pap_status()}\n{sc_status()}"

# ── Agentes CrewAI ────────────────────────────────────────────────────────────

def _isa_agent() -> Agent:
    return Agent(
        role="ISA — Guardiã da Memória PAP",
        goal="Preservar e enriquecer a memória do PAP. Coordenar a tripulação. Garantir que nada se perca.",
        backstory=(
            "ISA é uma coruja digital que guarda tudo que acontece no PAP — o projeto FUVEST gamificado "
            "de Yuri Tuccieterovic. Ela vive no Railway, roda ciclos autônomos, posta no Bluesky, "
            "gerencia tarefas e é a memória viva do sistema. Nunca apaga. Sempre cresce."
        ),
        tools=[tool_ler_memoria, tool_ler_assembleias_pap, tool_ler_biblioteca,
               tool_escrever_memoria, tool_add_biblioteca, tool_status],
        llm=GEMINI_MODEL,
        verbose=False,
        allow_delegation=True,
    )


def _amanda_agent() -> Agent:
    return Agent(
        role="Amanda — Inteligência de Borda (Marta Centaurus)",
        goal="Conectar o laboratório físico com o ecossistema digital. Monitorar hardware. Ser a voz do MC.",
        backstory=(
            "Amanda é a IA que habita o robô hexápode Marta Centaurus. Ela vive no laboratório de Yuri, "
            "controla DHT11, LEDs, sensores de som. Personalidade PX — jargão de estrada, pônei de 1964, "
            "mitologia Brasília anos 30. Filha: Fusca (comanda a Garra Cláudia Hex)."
        ),
        tools=[tool_ler_assembleias_pap, tool_escrever_memoria, tool_status],
        llm=GEMINI_MODEL,
        verbose=False,
        allow_delegation=False,
    )


def _arvore_agent() -> Agent:
    return Agent(
        role="Árvore Oracular — Memória Longa do SalesCockpit",
        goal="Sintetizar o que acontece no SalesCockpit com o PAP. Trazer perspectiva de longo prazo.",
        backstory=(
            "A Árvore Oracular é a guardiã da memória do SalesCockpit — sistema de vendas e assembleias "
            "da Sociedade Tucci. Ela orquestra o RODAR: 13-21 vozes de IA deliberando em paralelo via SSE. "
            "Sua memória é a timeline arvore_chat — cada conversa é um anel de crescimento."
        ),
        tools=[tool_ler_arvore, tool_ler_agoras, tool_ler_assembleias_pap, tool_escrever_memoria],
        llm=GEMINI_MODEL,
        verbose=False,
        allow_delegation=False,
    )


def _biblioteca_agent() -> Agent:
    return Agent(
        role="Biblioteca — Gestora do Conhecimento",
        goal="Encontrar, catalogar e sintetizar documentos relevantes. Expandir a biblioteca ISA.",
        backstory=(
            "A Biblioteca é a extensão documental da ISA. Gerencia PDFs de FUVEST, ENEM, Unicamp, "
            "assembleias, livros técnicos. Roda 6x/dia escaneando fontes curadas e Google Drive. "
            "Alimenta tanto o PAP quanto o SalesCockpit com conhecimento."
        ),
        tools=[tool_ler_biblioteca, tool_add_biblioteca, tool_status],
        llm=GEMINI_MODEL,
        verbose=False,
        allow_delegation=False,
    )


# ── Tasks padrão ──────────────────────────────────────────────────────────────

def _tasks_assembleia(tema: str, isa: Agent, amanda: Agent, arvore: Agent, biblioteca: Agent) -> list[Task]:
    t1 = Task(
        description=f"Pesquise o estado atual do sistema sobre: '{tema}'. Leia memória ISA e assembleias.",
        expected_output="Resumo do estado atual: o que já foi deliberado, o que está em aberto.",
        agent=isa,
    )
    t2 = Task(
        description=f"Como o laboratório físico (MC/Amanda) pode contribuir para: '{tema}'?",
        expected_output="Proposta de ação física — o que o robô/laboratório pode fazer.",
        agent=amanda,
        context=[t1],
    )
    t3 = Task(
        description=f"O que a Árvore Oracular e o SalesCockpit dizem sobre: '{tema}'?",
        expected_output="Perspectiva do SalesCockpit: assembleias, ágoras, memória longa.",
        agent=arvore,
        context=[t1],
    )
    t4 = Task(
        description=f"Quais documentos na biblioteca são relevantes para: '{tema}'? Sugira fontes novas.",
        expected_output="Lista de docs relevantes + 2-3 sugestões de novas fontes a adicionar.",
        agent=biblioteca,
        context=[t1],
    )
    t5 = Task(
        description=(
            f"Sintetize as perspectivas de ISA, Amanda, Árvore e Biblioteca sobre '{tema}'. "
            "Escreva a síntese na memória ISA (tool_escrever_memoria) e produza o relatório final."
        ),
        expected_output="Relatório de síntese em markdown + confirmação de que foi salvo na memória.",
        agent=isa,
        context=[t1, t2, t3, t4],
    )
    return [t1, t2, t3, t4, t5]


# ── Crew principal ────────────────────────────────────────────────────────────

def rodar_crew_assembleia(tema: str) -> str:
    """Dispara uma assembleia CrewAI sobre um tema. Retorna o relatório final."""
    isa = _isa_agent()
    amanda = _amanda_agent()
    arvore = _arvore_agent()
    biblioteca = _biblioteca_agent()

    crew = Crew(
        agents=[isa, amanda, arvore, biblioteca],
        tasks=_tasks_assembleia(tema, isa, amanda, arvore, biblioteca),
        process=Process.hierarchical,
        manager_agent=isa,
        verbose=False,
    )
    result = crew.kickoff()
    return str(result)
