"""Morning command center — one combined DM (RH posture + perps note)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)
ET = ZoneInfo("America/New_York")


class CommandCenterService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_date: Optional[str] = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        settings = get_settings()
        if not getattr(settings, "command_center_enabled", True):
            log.info("Command center disabled")
            return
        if self._task and not self._task.done():
            return
        self._running = True
        hour = int(getattr(settings, "command_center_hour_et", 8) or 8)
        self._task = asyncio.create_task(self._loop(), name="command_center")
        log.info("Command center started", hour_et=f"{hour:02d}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Command center stopped")

    async def _loop(self) -> None:
        await asyncio.sleep(25)
        while self._running:
            try:
                settings = get_settings()
                now = datetime.now(ET)
                if now.weekday() < 5:
                    h = int(getattr(settings, "command_center_hour_et", 8) or 8)
                    m = int(getattr(settings, "command_center_minute_et", 0) or 0)
                    date_key = now.strftime("%Y-%m-%d")
                    if (
                        now.hour == h
                        and now.minute >= m
                        and now.minute < m + 5
                        and self._last_date != date_key
                    ):
                        log.info("Command center tick", date=date_key)
                        await self._send()
                        self._last_date = date_key
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Command center error", error=str(e))
            await asyncio.sleep(30)

    async def _send(self) -> None:
        from app.alerts.discord import is_discord_ready, send_discord_alert

        if not is_discord_ready():
            log.warning("Command center skipped — Discord not ready")
            return

        settings = get_settings()
        allow = getattr(settings, "perp_allowlist_enabled", True)
        seeds = (getattr(settings, "perp_allowlist", "") or "BTC,ETH,SOL")[:120]
        micro = getattr(settings, "perp_micro_enabled", True)

        body = (
            "**Morning Command Center**\n\n"
            "**Robinhood (compound)**\n"
            "• Posture: WATCH research dips — prefer dry powder when unsure.\n"
            "• Max one name ≤15% · scale in · not a day-trade signal.\n\n"
            "**Perps (separate risk)**\n"
            f"• Allowlist active: **{allow}**\n"
            f"• Micro paper coach: **{micro}** (sim only · `/paper`)\n"
            f"• Seeds: `{seeds}`\n\n"
            "**Standing rules**\n"
            "• Target cash ≥40% when possible.\n"
            "• You place every order. Atlas does not execute.\n"
            f"_Generated {datetime.now(ET).strftime('%Y-%m-%d %H:%M')} ET · not advice_"
        )
        try:
            ok = await send_discord_alert(
                symbol="CMD",
                title="Atlas · Morning Command Center",
                description=body[:3900],
                price=0.0,
                severity="MEDIUM",
                opportunity=50,
                confidence=60,
                risk=40,
            )
            if ok:
                log.info("Command center delivered")
            else:
                log.warning("Command center send returned false")
        except Exception as e:
            log.error("Command center send failed", error=str(e))


command_center = CommandCenterService()