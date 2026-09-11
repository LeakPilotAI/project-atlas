"""Morning command center — read-only domain-isolated summary DM."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import structlog

from app.core.config import get_settings
from app.services.command_center_summary import live_command_center_summary
from app.services.perp_manual_service import perp_manual_service

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

    @staticmethod
    def _body(summary: dict) -> str:
        perps = summary.get("perps") or {}
        investments = summary.get("investments") or {}
        counts = investments.get("counts") or {}
        top_perp = perps.get("top_setup") or {}
        top_inv = investments.get("top_opportunity") or {}

        perp_top = "none"
        if top_perp:
            perp_top = (
                f"{top_perp.get('symbol')} {top_perp.get('side')} · "
                f"{top_perp.get('tier')} · {top_perp.get('state')}"
            )
        inv_top = "none"
        if top_inv:
            inv_top = (
                f"{top_inv.get('symbol')} · {top_inv.get('stance')} · "
                f"evidence {top_inv.get('evidence_quality')} · thesis {top_inv.get('thesis')}"
            )

        return (
            "**Morning Command Center**\n\n"
            "**Perp Day Trade — HYPERLIQUID_PERPS**\n"
            f"• Running: **{bool(perps.get('running'))}** · markets: **{perps.get('market_count', 0)}**\n"
            f"• PRIME: **{perps.get('prime_count', 0)}** · QUALIFIED: **{perps.get('qualified_count', 0)}**\n"
            f"• Actionable: **{perps.get('actionable_count', 0)}**\n"
            f"• Auto-paper open now: **{perps.get('auto_paper_open_count', 0)}** · opened total: **{perps.get('auto_paper_opened_total', 0)}** · closed total: **{perps.get('auto_paper_closed_total', 0)}**\n"
            f"• Top setup: **{perp_top}**\n\n"
            "**Quality Dips — EQUITY_INVESTMENT**\n"
            f"• Assets: **{investments.get('asset_count', 0)}**\n"
            f"• ACCUMULATE: **{counts.get('ACCUMULATE', 0)}** · PREPARE: **{counts.get('PREPARE', 0)}**\n"
            f"• WATCH: **{counts.get('WATCH', 0)}** · STAND_DOWN: **{counts.get('STAND_DOWN', 0)}**\n"
            f"• Top research row: **{inv_top}**\n\n"
            "**Isolation rules**\n"
            "• Perp and investment symbols, capital assumptions, performance, and action logic remain separate.\n"
            "• Auto-paper fills are research-only and never place exchange orders or unlock live capital.\n"
            "• Atlas places no orders from Command Center.\n"
            f"_Generated {datetime.now(ET).strftime('%Y-%m-%d %H:%M')} ET · read-only_"
        )

    async def _send(self) -> None:
        from app.alerts.discord import is_discord_ready, send_discord_alert

        if not is_discord_ready():
            log.warning("Command center skipped — Discord not ready")
            return

        summary = live_command_center_summary(perp_manual_service.snapshot())
        body = self._body(summary)
        try:
            ok = await send_discord_alert(
                symbol="CMD",
                title="Atlas · Morning Command Center",
                description=body[:3900],
                price=0.0,
                severity="LOW",
                opportunity=0,
                confidence=0,
                risk=0,
            )
            if ok:
                log.info("Command center delivered")
            else:
                log.warning("Command center send returned false")
        except Exception as e:
            log.error("Command center send failed", error=str(e))


command_center = CommandCenterService()
