"""A+ perp scanner — allowlist lane, shared HL cache, rate-limit safe."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)


def _f(d: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return default


def _sym(d: Dict[str, Any]) -> str:
    return str(d.get("symbol") or d.get("coin") or d.get("name") or "").upper()


def _to_dict(item: Any) -> Dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        try:
            return dict(item.model_dump())
        except Exception:
            pass
    if hasattr(item, "dict"):
        try:
            return dict(item.dict())
        except Exception:
            pass
    if hasattr(item, "__dict__"):
        return {k: v for k, v in vars(item).items() if not k.startswith("_")}
    out: Dict[str, Any] = {}
    for k in (
        "symbol", "coin", "name", "price", "markPx", "midPx", "volume_24h",
        "dayNtlVlm", "open_interest", "openInterest", "funding_rate", "funding",
    ):
        if hasattr(item, k):
            try:
                out[k] = getattr(item, k)
            except Exception:
                pass
    return out


class MarketScanner:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_alert: Dict[str, datetime] = {}

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="market_scanner")
        log.info("Market scanner started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Market scanner stopped")

    async def _loop(self) -> None:
        await asyncio.sleep(6)
        while self._running:
            try:
                await self._scan_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("Scanner cycle failed", error=str(e), exc_info=True)
                await asyncio.sleep(15)
            settings = get_settings()
            await asyncio.sleep(float(settings.scan_interval_seconds or 45))

    async def _fetch_tickers(self) -> List[Any]:
        try:
            from app.adapters.hyperliquid_cache import get_tickers_cached

            data = await get_tickers_cached()
            if data:
                log.info("Fetched tickers", count=len(data))
                return data
        except Exception as e:
            log.error("Ticker fetch failed", adapter="hyperliquid", error=str(e)[:300])
        return []

    def _apply_allowlist(self, tickers: List[Any]) -> List[Any]:
        settings = get_settings()
        if not settings.perp_allowlist_enabled:
            return tickers
        allow: Set[str] = set(settings.perp_allowlist_list)
        if not allow:
            return tickers
        out = []
        for raw in tickers:
            t = _to_dict(raw)
            s = _sym(t)
            if s in allow:
                out.append(raw)
        log.info("Allowlist applied", before=len(tickers), after=len(out))
        return out

    def _cooldown_ok(self, symbol: str) -> bool:
        settings = get_settings()
        mins = float(settings.perp_alert_cooldown_minutes or 90)
        last = self._last_alert.get(symbol)
        if not last:
            return True
        return (datetime.now(timezone.utc) - last).total_seconds() >= mins * 60

    async def _scan_cycle(self) -> None:
        settings = get_settings()
        tickers = await self._fetch_tickers()
        if not tickers:
            log.info("Scan complete", markets=0, sample="—", a_plus=0, sent=0)
            return

        filtered = self._apply_allowlist(tickers)
        sent = 0
        a_plus = 0
        sample = "—"
        max_alerts = int(settings.perp_max_alerts_per_cycle or 3)

        for raw in filtered:
            if sent >= max_alerts:
                break
            t = _to_dict(raw)
            symbol = _sym(t)
            if not symbol:
                continue
            sample = sample if sample != "—" else symbol

            price = _f(t, "price", "markPx", "midPx")
            vol = _f(t, "volume_24h", "dayNtlVlm", "volume24h", "volume")
            oi = _f(t, "open_interest", "openInterest", "oi")
            if price <= 0:
                continue
            if vol < float(settings.perp_min_volume_24h):
                continue
            if oi < float(settings.perp_min_open_interest):
                continue
            if not self._cooldown_ok(symbol):
                continue

            # Lightweight A+ gate — full decision engine when available
            try:
                from app.analytics.decision_engine import evaluate_setup

                result = evaluate_setup(
                    symbol=symbol,
                    price=price,
                    volume_24h=vol,
                    open_interest=oi,
                    ticker=t,
                )
            except TypeError:
                try:
                    from app.analytics.decision_engine import evaluate_setup

                    result = evaluate_setup(symbol, price, vol, oi, t)
                except Exception as e:
                    log.debug("evaluate_setup skip", symbol=symbol, error=str(e)[:120])
                    continue
            except Exception as e:
                log.debug("evaluate_setup skip", symbol=symbol, error=str(e)[:120])
                continue

            if result is None:
                continue

            score = float(getattr(result, "score", 0) or getattr(result, "setup_score", 0) or 0)
            conf = float(getattr(result, "confidence", 0) or 0)
            side = str(getattr(result, "side", "") or getattr(result, "recommendation", "") or "").upper()
            if score < float(settings.perp_min_setup_score):
                continue
            if conf < float(settings.perp_min_confidence):
                continue
            if side not in ("LONG", "SHORT"):
                continue

            a_plus += 1
            try:
                from app.alerts.dispatcher import dispatch_alert

                await dispatch_alert(
                    symbol=symbol,
                    title=f"{symbol} · {side}",
                    description=(
                        f"**{symbol} · {side}** Score {score:.0f} · Confidence {conf:.0f}\n"
                        f"Price `{price}` · Vol24h `{vol:,.0f}` · OI `{oi:,.0f}`\n"
                        f"_A+ scanner · Manual only — Atlas does not execute._"
                    ),
                    price=price,
                    severity="HIGH" if score >= 85 else "MEDIUM",
                    opportunity=int(min(95, score)),
                    confidence=int(min(95, conf)),
                    risk=50,
                    signal=result,
                )
                self._last_alert[symbol] = datetime.now(timezone.utc)
                sent += 1
            except Exception as e:
                log.warning("dispatch failed", symbol=symbol, error=str(e)[:200])

        log.info(
            "Scan complete",
            markets=len(filtered),
            sample=sample,
            a_plus=a_plus,
            sent=sent,
        )


scanner = MarketScanner()