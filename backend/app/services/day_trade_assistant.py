"""Intraday LONG setups for the equity watchlist. Manual only. Never places orders.

PREPARE = place these limit orders and wait.
TRIGGER = price reached L1 — starter is valid if you want it.
No WAIT spam. No shorts. R:R from L1 is 1.8. Not a bottom call.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

import yfinance as yf

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("day_trade")
settings = get_settings()
ET = ZoneInfo("America/New_York")

L1_PCT = 0.007
L2_PCT = 0.014
MIN_RR = 1.8
MIN_GAP_DOWN = 1.0


@dataclass
class DayPlan:
    symbol: str
    name: str = ""
    phase: str = "CLOSED"
    bias: str = "LONG"
    action: str = "SKIP"
    confidence: float = 0.0
    price: float = 0.0
    prior_close: float = 0.0
    gap_pct: float = 0.0
    l1: float = 0.0
    l2: float = 0.0
    stop: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    rr: float = 0.0
    coach: str = ""
    reasons: list[str] = field(default_factory=list)

    @property
    def recommendation(self) -> str:
        return self.action

    @property
    def score(self) -> float:
        return self.confidence

    @property
    def risk_score(self) -> float:
        return 45.0

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
    info: dict[str, Any] = {}
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
    """LONG dip-buy only. Limits below last. R:R 1.8 from L1."""
    symbol = str(snap["symbol"])
    price = float(snap["price"] or 0)
    prior = float(snap["prior_close"] or 0)
    gap = float(snap["gap_pct"] or 0)
    name = str(snap.get("name") or symbol)

    if price <= 0:
        return DayPlan(symbol=symbol, action="SKIP", coach="no price")
    if gap > -MIN_GAP_DOWN:
        return DayPlan(
            symbol=symbol,
            name=name,
            phase=phase,
            price=round(price, 4),
            prior_close=round(prior, 4),
            gap_pct=round(gap, 2),
            action="SKIP",
            coach=f"Skip {symbol} — gap {gap:+.2f}% is not a long day-trade dip.",
        )

    l1 = round(price * (1.0 - L1_PCT), 4)
    l2 = round(price * (1.0 - L2_PCT), 4)
    risk_l1 = price * 0.012
    stop = round(l2 - risk_l1 * 0.25, 4)
    risk = l1 - stop
    if risk <= 0:
        return DayPlan(symbol=symbol, action="SKIP", coach="zero risk")
    tp1 = round(l1 + MIN_RR * risk, 4)
    tp2 = round(l1 + 3.0 * risk, 4)
    if prior > tp1:
        tp2 = round(max(tp2, prior), 4)
    rr = (tp1 - l1) / risk
    conf = min(78.0, 52.0 + abs(gap) * 3.0)

    in_hole = gap <= -2.5
    if phase == "MIDDAY":
        action = "SKIP"
        coach = f"Midday — no new day entries for {symbol}. Cancel unfilled limits."
    elif phase == "OPEN" and in_hole:
        action = "TRIGGER"
        conf = min(85.0, conf + 8)
        coach = (
            f"Already −{abs(gap):.1f}% vs prior. Starter only at L1 **${l1:.2f}** if you want it. "
            f"Leave L2 **${l2:.2f}** working. Stop **${stop:.2f}**. "
            f"TP1 **${tp1:.2f}** · TP2 **${tp2:.2f}**. You place every order."
        )
    else:
        action = "PREPARE"
        coach = (
            f"Place day limits and wait. Do not buy ${price:.2f} at the ask. "
            f"L1 starter ${l1:.2f} · L2 add ${l2:.2f} · stop ${stop:.2f}. "
            f"TP1 ${tp1:.2f} ({rr:.1f}R) · TP2 ${tp2:.2f}. "
            f"Cancel unfilled by 11:30 ET. You place every order."
        )

    return DayPlan(
        symbol=symbol,
        name=name,
        phase=phase,
        bias="LONG",
        action=action,
        confidence=round(conf, 1),
        price=round(price, 4),
        prior_close=round(prior, 4),
        gap_pct=round(gap, 2),
        l1=l1,
        l2=l2,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        rr=round(rr, 2),
        coach=coach,
        reasons=[f"gap {gap:+.2f}%"],
    )


def _plan_embed_text(plan: DayPlan) -> str:
    return (
        f"**{plan.symbol}** — {plan.name}\n"
        f"**Live: ${plan.price:.2f}** · gap **{plan.gap_pct:+.2f}%** vs ${plan.prior_close:.2f}\n"
        f"Call: **{plan.action}** · LONG only · {plan.phase}\n"
        f"Confidence: **{plan.confidence:.0f}/100** · R:R from L1: **{plan.rr:.1f}**\n"
        f"\n"
        f"**PLACE THESE LIMITS (you, not Atlas):**\n"
        f"• L1 starter: **${plan.l1:.2f}** (−{L1_PCT * 100:.1f}% )\n"
        f"• L2 add: **${plan.l2:.2f}** (−{L2_PCT * 100:.1f}% ) if it keeps falling\n"
        f"• Stop: **${plan.stop:.2f}**\n"
        f"• TP1: **${plan.tp1:.2f}** · TP2: **${plan.tp2:.2f}**\n"
        f"\n"
        f"{plan.coach}\n"
        f"Cancel unfilled day limits by 11:30 ET. Not financial advice."
    )


def _digest_text(plans: list[DayPlan]) -> str:
    lines = [
        "ATLAS DAY TRADE — PREPARE limits",
        "LONG dips only. Place these and wait. Atlas does not place orders.",
        "",
    ]
    for p in plans:
        lines.append(
            f"• **{p.symbol}** ${p.price:.2f} ({p.gap_pct:+.1f}%)  "
            f"L1 **${p.l1:.2f}**  L2 **${p.l2:.2f}**  stop **${p.stop:.2f}**  "
            f"TP1 **${p.tp1:.2f}** ({p.rr:.1f}R)"
        )
    lines += ["", "Do not chase the ask. Not financial advice."]
    return "\n".join(lines)


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
        await asyncio.sleep(8)
        interval = float(getattr(settings, "day_trade_scan_seconds", 90) or 90)
        while self._running:
            try:
                await self._scan()
            except Exception as e:
                logger.error("Day trade scan failed", error=str(e))
            await asyncio.sleep(max(45.0, interval))

    async def _cooldown_ok(self, key: str, seconds: int) -> bool:
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            if await redis.get(key):
                return False
            await redis.set(key, "1", ex=max(60, seconds))
            return True
        except Exception:
            return True

    async def _scan(self) -> None:
        phase = _session_phase()
        if phase == "CLOSED":
            logger.info("Day trade idle (market closed)")
            return

        from app.alerts.discord import send_discord_alert

        symbols = _watchlist()
        if not symbols:
            return

        prepares: list[DayPlan] = []
        triggers: list[DayPlan] = []
        for symbol in symbols:
            try:
                snap = await asyncio.to_thread(_fetch_snapshot, symbol)
                if float(snap.get("price") or 0) <= 0:
                    continue
                plan = _build_plan(snap, phase)
                if plan.action == "PREPARE":
                    prepares.append(plan)
                elif plan.action == "TRIGGER":
                    triggers.append(plan)
            except Exception as e:
                logger.warning("Day trade symbol error", symbol=symbol, error=str(e))

        day = datetime.now(ET).strftime("%Y-%m-%d")
        if prepares and phase in ("PREMARKET", "OPEN"):
            if await self._cooldown_ok(f"atlas:daytrade:digest:{day}", 20 * 3600):
                await send_discord_alert(
                    symbol="DAY",
                    title=f"ATLAS DAY TRADE — PREPARE · {len(prepares)} names",
                    description=_digest_text(prepares)[:1900],
                    price=0,
                    severity="MEDIUM",
                    opportunity=60,
                    confidence=60,
                    risk=45,
                )

        if phase == "MIDDAY":
            return

        for plan in triggers:
            key = f"atlas:daytrade:trigger:{day}:{plan.symbol}"
            if not await self._cooldown_ok(key, 3 * 3600):
                continue
            await send_discord_alert(
                symbol=plan.symbol,
                title=f"ATLAS DAY TRADE — TRIGGER · {plan.symbol} ${plan.price:.2f}",
                description=_plan_embed_text(plan)[:1900],
                price=plan.price,
                severity="HIGH",
                opportunity=int(plan.confidence),
                confidence=int(plan.confidence),
                risk=45,
                decision=plan,
            )


day_trade_assistant = DayTradeAssistant()
