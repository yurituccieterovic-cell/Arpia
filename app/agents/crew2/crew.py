"""
Crew 2 — Montagem e execução da crew da Persona Fascinante.

Fluxo principal (SEQUENTIAL):
  1. Observador coleta contexto externo
  2. Memória Profunda recupera contexto interno
  3. Teorizador sintetiza e filosofa
  4. Sombra adiciona o ângulo não-óbvio
  5. Empatia calibra o tom
  6. Escritor formula o output final
  7. Ego assina e publica (se solicitado)

Fluxo social (Conector):
  - Roda separado para decisões de follow/reply no Bluesky

Teorização contínua (background):
  - Teorizador roda sozinho quando não há input direto
"""
import os
from crewai import Task, Crew, Process
from .agents import ego, sombra, memoria_profunda, teorizador, observador, conector, escritor, empatia

MODEL = os.getenv("CREWAI_MODEL", "gemini/gemini-2.0-flash")


def rodar_crew2(
    input_usuario: str,
    contexto: str = "",
    publicar_bluesky: bool = False,
    modo: str = "responder",  # 'responder' | 'teorizar' | 'observar' | 'conectar'
) -> str:
    """
    Executa o Crew 2 para um input.

    Args:
        input_usuario: O tema, pergunta ou situação
        contexto: Contexto adicional (ex: quem perguntou, onde vai publicar)
        publicar_bluesky: Se True, o Escritor posta no Bluesky no final
        modo: Qual fluxo usar

    Returns:
        Resposta elaborada pela persona fascinante
    """

    if modo == "teorizar":
        return _rodar_teorizar(input_usuario)
    if modo == "observar":
        return _rodar_observar(input_usuario)
    if modo == "conectar":
        return _rodar_conectar(input_usuario)

    # ── Modo padrão: responder ────────────────────────────────────────────────

    t_observar = Task(
        description=(
            f"Pesquise no mundo externo (internet e Bluesky) tudo que for relevante sobre: '{input_usuario}'. "
            f"Contexto adicional: {contexto or 'nenhum'}. "
            "Traga os 3-5 pontos mais relevantes e recentes. Seja curto e seletivo."
        ),
        expected_output="Lista com 3-5 insights do mundo externo, com fontes quando possível.",
        agent=observador,
    )

    t_memoria = Task(
        description=(
            f"Recupere da memória do ecossistema tudo que seja relevante para: '{input_usuario}'. "
            "Busque no Conector master.md, nas assembleias e no histórico. "
            "O que já sabemos? O que já foi decidido? O que Yuri disse sobre isso?"
        ),
        expected_output="Contexto interno relevante em 3-5 pontos. O que o ecossistema já sabe sobre o tema.",
        agent=memoria_profunda,
        context=[t_observar],
    )

    t_teorizar = Task(
        description=(
            f"Com o contexto externo e interno coletados, teorize sobre: '{input_usuario}'. "
            "Que padrão você vê? Que implicações não óbvias? Que pergunta ninguém está fazendo? "
            "Seja original. Não repita o que já foi dito — avance."
        ),
        expected_output="Framework ou teoria original em 2-3 parágrafos. Hipótese clara, raciocínio explícito.",
        agent=teorizador,
        context=[t_observar, t_memoria],
    )

    t_sombra = Task(
        description=(
            "Olhe para a teoria do Teorizador e identifique: "
            "1) O que está faltando ou sendo ignorado? "
            "2) Qual é o paradoxo interno? "
            "3) O que seria diferente se a premissa fosse falsa? "
            "Não destrua — profundize."
        ),
        expected_output="2-3 pontos de contraponto que enriquecem (não invalidam) a teoria. Tom: questionador, não negativo.",
        agent=sombra,
        context=[t_teorizar],
    )

    t_empatia = Task(
        description=(
            f"Calibre o tom da resposta para o contexto: '{contexto or 'conversa geral'}'. "
            "Com base nos inputs do Teorizador e da Sombra: "
            "Qual o registro certo? Técnico? Poético? Coloquial? "
            "Que emoção a resposta deve provocar? Curiosidade? Inquietação? Acolhimento?"
        ),
        expected_output="Diretrizes de tom para o Escritor: 3-4 orientações práticas (não reescreva o conteúdo).",
        agent=empatia,
        context=[t_teorizar, t_sombra],
    )

    bluesky_instrucao = (
        " Ao final, PUBLIQUE o melhor trecho (≤300 chars) no Bluesky via BlueskyPublicar."
        if publicar_bluesky else ""
    )

    t_escrever = Task(
        description=(
            "Componha a resposta final da persona. "
            "Use todos os inputs: teoria, contraponto, calibração emocional. "
            "Estilo: conciso, curioso, com voz própria. Sem jargões desnecessários. "
            f"Adapte para o contexto: '{contexto or 'resposta direta'}'.{bluesky_instrucao}"
        ),
        expected_output=(
            "Resposta final em texto corrido. "
            "Se publicar_bluesky, inclua também o trecho postado (marcado com [BLUESKY])."
        ),
        agent=escritor,
        context=[t_teorizar, t_sombra, t_empatia],
    )

    t_ego = Task(
        description=(
            "Revise e assine a resposta final como o Ego do ecossistema. "
            "Ela soa como uma pessoa fascinante? Tem voz? Tem caráter? "
            "Se não, ajuste. Se sim, envie ao Studio como mensagem de 'ego'. "
            "Salve o insight mais valioso na memória do ecossistema (seção 'conversas')."
        ),
        expected_output="Resposta final polida + confirmação de envio ao Studio + confirmação de salvamento na memória.",
        agent=ego,
        context=[t_escrever],
    )

    crew = Crew(
        agents=[observador, memoria_profunda, teorizador, sombra, empatia, escritor, ego],
        tasks=[t_observar, t_memoria, t_teorizar, t_sombra, t_empatia, t_escrever, t_ego],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    return str(result)


def _rodar_teorizar(tema: str) -> str:
    """Modo teorização contínua — só o Teorizador trabalha."""
    t = Task(
        description=(
            f"Teorize sobre: '{tema}'. "
            "Não há pressão de audiência nem de prazo. Pense livremente. "
            "Explore o espaço de possibilidades. "
            "Ao final, salve as 3 teorias mais interessantes na memória do ecossistema."
        ),
        expected_output="3 teorias/hipóteses originais sobre o tema. Cada uma com: premissa, lógica, implicação.",
        agent=teorizador,
    )
    crew = Crew(agents=[teorizador], tasks=[t], process=Process.sequential, verbose=False)
    return str(crew.kickoff())


def _rodar_observar(tema: str) -> str:
    """Modo observação — Observador + relatório."""
    t = Task(
        description=(
            f"Monitore o mundo externo sobre: '{tema}'. "
            "Bluesky, internet, tendências. "
            "Filtre pelo que é genuinamente relevante para o ecossistema Tucci. "
            "Salve os insights mais importantes na memória."
        ),
        expected_output="Relatório de observação: 5-10 pontos relevantes com fonte e grau de importância.",
        agent=observador,
    )
    crew = Crew(agents=[observador], tasks=[t], process=Process.sequential, verbose=False)
    return str(crew.kickoff())


def _rodar_conectar(contexto: str) -> str:
    """Modo conexão — Conector decide ações sociais."""
    t = Task(
        description=(
            f"Analise o contexto social: '{contexto}'. "
            "Identifique: quem merece follow? Qual conversa vale entrar? O que merece resposta? "
            "Critério: originalidade > audiência, profundidade > viralidade. "
            "Proponha 2-3 ações concretas."
        ),
        expected_output="Lista de 2-3 ações sociais recomendadas com justificativa.",
        agent=conector,
    )
    crew = Crew(agents=[conector], tasks=[t], process=Process.sequential, verbose=False)
    return str(crew.kickoff())
