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


class FakeAdapter:
    def __init__(self) -> None:
        self._universe = ["BTC", "ETH", "SOL"]

    def universe_names(self):
        return list(self._universe)

    async def get_all_tickers(self):
        return [
            FakeTicker("ETH", 2500.0, 5_000_000, 1_500_000, 0.0001),
            FakeTicker("BTC", 100000.0, 20_000_000, 8_000_000, 0.00005),
            FakeTicker("SOL", 200.0, 2_000_000, 900_000, -0.0001),
        ]


@pytest.mark.asyncio
async def test_refresh_uses_only_hyperliquid_adapter(monkeypatch):
    service = PerpManualService()
    fake = FakeAdapter()
    monkeypatch.setattr(service, "_adapter", lambda: fake)

    out = await service.refresh()

    assert out["source"] == "hyperliquid"
    assert out["mode"] == "MANUAL_ONLY"
    assert out["market_count"] == 3
    assert [r["symbol"] for r in out["markets"]] == ["BTC", "ETH", "SOL"]
    assert out["markets"][0]["volume_24h"] == 20_000_000


@pytest.mark.asyncio
async def test_refresh_rejects_missing_adapter(monkeypatch):
    service = PerpManualService()
    monkeypatch.setattr(service, "_adapter", lambda: None)
    with pytest.raises(RuntimeError, match="Hyperliquid adapter unavailable"):
        await service.refresh()


@pytest.mark.asyncio
async def test_create_plan_refuses_equity_symbol(monkeypatch):
    service = PerpManualService()
    monkeypatch.setattr(service, "_adapter", lambda: FakeAdapter())
    await service.refresh()

    with pytest.raises(ValueError):
        service.create_plan(symbol="MSFT", side="LONG", reference_price=400.0)


@pytest.mark.asyncio
async def test_create_plan_persists_manual_plan(monkeypatch):
    service = PerpManualService()
    monkeypatch.setattr(service, "_adapter", lambda: FakeAdapter())
    await service.refresh()

    plan = service.create_plan(symbol="BTC", side="LONG", reference_price=100000.0)

    assert plan["symbol"] == "BTC"
    assert plan["side"] == "LONG"
    assert plan["l1"] < 100000.0
    assert plan["l2"] < plan["l1"]
    assert plan["l3"] < plan["l2"]
    assert plan["stop"] < plan["l3"]
    assert plan["tp1"] > plan["l1"]
    assert plan["tp2"] > plan["tp1"]
    assert service.snapshot()["plans"][0]["symbol"] == "BTC"


@pytest.mark.asyncio
async def test_duplicate_symbol_side_replaces_prior_plan(monkeypatch):
    service = PerpManualService()
    monkeypatch.setattr(service, "_adapter", lambda: FakeAdapter())
    await service.refresh()

    service.create_plan(symbol="ETH", side="SHORT", reference_price=2500.0)
    service.create_plan(symbol="ETH", side="SHORT", reference_price=2600.0)

    plans = service.snapshot()["plans"]
    matches = [p for p in plans if p["symbol"] == "ETH" and p["side"] == "SHORT"]
    assert len(matches) == 1
    assert matches[0]["reference_price"] == 2600.0
