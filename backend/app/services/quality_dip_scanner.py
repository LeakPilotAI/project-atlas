"""
Quality Dip / Generational Discount scanner.

Watches a tight list of high-quality large-cap stocks.
Alerts only on significant discounts from 52-week highs
or sharp short-term drops. No auto-buy. Alert only.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import yfinance as yf

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.alerts.discord import send_discord_alert
from app.analytics.anomaly import AnomalySignal

logger = get_logger("quality_dip")
settings = get_settings()


def _watchlist() -> list[str]:
    raw = getattr(settings, "quality_dip_watchlist", None) or "ADBE,META,GOOGL,AMZN,MSFT"
    if isinstance(raw, str):
        return [t.strip().upper() for t in raw.split(",") if t.strip()]
    return list(raw)


def _threshold_pct() -> float:
    return float(getattr(settings, "quality_dip_threshold_pct", 25.0))


def _high_priority_pct() -> float:
    return float(getattr(settings, "quality_dip_high_priority_pct", 30.0))


def _short_drop_pct() -> float:
    return float(getattr(settings, "quality_dip_short_drop_pct", 15.0))


def _scan_interval_seconds() -> int:
    minutes = int(getattr(settings, "quality_dip_scan_interval_minutes", 60))
    return max(15, minutes) * 60


def _cooldown_seconds() -> int:
    hours = int(getattr(settings, "quality_dip_cooldown_hours", 24))
    return max(1, hours) * 3600


def _enabled() -> bool:
    val = getattr(settings, "quality_dip_enabled", True)
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes", "on")
    return bool(val)


@dataclass
class DipSnapshot:
    symbol: str
    name: str
    price: float
    high_52w: float
    low_52w: float
    pct_from_high: float
    drop_5d: Optional[float]
    drop_10d: Optional[float]
    drop_20d: Optional[float]
    is_new_52w_low: bool
    priority: str
    reasons: list[str]


def _fetch_snapshot(symbol: str) -> Optional[DipSnapshot]:
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        hist = t.history(period="1y", auto_adjust=True)

        if hist is None or hist.empty or len(hist) < 30:
            logger.warning("Insufficient history", symbol=symbol)
            return None

        price = float(hist["Close"].iloc[-1])
        high_52w = float(hist["High"].max())
        low_52w = float(hist["Low"].min())

        if high_52w <= 0:
            return None

        pct_from_high = ((high_52w - price) / high_52w) * 100.0
        is_new_52w_low = (
            abs(price - low_52w) / max(low_52w, 1e-9) < 0.01
            or price <= low_52w * 1.005
        )

        def drop_n(n: int) -> Optional[float]:
            if len(hist) < n + 1:
                return None
            past = float(hist["Close"].iloc[-(n + 1)])
            if past <= 0:
                return None
            return ((past - price) / past) * 100.0

        drop_5d = drop_n(5)
        drop_10d = drop_n(10)
        drop_20d = drop_n(20)

        name = info.get("shortName") or info.get("longName") or symbol

        reasons: list[str] = []
        priority = "normal"
        thr = _threshold_pct()
        hi = _high_priority_pct()
        short = _short_drop_pct()

        if pct_from_high >= hi:
            reasons.append(f"≥{hi:.0f}% below 52-week high")
            priority = "high"
        elif pct_from_high >= thr:
            reasons.append(f"≥{thr:.0f}% below 52-week high")

        if is_new_52w_low:
            reasons.append("At/near 52-week low")
            priority = "high"

        if drop_5d is not None and drop_5d >= short:
            reasons.append(f"Down {drop_5d:.1f}% in ~5 trading days")
        if drop_10d is not None and drop_10d >= short:
            reasons.append(f"Down {drop_10d:.1f}% in ~10 trading days")

        if not reasons:
            return None

        return DipSnapshot(
            symbol=symbol,
            name=str(name),
            price=round(price, 2),
            high_52w=round(high_52w, 2),
            low_52w=round(low_52w, 2),
            pct_from_high=round(pct_from_high, 1),
            drop_5d=round(drop_5d, 1) if drop_5d is not None else None,
            drop_10d=round(drop_10d, 1) if drop_10d is not None else None,
            drop_20d=round(drop_20d, 1) if drop_20d is not None else None,
            is_new_52w_low=is_new_52w_low,
            priority=priority,
            reasons=reasons,
        )
    except Exception as e:
        logger.warning("Failed to fetch snapshot", symbol=symbol, error=str(e))
        return None


async def _should_alert(symbol: str, pct_from_high: float) -> bool:
    redis = await get_redis()
    key = f"atlas:quality_dip:{symbol}"
    raw = await redis.get(key)

    if not raw:
        return True

    try:
        last_pct = float(raw.decode() if isinstance(raw, bytes) else raw)
    except Exception:
        return True

    if pct_from_high >= last_pct + 5.0:
        return True
    return False


async def _mark_alerted(symbol: str, pct_from_high: float) -> None:
    redis = await get_redis()
    key = f"atlas:quality_dip:{symbol}"
    await redis.set(key, str(pct_from_high), ex=_cooldown_seconds())


def _build_message(snap: DipSnapshot) -> str:
    lines = [
        f"**{snap.symbol}** — {snap.name}",
        "",
        f"**Current price:** ${snap.price:,.2f}",
        f"**% below 52-week high:** {snap.pct_from_high:.1f}%",
        f"**52-week high:** ${snap.high_52w:,.2f}",
        f"**52-week low:** ${snap.low_52w:,.2f}",
    ]
    if snap.drop_5d is not None:
        lines.append(f"**5-day change:** {snap.drop_5d:+.1f}%")
    if snap.drop_10d is not None:
        lines.append(f"**10-day change:** {snap.drop_10d:+.1f}%")
    if snap.drop_20d is not None:
        lines.append(f"**20-day change:** {snap.drop_20d:+.1f}%")

    lines.append("")
    lines.append("**Triggers:**")
    for r in snap.reasons:
        lines.append(f"• {r}")

    lines.append("")
    lines.append(
        "🏷️ **POSSIBLE QUALITY DIP / GENERATIONAL DISCOUNT – Review before buying**"
    )
    lines.append("")
    lines.append("_No auto-buy. Review with your process before deploying capital._")
    return "\n".join(lines)


class QualityDipScanner:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not _enabled():
            logger.info("Quality dip scanner disabled")
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "Quality dip scanner started",
            watchlist=_watchlist(),
            threshold=_threshold_pct(),
            high_priority=_high_priority_pct(),
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Quality dip scanner stopped")

    async def _loop(self) -> None:
        await asyncio.sleep(10)
        while self._running:
            try:
                await self._scan_once()
            except Exception as e:
                logger.error("Quality dip scan failed", error=str(e))
            await asyncio.sleep(_scan_interval_seconds())

    async def _scan_once(self) -> None:
        watchlist = _watchlist()
        logger.info("Quality dip scan starting", count=len(watchlist))

        for symbol in watchlist:
            try:
                snap = await asyncio.to_thread(_fetch_snapshot, symbol)
                if snap is None:
                    continue

                if not await _should_alert(symbol, snap.pct_from_high):
                    logger.info(
                        "Quality dip cooldown active",
                        symbol=symbol,
                        pct_from_high=snap.pct_from_high,
                    )
                    continue

                await self._send_alert(snap)
                await _mark_alerted(symbol, snap.pct_from_high)

            except Exception as e:
                logger.warning("Error scanning symbol", symbol=symbol, error=str(e))

            await asyncio.sleep(1.5)

        logger.info("Quality dip scan complete")

    async def _send_alert(self, snap: DipSnapshot) -> None:
        severity = "high" if snap.priority == "high" else "medium"
        title = (
            f"🔴 {snap.symbol} — Generational Discount Zone"
            if snap.priority == "high"
            else f"🟠 {snap.symbol} — Quality Dip Zone"
        )

        signal = AnomalySignal(
            symbol=snap.symbol,
            alert_type="quality_dip",
            severity=severity,
            title=title,
            message=_build_message(snap),
            opportunity_score=min(95.0, 50.0 + snap.pct_from_high),
            confidence_score=75.0,
            risk_score=45.0,
            price=snap.price,
            indicators={
                "pct_from_high": snap.pct_from_high,
                "high_52w": snap.high_52w,
                "low_52w": snap.low_52w,
                "drop_5d": snap.drop_5d,
                "drop_10d": snap.drop_10d,
                "drop_20d": snap.drop_20d,
                "is_new_52w_low": snap.is_new_52w_low,
                "priority": snap.priority,
                "reasons": snap.reasons,
            },
        )

        await send_discord_alert(signal, chart_bytes=None)
        logger.info(
            "Quality dip alert sent",
            symbol=snap.symbol,
            pct_from_high=snap.pct_from_high,
            priority=snap.priority,
        )

    async def current_discounts(self) -> list[dict]:
        results = []
        for symbol in _watchlist():
            snap = await asyncio.to_thread(_fetch_snapshot, symbol)
            if snap is None:
                continue
            results.append(
                {
                    "symbol": snap.symbol,
                    "name": snap.name,
                    "price": snap.price,
                    "pct_from_high": snap.pct_from_high,
                    "high_52w": snap.high_52w,
                    "low_52w": snap.low_52w,
                    "priority": snap.priority,
                    "reasons": snap.reasons,
                }
            )
        return results


quality_dip_scanner = QualityDipScanner()