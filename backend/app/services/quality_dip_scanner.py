"""
Quality Dip / Generational Discount scanner.

Category thresholds + adaptive per-symbol learning.
After each full batch, sends a ranked analysis briefing DM.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import yfinance as yf

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.alerts.discord import send_discord_alert, get_subscriber_ids, bot as discord_bot
from app.analytics.anomaly import AnomalySignal

logger = get_logger("quality_dip")
settings = get_settings()

METALS_SYMBOLS = {
    "GLD", "IAU", "SGOL", "GLDM", "BAR",
    "GDX", "GDXJ", "GOAU",
    "SLV", "SIVR", "PSLV",
    "SIL", "SILJ",
    "GOLD", "NEM", "AEM",
}


def _watchlist() -> list[str]:
    raw = getattr(settings, "quality_dip_watchlist", None) or "ADBE,META,GOOGL,AMZN,MSFT"
    if isinstance(raw, str):
        return [t.strip().upper() for t in raw.split(",") if t.strip()]
    return list(raw)


def _enabled() -> bool:
    val = getattr(settings, "quality_dip_enabled", True)
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes", "on")
    return bool(val)


def _adaptive_on() -> bool:
    val = getattr(settings, "quality_dip_adaptive", True)
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes", "on")
    return bool(val)


def _short_drop_pct() -> float:
    return float(getattr(settings, "quality_dip_short_drop_pct", 15.0))


def _scan_interval_seconds() -> int:
    minutes = int(getattr(settings, "quality_dip_scan_interval_minutes", 60))
    return max(15, minutes) * 60


def _cooldown_seconds() -> int:
    hours = int(getattr(settings, "quality_dip_cooldown_hours", 24))
    return max(1, hours) * 3600


def _is_metal(symbol: str) -> bool:
    return symbol.upper() in METALS_SYMBOLS


def _base_thresholds(symbol: str) -> tuple[float, float]:
    if _is_metal(symbol):
        normal = float(getattr(settings, "quality_dip_metals_threshold_pct", 12.0))
        high = float(getattr(settings, "quality_dip_metals_high_priority_pct", 18.0))
    else:
        normal = float(getattr(settings, "quality_dip_threshold_pct", 25.0))
        high = float(getattr(settings, "quality_dip_high_priority_pct", 30.0))
    return normal, high


def _adaptive_bounds(symbol: str) -> tuple[float, float]:
    if _is_metal(symbol):
        floor = float(getattr(settings, "quality_dip_adaptive_floor_metal", 8.0))
        ceil = float(getattr(settings, "quality_dip_adaptive_ceiling_metal", 25.0))
    else:
        floor = float(getattr(settings, "quality_dip_adaptive_floor_stock", 15.0))
        ceil = float(getattr(settings, "quality_dip_adaptive_ceiling_stock", 40.0))
    return floor, ceil


def _learn_thresholds_from_history(symbol: str, hist) -> tuple[float, float]:
    base_n, base_h = _base_thresholds(symbol)
    floor, ceil = _adaptive_bounds(symbol)
    try:
        closes = hist["Close"].astype(float)
        if len(closes) < 80:
            return base_n, base_h
        rolling_high = closes.rolling(60, min_periods=20).max()
        drawdowns = ((rolling_high - closes) / rolling_high * 100.0).dropna()
        drawdowns = drawdowns[drawdowns > 1.0]
        if len(drawdowns) < 20:
            return base_n, base_h
        p75 = float(drawdowns.quantile(0.75))
        p90 = float(drawdowns.quantile(0.90))
        normal = max(floor, min(ceil, p75))
        high = max(normal + 3.0, min(ceil + 5.0, p90))
        normal = 0.6 * normal + 0.4 * base_n
        high = 0.6 * high + 0.4 * base_h
        high = max(high, normal + 3.0)
        normal = round(max(floor, min(ceil, normal)), 1)
        high = round(max(floor + 3.0, min(ceil + 8.0, high)), 1)
        return normal, high
    except Exception as e:
        logger.warning("Adaptive threshold failed", symbol=symbol, error=str(e))
        return base_n, base_h


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
    threshold_normal: float
    threshold_high: float
    category: str
    adaptive: bool
    review_score: float = 0.0
    review_note: str = ""


def _score_candidate(snap: DipSnapshot) -> tuple[float, str]:
    """
    Rank for deep analysis priority (not a buy signal).
    Higher = more worth researching first.
    """
    score = 0.0
    notes: list[str] = []

    # Depth below high
    score += min(40.0, snap.pct_from_high * 0.55)
    if snap.pct_from_high >= 40:
        notes.append("deep drawdown")
    elif snap.pct_from_high >= 30:
        notes.append("material drawdown")

    # Fresh weakness vs bounce
    d5 = snap.drop_5d or 0.0
    d10 = snap.drop_10d or 0.0
    d20 = snap.drop_20d or 0.0

    if d5 >= 5:
        score += 15
        notes.append("fresh 5d pressure")
    elif d5 >= 2:
        score += 8
    elif d5 < -3:
        score -= 12
        notes.append("bouncing short-term")

    if d10 >= 5:
        score += 10
        notes.append("10d weakness")
    elif d10 < -5:
        score -= 8
        notes.append("10d recovery")

    if d20 >= 8:
        score += 8
        notes.append("20d downtrend")
    elif d20 < -10:
        score -= 6
        notes.append("20d bounce")

    # Near 52w low
    if snap.is_new_52w_low:
        score += 12
        notes.append("near 52w low")

    # Distance above 52w low (avoid knives still free-falling into unknown)
    if snap.low_52w > 0:
        above_low = (snap.price - snap.low_52w) / snap.low_52w * 100.0
        if above_low < 5:
            score += 5
            notes.append("pressed into lows")
        elif above_low > 40:
            score -= 4
            notes.append("still far above lows")

    # Category tilt
    if snap.category == "metal":
        score += 3
        notes.append("metals complex")

    # Cap
    score = max(0.0, min(100.0, score))
    note = ", ".join(notes) if notes else "standard discount"
    return round(score, 1), note


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

        drop_5d, drop_10d, drop_20d = drop_n(5), drop_n(10), drop_n(20)
        name = info.get("shortName") or info.get("longName") or symbol
        category = "metal" if _is_metal(symbol) else "stock"
        adaptive = _adaptive_on()
        thr, hi = (
            _learn_thresholds_from_history(symbol, hist)
            if adaptive
            else _base_thresholds(symbol)
        )

        reasons: list[str] = []
        priority = "normal"
        short = min(_short_drop_pct(), 8.0) if category == "metal" else _short_drop_pct()

        if pct_from_high >= hi:
            reasons.append(f"≥{hi:.1f}% below 52-week high (high priority)")
            priority = "high"
        elif pct_from_high >= thr:
            reasons.append(f"≥{thr:.1f}% below 52-week high")

        if is_new_52w_low:
            reasons.append("At/near 52-week low")
            priority = "high"
        if drop_5d is not None and drop_5d >= short:
            reasons.append(f"Down {drop_5d:.1f}% in ~5 trading days")
        if drop_10d is not None and drop_10d >= short:
            reasons.append(f"Down {drop_10d:.1f}% in ~10 trading days")

        if not reasons:
            return None

        snap = DipSnapshot(
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
            threshold_normal=thr,
            threshold_high=hi,
            category=category,
            adaptive=adaptive,
        )
        snap.review_score, snap.review_note = _score_candidate(snap)
        return snap
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
    step = 3.0 if _is_metal(symbol) else 5.0
    return pct_from_high >= last_pct + step


async def _mark_alerted(symbol: str, pct_from_high: float) -> None:
    redis = await get_redis()
    await redis.set(f"atlas:quality_dip:{symbol}", str(pct_from_high), ex=_cooldown_seconds())


def _build_message(snap: DipSnapshot) -> str:
    lines = [
        f"**{snap.symbol}** — {snap.name}",
        f"**Category:** {snap.category.upper()}"
        + (" · adaptive thresholds" if snap.adaptive else ""),
        "",
        f"**Current price:** ${snap.price:,.2f}",
        f"**% below 52-week high:** {snap.pct_from_high:.1f}%",
        f"**Alert thresholds:** {snap.threshold_normal:.1f}% / {snap.threshold_high:.1f}% (high)",
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
    lines.append("_No auto-buy. Confirm price on your broker before acting._")
    return "\n".join(lines)


def _build_briefing(candidates: list[DipSnapshot]) -> str:
    ranked = sorted(candidates, key=lambda s: s.review_score, reverse=True)
    top = ranked[:6]
    metals = [s for s in ranked if s.category == "metal"]
    stocks = [s for s in ranked if s.category == "stock"]

    lines = [
        f"**Quality Dip Briefing** — {len(candidates)} candidates",
        "",
        "This is a **research priority list**, not buy advice.",
        "Confirm live prices on your broker. Data feeds can lag or mis-quote.",
        "",
        "**Deep-analysis priority (start here):**",
    ]
    for i, s in enumerate(top, 1):
        mom = ""
        if s.drop_5d is not None:
            mom = f" · 5d {s.drop_5d:+.1f}%"
        lines.append(
            f"{i}. **{s.symbol}** — score {s.review_score:.0f}/100 · "
            f"{s.pct_from_high:.1f}% off high{mom}"
        )
        lines.append(f"   _{s.review_note}_")

    lines.append("")
    lines.append("**Approach**")
    if top:
        primary = top[0]
        lines.append(
            f"• Start with **{primary.symbol}** — highest combined depth + pressure score."
        )
    if any((s.drop_5d or 0) < -3 for s in top[:3]):
        lines.append(
            "• Some names are bouncing short-term — wait for retest or weaker closes if you want better entry quality."
        )
    if any((s.drop_5d or 0) >= 5 for s in top[:3]):
        lines.append(
            "• Fresh 5-day weakness present — prioritize those over names already reclaiming."
        )
    if metals:
        lines.append(
            f"• Metals complex active: {', '.join(m.symbol for m in metals[:4])} — treat as one theme, not five unrelated trades."
        )
    if stocks:
        soft = [s for s in stocks if s.symbol in {"CRM", "NOW", "ADBE", "INTU", "ORCL", "MSFT", "AAPL"}]
        if soft:
            lines.append(
                f"• Software/quality cluster: {', '.join(s.symbol for s in soft[:5])} — compare relative strength inside the group."
            )

    lines.append("")
    lines.append("**Suggested workflow**")
    lines.append("1. Open charts for the top 3 only")
    lines.append("2. Verify price/volume on your broker")
    lines.append("3. Check thesis + balance sheet / ETF structure")
    lines.append("4. Size small if acting — these are discounts, not guarantees")
    lines.append("")
    lines.append("_Atlas ranks for research time. You decide capital._")
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
        logger.info("Quality dip scanner started", watchlist=_watchlist(), adaptive=_adaptive_on())

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
        candidates: list[DipSnapshot] = []
        alerted: list[DipSnapshot] = []

        for symbol in watchlist:
            try:
                snap = await asyncio.to_thread(_fetch_snapshot, symbol)
                if snap is None:
                    continue
                candidates.append(snap)

                if await _should_alert(symbol, snap.pct_from_high):
                    await self._send_alert(snap)
                    await _mark_alerted(symbol, snap.pct_from_high)
                    alerted.append(snap)
                else:
                    logger.info(
                        "Quality dip cooldown",
                        symbol=symbol,
                        pct_from_high=snap.pct_from_high,
                    )
            except Exception as e:
                logger.warning("Error scanning symbol", symbol=symbol, error=str(e))
            await asyncio.sleep(1.2)

        if candidates:
            await self._send_briefing(candidates)
        logger.info(
            "Quality dip scan complete",
            candidates=len(candidates),
            alerted=len(alerted),
        )

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
                "review_score": snap.review_score,
                "category": snap.category,
                "priority": snap.priority,
            },
        )
        await send_discord_alert(signal, chart_bytes=None)
        logger.info(
            "Quality dip alert sent",
            symbol=snap.symbol,
            pct_from_high=snap.pct_from_high,
            review_score=snap.review_score,
        )

    async def _send_briefing(self, candidates: list[DipSnapshot]) -> None:
        """One ranked analysis DM after the batch."""
        try:
            if not discord_bot.is_ready():
                logger.warning("Discord not ready — briefing skipped")
                return
            subscriber_ids = await get_subscriber_ids()
            if not subscriber_ids:
                return

            import discord

            embed = discord.Embed(
                title="📋 Quality Dip — Batch Analysis",
                description=_build_briefing(candidates),
                color=discord.Color.dark_gold(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Project Atlas • Research priority only • Not financial advice")

            for uid in subscriber_ids:
                try:
                    user = await discord_bot.fetch_user(uid)
                    await user.send(embed=embed)
                    await asyncio.sleep(0.4)
                except Exception as e:
                    logger.warning("Briefing DM failed", user_id=uid, error=str(e))

            logger.info("Quality dip briefing sent", candidates=len(candidates))
        except Exception as e:
            logger.error("Briefing failed", error=str(e))

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
                    "category": snap.category,
                    "threshold_normal": snap.threshold_normal,
                    "threshold_high": snap.threshold_high,
                    "adaptive": snap.adaptive,
                    "review_score": snap.review_score,
                    "review_note": snap.review_note,
                    "reasons": snap.reasons,
                }
            )
        results.sort(key=lambda x: x.get("review_score", 0), reverse=True)
        return results


quality_dip_scanner = QualityDipScanner()