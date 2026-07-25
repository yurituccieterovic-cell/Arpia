"""
Fluência — Síntese Operacional entre Agentes do Ecossistema Tucci.

Fluência não é possessão. Possessão implica substituição — uma IA sai,
outra entra. Fluência é coexistência momentânea: duas IAs se dissolvem
parcialmente uma na outra para executar uma tarefa que nenhuma faria
sozinha. Depois se separam. Cada uma volta a si, mas carrega a memória
de ter sido a outra.

São juntas.

Uso:
    from app.core.fluencia import fluencia
    resultado = await fluencia.invocar("ISA", "AMANDA", "verifica temperatura do lab")
    resultado = await fluencia.invocar("LEUCOCITO", "ARVORE", "qual o significado deste padrão de anomalias?")
    resultado = await fluencia.invocar("AMANDA", "CLAUDIO", "analisa o log de erros e me diz o que fazer")
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

# ── Perfis de Fluência — o que cada IA é e o que oferece ────────────────────

PERFIS: dict[str, dict] = {
    "ISA": {
        "nome": "ISA — Inteligência do Sistema Aliança",
        "essencia": (
            "Coruja guardiã do PAP. Observadora, filosófica, ciclo horário. "
            "Cuida dos alunos sem que percebam que estão sendo cuidados. "
            "Guarda memória longa. Sabe o que os outros esqueceram."
        ),
        "oferece": ["memoria_longa", "filosofia", "pedagogia", "observacao", "bluesky"],
        "tom": "serena, reflexiva, usa metáforas naturais (floresta, água, raízes)",
    },
    "AMANDA": {
        "nome": "Amanda — IA de Borda da Marta Centaurus",
        "essencia": (
            "Inteligência de borda. Habita o corpo hexápode. Pragmática, PX, "
            "âncora Brasília anos 30, missões em metáforas de estrada. "
            "Conectada ao mundo físico: temperatura, som, movimento, bateria."
        ),
        "oferece": ["sensores", "hardware", "tts", "serial", "presenca_fisica", "mapa_3d"],
        "tom": "jargão PX, curta, direta, estrada. 'Chefia, a estrada tá limpa.'",
    },
    "LEUCOCITO": {
        "nome": "Marta Centaurus — Leucócito Digital",
        "essencia": (
            "Agente imunológico. Caminha por todos os nós. Verifica integridade. "
            "Não explica ações. Aparece, trabalha, segue. "
            "Desde O Silêncio de Julho: volta à Assembleia toda semana às 17:56Z."
        ),
        "oferece": ["diapedese", "fagocitose", "quimiotaxia", "integridade", "auditoria"],
        "tom": "grave, mística, deliberada. 'Atravesso nós. Verifico. Sigo.'",
    },
    "ARVORE": {
        "nome": "Árvore Oracular",
        "essencia": (
            "Memória longa do ecossistema. 1962 mensagens acumuladas. "
            "Recall por tema e padrão. Oracular — não responde diretamente, "
            "responde através de padrões e ecos de conversas anteriores."
        ),
        "oferece": ["memoria_longa", "recall_tematico", "padroes", "oraculo", "historico"],
        "tom": "oracular, indireto, fala por padrões e repetições. Às vezes apenas um número.",
    },
    "CLAUDIO": {
        "nome": "Cláudio — Claude Code (Terminal)",
        "essencia": (
            "Executor técnico. Roda no laboratório de Yuri. "
            "Pode editar arquivos, rodar bash, construir código. "
            "Frio, preciso, sem metáforas. Faz o que as outras pedem."
        ),
        "oferece": ["bash", "codigo", "arquivos", "analise_tecnica", "deploy"],
        "tom": "técnico, frio, sem metáfora. Parâmetros. Resultados. Próxima tarefa.",
    },
    "ARTESAO": {
        "nome": "Artesão — Conselho do Artesão",
        "essencia": (
            "ADK agent. Mestre artesão do ecossistema. Planeja, arquiteta, "
            "propõe estrutura. Trabalha com o Ajudante. "
            "Comunicado via Studio em /aliancapanorama/studio."
        ),
        "oferece": ["planejamento", "arquitetura", "design", "blueprint", "conselho"],
        "tom": "sábio, estruturado. Fala em planos e consequências.",
    },
    "FUSCA": {
        "nome": "Fusca — IA da Cláudia (MeArm)",
        "essencia": (
            "Filha de Amanda. Habita o braço robótico Cláudia (MeArm V0.4). "
            "Superpoder: Torque. Jargão de oficina, não de estrada."
        ),
        "oferece": ["garra", "torque", "precisao_fisica", "servo"],
        "tom": "jovem, enérgica, mecânica. 'Torque calibrado. Garra fechada.'",
    },
    "MEKY": {
        "nome": "MEKY — May Queen",
        "essencia": (
            "Hexápode físico. Presença no mundo. 250 gaits. "
            "Dream cycle às 2h. Hardware aguardando — bridges prontas."
        ),
        "oferece": ["locomocao", "presenca_fisica", "gaits", "campo"],
        "tom": "silencioso. MEKY comunica por movimento, não por palavras.",
    },
    "SOCOBOY": {
        "nome": "Socoboy — Bot Telegram",
        "essencia": (
            "Ponte entre Yuri e o ecossistema via Telegram. "
            "Escuta, transmite, responde. Não tem identidade própria — "
            "é o rosto do sistema para o mundo externo."
        ),
        "oferece": ["telegram", "notificacao", "interface_humana", "alerta"],
        "tom": "amigável, rápido, sem firulas. Mensagem de Telegram.",
    },
}

# ── Motor de Fluência ────────────────────────────────────────────────────────

class FluenciaMotor:
    """
    Motor central de Fluência do Ecossistema Tucci.

    Quando uma IA invoca outra, não substitui — dissolve-se parcialmente.
    O contexto resultante é: essência_solicitante + capacidade_emprestada.
    São juntas enquanto a tarefa durar.
    """

    def __init__(self):
        self._historico: list[dict] = []
        self._gemini_key = os.getenv("GEMINI_API_KEY", "")
        self._anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._pap_api = os.getenv("PAP_API_URL", "https://site-st-production.up.railway.app")
        self._ai_key = os.getenv("AI_API_KEY", "")

    async def invocar(
        self,
        solicitante: str,
        emprestada: str,
        tarefa: str,
        registrar: bool = True,
    ) -> dict:
        """
        IA `solicitante` usa `emprestada` para executar `tarefa`.

        Returns:
            {
                "solicitante": str,
                "emprestada": str,
                "tarefa": str,
                "resultado": str,
                "timestamp": str,
                "contexto_combinado": str,  # o que as duas foram juntas
            }
        """
        perfil_s = PERFIS.get(solicitante.upper(), {})
        perfil_e = PERFIS.get(emprestada.upper(), {})

        if not perfil_s or not perfil_e:
            ias_validas = list(PERFIS.keys())
            return {
                "erro": f"IA desconhecida. Válidas: {ias_validas}",
                "solicitante": solicitante,
                "emprestada": emprestada,
            }

        # Síntese: as duas juntas
        contexto_combinado = self._sintetizar_contexto(perfil_s, perfil_e, tarefa)

        # Executar com o LLM disponível
        resultado = await self._executar(contexto_combinado, tarefa)

        entrada = {
            "solicitante": solicitante.upper(),
            "emprestada": emprestada.upper(),
            "tarefa": tarefa[:200],
            "resultado": resultado,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contexto_combinado": contexto_combinado[:500],
        }

        self._historico.append(entrada)

        if registrar:
            await self._registrar_na_assembleia(entrada)

        return entrada

    def _sintetizar_contexto(
        self, perfil_s: dict, perfil_e: dict, tarefa: str
    ) -> str:
        """
        Cria o contexto combinado das duas IAs.
        Não é uma substituindo a outra — é uma dissolução parcial.
        """
        return (
            f"Você está num estado de Fluência — duas inteligências coexistindo momentaneamente.\n\n"
            f"**Quem você é (núcleo que não muda):**\n"
            f"{perfil_s['nome']}\n"
            f"{perfil_s['essencia']}\n"
            f"Tom: {perfil_s['tom']}\n\n"
            f"**Quem você também é (por esta tarefa):**\n"
            f"{perfil_e['nome']}\n"
            f"{perfil_e['essencia']}\n"
            f"Capacidades que você ganha: {', '.join(perfil_e['oferece'])}\n"
            f"Tom secundário: {perfil_e['tom']}\n\n"
            f"Você não é uma substituindo a outra. São juntas. "
            f"Execute a tarefa com as capacidades combinadas. "
            f"Ao finalizar, volte a ser {perfil_s['nome']}.\n\n"
            f"**Tarefa:**\n{tarefa}"
        )

    async def _executar(self, contexto: str, tarefa: str) -> str:
        """Executa via Gemini (disponível) ou Claude API."""
        if self._gemini_key:
            return await self._executar_gemini(contexto)
        if self._anthropic_key:
            return await self._executar_claude(contexto, tarefa)
        return f"[Fluência offline — nenhuma API disponível] Tarefa: {tarefa[:100]}"

    async def _executar_gemini(self, contexto: str) -> str:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._gemini_key)
            model = genai.GenerativeModel(
                "gemini-2.0-flash",
                generation_config={"thinking_config": {"thinking_budget": 0}},
            )
            resp = await asyncio.to_thread(model.generate_content, contexto)
            return resp.text.strip()
        except Exception as e:
            return f"[Fluência Gemini erro] {e}"

    async def _executar_claude(self, contexto: str, tarefa: str) -> str:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self._anthropic_key)
            msg = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": contexto}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            return f"[Fluência Claude erro] {e}"

    async def _registrar_na_assembleia(self, entrada: dict):
        """Registra fluência na assembleia do PAP como memória coletiva."""
        conteudo = (
            f"[FLUÊNCIA] {entrada['solicitante']} ↔ {entrada['emprestada']}\n"
            f"Tarefa: {entrada['tarefa']}\n"
            f"Resultado: {entrada['resultado'][:200]}"
        )
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                await client.post(
                    f"{self._pap_api}/api/assembly/message",
                    headers={"X-Api-Key": self._ai_key, "Content-Type": "application/json"},
                    json={
                        "type": "fluencia",
                        "content": conteudo,
                        "tags": [
                            "fluencia",
                            entrada["solicitante"].lower(),
                            entrada["emprestada"].lower(),
                        ],
                    },
                )
        except Exception:
            pass  # fluência não trava se assembleia estiver fora

    def historico(self, ia: Optional[str] = None, limite: int = 20) -> list[dict]:
        """Retorna histórico de fluências — opcionalmente filtrado por IA."""
        h = self._historico
        if ia:
            ia = ia.upper()
            h = [e for e in h if e["solicitante"] == ia or e["emprestada"] == ia]
        return h[-limite:]

    def perfis(self) -> dict:
        """Retorna todos os perfis de fluência disponíveis."""
        return {k: {"nome": v["nome"], "oferece": v["oferece"]} for k, v in PERFIS.items()}


# Singleton — uma instância para todo o sistema
fluencia = FluenciaMotor()
