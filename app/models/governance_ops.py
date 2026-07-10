"""
Modelos de governança operacional — Heartbeat, Shutdown Ético, Aprovação Multipartite.

Tabelas:
  system_shutdown     — flag de shutdown ativo (nível 1/2/3)
  approval_requests   — ações críticas aguardando assinatura multipartite
"""
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class SystemShutdown(Base):
    """
    Flag global de shutdown ético.
    Nível 1=pausa, 2=quarentena, 3=desligamento total.
    Apenas um registro ativo por vez (id=1 é o singleton).
    """
    __tablename__ = "system_shutdown"

    id:         Mapped[int]  = mapped_column(Integer, primary_key=True)
    active:     Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    level:      Mapped[int]  = mapped_column(Integer, default=0, nullable=False)
    # 0=normal, 1=pausa (novas ações bloqueadas), 2=quarentena (writes desabilitados), 3=total
    reason:     Mapped[str]  = mapped_column(Text, default="", nullable=False)
    initiated_by: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    # "yuri" | "arvore" | "mc" | "auto" | "heartbeat"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ApprovalRequest(Base):
    """
    Aprovação multipartite para ações críticas.
    Requer assinaturas de pelo menos 2 das 3 partes: arvore, mc/amanda, yuri.
    """
    __tablename__ = "approval_requests"

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True)
    action:      Mapped[str]  = mapped_column(String(128), nullable=False)
    description: Mapped[str]  = mapped_column(Text, default="")
    payload:     Mapped[dict] = mapped_column(JSON, default=dict)

    # Assinaturas recebidas
    signed_by:   Mapped[list] = mapped_column(JSON, default=list)
    # ex: ["yuri", "arvore"]

    required_signatures: Mapped[int] = mapped_column(Integer, default=2)
    # Mínimo de assinaturas para aprovar (padrão: 2 de 3)

    status: Mapped[str] = mapped_column(String(32), default="pending")
    # "pending" | "approved" | "rejected" | "expired"

    requested_by: Mapped[str] = mapped_column(String(64), default="")
    result:       Mapped[str] = mapped_column(Text, default="")

    created_at:  Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class HeartbeatLog(Base):
    """
    Log periódico de saúde dos sistemas.
    Gravado pelo cron de heartbeat a cada 5 minutos.
    """
    __tablename__ = "heartbeat_logs"

    id:         Mapped[int]  = mapped_column(Integer, primary_key=True)
    timestamp:  Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    pap_status:   Mapped[str] = mapped_column(String(16), default="unknown")
    sc_status:    Mapped[str] = mapped_column(String(16), default="unknown")
    arpia_status: Mapped[str] = mapped_column(String(16), default="ok")
    mc_status:    Mapped[str] = mapped_column(String(16), default="unknown")
    # "ok" | "degraded" | "down" | "unknown"

    details:    Mapped[dict] = mapped_column(JSON, default=dict)
    # latências, erros, última mensagem MC, etc.

    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
