"""Single yfinance access point for the investment engine. Never invent values."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.investment.bars import ProviderFailure

_STUB_KEYS = {"trailingPegRatio"}

# fast_info uses mixed camel/snake; map onto the info keys providers already read.
_FAST_TO_INFO = {
    "lastPrice": "regularMarketPrice",
    "last_price": "regularMarketPrice",
    "marketCap": "marketCap",
    "market_cap": "marketCap",
    "shares": "sharesOutstanding",
    "previousClose": "previousClose",
    "regularMarketPreviousClose": "previousClose",
    "currency": "currency",
    "exchange": "exchange",
}


class ProviderCallError(RuntimeError):
    def __init__(self, code: str, message: str, symbol: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.failure = ProviderFailure(
            code=code,
            message=message,
            source="yfinance",
            symbol=symbol,
            retryable=retryable,
        )


def wrap_provider_error(exc: BaseException, symbol: str) -> ProviderCallError:
    """Map raw client exceptions to structured failures. Never invent a value."""
    if isinstance(exc, ProviderCallError):
        return exc
    msg = str(exc)[:300]
    low = msg.lower()
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in low or "timed out" in low:
        return ProviderCallError("TIMEOUT", msg or "timeout", symbol, retryable=True)
    if "429" in low or "rate limit" in low or "too many requests" in low:
        return ProviderCallError("RATE_LIMIT", msg or "rate limited", symbol, retryable=True)
    if "401" in low or "unauthorized" in low or "invalid crumb" in low:
        return ProviderCallError("HTTP_401", msg or "unauthorized", symbol, retryable=False)
    if (
        "delisted" in low
        or "symbol may be delisted" in low
        or "no timezone found" in low
        or "quote not found" in low
        or "not found" in low
    ):
        return ProviderCallError("MISSING_TICKER", msg or "ticker not found", symbol, retryable=False)
    if "empty" in low:
        return ProviderCallError("EMPTY", msg or "empty payload", symbol, retryable=True)
    return ProviderCallError("PROVIDER_ERROR", msg or type(exc).__name__, symbol, retryable=True)


def is_usable_info(info: object) -> bool:
    """Reject empty dicts and Yahoo's `{trailingPegRatio: None}` crumb-failure stub."""
    if not isinstance(info, dict) or not info:
        return False
    for k, v in info.items():
        if k in _STUB_KEYS:
            continue
        if v is None or v == "":
            continue
        return True
    return False


def normalize_fast_info(fast: object) -> Dict[str, Any]:
    if fast is None:
        return {}
    raw: Dict[str, Any] = {}
    try:
        raw = dict(fast)
    except Exception:
        for attr in (
            "last_price",
            "lastPrice",
            "market_cap",
            "marketCap",
            "shares",
            "previous_close",
            "previousClose",
            "currency",
            "exchange",
        ):
            try:
                raw[attr] = getattr(fast, attr)
            except Exception:
                pass
    out = dict(raw)
    for src, dest in _FAST_TO_INFO.items():
        if out.get(dest) is None and raw.get(src) is not None:
            out[dest] = raw[src]
    return out


class YFinanceClient:
    """Thin wrapper. Call from providers only. Rate-limited. Failures are structured."""

    name = "yfinance"

    def __init__(self, *, min_interval_sec: float = 0.25, timeout_sec: float = 20.0) -> None:
        self.min_interval_sec = min_interval_sec
        self.timeout_sec = timeout_sec
        self._last_call = 0.0

    def _throttle(self) -> None:
        wait = self.min_interval_sec - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _ticker(self, symbol: str) -> Any:
        try:
            import yfinance as yf
        except ImportError as e:
            raise ProviderCallError("DEPENDENCY", "yfinance not installed", symbol, retryable=False) from e
        self._throttle()
        return yf.Ticker(symbol)

    def fetch_info(self, symbol: str) -> Dict[str, Any]:
        try:
            t = self._ticker(symbol)
            info = t.info if hasattr(t, "info") else {}
            if not isinstance(info, dict):
                info = {}
            if not is_usable_info(info):
                fast = normalize_fast_info(getattr(t, "fast_info", None))
                if is_usable_info(fast):
                    info = fast
            if not is_usable_info(info):
                raise ProviderCallError("EMPTY", "empty info payload", symbol, retryable=True)
            from app.investment.provider_health import record_provider_event

            record_provider_event("OK", success=True)
            return info
        except ProviderCallError as e:
            from app.investment.provider_health import record_provider_event

            record_provider_event(e.failure.code, success=False, message=e.failure.message)
            raise
        except Exception as e:
            err = wrap_provider_error(e, symbol)
            from app.investment.provider_health import record_provider_event

            record_provider_event(err.failure.code, success=False, message=err.failure.message)
            raise err from e

    def fetch_history(
        self,
        symbol: str,
        *,
        period: str = "5y",
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1d",
    ) -> Any:
        try:
            t = self._ticker(symbol)
            kwargs: Dict[str, Any] = {"interval": interval, "auto_adjust": False}
            if start or end:
                kwargs["start"] = start
                kwargs["end"] = end
            else:
                kwargs["period"] = period
            df = t.history(**kwargs)
            if df is None or getattr(df, "empty", True):
                raise ProviderCallError("EMPTY", "empty history payload", symbol, retryable=True)
            from app.investment.provider_health import record_provider_event

            record_provider_event("OK", success=True)
            return df
        except ProviderCallError as e:
            from app.investment.provider_health import record_provider_event

            record_provider_event(e.failure.code, success=False, message=e.failure.message)
            raise
        except Exception as e:
            err = wrap_provider_error(e, symbol)
            from app.investment.provider_health import record_provider_event

            record_provider_event(err.failure.code, success=False, message=err.failure.message)
            raise err from e

    async def info(self, symbol: str) -> Dict[str, Any]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.fetch_info, symbol),
                timeout=self.timeout_sec,
            )
        except asyncio.TimeoutError as e:
            from app.investment.provider_health import record_provider_event

            record_provider_event("TIMEOUT", success=False, message=f"info timeout after {self.timeout_sec}s")
            raise ProviderCallError(
                "TIMEOUT",
                f"info timeout after {self.timeout_sec}s",
                symbol,
                retryable=True,
            ) from e

    async def history(self, symbol: str, **kwargs: Any) -> Any:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.fetch_history, symbol, **kwargs),
                timeout=self.timeout_sec,
            )
        except asyncio.TimeoutError as e:
            from app.investment.provider_health import record_provider_event

            record_provider_event("TIMEOUT", success=False, message=f"history timeout after {self.timeout_sec}s")
            raise ProviderCallError(
                "TIMEOUT",
                f"history timeout after {self.timeout_sec}s",
                symbol,
                retryable=True,
            ) from e


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
