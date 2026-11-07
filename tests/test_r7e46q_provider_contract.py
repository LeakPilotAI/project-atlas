"""Isolated shared quote work and cancellation contracts."""
import asyncio
from datetime import UTC, datetime

import pytest
from app.investment.quality_dip_quotes import QualityDipQuoteService


@pytest.mark.asyncio
async def test_cancel_one_waiter_preserves_shared_fetch_and_returns_copies():
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    class RH:
        async def get_quote(self, symbol):
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            return {"price": 250, "effective_timestamp": datetime.now(UTC).isoformat()}

    service = QualityDipQuoteService(robinhood_client=RH())
    first = asyncio.create_task(service.get_many(["TEST"]))
    try:
        await asyncio.wait_for(entered.wait(), 2)
    except TimeoutError:
        release.set()
        await first
        raise
    second = asyncio.create_task(service.get_many(["TEST"]))
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    release.set()
    result = await second
    assert calls == 1
    assert not service._inflight
    result["TEST"]["price"] = 1
    assert (await service.get_many(["TEST"]))["TEST"]["price"] == 250


@pytest.mark.asyncio
async def test_failed_fetch_is_removed_and_can_be_retried():
    service = QualityDipQuoteService()
    calls = 0

    async def fetch(symbol):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        if calls == 1:
            raise ValueError("synthetic failure")
        return {"price": 250}

    service._fetch = fetch
    results = await asyncio.gather(service.get_many(["TEST"]), service.get_many(["TEST"]), return_exceptions=True)
    assert all(isinstance(result, ValueError) for result in results)
    assert calls == 1
    assert not service._inflight
    assert (await service.get_many(["TEST"]))["TEST"]["price"] == 250
    assert calls == 2


@pytest.mark.asyncio
async def test_disjoint_consumers_share_six_slots():
    service = QualityDipQuoteService()
    entered, release = asyncio.Event(), asyncio.Event()
    active = peak = calls = 0

    async def fetch(symbol):
        nonlocal active, peak, calls
        active += 1
        calls += 1
        peak = max(peak, active)
        if active == 6:
            entered.set()
        try:
            await release.wait()
            await asyncio.sleep(0)
            return {"price": 250}
        finally:
            active -= 1

    service._fetch = fetch
    tasks = [asyncio.create_task(service.get_many([f"T{i}_{j}" for j in range(12)])) for i in range(3)]
    try:
        await asyncio.wait_for(entered.wait(), 2)
        await asyncio.sleep(0)
        assert peak == 6
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert calls == 36
    assert peak == 6
    assert active == 0
    assert not service._inflight
