"""Fresh market quote overlay for the Quality Dips research dashboard.

Atlas prefers Robinhood's read-only underlying-equity bid/ask when that surface
returns a timestamped quote, because Quality Dips is intended for manual Robinhood
accumulation. Yahoo 1-minute and quote-field data remain an independent fallback.
A stale/reference quote remains visible for context but cannot trigger an L-level.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timezone
from datetime import time as dt_time
from typing import Any
from zoneinfo import ZoneInfo

from app.investment.provider_dispatch import ProviderDispatcher, ProviderRejected
from app.investment.robinhood_equity_quotes import (
    RobinhoodEquityQuoteClient,
)
from app.investment.yfinance_client import ProviderCallError, YFinanceClient

CACHE_TTL_SEC = 15.0
LIVE_AGE_SEC = 120.0
FRESH_AGE_SEC = 15 * 60.0
MAX_REFERENCE_AGE_SEC = 96 * 3600.0
ET = ZoneInfo("America/New_York")


class QualityDipQuoteService:
    def __init__(
        self,
        client: YFinanceClient | None = None,
        robinhood_client: RobinhoodEquityQuoteClient | None = None,
        alpaca_feed=None,
    ) -> None:
        self.alpaca_feed = alpaca_feed
        self._providers = [ProviderDispatcher("robinhood"), ProviderDispatcher("yahoo")]
        self.client = client or YFinanceClient(min_interval_sec=0.05, timeout_sec=8.0,
                                              dispatcher=self._providers[1])
        self.robinhood_client = robinhood_client or RobinhoodEquityQuoteClient(
            dispatcher=self._providers[0])
        self._closed = False
        self.max_pending_quotes = 64
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._fetch_slots = asyncio.Semaphore(6)
        self._inflight: dict[str, asyncio.Task] = {}
        self._waiters: dict[asyncio.Task, int] = {}
        self._rejected_quotes = 0

    async def get_many(
        self,
        symbols: Iterable[str],
        *,
        max_cache_age_sec: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        clean = sorted({str(s or "").upper().strip() for s in symbols if str(s or "").strip()})
        if self.alpaca_feed is not None:
            if self._closed or len(clean) > self.max_pending_quotes:
                raise ProviderRejected('Alpaca quote admission closed or capacity exceeded')
            # Cache-only: GET/scanner reads never connect or fall back to another feed.
            return {s: self.alpaca_feed.research_snapshot(s) for s in clean}
        if self._closed:
            self._rejected_quotes += 1
            raise ProviderRejected("Quote service closed")
        new_symbols = set(clean) - self._inflight.keys()
        if len(clean) > self.max_pending_quotes or len(new_symbols) + len(self._inflight) > self.max_pending_quotes:
            self._rejected_quotes += 1
            raise ProviderRejected("Quote admission capacity exceeded")
        cache_age = CACHE_TTL_SEC if max_cache_age_sec is None else max(3.0, float(max_cache_age_sec))

        async def fetch_once(symbol: str) -> dict[str, Any]:
            try:
                try:
                    async with asyncio.timeout(30.0):
                        async with self._fetch_slots:
                            snap = await self._fetch(symbol)
                except TimeoutError:
                    snap = self._missing(symbol, datetime.now(UTC), "DEADLINE", "Quote deadline exceeded")
                self._cache[symbol] = (time.monotonic(), dict(snap))
                return snap
            finally:
                self._inflight.pop(symbol, None)

        async def one(symbol: str) -> tuple[str, dict[str, Any]]:
            # No await between lookup and registration: atomic on this service's
            # event loop. All callers share slots and the same symbol task.
            cached = self._cache.get(symbol)
            if cached and time.monotonic() - cached[0] <= cache_age:
                return symbol, dict(cached[1])
            task = self._inflight.get(symbol)
            if task is None:
                task = asyncio.create_task(fetch_once(symbol))
                self._inflight[symbol] = task
                # A canceled waiter must not leave an unobserved task exception.
                task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            self._waiters[task] = self._waiters.get(task, 0) + 1
            try:
                snap = await asyncio.shield(task)
                return symbol, dict(snap)
            finally:
                self._waiters[task] -= 1
                if not self._waiters[task]:
                    self._waiters.pop(task)
                    if not task.done():
                        task.cancel()

        return dict(await asyncio.gather(*(one(s) for s in clean)))

    def provider_status(self) -> dict:
        return {"closed": self._closed, "pending_quotes": len(self._inflight),
                "rejected_quotes": self._rejected_quotes, "quote_deadline_seconds": 30.0,
                "pending_quote_limit": self.max_pending_quotes,
                "providers": [provider.status() for provider in self._providers]}

    async def shutdown(self, timeout: float = 20.0) -> None:
        self._closed = True
        tasks = list(self._inflight.values())
        for task in tasks:
            task.cancel()
        # Both providers drain concurrently, sharing the same wall-clock budget.
        drains = [asyncio.create_task(provider.shutdown(timeout)) for provider in self._providers]
        done, pending = await asyncio.wait([*tasks, *drains], timeout=max(0.0, timeout))
        if pending:
            from app.investment.provider_dispatch import ProviderDrainTimeout

            # Do not cancel ownership supervisors while their threads are alive.
            for task in drains:
                task.add_done_callback(lambda item: None if item.cancelled() else item.exception())
            raise ProviderDrainTimeout("Quote work remains owned; shutdown incomplete")
        for task in done:
            if not task.cancelled() and task in drains:
                task.result()

    async def _fetch(self, symbol: str) -> dict[str, Any]:
        retrieved = datetime.now(UTC)
        candidates: list[dict[str, Any]] = []
        provider_errors: list[str] = []
        market_state = "UNKNOWN"

        # Robinhood first. RHJ exposes raw underlying bid/ask; for buy-limit monitoring
        # Atlas uses the ask as trigger_price and the midpoint as the display price.
        try:
            rh = await self.robinhood_client.get_quote(symbol)
            # Source time is compared with receipt, never request-start time.
            # Retrieval latency must contribute to age, not make a new quote future.
            retrieved = datetime.now(UTC)
            rh_ts = _iso_ts(rh.get("effective_timestamp"))
            rh_price = _float(rh.get("display_price") or rh.get("price"))
            if rh_ts is not None and rh_price is not None and rh_price > 0 and rh_ts <= retrieved:
                candidates.append({
                    "timestamp": rh_ts,
                    "price": rh_price,
                    "trigger_price": _float(rh.get("trigger_price")) or rh_price,
                    "bid": _float(rh.get("bid")),
                    "ask": _float(rh.get("ask")),
                    "session": str(rh.get("session") or "ROBINHOOD_MARKET_DATA"),
                    "source": str(rh.get("source") or "robinhood"),
                    "source_priority": 3 if str(rh.get("raw_kind") or "") == "RHJ_UNDERLYING_BID_ASK" else 2,
                    "raw_kind": rh.get("raw_kind"),
                })
            elif rh.get("error"):
                provider_errors.append(f"robinhood:{(rh.get('error') or {}).get('code', 'UNAVAILABLE')}")
        except Exception as exc:
            provider_errors.append(f"robinhood:{type(exc).__name__}")

        # Robinhood is the preferred live source. Do not fan out into two blocking
        # yfinance calls when RH already supplied a valid timestamped quote. The
        # dashboard polls frequently and the old behavior could enqueue dozens of
        # yfinance worker-thread jobs every refresh, starving the API/GIL and
        # growing the process to multiple GB even though the quote was already
        # available. Yahoo remains an independent fallback only when RH produced
        # no usable candidate.
        if candidates:
            chosen = max(candidates, key=lambda x: (x["timestamp"], int(x.get("source_priority") or 0)))
            ts = chosen["timestamp"]
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
                "price": chosen["price"],
                "display_price": chosen["price"],
                "trigger_price": chosen.get("trigger_price") if actionable else None,
                "bid": chosen.get("bid"),
                "ask": chosen.get("ask"),
                "source": chosen["source"],
                "session": chosen["session"],
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
                "raw_kind": chosen.get("raw_kind"),
            }

        # Independent Yahoo 1-minute fallback with pre/post-market enabled.
        try:
            history = await self.client.history(symbol, period="5d", interval="1m", prepost=True)
            retrieved = datetime.now(UTC)
            intraday = _latest_intraday(history, retrieved)
            if intraday is not None:
                ts, price = intraday
                candidates.append({
                    "timestamp": ts,
                    "price": price,
                    "trigger_price": price,
                    "bid": None,
                    "ask": None,
                    "session": _session_for_ts(ts),
                    "source": "yfinance_1m",
                    "source_priority": 1,
                    "raw_kind": "TRADE",
                })
        except ProviderCallError as exc:
            provider_errors.append(f"history:{exc.failure.code}")
        except Exception as exc:
            provider_errors.append(f"history:{type(exc).__name__}")

        info: dict[str, Any] = {}
        try:
            info = await self.client.info(symbol)
            retrieved = datetime.now(UTC)
            market_state = str(info.get("marketState") or "UNKNOWN").upper()
        except ProviderCallError as exc:
            provider_errors.append(f"info:{exc.failure.code}")
        except Exception as exc:
            provider_errors.append(f"info:{type(exc).__name__}")

        retrieved = datetime.now(UTC)
        # A backward local-clock change cannot make an earlier candidate actionable.
        candidates = [row for row in candidates if row["timestamp"] <= retrieved]
        for price_key, time_key, label in (
            ("postMarketPrice", "postMarketTime", "POST_MARKET"),
            ("preMarketPrice", "preMarketTime", "PRE_MARKET"),
            ("regularMarketPrice", "regularMarketTime", "REGULAR"),
            ("currentPrice", "regularMarketTime", "REGULAR"),
        ):
            price = _float(info.get(price_key))
            ts = _epoch(info.get(time_key))
            if price is not None and price > 0 and ts is not None and ts <= retrieved:
                candidates.append({
                    "timestamp": ts,
                    "price": price,
                    "trigger_price": price,
                    "bid": None,
                    "ask": None,
                    "session": label,
                    "source": "yfinance_quote",
                    "source_priority": 0,
                    "raw_kind": "QUOTE_FIELD",
                })

        if not candidates:
            price = _float(info.get("previousClose"))
            if price is not None and price > 0:
                return {
                    "symbol": symbol,
                    "price": price,
                    "display_price": price,
                    "trigger_price": None,
                    "bid": None,
                    "ask": None,
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

        chosen = max(candidates, key=lambda x: (x["timestamp"], int(x.get("source_priority") or 0)))
        ts = chosen["timestamp"]
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
            "price": chosen["price"],
            "display_price": chosen["price"],
            "trigger_price": chosen.get("trigger_price") if actionable else None,
            "bid": chosen.get("bid"),
            "ask": chosen.get("ask"),
            "source": chosen["source"],
            "session": chosen["session"],
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
            "raw_kind": chosen.get("raw_kind"),
        }

    @staticmethod
    def _missing(symbol: str, retrieved: datetime, code: str, message: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "price": None,
            "display_price": None,
            "trigger_price": None,
            "bid": None,
            "ask": None,
            "source": "robinhood+yfinance",
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
        row["quote_trigger_price"] = quote.get("trigger_price") if quote.get("tradable_for_ladder") else None
        row["quote_bid"] = quote.get("bid")
        row["quote_ask"] = quote.get("ask")

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
        "robinhood": sum(1 for q in values if str(q.get("source") or "").startswith("robinhood")),
        "source": "robinhood_underlying+yfinance_fallback",
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
    t = local.timetz().replace(tzinfo=None)
    if local.weekday() == 6 and t >= dt_time(20, 0):
        return "OVERNIGHT"
    if local.weekday() >= 5:
        return "OFF_HOURS"
    if dt_time(4, 0) <= t < dt_time(9, 30):
        return "PRE_MARKET"
    if dt_time(9, 30) <= t < dt_time(16, 0):
        return "REGULAR"
    if dt_time(16, 0) <= t <= dt_time(20, 0):
        return "POST_MARKET"
    if t > dt_time(20, 0) or t < dt_time(4, 0):
        return "OVERNIGHT"
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


def _iso_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return None
        return stamp.astimezone(timezone.utc)
    except Exception:
        return None


quality_dip_quote_service = QualityDipQuoteService()
