from __future__ import annotations

from pathlib import Path

from app.investment.quality_dips_v2_alert_store import QualityDipsV2AlertStore


def test_store_round_trip(tmp_path: Path):
    path = tmp_path / "v2-alerts.json"
    store = QualityDipsV2AlertStore(path)
    store.remember_snapshot("test", {"patient_state": "ACCUMULATION"})
    store.mark_event(
        dedupe_key="V2:TEST:STATE_TRANSITION:ACCUMULATION",
        delivered=True,
        event_type="STATE_TRANSITION",
        symbol="TEST",
        at="2026-09-17T12:00:00+00:00",
    )
    store.save()

    loaded = QualityDipsV2AlertStore(path)
    assert loaded.previous("TEST")["patient_state"] == "ACCUMULATION"
    event = loaded.prior_event("V2:TEST:STATE_TRANSITION:ACCUMULATION")
    assert event["delivered"] is True
    assert event["symbol"] == "TEST"


def test_store_returns_copies(tmp_path: Path):
    store = QualityDipsV2AlertStore(tmp_path / "v2-alerts.json")
    store.remember_snapshot("TEST", {"patient_state": "WATCH"})
    copy = store.previous("TEST")
    copy["patient_state"] = "GENERATIONAL"
    assert store.previous("TEST")["patient_state"] == "WATCH"


def test_store_contains_no_broker_execution_behavior(tmp_path: Path):
    store = QualityDipsV2AlertStore(tmp_path / "v2-alerts.json")
    assert not hasattr(store, "place_order")
    assert not hasattr(store, "buy")
    assert not hasattr(store, "sell")
