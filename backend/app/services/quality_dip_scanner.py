"""Quality-dip view. Thin consumer of the investment engine. No second Yahoo loop."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)


class QualityDipScanner:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.last_scan_at: Optional[str] = None
        self.last_snapshot: List[Dict[str, Any]] = []

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        settings = get_settings()
        if not getattr(settings, "quality_dip_enabled", True):
            log.info("Quality dip consumer disabled")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="quality_dip_consumer")
        log.info("Quality dip consumer started (investment engine is source of truth)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Quality dip consumer stopped")

    async def _consume(self) -> None:
        from app.investment.scan import investment_scanner
        from app.investment.storage import bootstrap_universe_if_missing
        from app.investment.tape import as_quality_dip_rows

        bootstrap_universe_if_missing()
        if not getattr(investment_scanner, "running", False):
            try:
                await investment_scanner.run_once()
            except Exception as e:
                log.warning("investment run_once from quality-dip consumer failed", error=str(e)[:200])
        self.last_snapshot = as_quality_dip_rows()
        self.last_scan_at = datetime.now(timezone.utc).isoformat()

    async def _loop(self) -> None:
        settings = get_settings()
        interval = max(
            300.0,
            float(getattr(settings, "quality_dip_scan_interval_minutes", 60) or 60) * 60.0,
        )
        await asyncio.sleep(10)
        while self._running:
            try:
                await self._consume()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("Quality dip consume failed", error=str(e))
            await asyncio.sleep(interval)


quality_dip_scanner = QualityDipScanner()
