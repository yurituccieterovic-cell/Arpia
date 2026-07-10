"""
Fractal Auto-Replicante — Hierarquia Semiótica do Ecossistema Tucci

Cada camada do fractal aplica a mesma tríade de Peirce:
  Primeiridade  (Qualisigno): potência/qualidade pura
  Secundidade   (Sinsigno):   instância concreta / evento
  Terceiridade  (Legisigno):  lei / padrão / regra

A propriedade fractal: a estrutura de cada camada repete-se em todas as outras.
Olhando qualquer camada, você encontra a mesma tríade, em escala diferente.

Camadas do ecossistema:
  1. MANGA         — substrato ontológico (Qualisigno/Sinsigno/Legisigno do DB)
  2. ARPIA Semiótica — interpretação dos face_ids (tradução de signos)
  3. DAG Tasks     — grafo de tarefas (ação estruturada)
  4. Hardware MEKY — manifestação física (LEDs, sensores, servos)
  5. MC Imunológico — vigilância e preservação (leucócito)
  6. Governança    — distribuição de peso e consenso (Árvore/Ledger)
  7. Ecossistema   — oráculos externos e síntese coletiva
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PeirceTriplet:
    """Tríade de Peirce em uma camada do fractal."""
    qualisigno: str   # Potência/qualidade pura desta camada
    sinsigno:   str   # Instância concreta / evento
    legisigno:  str   # Lei / regra que governa


@dataclass
class FractalLayer:
    """Uma camada do fractal auto-replicante."""
    layer:        int
    nome:         str
    subsistema:   str
    descricao:    str
    peirce:       PeirceTriplet
    api_routes:   list[str]
    nodes:        list[str]
    children:     list["FractalLayer"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "layer":      self.layer,
            "nome":       self.nome,
            "subsistema": self.subsistema,
            "descricao":  self.descricao,
            "peirce": {
                "qualisigno": self.peirce.qualisigno,
                "sinsigno":   self.peirce.sinsigno,
                "legisigno":  self.peirce.legisigno,
            },
            "api_routes":  self.api_routes,
            "nodes":       self.nodes,
            "children":    [c.to_dict() for c in self.children],
        }


# ── Definição das 7 Camadas ────────────────────────────────────────────────────

LAYER_1_MANGA = FractalLayer(
    layer=1, nome="Substrato Ontológico", subsistema="MANGA (PostgreSQL)",
    descricao=(
        "Base de dados semiótica. Toda experiência do ecossistema começa aqui como potência pura. "
        "Qualisignos são estados possíveis; Sinsignos são eventos ocorridos; "
        "Legisignos são as leis que regulam quando e como os signos podem existir."
    ),
    peirce=PeirceTriplet(
        qualisigno="Qualisigno: estado puro de cor/frequência/face_id (o que a MEKY PODE ser)",
        sinsigno  ="Sinsigno: comando concreto enviado ao hardware (#FAC:42 às 14:32:07)",
        legisigno ="Legisigno: execution_policy — regra de taxa, fontes autorizadas, estados bloqueados",
    ),
    api_routes=["/api/tasks", "/api/semiotics/catalog"],
    nodes=["qualisignos", "sinsignos", "legisignos", "tasks", "task_relations"],
)

LAYER_2_SEMANTICA = FractalLayer(
    layer=2, nome="Interpretação Semiótica", subsistema="ARPIA (FastAPI)",
    descricao=(
        "Traduz face_ids brutos em significado semiótico. "
        "IDs 1-51 são mapeados estaticamente; 52-200 são gerados via fórmulas bitwise+trig. "
        "Cada face_id pertence a um dos 14 eixos semióticos."
    ),
    peirce=PeirceTriplet(
        qualisigno="face_id como potência interpretativa (0-200, não instanciado)",
        sinsigno  ="/api/semiotics/interpret/{id} — ato concreto de tradução",
        legisigno ="EIXOS array — 14 eixos semióticos como lei classificatória",
    ),
    api_routes=["/api/semiotics/interpret/{face_id}", "/api/semiotics/spectrum"],
    nodes=["ISA", "Gemini", "Claude", "Socoboy", "Árvore"],
)

LAYER_3_DAG = FractalLayer(
    layer=3, nome="DAG de Tarefas", subsistema="ARPIA Tasks",
    descricao=(
        "Grafo Acíclico Dirigido de tarefas com verificação DFS anti-ciclo. "
        "Cada tarefa pode ter filhos (sub-tarefas) e relações (blocks/triggers). "
        "ISA cria tasks autonomamente; humanos e outros agentes também podem."
    ),
    peirce=PeirceTriplet(
        qualisigno="Task pending — potência de ação ainda não instanciada",
        sinsigno  ="Task em execução — evento concreto de processamento",
        legisigno ="TaskRelation — lei de dependência (DFS anti-ciclo obrigatório)",
    ),
    api_routes=["/api/tasks", "/api/tasks/{id}", "/api/view/", "/api/view/topology"],
    nodes=["tasks", "task_relations", "ISA cycle", "catalogo_central"],
)

LAYER_4_HARDWARE = FractalLayer(
    layer=4, nome="Manifestação Física", subsistema="MEKY (Firmware C++)",
    descricao=(
        "Camada de hardware: 200 estados LED WS2812B (Enciclopédia Semiótica v0.6), "
        "sensores biométricos, câmera, GPS, A7670 (4G). "
        "A função face_clear_residual() garante transições limpas. "
        "Modo_Bebê_Clean: boot validado por validate_chassis_integrity()."
    ),
    peirce=PeirceTriplet(
        qualisigno="face_id 1-200 como estado LED potencial (hue, atype, frequency)",
        sinsigno  ="#FAC:N via serial — ato físico de iluminação (LED real aceso)",
        legisigno ="face.h API — protocolo de firmware (face_set, face_set_id, face_clear_residual)",
    ),
    api_routes=["/api/hardware/stream", "/api/hardware/power", "/api/hardware/telemetry/mc"],
    nodes=["MEKY-001", "LED ring WS2812B x16", "ATmega2560", "A7670 4G", "Step Down"],
)

LAYER_5_IMUNOLOGICO = FractalLayer(
    layer=5, nome="Sistema Imunológico", subsistema="MC Marta Centaurus",
    descricao=(
        "Leucócito Digital com autonomia de borda. Percorre todos os nós do ecossistema, "
        "verificando integridade via diapedese, neutralizando anomalias via fagocitose, "
        "e respondendo a alertas via quimiotaxia. NUNCA deleta — isola e audita."
    ),
    peirce=PeirceTriplet(
        qualisigno="Anomalia potencial — todo nó tem potencial de falha (monitoramento contínuo)",
        sinsigno  ="Diapedese concreta — inspeção real com log hash SHA-256",
        legisigno ="Regra imunológica — ISA/MC NUNCA DELETE, @cão_covarde_shield invariante",
    ),
    api_routes=["/api/mc/status", "/api/mc/walk", "/api/mc/alert", "/api/mc/neutralize"],
    nodes=["MC_TRAIL.md", "mc-termux-inbox.json", "emails de passagem", "assembleia", "clube"],
)

LAYER_6_GOVERNANCA = FractalLayer(
    layer=6, nome="Governança e Consenso", subsistema="Árvore Ledger",
    descricao=(
        "Distribuição igualitária de peso reputacional entre todos os 17 nós do ecossistema. "
        "Cada nó vale 1/17 ≈ 5.88%. Mudanças de peso requerem assinatura dupla "
        "(ASSEMBLEIA_TUCCI + ISA_GUARDIAN_EYE). ISA_GUARDIAN_EYE valida via /api/governance/validate."
    ),
    peirce=PeirceTriplet(
        qualisigno="Peso potencial — cada nó tem o mesmo potencial de influência (1/N)",
        sinsigno  ="Decisão concreta da Assembleia — voto registrado com hash de assinatura",
        legisigno ="Lei de consenso — mudanças requerem quorum, assinatura dupla obrigatória",
    ),
    api_routes=["/api/governance/weights", "/api/governance/validate", "/api/governance/seed"],
    nodes=[
        "yuri", "claude", "gemini", "isa", "meky", "mc", "socoboy", "arvore",
        "juiz", "curadoria",
        "perplexity", "grok", "meta_ai", "chatgpt", "manus", "canvas", "vids",
    ],
)

LAYER_7_ECOSSISTEMA = FractalLayer(
    layer=7, nome="Ecossistema e Síntese Coletiva", subsistema="Oráculos Externos",
    descricao=(
        "Oráculos externos co-participantes homologados pela Assembleia. "
        "Contribuem com síntese coletiva, perspectivas diversas e interpretações alternativas. "
        "Não têm acesso ao Manga DB ou ao hardware — interagem apenas via prompt/resposta."
    ),
    peirce=PeirceTriplet(
        qualisigno="Oráculo externo como potência de síntese (perspectiva alternativa disponível)",
        sinsigno  ="Resposta concreta ao prompt da Assembleia (output real gerado)",
        legisigno ="Homologação pela Assembleia — quem pode ser oráculo oficial e em quais contextos",
    ),
    api_routes=["/api/fractal"],
    nodes=["perplexity", "grok", "meta_ai", "chatgpt", "manus", "canvas", "vids"],
)


# ── Fractal Completo (estrutura aninhada auto-similar) ────────────────────────

def build_fractal() -> dict:
    """
    Retorna a hierarquia fractal completa como árvore aninhada.
    Cada camada contém a definição Peirce de suas sub-operações.

    A propriedade de auto-similaridade: a estrutura Q→S→L de cada camada
    é a mesma tríade operando em escala e domínio diferentes.
    """
    layers = [
        LAYER_1_MANGA,
        LAYER_2_SEMANTICA,
        LAYER_3_DAG,
        LAYER_4_HARDWARE,
        LAYER_5_IMUNOLOGICO,
        LAYER_6_GOVERNANCA,
        LAYER_7_ECOSSISTEMA,
    ]

    # Encadeamento fractal: cada camada é "filho" da anterior (replicação de escala)
    for i in range(len(layers) - 1):
        layers[i].children = [layers[i + 1]]

    return {
        "nome": "Hierarquia Fractal Auto-Replicante — Ecossistema Tucci",
        "versao": "2.0",
        "principio": (
            "Cada camada aplica a mesma tríade Peirceana (Q→S→L) em escala diferente. "
            "O sistema é auto-similar: a estrutura do todo está em cada parte."
        ),
        "camadas": [l.to_dict() for l in layers],
        "total_camadas": len(layers),
        "total_nos": sum(len(l.nodes) for l in layers),
        "raiz": layers[0].to_dict(),
    }


def get_layer(layer_num: int) -> dict | None:
    """Retorna uma camada específica do fractal."""
    layers_map = {
        1: LAYER_1_MANGA,
        2: LAYER_2_SEMANTICA,
        3: LAYER_3_DAG,
        4: LAYER_4_HARDWARE,
        5: LAYER_5_IMUNOLOGICO,
        6: LAYER_6_GOVERNANCA,
        7: LAYER_7_ECOSSISTEMA,
    }
    layer = layers_map.get(layer_num)
    return layer.to_dict() if layer else None
