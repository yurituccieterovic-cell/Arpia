from fastapi import APIRouter
from sqlalchemy import text
from app.core.database import SessionLocal
from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health():
    cfg = get_settings()
    db_ok = False
    try:
        async with SessionLocal()() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "app":    cfg.app_name,
        "version": cfg.app_version,
        "db":     "ok" if db_ok else "unreachable",
    }
