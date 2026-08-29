"""Opt-in investment scan cadence. Independent from perp scan_interval_seconds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScanSettings:
    """Yahoo-respectful defaults. Not an aggressive quote loop."""

    enabled: bool = False
    interval_open_seconds: float = 3600.0
    interval_closed_seconds: float = 21600.0
    price_refresh_seconds: float = 900.0
    fundamental_refresh_seconds: float = 86400.0
    valuation_refresh_seconds: float = 86400.0
    history_refresh_seconds: float = 86400.0
    inter_symbol_delay_seconds: float = 0.75
    notify_discord: bool = True
    max_retries: int = 2
    retry_base_seconds: float = 1.0
    history_period: str = "5y"
    persist: bool = True

    @classmethod
    def from_env(cls) -> "ScanSettings":
        try:
            from app.core.config import get_settings

            s = get_settings()
        except Exception:
            return cls()
        return cls(
            enabled=bool(getattr(s, "investment_scan_enabled", False)),
            interval_open_seconds=float(getattr(s, "investment_scan_interval_seconds", 3600.0) or 3600.0),
            interval_closed_seconds=float(
                getattr(s, "investment_scan_closed_interval_seconds", 21600.0) or 21600.0
            ),
            price_refresh_seconds=float(getattr(s, "investment_price_refresh_seconds", 900.0) or 900.0),
            fundamental_refresh_seconds=float(
                getattr(s, "investment_fundamental_refresh_seconds", 86400.0) or 86400.0
            ),
            valuation_refresh_seconds=float(
                getattr(s, "investment_valuation_refresh_seconds", 86400.0) or 86400.0
            ),
            history_refresh_seconds=float(getattr(s, "investment_history_refresh_seconds", 86400.0) or 86400.0),
            inter_symbol_delay_seconds=float(
                getattr(s, "investment_inter_symbol_delay_seconds", 0.75) or 0.75
            ),
            notify_discord=bool(getattr(s, "investment_notify_discord", True)),
            max_retries=int(getattr(s, "investment_max_retries", 2) or 0),
            retry_base_seconds=float(getattr(s, "investment_retry_base_seconds", 1.0) or 1.0),
            history_period=str(getattr(s, "investment_history_period", "5y") or "5y"),
            persist=True,
        )
