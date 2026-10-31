import asyncio
import time

from app.services.runtime_watchdog import RuntimeWatchdog


def test_watchdog_captures_blocked_loop_without_locals_and_stops():
    monitor = RuntimeWatchdog()

    async def run():
        await monitor.start()
        time.sleep(1.3)  # deliberately block only this test's event loop
        await monitor.stop()

    asyncio.run(run())
    rows = monitor.snapshot()
    assert rows and rows[0]["lag_ms"] >= 1000
    assert any(frame["function"] == "run" for frame in rows[0]["stack"])
    assert all(set(frame) == {"file", "line", "function"} for frame in rows[0]["stack"])
    assert monitor._stop.is_set()
    assert monitor.samples.maxlen == 8
    assert monitor.metrics()["stall_samples"] >= 1
    assert monitor.thread_samples.maxlen == 60
    assert monitor.metrics()["tasks"] > 0
