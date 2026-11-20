"""Bounded teardown evidence, independent of logging and production controls."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class ShutdownReport:
    """A timeout retains task ownership; cancellation is never exit proof."""

    def __init__(self, timeout: float = 20.0, *, clock=None):
        self.clock = clock or asyncio.get_running_loop().time
        self.deadline = self.clock() + max(0.0, timeout)
        self.errors: list[tuple[str, BaseException]] = []
        self.tasks: dict[str, asyncio.Task] = {}
        self.completed: set[str] = set()
        self.timed_out = False
        self.unknown = False
        self.sealed = False

    def remaining(self) -> float:
        return max(0.0, self.deadline - self.clock())

    def record(self, name: str, error: BaseException) -> None:
        if not any(item is error for _, item in self.errors):
            self.errors.append((name, error))
        self.timed_out |= isinstance(error, TimeoutError)
        self.unknown |= isinstance(error, asyncio.CancelledError)

    @property
    def outcome(self) -> str:
        if self.timed_out:
            return "TIMED_OUT"
        if self.unknown or not self.sealed:
            return "UNKNOWN"
        return "INCOMPLETE" if self.errors else "COMPLETE"

    async def run(self, name: str, action: Callable[[], Awaitable[Any]]) -> Any:
        if name in self.completed:
            return None  # Do not repeat successful destructive cleanup.
        if self.sealed or name in self.tasks:
            error = RuntimeError("Cleanup already attempted or report sealed")
            self.record(name, error)
            raise error
        if not self.remaining():
            error = TimeoutError("Shared shutdown deadline exhausted")
            self.record(name, error)
            raise error
        try:
            task = asyncio.create_task(action(), name=f"atlas-cleanup-{name}")
            self.tasks[name] = task
            # Retrieve late failures without treating a late result as success.
            task.add_done_callback(lambda item: None if item.cancelled() else item.exception())
            _, pending = await asyncio.wait([task], timeout=self.remaining())
            if pending:
                # Keep the supervisor alive: canceling it might orphan its workers.
                raise TimeoutError("Cleanup remains owned after shutdown deadline")
            value = task.result()
            self.completed.add(name)
            return value
        except (Exception, asyncio.CancelledError) as error:
            self.record(name, error)
            raise

    def emit(self, logger, level: str, message: str, **fields) -> None:
        try:
            getattr(logger, level)(message, **fields)
        except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001 - preserve reporting failure
            self.unknown = True
            self.record("logging", error)

    def finish(self, logger) -> None:
        if not self.sealed:
            if not self.completed:
                self.unknown = True
            if not self.remaining():
                self.record("deadline", TimeoutError("Shared shutdown deadline exhausted"))
            if any(not task.done() for task in self.tasks.values()):
                self.unknown = True
            self.sealed = True
            message = ("Project Atlas shutdown complete" if self.outcome == "COMPLETE"
                       else "Project Atlas shutdown incomplete; operator recovery required")
            self.emit(logger, "info" if self.outcome == "COMPLETE" else "error",
                      message, outcome=self.outcome,
                      failed_steps=[name for name, _ in self.errors])
        if self.errors or self.outcome != "COMPLETE":
            errors = [error for _, error in self.errors] or [RuntimeError("Shutdown evidence unknown")]
            raise BaseExceptionGroup(f"Atlas shutdown {self.outcome}", errors)
