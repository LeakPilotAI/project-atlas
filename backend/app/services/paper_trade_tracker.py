"""Legacy paper trade tracker — soft-disabled.

Real Hyperliquid paper simulation lives in perp_micro_coach (Redis).
This service stays importable for main.py lifespan but does not call
missing model methods like PaperTrade.evaluate_after.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


class PaperTradeTracker:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="paper_trade_tracker")
        log.info(
            "Paper trade tracker started (legacy no-op; use perp_micro_coach + /paper)"
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("Paper trade tracker stopped")

    async def _loop(self) -> None:
        """Idle loop — does not evaluate DB PaperTrade rows."""
        await asyncio.sleep(5)
        while self._running:
            try:
                # Intentionally empty: avoid PaperTrade.evaluate_after and
                # duplicate logic with perp_micro_coach.
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("Paper trade tracker cycle error", error=str(e))
                await asyncio.sleep(30)


paper_trade_tracker = PaperTradeTracker()