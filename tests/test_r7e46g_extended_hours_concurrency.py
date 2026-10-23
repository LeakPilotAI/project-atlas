"""R7E46G concurrency and partial-write safety tests."""

import asyncio
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.investment.extended_hours_collector import ExtendedHoursCollector

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 16, 8, 0, tzinfo=ET)
QUOTE_TS = datetime(2026, 10, 16, 7, 59, tzinfo=ET)


class CoordinatedQuotes:
    def __init__(self):
        self.calls = 0
        self.ready = asyncio.Event()

    async def get_many(self, symbols):
        self.calls += 1
        if self.calls == 2:
            self.ready.set()
        await self.ready.wait()

        return {
            symbol: {
                "price": 250.0,
                "effective_timestamp": QUOTE_TS.astimezone(
                    timezone.utc
                ).isoformat(),
                "quality": "LIVE",
                "source": "fake",
            }
            for symbol in symbols
        }


def test_two_collectors_do_not_duplicate_same_quote(tmp_path):
    path = tmp_path / "history.jsonl"
    service = CoordinatedQuotes()

    async def exercise():
        first = ExtendedHoursCollector(service, path)
        second = ExtendedHoursCollector(service, path)
        return await asyncio.gather(
            first.collect_once(["MSFT"], now=NOW),
            second.collect_once(["MSFT"], now=NOW),
        )

    results = asyncio.run(exercise())
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]

    assert sum(len(batch) for batch in results) == 1
    assert len(records) == 1


def test_partial_history_record_fails_closed(tmp_path):
    path = tmp_path / "history.jsonl"
    path.write_text(
        '{"symbol":"MSFT","effective_timestamp":"2026-10-16T11:59:',
        encoding="utf-8",
    )

    collector = ExtendedHoursCollector(CoordinatedQuotes(), path)

    async def exercise():
        return await collector.collect_once(["MSFT"], now=NOW)

    # No network wait: use a single-call quote service for this test.
    class ImmediateQuotes:
        async def get_many(self, symbols):
            return {
                symbol: {
                    "price": 250.0,
                    "effective_timestamp": QUOTE_TS.astimezone(
                        timezone.utc
                    ).isoformat(),
                    "quality": "LIVE",
                    "source": "fake",
                }
                for symbol in symbols
            }

    collector.quote_service = ImmediateQuotes()

    original = path.read_bytes()

    with pytest.raises((ValueError, RuntimeError)):
        asyncio.run(exercise())

    assert path.read_bytes() == original