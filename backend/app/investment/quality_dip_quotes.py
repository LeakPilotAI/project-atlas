"""Fresh market quote overlay for the Quality Dips research dashboard.

Atlas prefers the newest timestamped 1-minute pre/regular/post-market print that
Yahoo exposes, then falls back to timestamped quote fields. A last-session quote can
remain visible across a weekend/holiday, but only LIVE/FRESH quotes may trigger an
accumulation ladder hit.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, time as dt_time, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from app.investment.yfinance_client import ProviderCallError, YFinanceClient

CACHE_TTL_SEC = 30.0
LIVE_AGE_SEC = 120.0
FRESH_AGE_SEC = 15 * 60.0
MAX_REFERENCE_AGE_SEC = 96 * 3600.0
ET = ZoneInfo("America/New_York")


class QualityDipQuoteService:
    def __init__(self, client: YFinanceClient | None = None) -> None:
        self.client = client or YFinanceClient(min_interval_sec=0.05, timeout_sec=8.0)
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def get_many(
        self,
        symbols: Iterable[str],
        *,
        max_cache_age_sec: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        clean = sorted({str(s or "").upper().strip() for s in symbols if str(s or "").strip()})
        sem = asyncio.Semaphore(6)
        cache_age = CACHE_TTL_SEC if max_cache_age_sec is None else max(5.0, float(max_cache_age_sec))

        async def one(symbol: str) -> tuple[str, dict[str, Any]]:
            cached = self._cache.get(symbol)
            if cached and time.monotonic() - cached[0] <= cache_age:
                return symbol, dict(cached[1])
            async with sem:
                snap = await self._fetch(symbol)
            async with self._lock:
                self._cache[symbol] = (time.monotonic(), dict(snap))
            return symbol, snap

        return dict(await asyncio.gather(*(one(s) for s in clean)))

    async def _fetch(self, symbol: str) -> dict[str, Any]:
        retrieved = datetime.now(timezone.utc)
        candidates: list[tuple[datetime, float, str, str]] = []
        market_state = "UNKNOWN"
        provider_errors: list[str] = []

        # Prefer the newest real 1-minute print, including supported pre/post market.
        try:
            history = await self.client.history(symbol, period="5d", interval="1m", prepost=True)
            intraday = _latest_intraday(history, retrieved)
            if intraday is not None:
                ts, price = intraday
                candidates.append((ts, price, _session_for_ts(ts), "yfinance_1m"))
        except ProviderCallError as exc:
            provider_errors.append(f"history:{exc.failure.code}")
        except Exception as exc:
            provider_errors.append(f"history:{type(exc).__name__}")

        info: dict[str, Any] = {}
        try:
            info = await self.client.info(symbol)
            market_state = str(info.get("marketState") or "UNKNOWN").upper()
        except ProviderCallError as exc:
            provider_errors.append(f"info:{exc.failure.code}")
        except Exception as exc:
            provider_errors.append(f"info:{type(exc).__name__}")

        for price_key, time_key, label in (
            ("postMarketPrice", "postMarketTime", "POST_MARKET"),
            ("preMarketPrice", "preMarketTime", "PRE_MARKET"),
            ("regularMarketPrice", "regularMarketTime", "REGULAR"),
            ("currentPrice", "regularMarketTime", "REGULAR"),
        ):
            price = _float(info.get(price_key))
            ts = _epoch(info.get(time_key))
            if price is not None and price > 0 and ts is not None and ts <= retrieved:
                candidates.append((ts, price, label, "yfinance_quote"))

        if not candidates:
            price = _float(info.get("previousClose"))
            if price is not None and price > 0:
                return {
                    "symbol": symbol,
                    "price": price,
                    "display_price": price,
                    "source": "yfinance",
                    "session": "PREVIOUS_CLOSE",
                    "market_state": market_state,
                    "effective_timestamp": None,
                    "retrieved_at": retrieved.isoformat(),
                    "age_sec": None,
                    "quality": "REFERENCE_ONLY",
                    "fresh_for_display": True,
                    "tradable_for_ladder": False,
                    "is_live": False,
                    "error": None,
                    "provider_notes": provider_errors,
                }
            return self._missing(symbol, retrieved, "EMPTY", ", ".join(provider_errors) or "no timestamped quote fields")

        ts, price, session, source = max(candidates, key=lambda x: x[0])
        age = max(0.0, (retrieved - ts).total_seconds())
        if age <= LIVE_AGE_SEC:
            quality = "LIVE"
        elif age <= FRESH_AGE_SEC:
            quality = "FRESH"
        elif age <= MAX_REFERENCE_AGE_SEC:
            quality = "REFERENCE"
        else:
            quality = "STALE"
        actionable = quality in {"LIVE", "FRESH"}
        return {
            "symbol": symbol,
            "price": price,
            "display_price": price,
            "source": source,
            "session": session,
            "market_state": market_state,
            "effective_timestamp": ts.isoformat(),
            "retrieved_at": retrieved.isoformat(),
            "age_sec": round(age, 1),
            "quality": quality,
            "fresh_for_display": quality in {"LIVE", "FRESH", "REFERENCE"},
            "tradable_for_ladder": actionable,
            "is_live": quality == "LIVE",
            "error": None,
            "provider_notes": provider_errors,
        }

    @staticmethod
    def _missing(symbol: str, retrieved: datetime, code: str, message: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "price": None,
            "display_price": None,
            "source": "yfinance",
            "session": "UNKNOWN",
            "market_state": "UNKNOWN",
            "effective_timestamp": None,
            "retrieved_at": retrieved.isoformat(),
            "age_sec": None,
            "quality": "MISSING",
            "fresh_for_display": False,
            "tradable_for_ladder": False,
            "is_live": False,
            "error": {"code": code, "message": message[:180]},
            "provider_notes": [],
        }


def apply_quote_overlay(rows: Iterable[dict[str, Any]], quotes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        symbol = str(row.get("symbol") or "").upper()
        quote = dict(quotes.get(symbol) or {})
        research_price = _float(row.get("price"))
        row["research_price"] = research_price
        row["research_timestamp"] = row.get("timestamp")
        row["current_quote"] = quote
        row["quote_display_price"] = quote.get("display_price") or quote.get("price")
        row["quote_price"] = quote.get("price") if quote.get("fresh_for_display") else None

        current_price = _float(row.get("quote_price"))
        drawdown = dict(row.get("drawdown") or {})
        old_dd = _float(drawdown.get("current_drawdown"))
        if current_price is not None and research_price and research_price > 0 and old_dd is not None and -1 < old_dd < 0:
            prior_high = research_price / (1.0 + old_dd)
            if prior_high > 0:
                drawdown["research_current_drawdown"] = old_dd
                drawdown["prior_high_anchor"] = prior_high
                drawdown["current_drawdown"] = current_price / prior_high - 1.0
                row["price"] = current_price
                row["price_provenance"] = "CURRENT_QUOTE"
        else:
            row["price_provenance"] = "RESEARCH_OBSERVATION"
        row["drawdown"] = drawdown
        out.append(row)
    return out


def quote_health(quotes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    values = list(quotes.values())
    return {
        "requested": len(values),
        "live": sum(1 for q in values if q.get("quality") == "LIVE"),
        "fresh": sum(1 for q in values if q.get("quality") == "FRESH"),
        "reference": sum(1 for q in values if q.get("quality") in {"REFERENCE", "REFERENCE_ONLY"}),
        "stale": sum(1 for q in values if q.get("quality") == "STALE"),
        "missing": sum(1 for q in values if q.get("quality") == "MISSING"),
        "source": "yfinance_1m+quote_fields",
        "cache_ttl_sec": CACHE_TTL_SEC,
        "live_age_sec": LIVE_AGE_SEC,
        "fresh_age_sec": FRESH_AGE_SEC,
        "reference_age_sec": MAX_REFERENCE_AGE_SEC,
    }


def _latest_intraday(frame: Any, retrieved: datetime) -> tuple[datetime, float] | None:
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        closes = frame["Close"].dropna()
    except Exception:
        return None
    if getattr(closes, "empty", True):
        return None
    try:
        raw_ts = closes.index[-1]
        price = _float(closes.iloc[-1])
        if price is None or price <= 0:
            return None
        if hasattr(raw_ts, "to_pydatetime"):
            ts = raw_ts.to_pydatetime()
        elif isinstance(raw_ts, datetime):
            ts = raw_ts
        else:
            ts = datetime.fromisoformat(str(raw_ts))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        if ts > retrieved:
            return None
        return ts, price
    except Exception:
        return None


def _session_for_ts(ts: datetime) -> str:
    local = ts.astimezone(ET)
    if local.weekday() >= 5:
        return "OFF_HOURS"
    t = local.timetz().replace(tzinfo=None)
    if dt_time(4, 0) <= t < dt_time(9, 30):
        return "PRE_MARKET"
    if dt_time(9, 30) <= t < dt_time(16, 0):
        return "REGULAR"
    if dt_time(16, 0) <= t <= dt_time(20, 0):
        return "POST_MARKET"
    return "OFF_HOURS"


def _float(value: Any) -> float | None:
    try:
        x = float(value)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _epoch(value: Any) -> datetime | None:
    try:
        if value is None:
            return None
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


quality_dip_quote_service = QualityDipQuoteService()
