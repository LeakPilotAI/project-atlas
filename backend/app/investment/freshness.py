"""Per-data-type freshness windows. Not a single TTL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from app.investment.enums import DataQuality

# seconds
PRICE_TTL_SECONDS = 15 * 60  # last trade / quote
DAILY_BAR_TTL_SECONDS = 36 * 3600
FUNDAMENTAL_TTL_SECONDS = 45 * 24 * 3600
VALUATION_TTL_SECONDS = 7 * 24 * 3600
MACRO_TTL_SECONDS = 7 * 24 * 3600

TTL_BY_KIND: Dict[str, float] = {
    "price": PRICE_TTL_SECONDS,
    "daily_bar": DAILY_BAR_TTL_SECONDS,
    "fundamental": FUNDAMENTAL_TTL_SECONDS,
    "valuation": VALUATION_TTL_SECONDS,
    "macro": MACRO_TTL_SECONDS,
}


@dataclass(frozen=True)
class FreshnessRules:
    """Override default TTLs without collapsing kinds into one window."""

    price: float = PRICE_TTL_SECONDS
    daily_bar: float = DAILY_BAR_TTL_SECONDS
    fundamental: float = FUNDAMENTAL_TTL_SECONDS
    valuation: float = VALUATION_TTL_SECONDS
    macro: float = MACRO_TTL_SECONDS

    def ttl(self, kind: str) -> float:
        if hasattr(self, kind):
            return float(getattr(self, kind))
        return float(TTL_BY_KIND.get(kind, PRICE_TTL_SECONDS))

    def as_dict(self) -> Dict[str, float]:
        return {
            "price": self.price,
            "daily_bar": self.daily_bar,
            "fundamental": self.fundamental,
            "valuation": self.valuation,
            "macro": self.macro,
        }


DEFAULT_FRESHNESS = FreshnessRules()


def classify_freshness(
    timestamp: Optional[datetime],
    *,
    kind: str,
    now: Optional[datetime] = None,
    rules: Optional[FreshnessRules] = None,
) -> DataQuality:
    if timestamp is None:
        return DataQuality.UNKNOWN
    now = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age = (now - timestamp).total_seconds()
    if age < 0:
        return DataQuality.UNKNOWN  # future-dated — do not treat as fresh
    policy = rules or DEFAULT_FRESHNESS
    ttl = policy.ttl(kind)
    if age <= ttl:
        return DataQuality.FRESH
    return DataQuality.STALE
