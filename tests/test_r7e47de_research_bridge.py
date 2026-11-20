from datetime import datetime, timezone

import pytest

from scripts.observation_runtime.r7e47de_research_bridge import (
    ResearchBridgeRefused,
    analyze_research,
    bridge_research,
)


def candle(iso, price, volume):
    return {
        "timestamp": datetime.fromisoformat(iso),
        "Close": price,
        "Volume": volume,
    }


def valid_observation(**overrides):
    base = {
        "symbol": "AAPL",
        "price": 102.5,
        "source": "ROBINHOOD",
        "session": "PRE_MARKET",
        "effective_timestamp": "2026-10-19T07:59:00-04:00",
        "research_only": True,
        "trading_enabled": False,
    }
    base.update(overrides)
    return base


def valid_candles():
    return [
        candle("2026-10-19T07:59:00-04:00", 101.0, 1000),
        candle("2026-10-19T08:00:00-04:00", 102.5, 2000),
    ]


def test_bridge_accepts_valid_research_payload():
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    result = bridge_research(
        valid_observation(),
        valid_candles(),
        100.0,
        now=now,
    )

    assert result["symbol"] == "AAPL"
    assert result["research_only"] is True
    assert result["trading_enabled"] is False
    assert result["quote_source"] == "ROBINHOOD"
    assert result["quote_price"] == 102.5
    assert result["provider_request_count"] == 0
    assert result["network_authorized"] is False


def test_bridge_rejects_stale_quote():
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    stale = valid_observation(effective_timestamp="2026-10-19T06:00:00-04:00")

    with pytest.raises(ResearchBridgeRefused, match="stale|Quote"):
        bridge_research(stale, valid_candles(), 100.0, now=now, max_quote_age_seconds=1800)


def test_bridge_rejects_mismatched_symbol():
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    mismatch = {**valid_observation(symbol="AAPL"), "symbol": "AAPL"}
    mismatched_candles = [{**valid_candles()[0], "symbol": "MSFT"}, {**valid_candles()[1], "symbol": "MSFT"}]
    with pytest.raises(ResearchBridgeRefused, match="Symbol mismatch|symbol"):
        bridge_research(mismatch, mismatched_candles, 100.0, now=now)


def test_bridge_rejects_session_mismatch():
    now = datetime(2026, 10, 19, 13, 32, tzinfo=timezone.utc)
    mismatched = valid_observation(session="PRE_MARKET")
    regular_candles = [
        candle("2026-10-19T09:31:00-04:00", 101.0, 1000),
        candle("2026-10-19T09:32:00-04:00", 101.5, 1000),
    ]

    with pytest.raises(ResearchBridgeRefused, match="session|Session"):
        bridge_research(mismatched, regular_candles, 100.0, now=now, max_quote_age_seconds=7200)


def test_bridge_rejects_invalid_previous_close():
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ResearchBridgeRefused, match="Previous close"):
        bridge_research(valid_observation(), valid_candles(), 0, now=now)


def test_bridge_rejects_future_timestamp():
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    future_quote = valid_observation(effective_timestamp="2026-10-19T15:00:00-04:00")
    with pytest.raises(ResearchBridgeRefused, match="future|Future"):
        bridge_research(future_quote, valid_candles(), 100.0, now=now)


def test_analyze_research_aliases_bridge():
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    result = analyze_research(valid_observation(), valid_candles(), 100.0, now=now)
    assert "previous_close" in result
    assert result["previous_close"] == 100.0
