"""Robinhood joint-account morning brief — research only, one DM per weekday."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)
ET = ZoneInfo("America/New_York")


class RobinhoodBriefService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_date: Optional[str] = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        settings = get_settings()
        if not getattr(settings, "robinhood_brief_enabled", True):
            log.info("Robinhood brief disabled")
            return
        if self._task and not self._task.done():
            return
        self._running = True
        hour = int(getattr(settings, "robinhood_brief_hour_et", 8) or 8)
        minute = int(getattr(settings, "robinhood_brief_minute_et", 0) or 0)
        self._task = asyncio.create_task(self._loop(), name="robinhood_brief")
        log.info("Robinhood brief service started", hour_et=f"{hour:02d}:{minute:02d}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Robinhood brief service stopped")

    async def _loop(self) -> None:
        await asyncio.sleep(20)
        while self._running:
            try:
                settings = get_settings()
                now = datetime.now(ET)
                # Weekdays only
                if now.weekday() < 5:
                    target_h = int(getattr(settings, "robinhood_brief_hour_et", 8) or 8)
                    target_m = int(getattr(settings, "robinhood_brief_minute_et", 0) or 0)
                    date_key = now.strftime("%Y-%m-%d")
                    if (
                        now.hour == target_h
                        and now.minute >= target_m
                        and now.minute < target_m + 5
                        and self._last_date != date_key
                    ):
                        await self._send_brief()
                        self._last_date = date_key
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Robinhood brief loop error", error=str(e))
            await asyncio.sleep(30)

    async def _fetch_candidates(self) -> List[Dict[str, Any]]:
        """Rank core watchlist by % off 52w high (yfinance)."""
        settings = get_settings()
        symbols = list(getattr(settings, "robinhood_core_watchlist_list", []) or [])
        min_pct = float(getattr(settings, "robinhood_dip_min_pct", 12.0) or 12.0)
        max_n = int(getattr(settings, "robinhood_max_names_in_brief", 8) or 8)
        out: List[Dict[str, Any]] = []

        try:
            import yfinance as yf
        except Exception as e:
            log.warning("yfinance missing", error=str(e))
            return out

        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                info = t.info or {}
                hist = t.history(period="1y")
                if hist is None or hist.empty:
                    continue
                price = float(hist["Close"].iloc[-1])
                high_52 = float(hist["High"].max())
                low_52 = float(hist["Low"].min())
                if high_52 <= 0:
                    continue
                pct = (high_52 - price) / high_52 * 100.0
                if pct < min_pct:
                    continue
                name = str(info.get("shortName") or info.get("longName") or sym)
                # 5d change
                ch5 = 0.0
                if len(hist) >= 6:
                    p5 = float(hist["Close"].iloc[-6])
                    if p5 > 0:
                        ch5 = (price - p5) / p5 * 100.0
                out.append(
                    {
                        "symbol": sym,
                        "name": name,
                        "price": round(price, 2),
                        "pct_from_high": round(pct, 1),
                        "high_52w": round(high_52, 2),
                        "low_52w": round(low_52, 2),
                        "ch5": round(ch5, 1),
                    }
                )
            except Exception as e:
                log.warning("RH brief symbol fail", symbol=sym, error=str(e))
                continue

        out.sort(key=lambda x: x["pct_from_high"], reverse=True)
        return out[:max_n]

    async def _send_brief(self) -> None:
        from app.alerts.discord import is_discord_ready, send_discord_alert

        if not is_discord_ready():
            log.warning("Robinhood brief skipped — Discord not ready")
            return

        log.info("Building Robinhood morning brief")
        try:
            candidates = await self._fetch_candidates()
        except Exception as e:
            log.error("Robinhood brief failed", error=str(e))
            return

        if not candidates:
            posture = "HOLD CASH BIAS"
            body = (
                "No core names currently ≥ min dip threshold.\n"
                "Prefer dry powder. Wait for better discounts.\n"
                "_Research only · not advice_"
            )
            score = 40
        else:
            posture = "WATCH"
            lines = [
                f"**Posture: {posture}** — soft names for research only.",
                "Top candidates (compound lane):",
                "",
            ]
            for i, c in enumerate(candidates, 1):
                lines.append(
                    f"{i}. **{c['symbol']}** ${c['price']} · "
                    f"{c['pct_from_high']}% off 52w high · 5d {c['ch5']:+.1f}%\n"
                    f"   _{c['name']}_"
                )
            lines.extend(
                [
                    "",
                    "Rules: ≤15% one name · scale in · RH ≠ day-trade TRIGGER.",
                    "You place every order. Atlas does not execute.",
                    "_Research only · not financial advice_",
                ]
            )
            body = "\n".join(lines)
            score = int(min(85, 40 + candidates[0]["pct_from_high"]))

        try:
            ok = await send_discord_alert(
                symbol="RH",
                title=f"Atlas · Robinhood Brief · {posture}",
                description=body[:3900],
                price=0.0,
                severity="MEDIUM",
                opportunity=score,
                confidence=65,
                risk=40,
            )
            if ok:
                log.info("Robinhood brief delivered", names=len(candidates))
            else:
                log.warning("Robinhood brief send returned false")
        except Exception as e:
            log.error("Robinhood brief failed", error=str(e))


robinhood_brief_service = RobinhoodBriefService()