"""No network: controlled clocks and explicitly released owned workers."""

import asyncio
import threading
from itertools import pairwise
from urllib.error import HTTPError

import pytest
from app.investment import provider_dispatch as module
from app.investment.provider_dispatch import (
    ProviderDispatcher,
    ProviderDrainTimeout,
    ProviderRejected,
)
from app.investment.quality_dip_quotes import QualityDipQuoteService


class Clock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    async def sleep(self, seconds):
        self.value += seconds
        await asyncio.sleep(0)


class InlineThread:
    def __init__(self, *, target, **kwargs):
        self.target = target

    def start(self):
        self.target()

    def is_alive(self):
        return False


@pytest.mark.asyncio
async def test_fifo_pacing_no_burst_and_shared_throttle_cooldown(monkeypatch):
    monkeypatch.setattr(module, "Thread", InlineThread)
    clock = Clock()
    dispatch = ProviderDispatcher("fake", clock=clock.now, sleep=clock.sleep, jitter=lambda: 0.125)
    starts = []

    def call(index):
        starts.append((index, clock.now()))
        if index == 0:
            raise HTTPError("https://fixture.invalid", 429, "synthetic", {"Retry-After": "10"}, None)
        return index

    outcomes = await asyncio.gather(*(dispatch.run(call, i, timeout=2) for i in range(5)),
                                    return_exceptions=True)
    assert isinstance(outcomes[0], HTTPError)
    assert outcomes[1:] == [1, 2, 3, 4]
    assert [index for index, _ in starts] == list(range(5))
    assert all(right[1] - left[1] >= 0.199999 for left, right in pairwise(starts))
    # A request already started before a throttle response may complete; later
    # starts must honor the shared Retry-After cooldown, never retry index zero.
    assert max(stamp for _, stamp in starts) >= 10.125
    assert dispatch.metrics["throttled"] == 1
    assert dispatch.status()["automatic_retry_limit"] == 0
    await dispatch.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", ["deadline", "cancel"])
async def test_blocked_worker_retains_capacity_late_result_discarded(interrupt):
    entered, release = threading.Event(), threading.Event()
    dispatch = ProviderDispatcher("fake", concurrency=1, starts_per_second=1000, max_pending=1)

    def blocked():
        entered.set()
        assert release.wait(5), "fixture must always release its worker"
        return "late"

    task = asyncio.create_task(dispatch.run(blocked, timeout=0.05 if interrupt == "deadline" else 2))
    try:
        for _ in range(200):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        second = asyncio.create_task(dispatch.run(lambda: "queued", timeout=2))
        await asyncio.sleep(0)
        with pytest.raises(ProviderRejected):
            await dispatch.run(lambda: "overflow", timeout=2)
        if interrupt == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(TimeoutError):
                await task
        assert dispatch.status()["owned_workers"] == 1
        assert dispatch.status()["quarantined_workers"] == 1
        with pytest.raises(ProviderRejected):
            await dispatch.run(lambda: "quarantined", timeout=2)
        with pytest.raises(ProviderDrainTimeout):
            await dispatch.shutdown(0.01)
        with pytest.raises(ProviderRejected):
            await second
        with pytest.raises(ProviderRejected):
            await dispatch.run(lambda: "closed", timeout=2)
        assert dispatch.metrics["started"] == 1
    finally:
        release.set()
        await dispatch.shutdown(2)
    assert dispatch.status()["owned_workers"] == 0
    assert dispatch.status()["quarantined_workers"] == 0
    assert dispatch.metrics["late_results_discarded"] == 1


@pytest.mark.asyncio
async def test_queue_timeout_removes_work_without_starting_it():
    entered, release = threading.Event(), threading.Event()
    dispatch = ProviderDispatcher("fake", concurrency=1)

    def blocked():
        entered.set()
        assert release.wait(5)

    task = asyncio.create_task(dispatch.run(blocked, timeout=2))
    try:
        for _ in range(200):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        with pytest.raises(TimeoutError):
            await dispatch.run(lambda: pytest.fail("expired queued work started"), timeout=0.01)
        assert dispatch.status()["queued"] == 0
    finally:
        release.set()
        await task
        await dispatch.shutdown(2)


