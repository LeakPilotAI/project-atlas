import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.investment.extended_hours_collector import (
    ExtendedHoursCollector,
    extended_session,
    validated_observation,
)

ET = ZoneInfo("America/New_York")


class FakeQuotes:
    def __init__(self, quotes):
        self.quotes = quotes

    async def get_many(self, symbols):
        return {s: self.quotes[s] for s in symbols if s in self.quotes}


def moment(hour, minute=0):
    return datetime(2026, 10, 16, hour, minute, tzinfo=ET)


def quote(ts, price=250.0, quality="LIVE"):
    return {
        "price": price,
        "effective_timestamp": ts.astimezone(timezone.utc).isoformat(),
        "quality": quality,
        "source": "fake_robinhood",
    }


def test_extended_session_boundaries():
    assert extended_session(moment(4)) == "PRE_MARKET"
    assert extended_session(moment(9, 29)) == "PRE_MARKET"
    assert extended_session(moment(9, 30)) is None
    assert extended_session(moment(16)) == "POST_MARKET"
    assert extended_session(moment(19, 59)) == "POST_MARKET"
    assert extended_session(moment(20)) is None


def test_rejects_stale_and_wrong_session():
    now = moment(8)
    assert validated_observation("MSFT", quote(moment(7, 59)), now)
    assert validated_observation("MSFT", quote(moment(7, 30)), now) is None
    assert validated_observation("MSFT", quote(moment(16)), now) is None


def test_collects_and_deduplicates(tmp_path):
    now = moment(8)
    service = FakeQuotes({"MSFT": quote(moment(7, 59))})
    path = tmp_path / "extended_hours.jsonl"
    collector = ExtendedHoursCollector(service, path)

    first = asyncio.run(collector.collect_once(["MSFT"], now=now))
    second = asyncio.run(collector.collect_once(["MSFT"], now=now))

    assert len(first) == 1
    assert second == []
    assert len(path.read_text().splitlines()) == 1


def test_no_collection_during_regular_hours(tmp_path):
    path = tmp_path / "extended_hours.jsonl"
    collector = ExtendedHoursCollector(FakeQuotes({}), path)

    assert asyncio.run(
        collector.collect_once(["MSFT"], now=moment(10))
    ) == []
    assert not path.exists()

def test_exchange_holiday_is_closed():
    from datetime import datetime
    assert extended_session(datetime(2026, 12, 25, 8, tzinfo=ET)) is None


def test_early_close_postmarket_begins_at_one_pm():
    from datetime import datetime
    day = datetime(2026, 11, 27, 13, 0, tzinfo=ET)
    assert extended_session(day) == "POST_MARKET"


def test_unsupported_calendar_year_fails_closed():
    from datetime import datetime
    assert extended_session(datetime(2029, 10, 16, 8, tzinfo=ET)) is None