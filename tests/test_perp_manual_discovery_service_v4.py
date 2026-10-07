from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.perp_manual_service import PerpManualService


@dataclass
class FakeTicker:
    symbol: str
    price: float
    volume_24h: float
    open_interest: float
    funding_rate: float | None = None


class CandleAdapter:
    def universe_names(self):
        return ["BTC", "ETH", "SOL"]

    async def get_all_tickers(self):
        return [
            FakeTicker("BTC", 114.0, 20_000_000, 8_000_000, -0.0001),
            FakeTicker("ETH", 106.0, 5_000_000, 2_000_000, 0.0001),
            FakeTicker("SOL", 100.0, 2_000_000, 900_000, 0.0),
        ]

    async def get_candles(self, symbol: str, interval: str = "5m", lookback: int = 48):
        if symbol == "BTC":
            return [{"close": 100.0 + 0.30 * i} for i in range(48)]
        if symbol == "ETH":
            return [{"close": 120.0 - 0.30 * i} for i in range(48)]
        return [{"close": 100.0 + (0.02 if i % 2 else -0.02)} for i in range(48)]


@pytest.mark.asyncio
async def test_refresh_discovers_ranked_directional_setups(monkeypatch):
    service = PerpManualService()
    monkeypatch.setattr(service, "_adapter", lambda: CandleAdapter())

    out = await service.refresh()

    assert out["source"] == "hyperliquid"
    assert out["mode"] == "MANUAL_ONLY"
    assert len(out["setups"]) == 2
    by_symbol = {row["symbol"]: row for row in out["setups"]}
    assert by_symbol["BTC"]["side"] == "LONG"
    assert by_symbol["ETH"]["side"] == "SHORT"
    assert "SOL" not in by_symbol
    for row in out["setups"]:
        assert row["levels"]["l1"] > 0
        assert row["levels"]["stop"] > 0
        assert row["levels"]["tp1"] > 0
        assert row["state"] in {"WAIT", "PREPARE", "L1_ACTIVE", "L2_ACTIVE", "L3_ACTIVE"}


@pytest.mark.asyncio
async def test_discovery_never_introduces_non_hyperliquid_symbol(monkeypatch):
    service = PerpManualService()
    adapter = CandleAdapter()
    monkeypatch.setattr(service, "_adapter", lambda: adapter)
    out = await service.refresh()
    universe = set(adapter.universe_names())
    assert all(row["symbol"] in universe for row in out["setups"])
