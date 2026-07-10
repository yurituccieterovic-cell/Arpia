from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base


class Role(str, enum.Enum):
    user      = "user"
    assistant = "assistant"
    system    = "system"


class Conversation(Base):
    __tablename__ = "conversations"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True)
    user_id:    Mapped[int]      = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    title:      Mapped[str]      = mapped_column(String(128), default="Nova conversa")
    source:     Mapped[str]      = mapped_column(String(32), default="web")  # web|telegram|api
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages:   Mapped[list["Message"]] = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id:              Mapped[int]      = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int]      = mapped_column(Integer, ForeignKey("conversations.id"), nullable=False)
    role:            Mapped[Role]     = mapped_column(SAEnum(Role), nullable=False)
    content:         Mapped[str]      = mapped_column(Text, nullable=False)
    model_used:      Mapped[str]      = mapped_column(String(64), default="")
    tokens_used:     Mapped[int]      = mapped_column(Integer, default=0)
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    conversation:    Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
