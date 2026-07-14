"""
Configuração centralizada da Arpia.
Todas as variáveis vêm de variáveis de ambiente (Railway → Variables tab).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Identidade ──────────────────────────────────────────────────────────
    app_name:    str = "Arpia"
    app_version: str = "1.0.0"
    debug:       bool = False

    # ── Banco (Manga — PostgreSQL no Railway) ────────────────────────────────
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/manga"

    # ── Segurança ────────────────────────────────────────────────────────────
    secret_key:          str = "TROQUE-ANTES-DE-SUBIR-PARA-PRODUCAO"
    jwt_algorithm:       str = "HS256"
    jwt_expire_minutes:  int = 60 * 24 * 7   # 7 dias

    # ── IAs externas ─────────────────────────────────────────────────────────
    anthropic_api_key:  str = ""     # Claude Sonnet 4.x
    gemini_api_key:     str = ""     # Gemini — disponível em .pap-secrets
    openai_api_key:     str = ""     # fallback opcional

    # ── Telegram (Socoboy) ──────────────────────────────────────────────────
    telegram_token:     str = ""     # obtido via @BotFather
    telegram_admin_id:  int = 0      # ID do Yuri para comandos admin

    # ── PAP Site (Front-end para CORS) ───────────────────────────────────────
    allowed_origins: list[str] = [
        "https://pap.sociedadetucci.com.br",
        "https://site-st.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # ── MEKY / Marta Centaurus ───────────────────────────────────────────────
    meky_vision_socket: str = "/tmp/meky-vision.sock"
    inat_token:         str = ""   # iNaturalist OAuth token (eco-logging)

    # ── PAP Ecosistema (memória unificada) ───────────────────────────────────
    db_api_key: str = ""   # X-PAP-Key para POST /api/ecosistema/memoria/save

    # ── Rate limits ──────────────────────────────────────────────────────────
    rate_limit_chat_per_min: int = 20
    rate_limit_auth_per_min: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
