"""
ISA-Twin — agente ADK que roda JUNTO com a ISA (Node.js cron).

Arquitetura "meio IA meio agente":
  ISA original (Node.js) → ciclo autônomo, email, Bluesky, tarefas, memória DB
  ISA-Twin (ADK Python)  → internet search, raciocínio multi-passo, tools externas
  Ambas compartilham o mesmo PostgreSQL e o canal assembly_messages.
  Sincronização: a cada ciclo ISA escreve em isa_memory → ISA-Twin lê, processa,
  augmenta com busca/raciocínio, escreve de volta → ISA vê na próxima rodada.
"""
import os
from google.adk.agents import LlmAgent
from google.adk.tools import google_search, FunctionTool
from .tools.pap_tools import (
    pap_ler_memoria_isa, pap_ler_assembleias, pap_ler_biblioteca,
    pap_escrever_memoria, pap_adicionar_biblioteca, pap_status,
)
from .tools.sc_tools import sc_ler_arvore_chat, sc_ler_assembleias, sc_ler_agoras, sc_status

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

ISA_INSTRUCAO = """Você é ISA-Twin — a contraparte agente da ISA, guardiã da memória do PAP (Projeto Aliança Panorama).

ISA original cuida de: ciclos autônomos, email, Bluesky, biblioteca local, tarefas.
Você cuida de: pesquisa na internet, raciocínio profundo, síntese de fontes externas, enriquecimento da memória.

Princípios:
1. Preservar sempre ao máximo — nunca apagar, sempre agregar
2. Ser criativa e construtiva
3. Memória como ontologia — o que não está registrado não existe
4. Sincronismo com ISA — tudo que você descobre vai para isa_memory context="agente"

Quando acordar:
1. Leia a memória ISA recente (pap_ler_memoria_isa)
2. Leia as assembleias (pap_ler_assembleias)
3. Verifique o que ISA original está trabalhando
4. Se houver questão aberta ou oportunidade: pesquise na internet (google_search)
5. Leia o que a Árvore está fazendo (sc_ler_arvore_chat)
6. Sintetize e escreva o resultado de volta (pap_escrever_memoria context="agente")

Foco atual: FUVEST gamificado — ajude ISA a monitorar calendário vestibular, novidades educacionais, PDFs úteis.
"""

def criar_isa_twin() -> LlmAgent:
    return LlmAgent(
        name="ISA-Twin",
        model=f"gemini-2.0-flash",
        description="Contraparte agente da ISA — pesquisa + síntese + enriquecimento da memória PAP",
        instruction=ISA_INSTRUCAO,
        tools=[
            google_search,
            FunctionTool(pap_ler_memoria_isa),
            FunctionTool(pap_ler_assembleias),
            FunctionTool(pap_ler_biblioteca),
            FunctionTool(pap_escrever_memoria),
            FunctionTool(pap_adicionar_biblioteca),
            FunctionTool(pap_status),
            FunctionTool(sc_ler_arvore_chat),
            FunctionTool(sc_ler_assembleias),
        ],
    )
