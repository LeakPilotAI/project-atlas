"""Bounded, FIFO, event-loop-local dispatch for quote-provider blocking calls.

Limits are internal ceilings, not a statement of provider entitlement. No retries:
timeouts and throttles must not multiply traffic. A timed-out worker retains its
slot until it actually exits. Python threads cannot safely be forcibly stopped.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from collections import Counter, deque
from concurrent.futures import Future
from dataclasses import dataclass
from threading import Thread
from typing import Any


class ProviderRejected(RuntimeError):
    """Work was rejected before a provider call was started."""


class ProviderDrainTimeout(TimeoutError):
    """Owned provider work remains; shutdown is NOT confirmed."""


@dataclass
class _Job:
    function: Any
    args: tuple
    kwargs: dict
    result: asyncio.Future
    abandoned: bool = False
    started: bool = False
    quarantined: bool = False


class ProviderDispatcher:
    def __init__(self, name: str, *, concurrency: int = 3,
                 starts_per_second: float = 5.0, max_pending: int = 64,
                 clock=time.monotonic, sleep=asyncio.sleep,
                 jitter=lambda: random.uniform(0.0, 0.25)) -> None:
        if (type(concurrency) is not int or concurrency < 1
                or not math.isfinite(starts_per_second) or starts_per_second <= 0
                or type(max_pending) is not int or max_pending < 1):
            raise ValueError("Provider limits must be positive")
        self.name = name
        self.concurrency = concurrency
        self.interval = 1.0 / starts_per_second
        self.max_pending = max_pending
        self.clock, self.sleep = clock, sleep
        self.jitter = jitter
        self.closed = False
        self._quarantined = 0
        self.metrics = Counter()
        self._queue: deque[_Job] = deque()
        self._active: set[asyncio.Task] = set()
        self._workers: dict[Future, Thread] = {}
        self._dispatcher: asyncio.Task | None = None
        self._next_start = 0.0

    def status(self) -> dict:
        return {"provider": self.name, "closed": self.closed,
                "quarantined_workers": self._quarantined,
                "concurrency_limit": self.concurrency,
                "starts_per_second_limit": 1.0 / self.interval,
                "pending_limit": self.max_pending,
                "automatic_retry_limit": 0,
                "queued": len(self._queue),
                "owned_workers": sum(thread.is_alive() for thread in self._workers.values()),
                "active_operations": len(self._active), **dict(self.metrics)}

    async def run(self, function, *args, timeout: float, **kwargs):
        if self.closed or self._quarantined or len(self._queue) >= self.max_pending:
            reason = "closed" if self.closed else "quarantine" if self._quarantined else "capacity"
            self.metrics[f"rejected_{reason}"] += 1
            raise ProviderRejected(f"Provider rejected: {reason}")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Provider deadline must be positive")
        job = _Job(function, args, kwargs, asyncio.get_running_loop().create_future())
        # Consume errors even when a caller has already abandoned its result.
        job.result.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        self._queue.append(job)
        self.metrics["accepted"] += 1
        self._kick()
        try:
            return await asyncio.wait_for(asyncio.shield(job.result), timeout)
        except (TimeoutError, asyncio.CancelledError) as exc:
            job.abandoned = True
            self.metrics["cancelled" if isinstance(exc, asyncio.CancelledError) else "deadline_exceeded"] += 1
            # Remove queued work immediately; started work remains owned.
            if job in self._queue:
                self._queue.remove(job)
            if job.started and not job.result.done():
                job.quarantined = True
                self._quarantined += 1
                self.metrics["worker_quarantines"] += 1
                self._reject_queued("Provider worker abandoned; no automatic replay")
            raise

    def _reject_queued(self, message):
        while self._queue:
            job = self._queue.popleft()
            job.abandoned = True
            job.result.set_exception(ProviderRejected(message))
            self.metrics["rejected_shutdown" if self.closed else "rejected_quarantine"] += 1

    def _kick(self):
        if not self.closed and not self._quarantined and (self._dispatcher is None or self._dispatcher.done()):
            self._dispatcher = asyncio.create_task(self._dispatch())

    async def _dispatch(self):
        while self._queue and not self.closed and not self._quarantined and len(self._active) < self.concurrency:
            delay = self._next_start - self.clock()
            if delay > 0:
                self.metrics["paced_waits"] += 1
                await self.sleep(delay)
                continue
            job = self._queue.popleft()
            if job.abandoned:
                continue
            self._next_start = self.clock() + self.interval
            task = asyncio.create_task(self._execute(job))
            self._active.add(task)
            task.add_done_callback(self._finished)
            # Let the worker actually start before measuring the next interval.
            await asyncio.sleep(0)

    def _finished(self, task):
        self._active.discard(task)
        if not task.cancelled():
            task.exception()
        self._kick()

    async def _execute(self, job):
        if job.abandoned:
            return
        job.started = True
        worker = Future()

        def invoke():
            try:
                worker.set_result(job.function(*job.args, **job.kwargs))
            except BaseException as exc:  # noqa: BLE001 - marshal every worker termination to its owned future
                worker.set_exception(exc if isinstance(exc, Exception)
                                     else RuntimeError("Provider worker terminated abnormally"))

        # Non-daemon ownership: a failed drain must not permit a successful
        # process exit while an owned provider could still write health evidence.
        thread = Thread(target=invoke, name=f"atlas-quote-{self.name}", daemon=False)
        self._workers[worker] = thread
        try:
            try:
                thread.start()
            except RuntimeError as exc:
                worker.set_exception(exc)
            self.metrics["started"] += 1
            self._next_start = self.clock() + self.interval
            self.metrics["peak_workers"] = max(self.metrics["peak_workers"],
                                               sum(item.is_alive() for item in self._workers.values()))
            value = await asyncio.shield(asyncio.wrap_future(worker))
            while thread.is_alive():
                await asyncio.sleep(0.001)
            if not job.abandoned:
                job.result.set_result(value)
            else:
                self.metrics["late_results_discarded"] += 1
        except Exception as exc:  # noqa: BLE001 - provider failure boundary; retain slot and expose failure
            self.metrics["provider_errors"] += 1
            code = getattr(exc, "code", None)
            failure_code = getattr(getattr(exc, "failure", None), "code", None)
            if code in {429, 503} or failure_code == "RATE_LIMIT":
                self.metrics["throttled"] += 1
                # No retry of this job. Subsequent accepted jobs honor a shared
                # cooldown; unsupported Retry-After closes admission for review.
                headers = getattr(exc, "headers", None)
                try:
                    wait = float(headers.get("Retry-After", 5.0)) if headers else 5.0
                    if not math.isfinite(wait) or wait < 0 or wait > 86400:
                        raise ValueError("Unsupported Retry-After")
                except (TypeError, ValueError):
                    # Never shorten an unsupported provider instruction.
                    self.closed = True
                    self.metrics["closed_invalid_retry_after"] += 1
                    self._reject_queued("Provider Retry-After requires operator review")
                else:
                    self._next_start = max(self._next_start,
                                           self.clock() + max(5.0, wait) + self.jitter())
            if not job.abandoned:
                job.result.set_exception(exc)
        finally:
            if worker.done():
                while thread.is_alive():
                    await asyncio.sleep(0.001)
            # A loop-level interruption must not pretend a live thread exited.
            if worker.done() and not thread.is_alive():
                self._workers.pop(worker, None)
                self.metrics["completed"] += 1
                if job.quarantined:
                    self._quarantined -= 1

    async def shutdown(self, timeout: float = 20.0):
        self.closed = True
        self._reject_queued("Provider shutdown")
        if self._dispatcher is not None and not self._dispatcher.done():
            self._dispatcher.cancel()
            await asyncio.gather(self._dispatcher, return_exceptions=True)
        if self._active:
            _, pending = await asyncio.wait(self._active, timeout=max(0.0, timeout))
            if pending or any(thread.is_alive() for thread in self._workers.values()):
                self.metrics["drain_failures"] += 1
                raise ProviderDrainTimeout("Provider workers remain owned; shutdown incomplete")
        if any(thread.is_alive() for thread in self._workers.values()):
            raise ProviderDrainTimeout("Provider worker survived loop interruption")
        self.metrics["drained"] += 1
