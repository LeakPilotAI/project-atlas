"""Slow, bounded Robinhood-universe discovery/research service.

Runs independently from request handling and the normal Quality Dips scanner.
The small cadence is intentional: broad coverage must not recreate the API
starvation caused by expensive high-frequency research work.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.investment.robinhood_discovery_research import research_batch
from app.investment.robinhood_universe_discovery import sync_official_rhj_assets

log = get_logger("robinhood_universe_research")


class RobinhoodUniverseResearchService:
    def __init__(self) -> None:
        self.running = False
        self._task: asyncio.Task | None = None
        self.last_sync_at: str | None = None
        self.last_research_at: str | None = None
        self.last_error: str | None = None
        self.last_result: dict[str, Any] = {}
        self.batch_size = max(1, min(int(os.getenv("ATLAS_RH_UNIVERSE_BATCH_SIZE", "4")), 8))
        self.interval_seconds = max(3600.0, float(os.getenv("ATLAS_RH_UNIVERSE_INTERVAL_SECONDS", "21600")))
        self.sync_interval_seconds = max(21600.0, float(os.getenv("ATLAS_RH_UNIVERSE_SYNC_SECONDS", "86400")))

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._run(), name="robinhood_universe_research")
        log.info(
            "Robinhood universe research scheduled",
            batch_size=self.batch_size,
            interval_seconds=self.interval_seconds,
            sync_interval_seconds=self.sync_interval_seconds,
        )

    async def stop(self) -> None:
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _run(self) -> None:
        # Let startup and the latency-sensitive scanners settle first.
        await asyncio.sleep(90)
        loop = asyncio.get_running_loop()
        next_sync = 0.0
        while self.running:
            try:
                now = loop.time()
                if now >= next_sync:
                    await sync_official_rhj_assets()
                    self.last_sync_at = datetime.now(timezone.utc).isoformat()
                    next_sync = now + self.sync_interval_seconds
                self.last_result = await research_batch(limit=self.batch_size)
                self.last_research_at = datetime.now(timezone.utc).isoformat()
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                log.warning("Robinhood universe research pass failed", error=self.last_error)
            await asyncio.sleep(self.interval_seconds)

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "batch_size": self.batch_size,
            "interval_seconds": self.interval_seconds,
            "sync_interval_seconds": self.sync_interval_seconds,
            "last_sync_at": self.last_sync_at,
            "last_research_at": self.last_research_at,
            "last_error": self.last_error,
            "last_researched_count": int(self.last_result.get("researched") or 0),
            "execution": "RESEARCH_ONLY_MANUAL",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }


robinhood_universe_research_service = RobinhoodUniverseResearchService()
