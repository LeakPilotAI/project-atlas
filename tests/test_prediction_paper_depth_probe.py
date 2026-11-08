"""Bounded Kalshi diagnostic never places PAPER or live orders."""
import asyncio
from decimal import Decimal

import pytest

from scripts import prediction_paper_depth_probe as depth_probe


def test_probe_real_depth_read_only(monkeypatch):
    calls = []

    async def markets(**kwargs):
        calls.append(("markets", kwargs))
        return {"markets": [{"ticker": "KXTEST-A"}]}

    async def book(ticker, **kwargs):
        calls.append(("book", ticker))
        return {"orderbook": {
            "yes": {"asks": [{"price_dollars": "0.6", "quantity_contracts": "2"}],
                    "bids": [{"price_dollars": "0.4", "quantity_contracts": "2"}]},
            "no": {"asks": [], "bids": []},
        }}

    monkeypatch.setattr(depth_probe.kalshi_public, "get_markets", markets)
    monkeypatch.setattr(depth_probe.kalshi_public, "get_orderbook", book)
    result = asyncio.run(depth_probe.probe(limit=1))
    assert result["broker_orders"] == 0
    assert result["paper_positions_opened"] == 0
    assert result["unattended_paper_authorized"] is False
    assert result["future_exit_liquidity_proven"] is False
    assert result["books_checked"] == 1
    assert result["markets"][0]["sides"]["YES"]["entry_fillable"] is True
    assert result["markets"][0]["sides"]["YES"]["exit_fillable"] is True
    assert result["markets"][0]["sides"]["NO"]["entry_fillable"] is False
    assert len(calls) == 2


@pytest.mark.parametrize("quantity", [Decimal("NaN"), Decimal("Infinity"), Decimal("0"), Decimal("11")])
def test_probe_rejects_invalid_quantity(quantity):
    with pytest.raises(ValueError):
        asyncio.run(depth_probe.probe(quantity=quantity))


def test_probe_records_provider_timeout(monkeypatch):
    async def markets(**kwargs):
        return {"markets": [{"ticker": "KXTEST-A"}]}

    async def book(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(depth_probe.kalshi_public, "get_markets", markets)
    monkeypatch.setattr(depth_probe.kalshi_public, "get_orderbook", book)
    result = asyncio.run(depth_probe.probe(limit=1))
    assert result["markets"][0]["error_type"] == "TimeoutError"
    assert result["broker_orders"] == 0