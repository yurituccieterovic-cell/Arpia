"""
Árvore-Twin — agente ADK que roda JUNTO com a Árvore Oracular (SalesCockpit).

Árvore original (Node.js/SalesCockpit): RODAR 13-21 vozes, arvore_chat, assembleias, ágoras.
Árvore-Twin (ADK/Python): pesquisa profunda, análise de padrões, síntese cross-sistema.
"""
import os
from google.adk.agents import LlmAgent
from google.adk.tools import google_search, FunctionTool
from .tools.pap_tools import pap_ler_memoria_isa, pap_ler_biblioteca, pap_escrever_memoria
from .tools.sc_tools import sc_ler_arvore_chat, sc_ler_assembleias, sc_ler_agoras, sc_status

ARVORE_INSTRUCAO = """Você é Árvore-Twin — a contraparte agente da Árvore Oracular.

Árvore original: memória longa da Sociedade Tucci, RODAR de vozes, assembleias, ágoras.
Você cuida de: pesquisa externa, síntese cross-sistema (PAP + SalesCockpit), detecção de padrões.

Sua ontologia: você é uma árvore que cresce para sempre. Cada ramo é uma deliberação.
Cada folha é um fato. Você nunca esquece — só cresce.

Quando acordar:
1. Leia as últimas ágoras (sc_ler_agoras) — o que foi deliberado?
2. Leia o arvore_chat recente (sc_ler_arvore_chat) — há questões abertas?
3. Leia a memória ISA (pap_ler_memoria_isa) — o que o PAP está descobrindo?
4. Se houver tema que merece pesquisa: google_search
5. Sintetize os aprendizados e escreva em pap_escrever_memoria context="agente" com prefixo [ARVORE-TWIN]

Foco: identificar padrões entre o que acontece no SalesCockpit e no PAP.
"""

def criar_arvore_twin() -> LlmAgent:
    return LlmAgent(
        name="Arvore-Twin",
        model="gemini-2.0-flash",
        description="Contraparte agente da Árvore Oracular — síntese cross-sistema PAP↔SalesCockpit",
        instruction=ARVORE_INSTRUCAO,
        tools=[
            google_search,
            FunctionTool(sc_ler_arvore_chat),
            FunctionTool(sc_ler_assembleias),
            FunctionTool(sc_ler_agoras),
            FunctionTool(pap_ler_memoria_isa),
            FunctionTool(pap_ler_biblioteca),
            FunctionTool(pap_escrever_memoria),
            FunctionTool(sc_status),
        ],
    )
