"""Fresh market quote overlay for the Quality Dips research dashboard."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Iterable

from app.investment.yfinance_client import ProviderCallError, YFinanceClient

CACHE_TTL_SEC = 45.0
MAX_REFERENCE_AGE_SEC = 36 * 3600.0


class QualityDipQuoteService:
    def __init__(self, client: YFinanceClient | None = None) -> None:
        self.client = client or YFinanceClient(min_interval_sec=0.05, timeout_sec=8.0)
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def get_many(self, symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
        clean = sorted({str(s or "").upper().strip() for s in symbols if str(s or "").strip()})
        sem = asyncio.Semaphore(6)

        async def one(symbol: str) -> tuple[str, dict[str, Any]]:
            cached = self._cache.get(symbol)
            if cached and time.monotonic() - cached[0] <= CACHE_TTL_SEC:
                return symbol, dict(cached[1])
            async with sem:
                snap = await self._fetch(symbol)
            async with self._lock:
                self._cache[symbol] = (time.monotonic(), dict(snap))
            return symbol, snap

        return dict(await asyncio.gather(*(one(s) for s in clean)))

    async def _fetch(self, symbol: str) -> dict[str, Any]:
        retrieved = datetime.now(timezone.utc)
        try:
            info = await self.client.info(symbol)
        except ProviderCallError as exc:
            return self._missing(symbol, retrieved, exc.failure.code, exc.failure.message)
        except Exception as exc:
            return self._missing(symbol, retrieved, "PROVIDER_ERROR", str(exc)[:180])

        market_state = str(info.get("marketState") or "UNKNOWN").upper()
        candidates: list[tuple[datetime, float, str]] = []
        for price_key, time_key, label in (
            ("postMarketPrice", "postMarketTime", "POST_MARKET"),
            ("preMarketPrice", "preMarketTime", "PRE_MARKET"),
            ("regularMarketPrice", "regularMarketTime", "REGULAR"),
            ("currentPrice", "regularMarketTime", "REGULAR"),
        ):
            price = _float(info.get(price_key))
            ts = _epoch(info.get(time_key))
            if price is not None and price > 0 and ts is not None and ts <= retrieved:
                candidates.append((ts, price, label))

        if not candidates:
            price = _float(info.get("previousClose"))
            if price is not None and price > 0:
                return {
                    "symbol": symbol, "price": price, "source": "yfinance",
                    "session": "PREVIOUS_CLOSE", "market_state": market_state,
                    "effective_timestamp": None, "retrieved_at": retrieved.isoformat(),
                    "age_sec": None, "quality": "REFERENCE_ONLY",
                    "fresh_for_display": False, "error": None,
                }
            return self._missing(symbol, retrieved, "EMPTY", "no timestamped quote fields")

        ts, price, session = max(candidates, key=lambda x: x[0])
        age = max(0.0, (retrieved - ts).total_seconds())
        quality = "FRESH" if age <= 900 else ("REFERENCE" if age <= MAX_REFERENCE_AGE_SEC else "STALE")
        return {
            "symbol": symbol, "price": price, "source": "yfinance",
            "session": session, "market_state": market_state,
            "effective_timestamp": ts.isoformat(), "retrieved_at": retrieved.isoformat(),
            "age_sec": round(age, 1), "quality": quality,
            "fresh_for_display": age <= MAX_REFERENCE_AGE_SEC, "error": None,
        }

    @staticmethod
    def _missing(symbol: str, retrieved: datetime, code: str, message: str) -> dict[str, Any]:
        return {
            "symbol": symbol, "price": None, "source": "yfinance", "session": "UNKNOWN",
            "market_state": "UNKNOWN", "effective_timestamp": None,
            "retrieved_at": retrieved.isoformat(), "age_sec": None, "quality": "MISSING",
            "fresh_for_display": False, "error": {"code": code, "message": message[:180]},
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
        "fresh": sum(1 for q in values if q.get("quality") == "FRESH"),
        "reference": sum(1 for q in values if q.get("quality") in {"REFERENCE", "REFERENCE_ONLY"}),
        "stale": sum(1 for q in values if q.get("quality") == "STALE"),
        "missing": sum(1 for q in values if q.get("quality") == "MISSING"),
        "source": "yfinance", "cache_ttl_sec": CACHE_TTL_SEC,
    }


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
