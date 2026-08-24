"""LEGACY NO-OP. Hyperliquid paper stats = paper_journal + perp_micro_coach only.

Do not open HL paper trades here. Opportunity tracker / old paths must not write
stats through this module. Kept so imports in main.py / opportunity_tracker
do not crash.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


class PaperTradeTracker:
    def __init__(self) -> None:
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True
        log.info(
            "Paper trade tracker started (legacy no-op; use perp_micro_coach + /paper)"
        )

    async def stop(self) -> None:
        self._running = False
        log.info("Paper trade tracker stopped")

    async def open_trade(self, *args: Any, **kwargs: Any) -> Optional[str]:
        log.debug("paper_trade_tracker.open_trade ignored (legacy no-op)")
        return None

    async def close_trade(self, *args: Any, **kwargs: Any) -> None:
        log.debug("paper_trade_tracker.close_trade ignored (legacy no-op)")

    async def list_open(self) -> List[Dict[str, Any]]:
        return []

    async def stats(self) -> Dict[str, Any]:
        return {
            "legacy": True,
            "message": "Use paper_journal / perp_micro_coach for paper stats",
        }


paper_trade_tracker = PaperTradeTracker()