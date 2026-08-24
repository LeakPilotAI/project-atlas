"""
Morning Command Center — single daily decision panel.

One Discord DM per weekday (~8:00 ET by default):
  - Robinhood posture: DRY_POWDER | WATCH | SCALE_OK
  - Top quality names (or explicit NO DEPLOY)
  - Perps status (quiet / watch)
  - Cash / sizing reminders

Does not place trades. Research + process only.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

import yfinance as yf

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.alerts.discord import bot as discord_bot, get_subscriber_ids

logger = get_logger("command_center")
settings = get_settings()
ET = ZoneInfo("America/New_York")

CC_KEY = "atlas:command_center:date"


def _enabled() -> bool:
    v = getattr(settings, "command_center_enabled", True)
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes", "on")
    return bool(v)


def _hour() -> int:
    return int(getattr(settings, "command_center_hour_et", 8))


def _minute() -> int:
    return int(getattr(settings, "command_center_minute_et", 0))


def _rh_watchlist() -> list[str]:
    raw = getattr(settings, "robinhood_core_watchlist", "") or getattr(
        settings, "quality_dip_watchlist", ""
    )
    return [s.strip().upper() for s in str(raw).split(",") if s.strip()]


def _min_dip() -> float:
    return float(getattr(settings, "robinhood_dip_min_pct", 12.0))


def _scale_dip() -> float:
    """Stronger threshold for SCALE_OK posture."""
    return float(getattr(settings, "command_center_scale_dip_pct", 20.0))


def _max_names() -> int:
    return int(getattr(settings, "robinhood_max_names_in_brief", 5))


def _cash_pct() -> float:
    return float(getattr(settings, "rh_target_cash_pct", 40.0))


def _max_name_pct() -> float:
    return float(getattr(settings, "rh_max_single_name_pct", 15.0))


def _tranches() -> int:
    return int(getattr(settings, "rh_scale_tranches", 3))


def _perp_allowlist() -> list[str]:
    raw = getattr(settings, "perp_allowlist", "") or ""
    return [s.strip() for s in str(raw).split(",") if s.strip()]


@dataclass
class NameSnap:
    symbol: str
    name: str
    price: float
    pct_from_high: float
    high_52w: float
    low_52w: float
    chg_5d: Optional[float]
    chg_20d: Optional[float]
    score: float = 0.0


@dataclass
class CommandBoard:
    posture: str  # DRY_POWDER | WATCH | SCALE_OK
    names: list[NameSnap] = field(default_factory=list)
    rh_lines: list[str] = field(default_factory=list)
    perp_lines: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)


def _snapshot(symbol: str) -> Optional[NameSnap]:
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        hist = t.history(period="1y", auto_adjust=True)
        if hist is None or hist.empty or len(hist) < 40:
            return None
        price = float(hist["Close"].iloc[-1])
        high = float(hist["High"].max())
        low = float(hist["Low"].min())
        if high <= 0:
            return None
        pct = (high - price) / high * 100.0
        name = str(info.get("shortName") or info.get("longName") or symbol)

        def chg(n: int) -> Optional[float]:
            if len(hist) < n + 1:
                return None
            past = float(hist["Close"].iloc[-(n + 1)])
            if past <= 0:
                return None
            return (price / past - 1.0) * 100.0

        c5 = chg(5)
        c20 = chg(20)
        score = pct * 0.8
        if c5 is not None:
            if c5 <= -5:
                score += 15
            elif c5 <= -2:
                score += 8
            elif c5 >= 5:
                score -= 10
        return NameSnap(
            symbol=symbol,
            name=name,
            price=round(price, 2),
            pct_from_high=round(pct, 1),
            high_52w=round(high, 2),
            low_52w=round(low, 2),
            chg_5d=round(c5, 1) if c5 is not None else None,
            chg_20d=round(c20, 1) if c20 is not None else None,
            score=score,
        )
    except Exception as e:
        logger.warning("CC snapshot failed", symbol=symbol, error=str(e))
        return None


def _posture_for(names: list[NameSnap]) -> str:
    if not names:
        return "DRY_POWDER"
    best = names[0].pct_from_high
    scale = _scale_dip()
    watch = _min_dip()
    if best >= scale:
        return "SCALE_OK"
    if best >= watch:
        return "WATCH"
    return "DRY_POWDER"


def _build_board(names: list[NameSnap]) -> CommandBoard:
    posture = _posture_for(names)
    board = CommandBoard(posture=posture, names=names)

    if posture == "DRY_POWDER":
        board.rh_lines = [
            "**Posture: DRY_POWDER — NO DEPLOY**",
            "No name clears a meaningful discount bar today.",
            "Keep buying power in reserve. Missing mediocre dips is a win.",
            "Joint account: **do not force shares** just to be active.",
        ]
    elif posture == "WATCH":
        board.rh_lines = [
            "**Posture: WATCH**",
            "Some names are soft — research only, prefer waiting for better entry or stronger discount.",
            "If you act, use a **small first tranche** only.",
        ]
    else:
        board.rh_lines = [
            "**Posture: SCALE_OK**",
            "At least one name is in a deeper discount zone.",
            "Still not a market order panic — scale in, confirm on Robinhood, hold thesis.",
        ]

    if names:
        board.rh_lines.append("")
        board.rh_lines.append("**Top candidates (quality / compound lane):**")
        for i, n in enumerate(names[: _max_names()], 1):
            c5 = f" · 5d {n.chg_5d:+.1f}%" if n.chg_5d is not None else ""
            board.rh_lines.append(
                f"{i}. **{n.symbol}** ${n.price:,.2f} · "
                f"**{n.pct_from_high:.1f}%** off 52w high{c5}"
            )
            board.rh_lines.append(f"   _{n.name}_")
    else:
        board.rh_lines.append("")
        board.rh_lines.append("_No RH deploy list today._")

    allow = _perp_allowlist()
    if allow:
        board.perp_lines = [
            f"Allowlist active ({len(allow)} symbols).",
            "Only **A+** Discord alerts matter — ignore noise.",
            "Perps risk is **separate** from joint Robinhood capital.",
            f"Watch seeds: {', '.join(allow[:12])}{'…' if len(allow) > 12 else ''}",
        ]
    else:
        board.perp_lines = [
            "No allowlist filter — full Hyperliquid scan (or enable PERP_ALLOWLIST).",
            "Only A+ setups; never fund perp losses from RH compound capital.",
        ]

    board.rules = [
        f"Target cash / dry powder: **≥ {_cash_pct():.0f}%** of joint account when possible.",
        f"Max one name: **≤ {_max_name_pct():.0f}%** of account.",
        f"Scale in up to **{_tranches()}** tranches — never full size on first print.",
        "RH = own businesses for months. Day-trade TRIGGER ≠ RH buy signal.",
        "You place every order. Atlas does not execute.",
    ]
    return board


def _embed_description(board: CommandBoard) -> str:
    posture_icon = {
        "DRY_POWDER": "⬛",
        "WATCH": "🟡",
        "SCALE_OK": "🟢",
    }.get(board.posture, "⚪")

    lines = [
        f"# Morning Command Center",
        f"**{posture_icon} Robinhood: {board.posture}**",
        "",
        "## Joint account (compound)",
        *board.rh_lines,
        "",
        "## Perps (separate risk)",
        *[f"• {x}" for x in board.perp_lines],
        "",
        "## Standing rules",
        *[f"• {x}" for x in board.rules],
        "",
        f"_Generated {datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}_",
        "_Research only · Not financial advice · No guaranteed returns_",
    ]
    return "\n".join(lines)


class MorningCommandCenter:
    def __init__(self) -> None:
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not _enabled():
            logger.info("Morning command center disabled")
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "Morning command center started",
            hour_et=f"{_hour():02d}:{_minute():02d}",
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Morning command center stopped")

    async def run_now(self) -> None:
        """Manual trigger (tests / Discord command later)."""
        await self._send()

    async def _loop(self) -> None:
        await asyncio.sleep(15)
        while self._running:
            try:
                await self._maybe_run()
            except Exception as e:
                logger.error("Command center cycle failed", error=str(e))
            await asyncio.sleep(45)

    async def _maybe_run(self) -> None:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return
        if not (now.hour == _hour() and now.minute == _minute()):
            return

        redis = await get_redis()
        day = now.strftime("%Y-%m-%d")
        raw = await redis.get(CC_KEY)
        if raw:
            val = raw.decode() if isinstance(raw, bytes) else str(raw)
            if val == day:
                return

        await self._send()
        await redis.set(CC_KEY, day, ex=36 * 3600)

    async def _send(self) -> None:
        logger.info("Building morning command center")
        names: list[NameSnap] = []
        for sym in _rh_watchlist():
            snap = await asyncio.to_thread(_snapshot, sym)
            if snap and snap.pct_from_high >= _min_dip():
                names.append(snap)
            await asyncio.sleep(0.35)
        names.sort(key=lambda n: n.score, reverse=True)
        names = names[: _max_names()]
        board = _build_board(names)
        text = _embed_description(board)

        if not discord_bot.is_ready():
            logger.warning("Discord not ready for command center")
            return
        ids = await get_subscriber_ids()
        if not ids:
            logger.warning("No subscribers for command center")
            return

        import discord

        color = {
            "DRY_POWDER": discord.Color.dark_grey(),
            "WATCH": discord.Color.gold(),
            "SCALE_OK": discord.Color.green(),
        }.get(board.posture, discord.Color.blurple())

        # Discord embed description max ~4096
        if len(text) > 4000:
            text = text[:3990] + "\n…"

        embed = discord.Embed(
            title="🎯 Atlas · Morning Command Center",
            description=text,
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(
            text="Joint RH ≠ day trade ≠ perps · You execute · Not financial advice"
        )

        for uid in ids:
            try:
                user = await discord_bot.fetch_user(uid)
                await user.send(embed=embed)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning("CC DM failed", user_id=uid, error=str(e))

        logger.info(
            "Command center sent",
            posture=board.posture,
            names=[n.symbol for n in board.names],
        )


morning_command_center = MorningCommandCenter()