import asyncio
import time
from app.services.runtime_snapshot import RuntimeSnapshot


def test_single_flight_and_immediate_stale_then_fresh():
    async def scenario():
        cache = RuntimeSnapshot(ttl=0)
        gate = asyncio.Event()
        calls = 0
        async def build():
            nonlocal calls
            calls += 1
            await gate.wait()
            return {'value': calls}
        results = await asyncio.gather(*(cache.get(build, {}, budget=.01) for _ in range(20)))
        assert calls == 1
        assert all(r['runtime_refresh']['state'] == 'WARMING' for r in results)
        gate.set()
        await cache.task
        gate.clear()
        started = time.monotonic()
        stale = await cache.get(build, {})
        assert time.monotonic() - started < .05
        assert stale['value'] == 1
        assert stale['runtime_refresh']['state'] == 'STALE'
        gate.set()
        await cache.task
        assert calls == 2
    asyncio.run(scenario())


def test_refresh_failure_preserves_last_good_and_retries_at_bounded_cadence():
    async def scenario():
        cache = RuntimeSnapshot(ttl=60)
        async def good(): return {'value': 42}
        await cache.get(good, {})
        cache.updated = 0
        cache.last_attempt = 0
        async def bad(): raise ValueError('no credentials in diagnostics')
        result = await cache.get(bad, {})
        assert result['value'] == 42
        await cache.task
        result = await cache.get(bad, {})
        assert result['value'] == 42
        assert result['runtime_refresh']['error'] == 'ValueError'
        assert cache.task is None
    asyncio.run(scenario())
