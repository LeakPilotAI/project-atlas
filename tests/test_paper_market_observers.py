"""Actual adapter caches are observed without refresh/start or financial imports."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.adapters.hyperliquid import HyperliquidAdapter
from app.investment.alpaca_iex import IEXFeed
from app.services.paper_market_observers import (
    HyperliquidMarketObserver,
    IEXMarketObserver,
)


@pytest.mark.asyncio
async def test_existing_iex_observer_no_connect_or_signal_fabrication():
    f = IEXFeed(["SPY"])
    f.receive('[{"T":"success","msg":"authenticated"}]')
    f.receive('[{"T":"subscription","quotes":["SPY"]}]')
    observer = IEXMarketObserver(f, calendar=SimpleNamespace(read=lambda _: "CLOSED"), clock=lambda: int(f.clock()))
    row = await observer.observe()
    assert row["session"] == "CLOSED" and row["signal"] is None
    assert observer.verify_observation(row)
    f.disconnect()
    assert not observer.verify_observation(row)


@pytest.mark.asyncio
async def test_actual_hyperliquid_cache_read_is_research_not_execution(monkeypatch):
    adapter = HyperliquidAdapter()
    async def forbidden():
        pytest.fail("observation attempted provider connection")
    monkeypatch.setattr(adapter, "connect", forbidden)
    adapter._connected = True
    adapter._last_rest_observed_at = datetime.now(UTC)
    adapter._last_rest_prices = {"BTC": 100000.0}
    view = adapter.monitor_snapshot()
    assert view["connection"] == "CONNECTED"
    assert view["bid_ask"] is None and view["funding_history"] is None
    assert view["execution_eligible"] is False
    observer = HyperliquidMarketObserver(adapter, clock=lambda: int(datetime.now(UTC).timestamp()))
    row = await observer.observe()
    assert observer.verify_observation(row) and row["session"] == "OPEN"
    assert row["source"]["feed"] == "HYPERLIQUID_RESEARCH_MARK_NOT_EXECUTABLE"
    adapter._last_rest_prices["BTC"] = 100001.0
    assert not observer.verify_observation(row)


@pytest.mark.parametrize("damage", ["missing", "stale", "disconnected", "nonfinite"])
def test_hyperliquid_empty_stale_or_disconnected_cache_cannot_claim_health(damage):
    adapter = HyperliquidAdapter()
    adapter._connected = damage != "disconnected"
    adapter._last_rest_observed_at = datetime.now(UTC) - timedelta(seconds=31 if damage == "stale" else 0)
    adapter._last_rest_prices = {} if damage == "missing" else {"BTC": float("nan") if damage == "nonfinite" else 100000.0}
    assert adapter.monitor_snapshot()["connection"] == "UNAVAILABLE"
    assert adapter._client is None and adapter._ws_task is None
