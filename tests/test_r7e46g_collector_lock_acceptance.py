"""R7E46G real collector lock acceptance tests."""

import asyncio
import json
import multiprocessing
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.investment.extended_hours_collector import (
    ExtendedHoursCollector,
    _exclusive_history_lock,
)

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-only collector locking",
)

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 16, 8, 0, tzinfo=ET)
TS = datetime(2026, 10, 16, 7, 59, tzinfo=ET)


class Quotes:
    async def get_many(self, symbols):
        return {
            symbol: {
                "price": 250.0,
                "effective_timestamp": TS.astimezone(
                    timezone.utc
                ).isoformat(),
                "quality": "LIVE",
                "source": "fake",
            }
            for symbol in symbols
        }


def worker(path, queue, start):
    try:
        if not start.wait(timeout=10):
            queue.put(("error", "start timeout"))
            return

        collector = ExtendedHoursCollector(Quotes(), path)
        result = asyncio.run(
            collector.collect_once(["MSFT"], now=NOW)
        )
        queue.put(("ok", len(result)))
    except Exception as exc:
        queue.put(("error", repr(exc)))


def test_independent_processes_deduplicate(tmp_path):
    path = tmp_path / "history.jsonl"
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    start = context.Event()

    processes = [
        context.Process(target=worker, args=(path, queue, start))
        for _ in range(2)
    ]

    for process in processes:
        process.start()

    try:
        start.set()
        results = [queue.get(timeout=12) for _ in processes]

        for process in processes:
            process.join(timeout=5)
            assert process.exitcode == 0

        assert sorted(results) == [("ok", 0), ("ok", 1)]

        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]
        assert len(records) == 1
    finally:
        for process in processes:
            if process.is_alive():
                process.join(timeout=3)
            if process.is_alive():
                pytest.fail("Worker remained alive; preserve for diagnosis.")


def test_collector_lock_timeout_fails_closed(tmp_path):
    path = tmp_path / "history.jsonl"

    with _exclusive_history_lock(path):
        collector = ExtendedHoursCollector(Quotes(), path)

        with pytest.raises(TimeoutError):
            asyncio.run(
                collector.collect_once(["MSFT"], now=NOW)
            )

    assert not path.exists()