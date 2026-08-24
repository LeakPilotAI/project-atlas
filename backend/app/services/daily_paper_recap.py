"""Daily paper recap DM — every day including weekends (crypto 24/7)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)
ET = ZoneInfo("America/New_York")


class DailyPaperRecapService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_date: Optional[str] = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        settings = get_settings()
        if not getattr(settings, "daily_paper_recap_enabled", True):
            log.info("Daily paper recap disabled")
            return
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="daily_paper_recap")
        hour = int(getattr(settings, "daily_paper_recap_hour_et", 20) or 20)
        log.info("Daily paper recap started", hour_et=hour)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        await asyncio.sleep(40)
        while self._running:
            try:
                settings = get_settings()
                now = datetime.now(ET)
                hour = int(getattr(settings, "daily_paper_recap_hour_et", 20) or 20)
                minute = int(getattr(settings, "daily_paper_recap_minute_et", 0) or 0)
                date_key = now.strftime("%Y-%m-%d")
                if (
                    now.hour == hour
                    and now.minute >= minute
                    and now.minute < minute + 5
                    and self._last_date != date_key
                ):
                    await self._send()
                    self._last_date = date_key
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Daily paper recap error", error=str(e))
            await asyncio.sleep(30)

    async def _send(self) -> None:
        from app.alerts.discord import is_discord_ready, send_discord_alert
        from app.services.paper_journal import paper_journal

        if not is_discord_ready():
            log.warning("Daily paper recap skipped — Discord not ready")
            return

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        stats = await paper_journal.stats_since(since)
        all_stats = await paper_journal.stats()

        lines = [
            f"**Last 24h paper:** {stats['wins']}W / {stats['losses']}L · "
            f"sum R **{stats['sum_r']:+.2f}** · closed **{stats['closed']}**",
            f"**Open now:** {stats['open']}",
            f"**All-time:** {all_stats['wins']}W / {all_stats['losses']}L · "
            f"WR **{all_stats['win_rate_pct']}%** · sum R **{all_stats['sum_r']:+.2f}**",
            "",
        ]
        if stats["trades"]:
            lines.append("Recent closes:")
            for t in stats["trades"][-5:]:
                lines.append(
                    f"• `{t['symbol']}` {t['side']} → {t.get('result') or '?'} "
                    f"**{(t.get('pnl_r') or 0):+.2f}R**"
                )
        else:
            lines.append("_No closed paper trades in the last 24h — filters stayed strict._")
        lines.append("\n_Simulation only. Atlas does not execute live orders._")

        await send_discord_alert(
            symbol="PAPER",
            title="Atlas · Daily Paper Recap",
            description="\n".join(lines)[:3900],
            price=0.0,
            severity="MEDIUM",
            opportunity=50,
            confidence=60,
            risk=40,
        )
        log.info("Daily paper recap delivered", closed_24h=stats["closed"])


daily_paper_recap = DailyPaperRecapService()