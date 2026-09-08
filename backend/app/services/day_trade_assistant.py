"""Quality-dip coach for the equity watchlist. Manual only. Never places orders.

Replaces the old 0.3% scalp 'buy zone' (wrong pricing, 0.9 R:R, WAIT spam).
Limits are 3 / 7 / 12 / 18% below last. Not a bottom call. No shorts.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import yfinance as yf

from app.core.config import get_settings
from app.core.logging import get_logger
from app.investment.buy_prep import classify_buy_prep, format_quality_dip_alert

logger = get_logger("day_trade")
settings = get_settings()
ET = ZoneInfo("America/New_York")


@dataclass
class DayPlan:
    symbol: str
    name: str = ""
    phase: str = "CLOSED"
    bias: str = "LONG"
    action: str = "WAIT"
    stance: str = "WATCH"
    confidence: float = 0.0
    price: float = 0.0
    prior_close: float = 0.0
    gap_pct: float = 0.0
    off_high: float = 0.0
    bottom_risk: int = 0
    quality_score: int = 0
    trap: bool = False
    ladder: list = field(default_factory=list)
    coach: str = ""
    reasons: list[str] = field(default_factory=list)
    prep: dict = field(default_factory=dict)
    snap: dict = field(default_factory=dict)

    @property
    def recommendation(self) -> str:
        return self.stance or self.action

    @property
    def score(self) -> float:
        return float(self.quality_score or self.confidence)

    @property
    def risk_score(self) -> float:
        return float(self.bottom_risk or 40)

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
    if time(9, 30) <= t < time(16, 0):
        return "OPEN"
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
    r5 = None
    if hist is not None and len(hist) >= 2:
        prior_close = float(hist["Close"].iloc[-2])
        last = float(hist["Close"].iloc[-1])
        if len(hist) >= 6:
            base = float(hist["Close"].iloc[-6])
            if base > 0:
                r5 = last / base - 1.0
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
    high = float(info.get("fiftyTwoWeekHigh") or 0)
    if high <= 0 and hist is not None and len(hist):
        try:
            high = float(hist["High"].max())
        except Exception:
            high = 0.0
    name = str(info.get("shortName") or info.get("longName") or symbol)
    gap = ((last / prior_close) - 1.0) if prior_close > 0 else 0.0
    dd = ((high - last) / high) if high > last > 0 else 0.0
    return {
        "symbol": symbol,
        "name": name,
        "price": last,
        "prior_close": prior_close,
        "gap_pct": gap * 100.0,
        "ret_1d": gap,
        "ret_5d": r5,
        "drawdown": dd,
        "high_52w": high,
    }


def _thesis_and_move(snap: dict[str, Any]) -> tuple[str, str]:
    dd = float(snap.get("drawdown") or 0)
    r1 = snap.get("ret_1d")
    r1f = float(r1) if r1 is not None else 0.0
    if dd >= 0.40 and r1f < 0:
        th = "UNDER_PRESSURE"
    elif dd >= 0.25 and r1f <= -0.04:
        th = "UNDER_PRESSURE"
    else:
        th = "INTACT"
    if r1f <= -0.04:
        mv = "ELEVATED_SELLING"
    elif r1f <= -0.015:
        mv = "NORMAL_PULLBACK"
    elif r1f >= 0.04:
        mv = "NORMAL"
    else:
        mv = "NORMAL_PULLBACK" if dd >= 0.08 else "NORMAL"
    return th, mv


def _build_plan(snap: dict[str, Any], phase: str) -> DayPlan:
    """Quality-dip plan. Never shorts. Never a 0.3% scalp zone."""
    symbol = snap["symbol"]
    price = float(snap["price"] or 0)
    th, mv = _thesis_and_move(snap)
    prep = classify_buy_prep(
        thesis=th,
        move_class=mv,
        investment_class="NO_ACTION",
        drawdown=snap.get("drawdown") or 0.0,
        ret_1d=snap.get("ret_1d"),
        ret_5d=snap.get("ret_5d"),
        price=price,
    )
    stance = str(prep.get("stance") or "WATCH")
    action = str(prep.get("action") or "WATCH")
    ladder = prep.get("ladder") or []
    t1 = ladder[0]["limit"] if ladder else None
    coach = str(prep.get("reason") or "")
    if stance == "SCALE_SMALL" and t1:
        coach = (
            f"SCALE IN — {symbol} ${price:.2f}. First limit ${t1:,.2f} (3% below last). "
            f"Then 7 / 12 / 18% if it keeps falling. Not a bottom. You place the order."
        )
    elif stance == "WAIT_CHEAPER" and t1:
        coach = (
            f"WAIT — {symbol} ${price:.2f} is not a buy-the-ask. "
            f"Still-falling {prep.get('bottom_risk')}/100. Park T1 at ${t1:,.2f} or skip. "
            f"Do not chase."
        )
    elif stance == "DO_NOT_BUY":
        coach = f"DO NOT BUY {symbol} — thesis/trap. Cancel any working limits."

    return DayPlan(
        symbol=symbol,
        name=str(snap.get("name") or symbol),
        phase=phase,
        bias="LONG",
        action=action,
        stance=stance,
        confidence=float(prep.get("quality_score") or 0),
        price=round(price, 4),
        prior_close=round(float(snap.get("prior_close") or 0), 4),
        gap_pct=round(float(snap.get("gap_pct") or 0), 2),
        off_high=round(float(snap.get("drawdown") or 0) * 100.0, 1),
        bottom_risk=int(prep.get("bottom_risk") or 0),
        quality_score=int(prep.get("quality_score") or 0),
        trap=bool(prep.get("trap")),
        ladder=ladder,
        coach=coach,
        reasons=[th, mv, coach],
        prep=prep,
        snap=snap,
    )


def _plan_embed_text(plan: DayPlan) -> str:
    row = {
        "symbol": plan.symbol,
        "name": plan.name,
        "price": plan.price,
        "pct_from_high": plan.off_high,
        "ret_1d": plan.snap.get("ret_1d"),
        "ret_5d": plan.snap.get("ret_5d"),
        "thesis": (plan.reasons[0] if plan.reasons else "INTACT"),
        "classification": (plan.reasons[1] if len(plan.reasons) > 1 else ""),
    }
    return format_quality_dip_alert(row, plan.prep)


def _digest_text(plans: list[DayPlan]) -> str:
    lines = [
        "ATLAS QUALITY DIP — WAIT cheaper (digest)",
        "Not a bottom. Limits are 3/7/12/18% below last. You place any order.",
        "",
    ]
    for p in plans:
        t1 = p.ladder[0]["limit"] if p.ladder else None
        t1s = f"${t1:,.2f}" if t1 else "—"
        lines.append(
            f"• {p.symbol} ${p.price:,.2f}  off-high {p.off_high:.0f}%  "
            f"falling {p.bottom_risk}/100  T1 {t1s}  {p.stance}"
        )
    lines += ["", "Do not buy the ask on WAIT_CHEAPER names. Not financial advice."]
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
        logger.info("Day trade assistant started (quality-dip ladder)", symbols=_watchlist())

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
        interval = float(getattr(settings, "day_trade_scan_seconds", 300) or 300)
        while self._running:
            try:
                await self._scan()
            except Exception as e:
                logger.error("Day trade scan failed", error=str(e))
            await asyncio.sleep(max(120.0, interval))

    async def _cooldown_ok(self, key: str, hours: float) -> bool:
        try:
            from app.core.redis import get_redis

            redis = await get_redis()
            if await redis.get(key):
                return False
            await redis.set(key, "1", ex=int(max(1.0, hours) * 3600))
            return True
        except Exception:
            return True

    async def _scan(self) -> None:
        phase = _session_phase()
        if phase == "CLOSED":
            logger.info("Day trade idle (market closed)")
            return

        symbols = _watchlist()
        if not symbols:
            return

        scale: list[DayPlan] = []
        wait: list[DayPlan] = []
        stand: list[DayPlan] = []
        for symbol in symbols:
            try:
                snap = await asyncio.to_thread(_fetch_snapshot, symbol)
                if float(snap.get("price") or 0) <= 0:
                    continue
                plan = _build_plan(snap, phase)
                if plan.stance == "SCALE_SMALL":
                    scale.append(plan)
                elif plan.stance == "WAIT_CHEAPER":
                    wait.append(plan)
                elif plan.stance == "DO_NOT_BUY":
                    stand.append(plan)
            except Exception as e:
                logger.warning("Day trade symbol error", symbol=symbol, error=str(e))

        hours = float(getattr(settings, "day_trade_alert_cooldown_minutes", 720) or 720) / 60.0
        hours = max(6.0, hours)
        from app.alerts.discord import send_discord_alert

        for plan in scale:
            key = f"atlas:dip:scale:{plan.symbol}"
            if not await self._cooldown_ok(key, hours):
                continue
            await send_discord_alert(
                symbol=plan.symbol,
                title=f"ATLAS QUALITY DIP — SCALE · {plan.symbol} ${plan.price:.2f}",
                description=_plan_embed_text(plan)[:1900],
                price=plan.price,
                severity="HIGH",
                opportunity=plan.quality_score,
                confidence=plan.quality_score,
                risk=min(90, plan.bottom_risk),
                decision=plan,
            )

        if wait:
            day = datetime.now(ET).strftime("%Y-%m-%d")
            if await self._cooldown_ok(f"atlas:dip:waitdigest:{day}", hours):
                wait.sort(key=lambda p: -p.bottom_risk)
                await send_discord_alert(
                    symbol="DIP",
                    title=f"ATLAS QUALITY DIP — WAIT cheaper · {len(wait)} names",
                    description=_digest_text(wait)[:1900],
                    price=0,
                    severity="MEDIUM",
                    opportunity=40,
                    confidence=40,
                    risk=55,
                )

        for plan in stand:
            key = f"atlas:dip:stand:{plan.symbol}"
            if not await self._cooldown_ok(key, max(12.0, hours)):
                continue
            await send_discord_alert(
                symbol=plan.symbol,
                title=f"ATLAS QUALITY DIP — DO NOT BUY · {plan.symbol}",
                description=_plan_embed_text(plan)[:1900],
                price=plan.price,
                severity="HIGH",
                opportunity=10,
                confidence=plan.quality_score,
                risk=90,
                decision=plan,
            )


day_trade_assistant = DayTradeAssistant()
