"""R16 research IEX quotes never become accepted manual ladder triggers.

All feed frames and clocks are synthetic. Test is fully offline and does not
create native accounts, access credentials, or authorize financial PAPER.
"""
import json
from datetime import UTC, datetime, timedelta

import pytest
from app.investment.accumulation_ladder import AccumulationLadderStore
from app.investment.alpaca_iex import IEXFeed
from app.investment.quality_dip_quotes import (
    QualityDipQuoteService,
    apply_quote_overlay,
)

STAMP = int(datetime(2026, 10, 26, 14, tzinfo=UTC).timestamp())


def synthetic_live_iex():
    feed = IEXFeed(["MSFT"], clock=lambda: STAMP + 0.5)
    feed.receive('[{"T":"success","msg":"authenticated"}]')
    feed.receive('[{"T":"subscription","quotes":["MSFT"]}]')
    feed.receive(json.dumps([{
        "T": "q", "S": "MSFT", "bp": 99.9, "ap": 100.1, "bs": 2, "as": 3,
        "bx": "V", "ax": "V", "c": ["R"], "z": "C",
        "t": "2026-10-26T14:00:00.123456789Z",
    }]))
    assert feed.snapshot()["quotes"][0]["state"] == "FRESH"
    return feed


def board_row(price=100.0, trigger=100.1, source="robinhood_underlying_bid_ask"):
    return {
        "symbol": "MSFT", "stance": "ACCUMULATE",
        "quote_price": price,
        "quote_display_price": price,
        "quote_trigger_price": trigger,
        "quote_quality": "LIVE",
        "quote_session": "REGULAR",
        "quote_source": source,
        "quote_effective_timestamp": "2026-10-26T14:00:00Z",
    }


def test_connected_fresh_regular_iex_research_is_still_not_alert_authority():
    feed = synthetic_live_iex()
    snap = feed.research_snapshot("MSFT")
    assert snap["session"] == "REGULAR"
    assert snap["quality"] == "LIVE"
    assert snap["price"] == 100.1
    assert snap["display_price"] == 100.1
    assert snap["fresh_for_display"] is True
    assert snap["tradable_for_ladder"] is False
    assert snap["trigger_price"] is None
    assert snap["source"] == "ALPACA_IEX_SINGLE_EXCHANGE_NOT_NBBO"
    assert not feed.snapshot()["paper_startup_authorized"]


@pytest.mark.asyncio
async def test_iex_fresh_quote_cache_to_overlay_to_manual_ladder_never_arms(tmp_path):
    feed = synthetic_live_iex()
    service = QualityDipQuoteService(alpaca_feed=feed)
    snap = (await service.get_many(["MSFT"]))["MSFT"]
    research = [{"symbol": "MSFT", "price": 100.0,
                 "stance": "ACCUMULATE", "drawdown": {}}]
    row = apply_quote_overlay(research, {"MSFT": snap})[0]
    assert row["current_quote"]["quality"] == "LIVE"
    assert row["quote_price"] == 100.1
    assert row["quote_trigger_price"] is None
    row["quote_quality"] = snap["quality"]
    row["quote_session"] = snap["session"]
    row["quote_source"] = snap["source"]
    store = AccumulationLadderStore(tmp_path / "isolated_research_ladder.json")
    now = datetime(2026, 10, 26, 14, tzinfo=UTC)
    assert store.sync([row], now=now) == []
    assert store.get("MSFT") is None
    # Even a forged LIVE+REGULAR label and a subsequent large price drop
    # must not turn the display-only price into a manual-buy ladder trigger.
    lower = dict(row, quote_price=70.0, quote_display_price=70.0)
    assert store.sync([lower], now=now + timedelta(minutes=1)) == []
    assert store.get("MSFT") is None


@pytest.mark.parametrize("trigger", [None, 0.0, "", float("nan")])
def test_missing_accepted_trigger_never_arms_from_fresh_display_price(
        tmp_path, trigger):
    store = AccumulationLadderStore(tmp_path / "isolated_ladder.json")
    row = board_row(trigger=trigger)
    assert store.sync([row], now=datetime(2026, 10, 26, 14, tzinfo=UTC)) == []
    assert store.get("MSFT") is None


def test_missing_trigger_cannot_cross_already_armed_ladder(tmp_path):
    store = AccumulationLadderStore(tmp_path / "isolated_ladder.json")
    now = datetime(2026, 10, 26, 14, tzinfo=UTC)
    store.sync([board_row(price=100.0, trigger=100.1)], now=now)
    assert store.get("MSFT")["active"]
    display_only = board_row(price=70.0, trigger=None,
                             source="ALPACA_IEX_SINGLE_EXCHANGE_NOT_NBBO")
    assert store.sync([display_only], now=now + timedelta(minutes=1)) == []
    assert all(not level["hit"] for level in store.get("MSFT")["levels"])
    # Legitimate explicit manual-alert trigger still works.
    accepted = board_row(price=96.8, trigger=96.9)
    hits = store.sync([accepted], now=now + timedelta(minutes=2))
    assert [hit.level for hit in hits] == ["L1"]
    assert all(hit.market_price == 96.9 for hit in hits)


def test_old_rows_without_trigger_cannot_infer_quote_actionability(tmp_path):
    store = AccumulationLadderStore(tmp_path / "isolated_ladder.json")
    row = board_row()
    del row["quote_trigger_price"]
    assert store.sync([row], now=datetime(2026, 10, 26, 14, tzinfo=UTC)) == []
    assert store.get("MSFT") is None
