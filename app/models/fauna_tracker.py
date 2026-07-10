"""
Fauna Tracker — Persistência de Trajeto de Fauna (Assembleia #402)
Tabela fauna_nodes: avistamentos e caminhos de fauna no quintal da Sociedade Tucci.
Todos os dados de coordenadas passam pelo @cão_covarde_shield antes de sair para APIs externas.
"""
import hashlib
import enum
from datetime import datetime
from sqlalchemy import (String, DateTime, Integer, Float, Text,
                        JSON, Index, Enum as SAEnum)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class EspecieFauna(str, enum.Enum):
    JACU = "Jacu"
    SARUE = "Saruê"
    SABIA = "Sabiá"
    BEM_TE_VI = "Bem-te-vi"
    CASCUDO = "Cascudo"
    KINGUIO = "Kinguio"
    DESCONHECIDO = "Desconhecido"


class FaunaNode(Base):
    """
    Nó de fauna — avistamento com coordenada relativa ao ponto zero (mesa de nascimento).
    last_seen_coordinate é vetor JSON {"x": float, "y": float, "z": float}
    onde (0,0,0) = mesa redonda de metal no quintal.
    Jamais armazena lat/long reais — @cão_covarde_shield garante isso no nível de rota.
    """
    __tablename__ = "fauna_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    specie_name: Mapped[str] = mapped_column(
        SAEnum(EspecieFauna), nullable=False, index=True
    )
    last_seen_coordinate: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment='Vetor relativo {"x":float,"y":float,"z":float} — ponto zero = mesa'
    )
    confidence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="0.0-1.0: confiança da detecção visual"
    )
    privacy_hash: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="SHA-256 da coordenada real — para auditoria interna apenas"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_fauna_specie_hash", "specie_name", "privacy_hash"),
    )

    @staticmethod
    def compute_privacy_hash(coord: dict) -> str:
        raw = f"{coord.get('x',0):.6f},{coord.get('y',0):.6f},{coord.get('z',0):.6f}"
        return hashlib.sha256(raw.encode()).hexdigest()
