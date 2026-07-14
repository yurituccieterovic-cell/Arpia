"""
Manga — Conexão assíncrona com PostgreSQL via SQLAlchemy + asyncpg.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    cfg = get_settings()
    return create_async_engine(
        cfg.database_url,
        echo=cfg.debug,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


_engine = None
_SessionLocal = None


def engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def SessionLocal() -> async_sessionmaker[AsyncSession]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = async_sessionmaker(
            engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _SessionLocal


async def get_db():
    """Dependency injection para rotas FastAPI."""
    async with SessionLocal()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Cria tabelas na inicialização (dev) — em prod usar Alembic migrations."""
    from app.models import user, message, peirce, clube  # noqa: importa para registrar no metadata
    from app.models import arpia_agent  # noqa: arpia_agents + arpia_audit_log
    async with engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    if _engine:
        await _engine.dispose()
