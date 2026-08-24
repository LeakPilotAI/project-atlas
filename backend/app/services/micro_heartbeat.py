"""Always-on heartbeat so quiet markets still show the coach is alive."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)


class MicroHeartbeatService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.scans: int = 0
        self.triggers: int = 0
        self.last_trigger_at: Optional[datetime] = None
        self.last_error: Optional[str] = None

    @property
    def running(self) -> bool:
        return self._running

    def record_scan(self) -> None:
        self.scans += 1

    def record_trigger(self) -> None:
        self.triggers += 1
        self.last_trigger_at = datetime.now(timezone.utc)

    async def start(self) -> None:
        settings = get_settings()
        if not getattr(settings, "micro_heartbeat_enabled", True):
            log.info("Micro heartbeat disabled")
            return
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="micro_heartbeat")
        hours = float(getattr(settings, "micro_heartbeat_hours", 6.0) or 6.0)
        log.info("Micro heartbeat started", every_hours=hours)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Micro heartbeat stopped")

    async def _loop(self) -> None:
        settings = get_settings()
        hours = float(getattr(settings, "micro_heartbeat_hours", 6.0) or 6.0)
        interval = max(3600.0, hours * 3600.0)
        # First pulse ~10 minutes after start (not 6h)
        await asyncio.sleep(600.0)
        while self._running:
            try:
                await self._pulse()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.last_error = str(e)
                log.warning("Heartbeat pulse failed", error=str(e), exc_info=True)
            await asyncio.sleep(interval)

    async def _pulse(self) -> None:
        liquid = 0
        open_n = 0
        wins = losses = 0
        sum_r = 0.0
        wr = 0.0

        try:
            from app.services.perp_micro_coach import perp_micro_coach

            liquid = int(getattr(perp_micro_coach, "liquid_count", 0) or 0)
        except Exception as e:
            log.debug("heartbeat liquid lookup", error=str(e))

        try:
            from app.services.paper_journal import paper_journal

            stats = await paper_journal.stats()
            open_n = int(stats.get("open") or 0)
            wins = int(stats.get("wins") or 0)
            losses = int(stats.get("losses") or 0)
            sum_r = float(stats.get("sum_r") or 0)
            wr = float(stats.get("win_rate_pct") or 0)
        except Exception as e:
            log.warning("heartbeat paper stats failed", error=str(e))

        weekend = datetime.now(timezone.utc).weekday() >= 5
        focus = "majors+liquid" if weekend else "full liquid set"

        body = (
            f"**Micro coach heartbeat**\n"
            f"• Liquid set: **{liquid}** · focus: `{focus}`\n"
            f"• Scans (session): **{self.scans}**\n"
            f"• Triggers (session): **{self.triggers}**\n"
            f"• Paper open: **{open_n}** · "
            f"all-time {wins}W/{losses}L (WR {wr}%) · "
            f"sum R **{sum_r:+.2f}**\n"
            f"_Quiet = strict filters. Paper only · no live execution._"
        )

        # Always log so you see activity even if DM fails
        log.info(
            "Heartbeat pulse",
            liquid=liquid,
            scans=self.scans,
            triggers=self.triggers,
            open=open_n,
            sum_r=sum_r,
        )

        try:
            from app.alerts.discord import is_discord_ready, send_discord_alert

            if not is_discord_ready():
                log.info("Heartbeat (log only) — Discord not ready")
                return

            ok = await send_discord_alert(
                symbol="HB",
                title="Atlas · Micro Heartbeat",
                description=body[:3900],
                price=0.0,
                severity="LOW",
                opportunity=40,
                confidence=50,
                risk=30,
            )
            if ok:
                log.info("Heartbeat DM sent")
            else:
                log.warning("Heartbeat DM returned false")
        except Exception as e:
            self.last_error = str(e)
            log.warning("Heartbeat DM failed", error=str(e), exc_info=True)


micro_heartbeat = MicroHeartbeatService()