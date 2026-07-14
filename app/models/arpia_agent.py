"""
ArpiaAgent + ArpiaAuditLog — tabelas Manga para o middleware cognitivo.
"""
import secrets
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ArpiaAgent(Base):
    __tablename__ = "arpia_agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), default="generic")
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    telos_local: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    logs: Mapped[list["ArpiaAuditLog"]] = relationship(back_populates="agent", lazy="selectin")

    @staticmethod
    def generate_token() -> str:
        return secrets.token_hex(32)


class ArpiaAuditLog(Base):
    __tablename__ = "arpia_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(64), ForeignKey("arpia_agents.id"))
    action: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped["ArpiaAgent"] = relationship(back_populates="logs")
