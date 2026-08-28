"""Provider interfaces. Swap implementations later. Never invent fundamentals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Protocol, runtime_checkable

from app.investment.enums import DataQuality
from app.investment.freshness import classify_freshness
from app.investment.models import MeasuredValue


def _unknown(source: str, notes: str) -> MeasuredValue:
    return MeasuredValue.unknown(source=source, notes=notes)


@runtime_checkable
class PriceDataProvider(Protocol):
    name: str

    async def get_price(self, symbol: str) -> MeasuredValue: ...

    async def get_daily_ohlcv(self, symbol: str, **kwargs: object) -> list: ...


@runtime_checkable
class FundamentalDataProvider(Protocol):
    name: str

    async def get_metric(self, symbol: str, metric: str) -> MeasuredValue: ...


@runtime_checkable
class ValuationDataProvider(Protocol):
    name: str

    async def get_valuation(self, symbol: str) -> MeasuredValue: ...


@runtime_checkable
class NewsCatalystProvider(Protocol):
    name: str

    async def get_catalysts(self, symbol: str) -> MeasuredValue: ...


@runtime_checkable
class MacroDataProvider(Protocol):
    name: str

    async def get_series(self, series_id: str) -> MeasuredValue: ...


class NullProvider:
    """Safe default: always MISSING / UNKNOWN. Used until a real source is wired."""

    name = "null"

    async def get_price(self, symbol: str) -> MeasuredValue:
        return _unknown(self.name, f"price unavailable for {symbol}")

    async def get_metric(self, symbol: str, metric: str) -> MeasuredValue:
        return _unknown(self.name, f"fundamental {metric} unavailable for {symbol}")

    async def get_valuation(self, symbol: str) -> MeasuredValue:
        return _unknown(self.name, f"valuation unavailable for {symbol}")

    async def get_catalysts(self, symbol: str) -> MeasuredValue:
        return _unknown(self.name, f"catalysts unavailable for {symbol}")

    async def get_series(self, series_id: str) -> MeasuredValue:
        return _unknown(self.name, f"macro series {series_id} unavailable")

    async def get_daily_ohlcv(self, symbol: str, **kwargs: object) -> list:
        return []

    async def get_all(self, symbol: str) -> dict:
        return {}


def stamp_quality(
    *,
    value: object,
    source: str,
    timestamp: Optional[datetime],
    stale_after_seconds: float = 86400.0,
    kind: str = "price",
    now: Optional[datetime] = None,
) -> MeasuredValue:
    retrieved = now or datetime.now(timezone.utc)
    if value is None:
        return MeasuredValue.unknown(source=source, notes="missing")
    if timestamp is None:
        return MeasuredValue(
            value=value,
            source=source,
            timestamp=None,
            retrieved_at=retrieved,
            effective_timestamp=None,
            quality=DataQuality.UNKNOWN,
            availability=True,
            notes="timestamp missing",
        )
    # kind-specific TTL; stale_after_seconds is ignored so kinds stay independent
    _ = stale_after_seconds
    quality = classify_freshness(timestamp, kind=kind, now=retrieved)
    return MeasuredValue(
        value=value,
        source=source,
        timestamp=timestamp,
        retrieved_at=retrieved,
        effective_timestamp=timestamp,
        quality=quality,
        availability=True,
    )
