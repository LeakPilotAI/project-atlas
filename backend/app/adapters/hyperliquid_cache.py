"""Shared Hyperliquid ticker cache + 429-aware fetch."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any, List

import httpx
import structlog

from app.adapters import hyperliquid_gate_registry
from app.core.market_freshness import fresh_observation, positive_price

log = structlog.get_logger(__name__)

HL_INFO_URL = "https://api.hyperliquid.xyz/info"

_lock = asyncio.Lock()
_tickers: List[Any] = []
_tickers_ts: float = 0.0
_CACHE_TTL = 25.0
_backoff_until: float = 0.0


def _fresh_tickers(rows: list[Any]) -> list[Any]:
    def usable(row: Any) -> bool:
        read = row.get if isinstance(row, dict) else lambda key: getattr(row, key, None)
        return positive_price(read("price")) and fresh_observation(read("timestamp"))
    return [row for row in rows if usable(row)]


async def get_tickers_cached(force: bool = False) -> List[Any]:
    global _tickers, _tickers_ts, _backoff_until

    now = time.monotonic()
    fresh = _fresh_tickers(_tickers)
    if not force and fresh and len(fresh) == len(_tickers) and (now - _tickers_ts) < _CACHE_TTL:
        return fresh

    async with _lock:
        now = time.monotonic()
        fresh = _fresh_tickers(_tickers)
        if not force and fresh and len(fresh) == len(_tickers) and (now - _tickers_ts) < _CACHE_TTL:
            return fresh

        if now < _backoff_until:
            wait = min(_backoff_until - now, 30.0)
            log.warning("HL rate-limit backoff", wait_s=round(wait, 1))
            await asyncio.sleep(wait)

        data = _fresh_tickers(await _fetch_via_adapter())
        if not data:
            data = _fresh_tickers(await _fetch_direct())

        if data:
            _tickers = data
            _tickers_ts = time.monotonic()
            log.info("HL ticker cache refreshed", count=len(data))
        elif _tickers:
            log.warning("HL fetch empty — expired cache is not authoritative", count=len(_tickers))
        return _fresh_tickers(_tickers)


async def _fetch_via_adapter() -> List[Any]:
    try:
        from app.adapters.registry import registry
    except Exception:
        return []

    adapter = None
    for attr in ("get", "get_adapter", "require"):
        fn = getattr(registry, attr, None)
        if callable(fn):
            try:
                adapter = fn("hyperliquid")
                if adapter:
                    break
            except Exception:
                pass
    if adapter is None:
        d = getattr(registry, "_adapters", None) or getattr(registry, "adapters", None)
        if isinstance(d, dict):
            # An unrelated exchange is never authoritative Hyperliquid evidence.
            adapter = d.get("hyperliquid")
    if adapter is None:
        return []

    for name in ("get_all_tickers", "fetch_tickers", "get_tickers"):
        fn = getattr(adapter, name, None)
        if not callable(fn):
            continue
        try:
            data = await fn()
            if isinstance(data, list) and data:
                return data
        except hyperliquid_gate_registry.RequestGateRefused:
            raise
        except Exception as e:
            msg = str(e)
            if "429" in msg:
                await _trip_backoff(30.0)
            log.warning("adapter ticker fail", method=name, error=msg[:200])
    return []


async def _fetch_direct() -> List[Any]:
    observed_at = datetime.now(UTC)
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            hyperliquid_gate_registry.consume_before_attempt('HTTP')
            r = await client.post(HL_INFO_URL, json={"type": "metaAndAssetCtxs"})
            if r.status_code == 429:
                await _trip_backoff(45.0)
                return []
            r.raise_for_status()
            payload = r.json()
    except hyperliquid_gate_registry.RequestGateRefused:
        raise
    except httpx.HTTPStatusError as e:
        if e.response is not None and e.response.status_code == 429:
            await _trip_backoff(45.0)
        log.warning("HL direct HTTP error", error=str(e)[:200])
        return []
    except Exception as e:
        log.warning("HL direct fetch failed", error=str(e)[:200])
        return []

    if not fresh_observation(observed_at) or time.monotonic() - started > 30:
        return []

    try:
        if isinstance(payload, list) and len(payload) >= 2:
            meta, ctxs = payload[0], payload[1]
        elif isinstance(payload, dict):
            meta = payload.get("meta") or payload
            ctxs = payload.get("assetCtxs") or []
        else:
            return []

        universe = meta.get("universe") if isinstance(meta, dict) else []
        out: List[Any] = []
        for i, u in enumerate(universe or []):
            if not isinstance(u, dict):
                continue
            name = str(u.get("name") or "").upper()
            if not name:
                continue
            ctx = ctxs[i] if isinstance(ctxs, list) and i < len(ctxs) else {}
            if not isinstance(ctx, dict):
                ctx = {}

            def _f(*keys: str, default: float = 0.0) -> float:
                for k in keys:
                    if k in ctx and ctx[k] is not None:
                        try:
                            return float(ctx[k])
                        except (TypeError, ValueError):
                            pass
                return default

            mark = _f("markPx", "midPx")
            mid = _f("midPx", "markPx")
            vol = _f("dayNtlVlm")
            oi_coins = _f("openInterest")
            oi_usd = oi_coins * mark if mark > 0 else oi_coins
            out.append(
                {
                    "symbol": name,
                    "coin": name,
                    "price": mark or mid,
                    "timestamp": observed_at.isoformat(),
                    "timestamp_basis": "REST_REQUEST_START",
                    "price_source": "REST_MARK",
                    "markPx": mark,
                    "midPx": mid,
                    "volume_24h": vol,
                    "dayNtlVlm": vol,
                    "open_interest": oi_usd,
                    "openInterest": oi_coins,
                }
            )
        return out
    except Exception as e:
        log.warning("HL parse failed", error=str(e)[:200])
        return []


async def _trip_backoff(seconds: float) -> None:
    global _backoff_until
    _backoff_until = max(_backoff_until, time.monotonic() + seconds)
    log.warning("HL 429 backoff armed", seconds=seconds)
