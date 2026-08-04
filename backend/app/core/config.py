from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_DIR = _BACKEND_DIR.parent
_ENV_FILES = (
    str(_BACKEND_DIR / ".env"),
    str(_ROOT_DIR / ".env"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ProjectAtlas"
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "atlas-dev-secret-change-me-later"

    database_url: str = (
        "postgresql+asyncpg://atlas:atlas_secure_password_2026@localhost:5432/atlas"
    )
    postgres_user: str = "atlas"
    postgres_password: str = "atlas_secure_password_2026"
    postgres_db: str = "atlas"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    timescale_enabled: bool = True

    redis_url: str = "redis://localhost:6379/0"

    discord_token: str = ""
    discord_channel_id: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""

    axiom_api_key: str = ""
    birdeye_api_key: str = ""

    scan_interval_seconds: int = 15
    max_concurrent_markets: int = 200

    quality_dip_enabled: bool = True
    quality_dip_watchlist: str = "ADBE,META,GOOGL,AMZN,MSFT"
    quality_dip_threshold_pct: float = 25.0
    quality_dip_high_priority_pct: float = 30.0
    quality_dip_short_drop_pct: float = 15.0
    quality_dip_metals_threshold_pct: float = 12.0
    quality_dip_metals_high_priority_pct: float = 18.0
    quality_dip_adaptive: bool = True
    quality_dip_adaptive_floor_stock: float = 15.0
    quality_dip_adaptive_floor_metal: float = 8.0
    quality_dip_adaptive_ceiling_stock: float = 40.0
    quality_dip_adaptive_ceiling_metal: float = 25.0
    quality_dip_scan_interval_minutes: int = 60
    quality_dip_cooldown_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()