@pytest.mark.asyncio
async def test_quote_admission_is_bounded_and_closed_cache_is_not_served():
    service = QualityDipQuoteService()
    with pytest.raises(ProviderRejected):
        await service.get_many([f"TEST{i}" for i in range(65)])
    assert not service._inflight
    await service.shutdown()
    with pytest.raises(ProviderRejected):
        await service.get_many([])


@pytest.mark.parametrize("kwargs", [{"concurrency": 0}, {"starts_per_second": 0},
                                   {"starts_per_second": float("nan")}, {"max_pending": 0}])
def test_invalid_limits_fail_closed(kwargs):
    with pytest.raises(ValueError):
        ProviderDispatcher("fake", **kwargs)


@pytest.mark.asyncio
async def test_three_owned_workers_no_executor_backlog_and_fifo_drain():
    release = threading.Event()
    clock = Clock()
    dispatch = ProviderDispatcher("fake", clock=clock.now, sleep=clock.sleep)
    started = []

    def blocked(index):
        started.append(index)
        assert release.wait(10)
        return index

    tasks = [asyncio.create_task(dispatch.run(blocked, i, timeout=5)) for i in range(8)]
    try:
        for _ in range(200):
            if len(started) == 3:
                break
            await asyncio.sleep(0.001)
        assert set(started) == {0, 1, 2}, dispatch.status()
        assert dispatch.status()["owned_workers"] == 3
        assert dispatch.status()["queued"] == 5
        release.set()
        assert await asyncio.gather(*tasks) == list(range(8))
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await dispatch.shutdown(2)
    assert dispatch.metrics["peak_workers"] == 3
    assert set(started) == set(range(8))


@pytest.mark.asyncio
async def test_quote_diagnostics_create_no_work_and_legacy_clients_remain_opt_out(monkeypatch):
    from app.api.diagnostics import diagnostics_quote_dispatch
    from app.investment import quality_dip_quotes
    from app.investment.robinhood_equity_quotes import RobinhoodEquityQuoteClient
    from app.investment.yfinance_client import YFinanceClient

    service = QualityDipQuoteService()
    monkeypatch.setattr(quality_dip_quotes, "quality_dip_quote_service", service)
    before = service.provider_status()
    assert await diagnostics_quote_dispatch() == before
    assert service.provider_status() == before
    assert YFinanceClient().dispatcher is None
    assert RobinhoodEquityQuoteClient().dispatcher is None
    await service.shutdown()


@pytest.mark.asyncio
async def test_last_quote_waiter_cancellation_removes_pending_work():
    service = QualityDipQuoteService()
    entered = asyncio.Event()

    async def blocked(symbol):
        entered.set()
        await asyncio.Event().wait()

    service._fetch = blocked
    task = asyncio.create_task(service.get_many(["TEST"]))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    assert not service._inflight
    assert not service._waiters
    assert not service._cache
    await service.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_after", ["nan", "-1", "90000", "unsupported-date"])
async def test_unsupported_retry_after_closes_admission(monkeypatch, retry_after):
    monkeypatch.setattr(module, "Thread", InlineThread)
    dispatch = ProviderDispatcher("fake")

    def throttled():
        raise HTTPError("https://fixture.invalid", 429, "synthetic", {"Retry-After": retry_after}, None)

    with pytest.raises(HTTPError):
        await dispatch.run(throttled, timeout=1)
    with pytest.raises(ProviderRejected):
        await dispatch.run(lambda: None, timeout=1)
    assert dispatch.metrics["closed_invalid_retry_after"] == 1
    assert dispatch.closed
    await dispatch.shutdown()


@pytest.mark.asyncio
async def test_abnormal_worker_termination_is_failure_not_process_exit(monkeypatch):
    monkeypatch.setattr(module, "Thread", InlineThread)
    dispatch = ProviderDispatcher("fake")

    def terminated():
        raise SystemExit("synthetic worker termination")

    with pytest.raises(RuntimeError, match="terminated abnormally"):
        await dispatch.run(terminated, timeout=1)
    await dispatch.shutdown()
    assert dispatch.status()["owned_workers"] == 0
