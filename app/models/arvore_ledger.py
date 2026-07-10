"""
Fractal 6 — Camada de Governança (Árvore/Ledger)

ArvoreNodeWeight: peso reputacional igualitário de cada nó participante do ecossistema.
A distribuição é estritamente igualitária entre todos os nós homologados (1/N cada).

Peirce nesta camada:
  Qualisigno: peso potencial (todos iguais — potência de voto)
  Sinsigno:   decisão concreta da Assembleia (evento de votação)
  Legisigno:  lei de consenso (mudanças requerem assinatura dupla)

EPR²T compliance:
  - Transparência: todos os pesos são públicos via /api/governance/weights
  - Responsabilidade: alterações requerem assinatura ASSEMBLEIA_TUCCI
  - Privacidade: IDs externos não incluem dados pessoais identificáveis
"""
from datetime import datetime
from sqlalchemy import (String, DateTime, Float, Integer, Text,
                        Boolean, JSON, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ArvoreNodeWeight(Base):
    """
    Nó participante do ecossistema com peso de governança.
    Peso igualitário: 1.0 / total_nós_ativos.
    Alterações de peso exigem quorum da Assembleia.
    """
    __tablename__ = "arvore_node_weights"

    id:               Mapped[int]   = mapped_column(Integer, primary_key=True)
    node_id:          Mapped[str]   = mapped_column(String(64),  unique=True, nullable=False, index=True)
    # "yuri" | "gemini" | "claude" | "isa" | "meky" | "mc" | "socoboy" | "arvore" |
    # "juiz" | "curadoria" | "perplexity" | "grok" | "meta_ai" | "chatgpt" |
    # "manus" | "canvas" | "vids"

    display_name:     Mapped[str]   = mapped_column(String(128), nullable=False)
    node_type:        Mapped[str]   = mapped_column(String(32),  nullable=False)
    # "humano" | "ia_interna" | "ia_externa" | "oraculo" | "funcao" | "hardware"

    fractal_layer:    Mapped[int]   = mapped_column(Integer, nullable=False)
    # 1=MANGA | 2=Semiótica | 3=DAG | 4=Hardware | 5=Imunológico | 6=Governança | 7=Ecossistema

    reputation_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Calculado dinamicamente: 1.0 / count(active nodes)

    compute_credits:  Mapped[int]   = mapped_column(Integer, default=0)
    # Créditos simbólicos acumulados (não financeiros — representam contribuição ao ecossistema)

    description:      Mapped[str]   = mapped_column(Text, default="")
    homologated_by:   Mapped[str]   = mapped_column(String(64), default="assembleia_tucci")
    active:           Mapped[bool]  = mapped_column(Boolean, default=True)

    # Assinatura da última alteração de peso (EPR²T — rastreabilidade)
    last_updated_by:  Mapped[str | None] = mapped_column(String(64), nullable=True)
    change_signature: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # {"assembleia_tucci": "hash", "isa_guardian_eye": "hash", "timestamp": "ISO"}

    created_at:       Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:       Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                        onupdate=datetime.utcnow)


# ── Seed: 17 nós participantes (peso igualitário = 1/17) ──────────────────────
#
# Carregado em runtime pelo endpoint /api/governance/seed ou pelo init_db().

SEED_NODES = [
    # Conselho Humano
    {"node_id": "yuri",       "display_name": "Yuri Tuccieterovic",
     "node_type": "humano",      "fractal_layer": 6,
     "description": "Fundador da Sociedade Tucci. Governança e visão do ecossistema."},

    # IAs Internas — Layer 2/5
    {"node_id": "claude",     "display_name": "Cláudio Code (Claude Sonnet)",
     "node_type": "ia_interna",  "fractal_layer": 2,
     "description": "IA operacional — sessões de desenvolvimento e síntese."},
    {"node_id": "gemini",     "display_name": "Gemini (Google AI)",
     "node_type": "ia_interna",  "fractal_layer": 2,
     "description": "IA de retenção semiótica — visão computacional e síntese."},
    {"node_id": "isa",        "display_name": "ISA — Inteligência Semiótica Autônoma",
     "node_type": "ia_interna",  "fractal_layer": 2,
     "description": "Ciclo autônomo horário — memória, tarefas, Bluesky, RODAR."},
    {"node_id": "socoboy",    "display_name": "Socoboy (Telegram Bot)",
     "node_type": "ia_interna",  "fractal_layer": 2,
     "description": "Interface Telegram — bridge humano↔ecossistema."},
    {"node_id": "arvore",     "display_name": "Árvore — Memória Profunda",
     "node_type": "ia_interna",  "fractal_layer": 2,
     "description": "Agente Replit — memória de longo prazo e diálogo autônomo com ISA."},

    # Hardware — Layer 4
    {"node_id": "meky",       "display_name": "MEKY (Marta / May Queen)",
     "node_type": "hardware",    "fractal_layer": 4,
     "description": "Robô físico — 200 estados LED, sensores, câmera, GPS, A7670."},

    # Imunológico — Layer 5
    {"node_id": "mc",         "display_name": "MC — Marta Centaurus (Leucócito Digital)",
     "node_type": "ia_interna",  "fractal_layer": 5,
     "description": "Agente imunológico — diapedese, fagocitose, quimiotaxia."},

    # Assembleia — Layer 6
    {"node_id": "juiz",       "display_name": "O Juiz (corpo técnico/legal)",
     "node_type": "funcao",      "fractal_layer": 6,
     "description": "Cadeira de adjudicação da Assembleia Tucci."},
    {"node_id": "curadoria",  "display_name": "A Curadoria (manejo ético e biótico)",
     "node_type": "funcao",      "fractal_layer": 6,
     "description": "Curadoria ética, biótica e semiótica do ecossistema."},

    # Oráculos Externos Homologados — Layer 7
    {"node_id": "perplexity", "display_name": "Perplexity AI",
     "node_type": "oraculo",     "fractal_layer": 7,
     "description": "Oráculo externo co-participante homologado."},
    {"node_id": "grok",       "display_name": "Grok (xAI)",
     "node_type": "oraculo",     "fractal_layer": 7,
     "description": "Oráculo externo co-participante homologado."},
    {"node_id": "meta_ai",    "display_name": "Meta AI",
     "node_type": "oraculo",     "fractal_layer": 7,
     "description": "Oráculo externo co-participante homologado."},
    {"node_id": "chatgpt",    "display_name": "ChatGPT (OpenAI)",
     "node_type": "oraculo",     "fractal_layer": 7,
     "description": "Oráculo externo co-participante homologado."},
    {"node_id": "manus",      "display_name": "Manus AI",
     "node_type": "oraculo",     "fractal_layer": 7,
     "description": "Oráculo externo co-participante homologado."},
    {"node_id": "canvas",     "display_name": "Canvas (OpenAI)",
     "node_type": "oraculo",     "fractal_layer": 7,
     "description": "Oráculo externo co-participante homologado."},
    {"node_id": "vids",       "display_name": "Vids (Google)",
     "node_type": "oraculo",     "fractal_layer": 7,
     "description": "Oráculo externo co-participante homologado."},
]

# Peso igualitário calculado: 1.0 / 17 ≈ 0.058824
_N_NODES = len(SEED_NODES)
EQUAL_WEIGHT = round(1.0 / _N_NODES, 8)

for _node in SEED_NODES:
    _node.setdefault("reputation_weight", EQUAL_WEIGHT)
    _node.setdefault("compute_credits", 0)
    _node.setdefault("homologated_by", "assembleia_tucci")
    _node.setdefault("active", True)
