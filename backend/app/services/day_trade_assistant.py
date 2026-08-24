"""US equity day-trade coach — premarket PREPARE + open WAIT/TRIGGER/SKIP.

Manual only. Never places orders.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import yfinance as yf

from app.alerts.discord import send_discord_alert
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger("day_trade")
settings = get_settings()
ET = ZoneInfo("America/New_York")


@dataclass
class DayPlan:
    symbol: str
    name: str = ""
    phase: str = "CLOSED"  # PREMARKET | OPEN | MIDDAY | CLOSED
    bias: str = "LONG"
    action: str = "WAIT"  # PREPARE | TRIGGER | WAIT | SKIP
    confidence: float = 0.0
    price: float = 0.0
    prior_close: float = 0.0
    gap_pct: float = 0.0
    limit_low: float = 0.0
    limit_high: float = 0.0
    stop: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    rr: float = 0.0
    coach: str = ""
    reasons: list[str] = field(default_factory=list)

    # aliases used by send_discord_alert(decision=...)
    @property
    def recommendation(self) -> str:
        return self.action

    @property
    def score(self) -> float:
        return self.confidence

    @property
    def risk_score(self) -> float:
        return 40.0

    @property
    def description(self) -> str:
        return self.coach


def _watchlist() -> list[str]:
    raw = getattr(settings, "day_trade_watchlist", "") or ""
    return [s.strip().upper() for s in str(raw).split(",") if s.strip()]


def _session_phase(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(ET)
    if now.weekday() >= 5:
        return "CLOSED"
    t = now.time()
    if time(4, 0) <= t < time(9, 30):
        return "PREMARKET"
    if time(9, 30) <= t < time(11, 30):
        return "OPEN"
    if time(11, 30) <= t < time(16, 0):
        return "MIDDAY"
    return "CLOSED"


def _fetch_snapshot(symbol: str) -> dict[str, Any]:
    t = yf.Ticker(symbol)
    info = {}
    try:
        info = t.info or {}
    except Exception:
        info = {}
    hist = t.history(period="10d", interval="1d")
    prior_close = 0.0
    last = 0.0
    if hist is not None and len(hist) >= 2:
        prior_close = float(hist["Close"].iloc[-2])
        last = float(hist["Close"].iloc[-1])
    # prefer live-ish
    try:
        fast = t.history(period="1d", interval="1m")
        if fast is not None and len(fast):
            last = float(fast["Close"].iloc[-1])
    except Exception:
        pass
    if last <= 0:
        last = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
    if prior_close <= 0:
        prior_close = float(info.get("previousClose") or last)
    name = str(info.get("shortName") or info.get("longName") or symbol)
    gap = ((last / prior_close) - 1.0) * 100.0 if prior_close > 0 else 0.0
    return {
        "symbol": symbol,
        "name": name,
        "price": last,
        "prior_close": prior_close,
        "gap_pct": gap,
    }


def _build_plan(snap: dict[str, Any], phase: str) -> DayPlan:
    symbol = snap["symbol"]
    price = float(snap["price"])
    prior = float(snap["prior_close"])
    gap = float(snap["gap_pct"])
    name = snap.get("name") or symbol

    gap_long = float(getattr(settings, "day_trade_gap_long_pct", 1.5))
    gap_short = float(getattr(settings, "day_trade_gap_short_pct", 2.0))

    # Default long bias on gap-down quality names
    bias = "LONG"
    action = "WAIT"
    conf = 50.0
    reasons: list[str] = []

    if gap <= -gap_long:
        bias = "LONG"
        conf = min(78.0, 55.0 + abs(gap) * 3.0)
        reasons.append(f"Gap/session down {gap:.2f}% vs prior close")
    elif gap >= gap_short:
        bias = "SHORT"
        conf = min(72.0, 52.0 + abs(gap) * 2.5)
        reasons.append(f"Gap/session up {gap:.2f}% vs prior close")
    else:
        action = "SKIP"
        conf = 40.0
        reasons.append(f"Gap {gap:.2f}% too small — no day plan")

    # Levels (ATR proxy ~0.8% of price)
    atr = max(price * 0.008, 0.05)
    if bias == "LONG":
        limit_high = price * 0.998
        limit_low = price - atr * 0.6
        stop = limit_low - atr * 0.5
        tp1 = price + atr * 1.0
        tp2 = prior if prior > price else price + atr * 2.5
    else:
        limit_low = price * 1.002
        limit_high = price + atr * 0.6
        stop = limit_high + atr * 0.5
        tp1 = price - atr * 1.0
        tp2 = prior if prior < price else price - atr * 2.5

    risk = abs(price - stop) or 1e-9
    reward = abs(tp1 - price)
    rr = reward / risk

    if action != "SKIP":
        if phase == "PREMARKET":
            action = "PREPARE"
            coach = (
                f"Do not buy yet. Premarket only. Watch **{symbol}** at **${price:.2f}**. "
                f"If the open sells into **${limit_low:.2f}–${limit_high:.2f}** and holds above "
                f"**${stop:.2f}**, then consider a starter. Otherwise stand down. "
                f"You place every order. Atlas does not execute."
            )
        elif phase == "OPEN":
            # distance to zone
            if bias == "LONG":
                if limit_low <= price <= limit_high:
                    action = "TRIGGER"
                    conf = min(85.0, conf + 8)
                    coach = (
                        f"**TRIGGER** — {symbol} **${price:.2f}** is in the buy zone "
                        f"(${limit_low:.2f}–${limit_high:.2f}). Starter only. Stop **${stop:.2f}**. "
                        f"TP1 **${tp1:.2f}** · TP2 **${tp2:.2f}**. You place every order."
                    )
                elif price > limit_high:
                    action = "WAIT"
                    coach = (
                        f"**WAIT** — {symbol} **${price:.2f}** is above the buy zone "
                        f"(${limit_low:.2f}–${limit_high:.2f}). Let it come to you or skip. "
                        f"No market chase."
                    )
                else:
                    action = "WAIT"
                    coach = (
                        f"**WAIT** — {symbol} **${price:.2f}** below zone; watch for reclaim of "
                        f"${limit_low:.2f} or stand down if under stop **${stop:.2f}**."
                    )
            else:
                if limit_low <= price <= limit_high:
                    action = "TRIGGER"
                    conf = min(82.0, conf + 6)
                    coach = (
                        f"**TRIGGER SHORT** — {symbol} **${price:.2f}** in zone. "
                        f"Stop **${stop:.2f}**. TP1 **${tp1:.2f}**. Manual only."
                    )
                else:
                    action = "WAIT"
                    coach = (
                        f"**WAIT** — {symbol} **${price:.2f}** not in short zone "
                        f"(${limit_low:.2f}–${limit_high:.2f})."
                    )
        else:
            action = "SKIP"
            coach = f"Midday/late — no new day entries for {symbol} at ${price:.2f}."
    else:
        coach = f"Skip {symbol} today — gap {gap:.2f}% not actionable."

    return DayPlan(
        symbol=symbol,
        name=name,
        phase=phase,
        bias=bias,
        action=action,
        confidence=round(conf, 1),
        price=round(price, 4),
        prior_close=round(prior, 4),
        gap_pct=round(gap, 2),
        limit_low=round(min(limit_low, limit_high), 4),
        limit_high=round(max(limit_low, limit_high), 4),
        stop=round(stop, 4),
        tp1=round(tp1, 4),
        tp2=round(tp2, 4),
        rr=round(rr, 2),
        coach=coach,
        reasons=reasons,
    )


def _plan_embed_text(plan: DayPlan) -> str:
    return (
        f"**{plan.symbol}** — {plan.name}\n"
        f"**Live price: ${plan.price:.2f}**\n"
        f"Call: **{plan.action}** · Bias: **{plan.bias}** · Phase: **{plan.phase}**\n"
        f"Confidence: **{plan.confidence:.0f}/100** · R:R (TP1): **{plan.rr:.1f}**\n"
        f"Prior close: ${plan.prior_close:.2f} · Gap: **{plan.gap_pct:+.2f}%**\n"
        f"Limit zone: **${plan.limit_low:.2f} – ${plan.limit_high:.2f}**\n"
        f"Stop: **${plan.stop:.2f}**\n"
        f"TP1: **${plan.tp1:.2f}** · TP2: **${plan.tp2:.2f}**\n\n"
        f"**Coach:** {plan.coach}"
    )


class DayTradeAssistant:
    def __init__(self) -> None:
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        if not getattr(settings, "day_trade_enabled", True):
            logger.info("Day trade assistant disabled")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Day trade assistant started", symbols=_watchlist())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Day trade assistant stopped")

    async def _loop(self) -> None:
        await asyncio.sleep(5)
        interval = float(getattr(settings, "day_trade_scan_seconds", 60))
        while self._running:
            try:
                await self._scan()
            except Exception as e:
                logger.error("Day trade scan failed", error=str(e))
            await asyncio.sleep(max(30.0, interval))

    async def _cooldown_ok(self, symbol: str, action: str) -> bool:
        redis = await get_redis()
        day = datetime.now(ET).strftime("%Y-%m-%d")
        # One PREPARE per symbol per day; TRIGGER/WAIT use shorter cooldown
        if action == "PREPARE":
            key = f"atlas:daytrade:prepare:{day}:{symbol}"
            if await redis.get(key):
                return False
            await redis.set(key, "1", ex=86400)
            return True
        mins = int(getattr(settings, "day_trade_alert_cooldown_minutes", 15))
        key = f"atlas:daytrade:alert:{symbol}:{action}"
        if await redis.get(key):
            return False
        await redis.set(key, "1", ex=max(60, mins * 60))
        return True

    async def _scan(self) -> None:
        phase = _session_phase()
        if phase == "CLOSED":
            logger.info("Day trade idle (market closed)")
            return

        symbols = _watchlist()
        if not symbols:
            return

        for symbol in symbols:
            try:
                snap = await asyncio.to_thread(_fetch_snapshot, symbol)
                if snap["price"] <= 0:
                    continue
                plan = _build_plan(snap, phase)
                if plan.action == "SKIP":
                    continue
                # Premarket: only PREPARE once; Open: WAIT/TRIGGER with cooldown
                if phase == "PREMARKET" and plan.action != "PREPARE":
                    continue
                if phase == "MIDDAY" and plan.action != "TRIGGER":
                    continue
                if not await self._cooldown_ok(symbol, plan.action):
                    continue

                title = f"{plan.symbol} ${plan.price:.2f} · {plan.action}"
                description = _plan_embed_text(plan)

                # Keyword-style call (always safe)
                await send_discord_alert(
                    symbol=plan.symbol,
                    title=title,
                    description=description,
                    price=plan.price,
                    severity="HIGH" if plan.action == "TRIGGER" else "MEDIUM",
                    opportunity=plan.confidence,
                    confidence=plan.confidence,
                    risk=40,
                    decision=plan,
                )
            except Exception as e:
                logger.warning("Day trade symbol error", symbol=symbol, error=str(e))


day_trade_assistant = DayTradeAssistant()