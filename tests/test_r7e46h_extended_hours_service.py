"""R7E46H disabled-by-default research service acceptance."""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.investment.universe import InvestmentUniverse, UniverseEntry
from app.services.extended_hours_research import ExtendedHoursResearchService

ET = ZoneInfo("America/New_York")
PREMARKET = datetime(2026, 10, 16, 8, 0, tzinfo=ET)
CLOSED = datetime(2026, 10, 17, 8, 0, tzinfo=ET)


class FakeCollector:
    def __init__(self):
        self.calls = []

    async def collect_once(self, symbols, now=None):
        self.calls.append((list(symbols), now))
        return [{"symbol": symbol} for symbol in symbols]


def make_service(collector, entries=None):
    entries = entries if entries is not None else [
        UniverseEntry("MSFT", active=True),
        UniverseEntry("NVDA", active=False),
    ]
    return ExtendedHoursResearchService(
        collector=collector,
        universe_loader=lambda: InvestmentUniverse(entries),
        interval_seconds=30,
    )


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED", raising=False)
    service = make_service(FakeCollector())

    async def scenario():
        assert await service.start() is False
        assert service.running is False
        assert service._task is None
        await service.stop()

    asyncio.run(scenario())


def test_explicit_enable_and_graceful_stop(monkeypatch):
    monkeypatch.setenv("ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED", "true")
    service = make_service(FakeCollector())

    async def scenario():
        assert await service.start() is True
        assert service.running is True
        assert await service.start() is False
        await asyncio.sleep(0)
        await service.stop()
        assert service.running is False
        assert service._task is None

    asyncio.run(scenario())


def test_active_universe_only():
    collector = FakeCollector()
    service = make_service(collector)

    result = asyncio.run(service.collect_once(now=PREMARKET))

    assert result == [{"symbol": "MSFT"}]
    assert collector.calls == [(["MSFT"], PREMARKET)]


def test_closed_session_skips_universe_and_collector():
    collector = FakeCollector()
    calls = []

    def loader():
        calls.append("loaded")
        return InvestmentUniverse([UniverseEntry("MSFT")])

    service = ExtendedHoursResearchService(
        collector=collector,
        universe_loader=loader,
    )

    assert asyncio.run(service.collect_once(now=CLOSED)) == []
    assert calls == []
    assert collector.calls == []


def test_empty_active_universe_skips_collector():
    collector = FakeCollector()
    service = make_service(
        collector,
        entries=[UniverseEntry("NVDA", active=False)],
    )

    assert asyncio.run(service.collect_once(now=PREMARKET)) == []
    assert collector.calls == []