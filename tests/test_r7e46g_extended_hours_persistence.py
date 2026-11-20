"""R7E46G persistence safety regression tests."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from app.investment.extended_hours_collector import ExtendedHoursCollector
from app.investment.extended_hours_integrity import JournalIntegrityError

ET = ZoneInfo("America/New_York")


class FakeQuotes:
    async def get_many(self, symbols):
        timestamp = datetime(
            2026, 10, 16, 7, 59, tzinfo=ET
        ).astimezone(timezone.utc).isoformat()

        return {
            symbol: {
                "price": 250.0,
                "effective_timestamp": timestamp,
                "quality": "LIVE",
                "source": "fake",
            }
            for symbol in symbols
        }


NOW = datetime(2026, 10, 16, 8, 0, tzinfo=ET)


def run(collector):
    return asyncio.run(collector.collect_once(["MSFT"], now=NOW))


def test_deduplication_survives_collector_restart(tmp_path):
    path = tmp_path / "history.jsonl"

    assert len(run(ExtendedHoursCollector(FakeQuotes(), path))) == 1
    assert run(ExtendedHoursCollector(FakeQuotes(), path)) == []

    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1


def test_write_failure_quarantines_intent_without_poisoning_seen_state(tmp_path, monkeypatch):
    path = tmp_path / "history.jsonl"
    collector = ExtendedHoursCollector(FakeQuotes(), path)

    original_open = Path.open
    calls = {"count": 0}

    def flaky_open(self, *args, **kwargs):
        if self == path and calls["count"] == 0:
            calls["count"] += 1
            raise OSError("simulated disk failure")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", flaky_open)

    with pytest.raises(OSError):
        run(collector)

    assert collector._seen == set()
    # A durable pre-append intent is deliberately not retried automatically.
    with pytest.raises(JournalIntegrityError):
        run(collector)
    assert not path.exists()


def test_malformed_existing_history_fails_closed(tmp_path):
    path = tmp_path / "history.jsonl"
    path.write_text('{"symbol": "MSFT"\n', encoding="utf-8")

    collector = ExtendedHoursCollector(FakeQuotes(), path)

    with pytest.raises((ValueError, RuntimeError)):
        run(collector)

    assert path.read_text(encoding="utf-8") == '{"symbol": "MSFT"\n'
