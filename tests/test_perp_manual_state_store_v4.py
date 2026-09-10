from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.trading_core.perp_manual_state_store import (
    ManualPerpStateError,
    ManualPerpStateStore,
)


def test_state_store_roundtrip_keeps_plans_and_lifecycle_only(tmp_path):
    path = tmp_path / "perp-state.json"
    store = ManualPerpStateStore(path)
    store.save(
        plans=[{"setup_key": "BTC:LONG", "status": "ENTERED", "entry_price": 100.0}],
        setup_history=[{
            "setup_key": "BTC:LONG",
            "symbol": "BTC",
            "side": "LONG",
            "tier": "PRIME",
            "state": "PREPARE",
            "last_alert_at": datetime.now(timezone.utc).isoformat(),
            "price": 999999.0,
            "levels": {"l1": 1.0},
        }],
    )

    recovered = store.load()

    assert recovered["plans"][0]["status"] == "ENTERED"
    row = recovered["setup_history"][0]
    assert row["setup_key"] == "BTC:LONG"
    assert "price" not in row
    assert "levels" not in row


def test_state_store_rejects_corrupt_json(tmp_path):
    path = tmp_path / "perp-state.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ManualPerpStateError, match="unreadable"):
        ManualPerpStateStore(path).load()


def test_state_store_rejects_nonfinite_values(tmp_path):
    store = ManualPerpStateStore(tmp_path / "perp-state.json")

    with pytest.raises(ValueError):
        store.save(plans=[{"entry_price": float("nan")}], setup_history=[])
