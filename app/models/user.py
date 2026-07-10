from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True)
    username:   Mapped[str]      = mapped_column(String(64), unique=True, nullable=False)
    email:      Mapped[str]      = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str]   = mapped_column(String(256), nullable=False)
    is_active:  Mapped[bool]     = mapped_column(Boolean, default=True)
    tier:       Mapped[int]      = mapped_column(Integer, default=0)   # 0=free,1=basic,2=pro
    telegram_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen:  Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
