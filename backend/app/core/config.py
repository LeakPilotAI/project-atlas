"""Atlas settings — always load .env next to this package, not from cwd."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py → backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _BACKEND_DIR.parent
_ENV_CANDIDATES = (
    _BACKEND_DIR / ".env",
    _PROJECT_ROOT / ".env",
)


def _resolve_env_file() -> str | None:
    for p in _ENV_CANDIDATES:
        if p.is_file():
            return str(p)
    return None


def _csv(v: str | List[str] | None) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip().upper() for x in v if str(x).strip()]
    return [x.strip().upper() for x in str(v).split(",") if x.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "development"
    app_name: str = "ProjectAtlas"
    log_level: str = "INFO"
    secret_key: str = "change-me"

    # --- DB / Redis ---
    database_url: str = "postgresql+asyncpg://atlas:atlas_secure_password_2026@localhost:5432/atlas"
    redis_url: str = "redis://localhost:6379/0"
    timescale_enabled: bool = True

    # --- Discord ---
    discord_token: str = ""
    discord_channel_id: str = ""
    discord_owner_ids: str = ""

    telegram_token: str = ""
    telegram_chat_id: str = ""

    # --- Scanner / A+ ---
    scan_interval_seconds: float = 15.0
    max_concurrent_markets: int = 200
    perp_min_volume_24h: float = 15000.0
    perp_min_open_interest: float = 30000.0
    perp_min_setup_score: float = 78.0
    perp_min_confidence: float = 70.0
    perp_max_alerts_per_cycle: int = 3
    perp_alert_cooldown_minutes: int = 90
    perp_require_regime_align: bool = True
    perp_allowlist_enabled: bool = True
    perp_allowlist: str = "BTC,ETH,SOL,ANIME,BANANA,WCT,RSR,SOPH,kFLOKI,TNSR,NOT"

    # --- Perp micro coach — DEFAULTS = production targets (no silent 4/8/2M) ---
    perp_micro_enabled: bool = True
    perp_micro_paper_enabled: bool = True
    perp_micro_all_markets: bool = True
    perp_micro_risk_usd: float = 1.0
    perp_micro_max_open: int = 6
    perp_micro_max_triggers_per_day: int = 999
    perp_micro_min_oi: float = 75000.0
    perp_micro_min_vol: float = 150000.0
    perp_micro_rsi_long: float = 28.0
    perp_micro_rsi_short: float = 72.0
    perp_micro_min_extension_pct: float = 1.4
    perp_micro_scan_seconds: float = 60.0
    perp_micro_min_rr: float = 1.8
    perp_micro_prefer_majors: bool = True
    perp_micro_block_meme_for_live_stats: bool = True
    perp_micro_live_min_trades: int = 50
    perp_micro_live_min_winrate: float = 0.55
    perp_micro_live_min_sum_r: float = 8.0
    perp_micro_majors: str = (
        "BTC,ETH,SOL,XRP,BNB,DOGE,HYPE,SUI,LINK,AVAX,NEAR,APT,ARB,OP,"
        "LTC,BCH,ADA,DOT,ATOM,UNI,AAVE,MKR,CRV,LDO"
    )

    # --- Quality dip ---
    quality_dip_enabled: bool = True
    quality_dip_watchlist: str = (
        "MSFT,AAPL,GOOGL,AMZN,META,NVDA,AVGO,TSLA,MU,ADBE,CRM,NOW,ORCL,INTU,"
        "V,MA,COST,WMT,HD,NFLX,UNH,LLY,JNJ,ABBV,PG,KO,JPM,BRK-B,SPY,QQQ,IWM,"
        "DIA,VTI,VOO,QQQM,XLK,XLF,XLV,SMH,GLD,IAU,GDX,SLV,SIL"
    )
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
    quality_dip_scan_interval_minutes: float = 60.0
    quality_dip_cooldown_hours: float = 24.0

    # --- Day trade ---
    day_trade_enabled: bool = True
    day_trade_watchlist: str = (
        "MSFT,AAPL,GOOGL,AMZN,META,NVDA,TSLA,MU,ADBE,CRM,NOW,ORCL,INTU,SPY,QQQ,GLD,SLV"
    )
    day_trade_gap_long_pct: float = 1.5
    day_trade_gap_short_pct: float = 2.0
    day_trade_scan_seconds: float = 60.0
    day_trade_alert_cooldown_minutes: float = 15.0

    # --- Robinhood / command center ---
    robinhood_brief_enabled: bool = True
    robinhood_brief_hour_et: int = 8
    robinhood_brief_minute_et: int = 0
    robinhood_core_watchlist: str = (
        "MSFT,AAPL,GOOGL,AMZN,META,NVDA,AVGO,V,MA,JPM,BRK-B,UNH,LLY,JNJ,PG,KO,COST,WMT,SPY,QQQ,VOO,VTI"
    )
    robinhood_dip_min_pct: float = 12.0
    robinhood_max_names_in_brief: int = 8
    command_center_enabled: bool = True
    command_center_hour_et: int = 8
    command_center_minute_et: int = 0

    micro_heartbeat_enabled: bool = True
    micro_heartbeat_hours: float = 6.0
    daily_paper_recap_enabled: bool = True
    daily_paper_recap_hour_et: int = 20
    daily_paper_recap_minute_et: int = 0

    accum_enabled: bool = True
    accum_symbols: str = (
        "MSFT,GOOGL,META,ORCL,NVDA,TSLA,IAU,INTU,ADBE,AVGO,GLD,NFLX,MU,SLV,GDX,SIL,CRM,NOW"
    )
    accum_scan_minutes: float = 15.0
    btc_accum_enabled: bool = True
    btc_accum_levels: str = "60000,56000,52000,48000,42000,36000,30000"
    btc_accum_scan_minutes: float = 15.0
    btc_accum_cooldown_hours: float = 720.0

    # --- Investment engine (opt-in, isolated from perps) ---
    investment_scan_enabled: bool = False
    investment_scan_interval_seconds: float = 3600.0
    investment_scan_closed_interval_seconds: float = 21600.0
    investment_price_refresh_seconds: float = 900.0
    investment_fundamental_refresh_seconds: float = 86400.0
    investment_valuation_refresh_seconds: float = 86400.0
    investment_history_refresh_seconds: float = 86400.0
    investment_inter_symbol_delay_seconds: float = 0.75
    investment_notify_discord: bool = True
    investment_max_retries: int = 2
    investment_retry_base_seconds: float = 1.0
    investment_history_period: str = "5y"

    @property
    def database_url_safe(self) -> str:
        u = self.database_url
        if "@" in u and "://" in u:
            try:
                head, tail = u.split("://", 1)
                creds, host = tail.split("@", 1)
                if ":" in creds:
                    user, _ = creds.split(":", 1)
                    return f"{head}://{user}:***@{host}"
            except Exception:
                pass
        return u

    @property
    def perp_allowlist_list(self) -> List[str]:
        return _csv(self.perp_allowlist)

    @property
    def perp_micro_majors_list(self) -> List[str]:
        return _csv(self.perp_micro_majors)

    @property
    def quality_dip_watchlist_list(self) -> List[str]:
        return _csv(self.quality_dip_watchlist)

    @property
    def day_trade_watchlist_list(self) -> List[str]:
        return _csv(self.day_trade_watchlist)

    @property
    def robinhood_core_watchlist_list(self) -> List[str]:
        return _csv(self.robinhood_core_watchlist)

    @property
    def accum_symbol_list(self) -> List[str]:
        return _csv(self.accum_symbols)

    @property
    def btc_accum_levels_list(self) -> List[float]:
        out: List[float] = []
        for x in str(self.btc_accum_levels or "").split(","):
            x = x.strip()
            if not x:
                continue
            try:
                out.append(float(x))
            except ValueError:
                pass
        return out

    @property
    def discord_owner_id_list(self) -> List[int]:
        out: List[int] = []
        for x in str(self.discord_owner_ids or "").split(","):
            x = x.strip()
            if x.isdigit():
                out.append(int(x))
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()