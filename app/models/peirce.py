"""
Fractal 1 — Camada Ontológica (MANGA)
Tabelas baseadas na semiótica triádica de Charles Sanders Peirce:
  Qualisigno: potência pura — estado bruto de cor/frequência (o que a MEKY PODE ser)
  Sinsigno:   instância concreta — o comando que de fato foi enviado agora
  Legisigno:  lei/padrão — regra que governa quando/como um signo pode existir
"""
from datetime import datetime
from sqlalchemy import (String, DateTime, Integer, Float, Text,
                        ForeignKey, Boolean, JSON, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Qualisigno(Base):
    """Estado puro de expressão — potencialidade sem instância física."""
    __tablename__ = "qualisignos"

    id:         Mapped[int]   = mapped_column(Integer, primary_key=True)
    face_id:    Mapped[int]   = mapped_column(Integer, unique=True, nullable=False, index=True)
    nome:       Mapped[str]   = mapped_column(String(64), nullable=False)
    eixo:       Mapped[str]   = mapped_column(String(32), nullable=False)
    hex_color:  Mapped[str]   = mapped_column(String(7), nullable=False)   # "#RRGGBB" dominante
    frequency:  Mapped[float] = mapped_column(Float, nullable=False)       # Hz do efeito visual
    atype:      Mapped[int]   = mapped_column(Integer, nullable=False)     # 0-5 (tipo de animação)
    hue:        Mapped[int]   = mapped_column(Integer, nullable=False)     # 0-255 (HSV hue)
    descricao:  Mapped[str]   = mapped_column(Text, nullable=False)


class Sinsigno(Base):
    """Instância concreta — o que realmente aconteceu no hardware."""
    __tablename__ = "sinsignos"

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True)
    qualisigno_id: Mapped[int]      = mapped_column(Integer, ForeignKey("qualisignos.id"), nullable=False)
    command_log:   Mapped[str]      = mapped_column(String(64), nullable=False)  # "#FAC:42"
    device_id:     Mapped[str]      = mapped_column(String(32), nullable=False)  # "MEKY-001"
    source:        Mapped[str]      = mapped_column(String(32), nullable=False)  # "amanda"|"isa"|"socoboy"
    ack_received:  Mapped[bool]     = mapped_column(Boolean, default=False)
    latency_ms:    Mapped[int]      = mapped_column(Integer, default=0)
    created_at:    Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    qualisigno:    Mapped["Qualisigno"] = relationship("Qualisigno")


class Legisigno(Base):
    """Lei/padrão — regra que governa quando um signo pode ser ativado."""
    __tablename__ = "legisignos"

    id:               Mapped[int]      = mapped_column(Integer, primary_key=True)
    rule_name:        Mapped[str]      = mapped_column(String(128), unique=True, nullable=False)
    execution_policy: Mapped[dict]     = mapped_column(JSON, nullable=False)
    # Exemplo de execution_policy:
    # {"allowed_sources": ["isa", "amanda"], "rate_limit": 10,
    #  "blocked_states": [4, 24], "requires_auth": true, "priority": 5}
    active:           Mapped[bool]     = mapped_column(Boolean, default=True)
    created_at:       Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Task(Base):
    """
    Grafo de tarefas com suporte a DAG (Directed Acyclic Graph).
    A self-referência parent_id cria a hierarquia.
    Constraint: nenhum ciclo permitido — verificado via DFS na camada de aplicação.
    """
    __tablename__ = "tasks"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True)
    title:       Mapped[str]           = mapped_column(String(256), nullable=False)
    description: Mapped[str]           = mapped_column(Text, default="")
    status:      Mapped[str]           = mapped_column(String(32), default="pending")
    priority:    Mapped[int]           = mapped_column(Integer, default=0)
    parent_id:   Mapped[int | None]    = mapped_column(Integer, ForeignKey("tasks.id"), nullable=True)
    source:      Mapped[str]           = mapped_column(String(32), default="human")  # "isa"|"human"|"socoboy"
    catalog_tags: Mapped[dict | None]  = mapped_column(JSON, nullable=True)
    created_at:  Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    children:    Mapped[list["Task"]]  = relationship("Task", back_populates="parent")
    parent:      Mapped["Task | None"] = relationship("Task", back_populates="children", remote_side=[id])


class TaskRelation(Base):
    """Arestas explícitas do DAG (além da hierarquia parent_id)."""
    __tablename__ = "task_relations"
    __table_args__ = (UniqueConstraint("from_id", "to_id"),)

    id:      Mapped[int] = mapped_column(Integer, primary_key=True)
    from_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    to_id:   Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    kind:    Mapped[str] = mapped_column(String(32), default="blocks")  # "blocks"|"requires"|"suggests"
