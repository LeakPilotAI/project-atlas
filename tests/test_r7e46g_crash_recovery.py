"""R7E46G crash-interrupted history safety tests."""

import asyncio
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.investment.extended_hours_collector import ExtendedHoursCollector

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


def collect(path):
    collector = ExtendedHoursCollector(Quotes(), path)
    return asyncio.run(collector.collect_once(["MSFT"], now=NOW))


def test_valid_journal_survives_restart(tmp_path):
    path = tmp_path / "history.jsonl"

    assert len(collect(path)) == 1
    original = path.read_bytes()

    assert collect(path) == []
    assert path.read_bytes() == original


def test_truncated_final_record_is_preserved(tmp_path):
    path = tmp_path / "history.jsonl"

    assert len(collect(path)) == 1
    valid = path.read_bytes()

    with path.open("ab") as stream:
        stream.write(b'{"symbol":"NVDA","effective_timestamp":')

    damaged = path.read_bytes()

    with pytest.raises((ValueError, RuntimeError)):
        collect(path)

    assert path.read_bytes() == damaged
    assert path.read_bytes().startswith(valid)


def test_corrupted_middle_record_blocks_append(tmp_path):
    path = tmp_path / "history.jsonl"

    assert len(collect(path)) == 1

    with path.open("ab") as stream:
        stream.write(b'{"bad":\n')

    damaged = path.read_bytes()

    with pytest.raises((ValueError, RuntimeError)):
        collect(path)

    assert path.read_bytes() == damaged


def test_corrupted_history_does_not_create_replacement(tmp_path):
    path = tmp_path / "history.jsonl"

    path.write_bytes(b'{"symbol":')

    original = path.read_bytes()

    with pytest.raises((ValueError, RuntimeError)):
        collect(path)

    assert path.read_bytes() == original
    assert not path.with_suffix(".jsonl.recovered").exists()