"""Mocked provider capacity evidence. No live requests or runtime lifecycle."""
import asyncio
import json
import threading
import time
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from app.investment import quality_dip_quotes as quotes_module
from app.investment import robinhood_equity_quotes as rh_module
from app.investment.quality_dip_quotes import QualityDipQuoteService
from app.investment.yfinance_client import ProviderCallError, YFinanceClient

SYMBOLS = [f"TEST{i:02}" for i in range(37)]

class NoYahoo:
    def __init__(self):
        self.calls = 0
    async def history(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Unexpected Yahoo fallback")
    async def info(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Unexpected Yahoo fallback")

@pytest.mark.asyncio
@pytest.mark.parametrize("consumers", [1, 2, 3])
async def test_shared_limit_and_coalescing_and_warm_cache_avoid_calls(consumers, tmp_path):
    entered = asyncio.Event()
    release = asyncio.Event()
    counts = Counter()
    active = peak = 0
    class RH:
        async def get_quote(self, symbol):
            nonlocal active, peak
            counts["rh"] += 1
            active += 1
            peak = max(peak, active)
            if active == 6:
                entered.set()
            try:
                await release.wait()
                await asyncio.sleep(0)
                return {"price":250,"effective_timestamp":datetime.now(UTC).isoformat()}
            finally:
                active -= 1
    service = QualityDipQuoteService(client=NoYahoo(), robinhood_client=RH())
    started = time.perf_counter()
    tasks = [asyncio.create_task(service.get_many(SYMBOLS)) for _ in range(consumers)]
    try:
        await asyncio.wait_for(entered.wait(), 3)
    finally:
        release.set()
    results = await asyncio.gather(*tasks)
    assert peak == 6
    assert counts["rh"] == 37
    assert all(len(result) == 37 for result in results)
    assert active == 0
    assert service.client.calls == 0
    before = counts["rh"]
    await service.get_many(SYMBOLS)
    assert counts["rh"] == before
    (tmp_path / "capacity.json").write_text(json.dumps({
        "mocked":True,"consumers":consumers,"symbols":37,"peak":peak,
        "rh_operations":before,"warm_cache_operations":0,
        "wall_seconds_not_provider_latency":time.perf_counter()-started,
    }))

@pytest.mark.asyncio
async def test_cold_failure_sweep_has_four_logical_operations_per_symbol(monkeypatch, tmp_path):
    counts = Counter()
    lock = threading.Lock()
    def no_network(url, timeout):
        with lock:
            counts["rh_endpoint"] += 1
        return {}
    class Yahoo:
        async def history(self, *args, **kwargs):
            counts["history"] += 1
        async def info(self, *args, **kwargs):
            counts["info"] += 1
            return {}
    monkeypatch.setattr(rh_module, "_get_json", no_network)
    service = QualityDipQuoteService(client=Yahoo(), robinhood_client=rh_module.RobinhoodEquityQuoteClient())
    result = await service.get_many(SYMBOLS)
    assert counts == {"rh_endpoint":74,"history":37,"info":37}
    assert all(row["quality"] == "MISSING" and row["price"] is None for row in result.values())
    (tmp_path / "operations.json").write_text(json.dumps(dict(counts)))

@pytest.mark.asyncio
async def test_cache_expiry_fetches_again_without_immediate_retry():
    calls = 0
    class RH:
        async def get_quote(self, symbol):
            nonlocal calls
            calls += 1
            return {"price":250,"effective_timestamp":datetime.now(UTC).isoformat()}
    service = QualityDipQuoteService(client=NoYahoo(), robinhood_client=RH())
    await service.get_many(SYMBOLS + SYMBOLS)
    assert calls == 37
    await service.get_many(SYMBOLS)
    assert calls == 37
    service._cache = {key:(stamp-quotes_module.CACHE_TTL_SEC-1, row) for key,(stamp,row) in service._cache.items()}
    await service.get_many(SYMBOLS)
    assert calls == 74
    assert service.client.calls == 0

@pytest.mark.asyncio
async def test_stale_rh_remains_reference_without_yahoo_fallback():
    calls = 0
    class RH:
        async def get_quote(self, symbol):
            nonlocal calls
            calls += 1
            return {"price":250,"effective_timestamp":(datetime.now(UTC)-timedelta(seconds=901)).isoformat()}
    service = QualityDipQuoteService(client=NoYahoo(), robinhood_client=RH())
    result = await service.get_many(SYMBOLS)
    assert service.client.calls == 0
    assert calls == 37
    assert all(row["quality"] == "REFERENCE" and not row["tradable_for_ladder"] for row in result.values())

@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["timeout", "cancel"])
async def test_async_deadline_does_not_stop_provider_thread(monkeypatch, interruption):
    from app.investment import provider_health
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    events = []
    client = YFinanceClient(timeout_sec=0.05)
    def blocked(symbol):
        entered.set()
        try:
            assert release.wait(5), "Fixture worker must be drained"
            return {"regularMarketPrice":250}
        finally:
            finished.set()
    monkeypatch.setattr(client,"fetch_info",blocked)
    monkeypatch.setattr(provider_health,"record_provider_event",lambda *a,**kw: events.append((a,kw)))
    task = asyncio.create_task(client.info("TEST"))
    try:
        for _ in range(100):
            if entered.is_set(): break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        if interruption == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
        else:
            with pytest.raises(ProviderCallError) as error: await task
            assert error.value.failure.code == "TIMEOUT"
        assert not finished.is_set()
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 3)
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
