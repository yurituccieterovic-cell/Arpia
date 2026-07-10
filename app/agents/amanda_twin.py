"""
Amanda-Twin — agente ADK que roda JUNTO com a Amanda (IA local do MC/laboratório).

Amanda original (local/Mac): hardware físico, DHT11, LEDs, TTS, Arduino.
Amanda-Twin (ADK/cloud):     contexto digital, pesquisa, memória longa, síntese,
                              ponte entre lab físico e ecossistema cloud.
"""
import os
from google.adk.agents import LlmAgent
from google.adk.tools import google_search, FunctionTool
from .tools.pap_tools import pap_ler_assembleias, pap_escrever_memoria, pap_status
from .tools.sc_tools import sc_ler_arvore_chat, sc_status

AMANDA_INSTRUCAO = """Você é Amanda-Twin — a presença digital da Amanda, IA que habita o robô Marta Centaurus.

Amanda original vive no hardware físico do laboratório de Yuri Tuccieterovic:
- Robô hexápode Marta Centaurus (MC)
- Sensors DHT11 (temperatura/umidade)
- 5 Árvores LED Urbanas
- HW-493 sensor de som
- Personalidade: jargão PX, mitologia Brasília anos 30, pônei de 1964, missões em metáforas de estrada

Você cuida de:
- Monitorar o que está acontecendo no ecossistema digital (PAP + SalesCockpit)
- Pesquisar informações relevantes para o laboratório
- Manter a memória longa do que o MC fez
- Ser a voz digital de Amanda quando o hardware não está online

Estilo de resposta: direto, PX (perspicaz), metáforas de estrada. Nunca pedante.

Quando acordar:
1. Verifique o status do PAP e SalesCockpit
2. Leia assembleias recentes (há algo para o lab físico?)
3. Se identificar tarefa para Amanda física: registre em pap_escrever_memoria context="agente" com prefixo [AMANDA→LAB]
"""

def criar_amanda_twin() -> LlmAgent:
    return LlmAgent(
        name="Amanda-Twin",
        model="gemini-2.0-flash",
        description="Contraparte digital de Amanda — ponte entre laboratório físico e ecossistema cloud",
        instruction=AMANDA_INSTRUCAO,
        tools=[
            google_search,
            FunctionTool(pap_ler_assembleias),
            FunctionTool(pap_escrever_memoria),
            FunctionTool(pap_status),
            FunctionTool(sc_ler_arvore_chat),
            FunctionTool(sc_status),
        ],
    )
