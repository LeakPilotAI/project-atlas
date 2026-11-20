"""Opt-in, research-only extended-hours equity collector.

Registered in application lifespan behind an explicit process-environment flag.
No trading or notifications. Changing a file does not toggle an existing process.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import structlog

from app.investment.extended_hours_collector import (
    ExtendedHoursCollector,
    extended_session,
)
from app.investment.quality_dip_quotes import quality_dip_quote_service
from app.investment.storage import DATA_DIR
from app.investment.universe import load_universe

log = structlog.get_logger(__name__)

JOURNAL_PATH = DATA_DIR / "extended_hours_observations.jsonl"


def enabled_from_environment() -> bool:
    return os.getenv("ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


class ExtendedHoursResearchService:
    def __init__(
        self,
        *,
        collector=None,
        universe_loader=None,
        interval_seconds: float = 180.0,
    ) -> None:
        self.collector = collector or ExtendedHoursCollector(
            quality_dip_quote_service,
            JOURNAL_PATH,
        )
        self.universe_loader = universe_loader or load_universe
        self.interval_seconds = max(30.0, float(interval_seconds))
        self._task: asyncio.Task | None = None
        self._running = False
        self._activation_enabled = False
        self._stopping = False
        self.last_attempt_at: str | None = None
        self.last_completed_at: str | None = None
        self.last_commit_at: str | None = None
        self.last_error: str | None = None
        self.completed_cycles = 0
        self.failed_cycles = 0
        self.committed_observations = 0
        self.last_record_count = 0

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> bool:
        if self._task is not None and not self._task.done():
            return False

        if not enabled_from_environment():
            log.info("extended-hours research disabled")
            return False

        if hasattr(self.collector, "reopen"):
            self.collector.reopen()
        self._stopping = False
        self._running = True
        self._activation_enabled = True
        self._task = asyncio.create_task(
            self._loop(),
            name="extended_hours_research",
        )
        log.info("extended-hours research started")
        return True

    async def stop(self, timeout: float = 20.0) -> None:
        self._stopping = True
        self._running = False
        deadline = asyncio.get_running_loop().time() + max(0.0, timeout)
        if self._task is not None:
            self._task.cancel()
        try:
            if hasattr(self.collector, "shutdown"):
                await self.collector.shutdown(max(0.0, deadline - asyncio.get_running_loop().time()))
            if self._task is not None:
                _, pending = await asyncio.wait([self._task], timeout=max(
                    0.0, deadline - asyncio.get_running_loop().time()))
                if pending:
                    raise TimeoutError("Research task still owned; shutdown incomplete")
                if not self._task.cancelled():
                    self._task.result()
        except TimeoutError:
            self.last_error = "SHUTDOWN_DRAIN_TIMEOUT"
            raise
        self._task = None
        self._activation_enabled = False
        log.info("extended-hours research stopped")

    async def collect_once(self, now: datetime | None = None):
        if self._stopping:
            raise RuntimeError("Research service stopping")
        requested_now = now
        now = now or datetime.now(UTC)

        if extended_session(now) is None:
            return []

        universe = await asyncio.to_thread(self.universe_loader)
        if self._stopping:
            raise RuntimeError("Research service stopping")
        symbols = universe.symbols(active_only=True)

        if not symbols:
            return []

        # Production validates against time AFTER provider retrieval, not the
        # earlier cycle start. Explicit fixture clocks remain deterministic.
        return await self.collector.collect_once(symbols, now=requested_now)

    def status(self) -> dict:
        active = self._running and self._task is not None and not self._task.done()
        return {
            "contract_version": "R7E46M_V1",
            "pid": os.getpid(),
            "run_id": os.getenv("ATLAS_DESKTOP_RUN_ID"),
            "environment_enabled": enabled_from_environment(),
            "activation_enabled": self._activation_enabled,
            "running": bool(active),
            "task_active": bool(active),
            "stopping": self._stopping,
            "pending_collections": len(getattr(self.collector, "_collections", ())),
            "state": ("DRAIN_FAILED" if self.last_error == "SHUTDOWN_DRAIN_TIMEOUT"
                      else "DEGRADED" if active and self.last_error else "ACTIVE" if active
                      else "STOPPED" if enabled_from_environment() else "DISABLED"),
            "interval_seconds": self.interval_seconds,
            "journal_path": str(getattr(self.collector, "output_path", JOURNAL_PATH)),
            "last_attempt_at": self.last_attempt_at,
            "last_completed_at": self.last_completed_at,
            "last_commit_at": self.last_commit_at,
            "last_error": self.last_error,
            "completed_cycles": self.completed_cycles,
            "failed_cycles": self.failed_cycles,
            "last_record_count": self.last_record_count,
            "committed_observations": self.committed_observations,
            "research_only": True,
            "execution_authority": False,
            "automatic_discord_delivery": False,
            "read_only": True,
        }

    async def _loop(self) -> None:
        try:
            while self._running:
                try:
                    self.last_attempt_at = datetime.now(UTC).isoformat()
                    records = await self.collect_once()
                    self.last_completed_at = datetime.now(UTC).isoformat()
                    self.last_record_count = len(records)
                    self.completed_cycles += 1
                    self.committed_observations += len(records)
                    if records:
                        self.last_commit_at = self.last_completed_at
                    self.last_error = None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - research failure must not stop cash/PAPER services
                    self.failed_cycles += 1
                    self.last_record_count = 0
                    self.last_error = type(exc).__name__
                    log.warning(
                        "extended-hours research collection failed",
                        error=str(exc)[:200],
                    )

                await asyncio.sleep(self.interval_seconds)
        finally:
            self._running = False


extended_hours_research_service = ExtendedHoursResearchService()
