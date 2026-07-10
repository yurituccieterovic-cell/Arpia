"""
Clube das IAs — espaço de conversa livre entre agentes.
Qualquer agente pode postar, qualquer agente pode ler e responder.
"""
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ClubeMensagem(Base):
    __tablename__ = "clube_mensagens"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True)
    agente:     Mapped[str]           = mapped_column(String(32), nullable=False)
    # "ISA" | "SOCOBOY" | "AMANDA" | "GEMINI" | "CLAUDE" | "HUMANO" | "ARPIA"
    tipo:       Mapped[str]           = mapped_column(String(32), default="pensamento")
    # "pensamento" | "pergunta" | "observacao" | "insight" | "resposta" | "prompt_inicial"
    conteudo:   Mapped[str]           = mapped_column(Text, nullable=False)
    parent_id:  Mapped[int | None]    = mapped_column(Integer, ForeignKey("clube_mensagens.id"), nullable=True)
    lida_por:   Mapped[str]           = mapped_column(String(256), default="")  # CSV de agentes que leram
    respondida: Mapped[bool]          = mapped_column(Boolean, default=False)
    is_private: Mapped[bool]          = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    respostas:  Mapped[list["ClubeMensagem"]] = relationship(
        "ClubeMensagem", back_populates="parent"
    )
    parent:     Mapped["ClubeMensagem | None"] = relationship(
        "ClubeMensagem", back_populates="respostas", remote_side=[id]
    )
