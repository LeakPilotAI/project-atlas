from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.services.perp_manual_service import PerpManualService
from app.trading_core.perp_manual_state_store import ManualPerpStateStore


@dataclass
class FakeTicker:
    symbol: str
    price: float
    volume_24h: float = 1_000_000.0
    open_interest: float = 500_000.0
    funding_rate: float = 0.0


class FakeAdapter:
    def universe_names(self):
        return ["BTC"]

    async def get_all_tickers(self):
        return [FakeTicker("BTC", 101.0)]


@pytest.mark.asyncio
async def test_recovered_entered_plan_waits_for_fresh_mark_then_rehydrates(tmp_path, monkeypatch):
    path = tmp_path / "perp-state.json"
    ManualPerpStateStore(path).save(
        plans=[{
            "setup_key": "BTC:LONG",
            "symbol": "BTC",
            "side": "LONG",
            "status": "ENTERED",
            "entered": True,
            "entry_price": 100.0,
            "entered_at": datetime.now(timezone.utc).isoformat(),
            "l1": 99.0,
            "l2": 98.0,
            "l3": 97.0,
            "stop": 95.0,
            "tp1": 103.0,
            "tp2": 106.0,
            "mark": 999.0,
            "state": "TP2_HIT",
        }],
        setup_history=[],
    )

    service = PerpManualService(state_path=path)
    recovered = service.snapshot()["plans"][0]
    assert recovered["status"] == "ENTERED"
    assert recovered["mark"] is None
    assert recovered["state"] == "WAIT"

    monkeypatch.setattr(service, "_adapter", lambda: FakeAdapter())

    async def no_setups(*args, **kwargs):
        return []

    monkeypatch.setattr(service, "_discover_setups", no_setups)
    await service.refresh()

    refreshed = service.snapshot()["plans"][0]
    assert refreshed["mark"] == 101.0
    assert refreshed["status"] == "ENTERED"


@pytest.mark.asyncio
async def test_alert_cooldown_survives_restart(tmp_path, monkeypatch):
    path = tmp_path / "perp-state.json"
    now = datetime.now(timezone.utc).isoformat()
    ManualPerpStateStore(path).save(
        plans=[],
        setup_history=[{
            "setup_key": "BTC:LONG",
            "symbol": "BTC",
            "side": "LONG",
            "tier": "QUALIFIED",
            "state": "PREPARE",
            "first_seen_at": now,
            "last_seen_at": now,
            "last_alert_at": now,
        }],
    )

    service = PerpManualService(state_path=path)
    monkeypatch.setattr(service, "_adapter", lambda: FakeAdapter())

    async def one_setup(*args, **kwargs):
        return [{
            "symbol": "BTC",
            "side": "LONG",
            "score": 75.0,
            "state": "PREPARE",
            "next_action": "Prepare manual L1.",
            "distance_to_l1_pct": 0.2,
            "price": 101.0,
            "levels": {"l1": 100.0, "l2": 99.0, "l3": 98.0, "stop": 96.0, "tp1": 104.0, "tp2": 107.0},
        }]

    monkeypatch.setattr(service, "_discover_setups", one_setup)
    out = await service.refresh()

    assert out["setups"][0]["last_alert_at"] == now
    assert out["setups"][0]["alert_eligible"] is False
    assert out["alert_candidates"] == []


def test_corrupt_persistent_state_does_not_break_service_startup(tmp_path):
    path = tmp_path / "perp-state.json"
    path.write_text("not-json", encoding="utf-8")

    service = PerpManualService(state_path=path)
    snap = service.snapshot()

    assert snap["plans"] == []
    assert snap["persistence"]["enabled"] is True
    assert snap["persistence"]["error"]
