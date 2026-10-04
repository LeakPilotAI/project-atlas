from __future__ import annotations

from pathlib import Path

from app.trading_core.shadow_coordinator import V4ShadowCoordinator


def test_shadow_mirror_open_and_restart(tmp_path, monkeypatch):
    path = tmp_path / "shadow.jsonl"
    c = V4ShadowCoordinator(path)
    assert c.mirror_legacy_open(
        {
            "symbol": "BTC",
            "side": "LONG",
            "signal_price": 100.0,
            "stop_price": 99.0,
            "setup_rr": 1.8,
            "risk_usd": 1.0,
        },
        trade_id="t1",
        price=100.0,
    )
    assert c.snapshot()["open"] == 1

    c2 = V4ShadowCoordinator(path)
    assert c2.recover() == 1
    assert c2.snapshot()["open_positions"][0]["trade_id"] == "t1"


def test_shadow_marks_close_without_legacy_state(tmp_path):
    path = tmp_path / "shadow.jsonl"
    c = V4ShadowCoordinator(path)
    assert c.mirror_legacy_open(
        {
            "symbol": "BTC",
            "side": "LONG",
            "signal_price": 100.0,
            "stop_price": 99.0,
            "setup_rr": 1.8,
            "risk_usd": 1.0,
        },
        trade_id="t1",
        price=100.0,
    )
    assert c.mark_prices({"BTC": 102.0}) == 1
    snap = c.snapshot()
    assert snap["open"] == 0
    assert snap["closed"] == 1
    assert snap["closed_positions"][0]["trade_id"] == "t1"


def test_shadow_duplicate_open_is_idempotent(tmp_path):
    path = tmp_path / "shadow.jsonl"
    c = V4ShadowCoordinator(path)
    row = {
        "symbol": "ETH",
        "side": "SHORT",
        "signal_price": 100.0,
        "stop_price": 101.0,
        "setup_rr": 1.8,
        "risk_usd": 1.0,
    }
    assert c.mirror_legacy_open(row, trade_id="same", price=100.0)
    assert c.mirror_legacy_open(row, trade_id="same", price=100.0)
    assert c.snapshot()["open"] == 1


def test_shadow_error_is_contained(tmp_path):
    c = V4ShadowCoordinator(tmp_path / "shadow.jsonl")
    ok = c.mirror_legacy_open(
        {
            "symbol": "BTC",
            "side": "LONG",
            "signal_price": 100.0,
            "stop_price": 101.0,
            "setup_rr": 1.8,
            "risk_usd": 1.0,
        },
        trade_id="bad",
        price=100.0,
    )
    assert ok is False
    assert c.snapshot()["last_error"] is not None


def test_shadow_missing_price_does_not_close(tmp_path):
    path = tmp_path / "shadow.jsonl"
    c = V4ShadowCoordinator(path)
    assert c.mirror_legacy_open(
        {
            "symbol": "SOL",
            "side": "LONG",
            "signal_price": 100.0,
            "stop_price": 99.0,
            "setup_rr": 1.8,
            "risk_usd": 1.0,
        },
        trade_id="t1",
        price=100.0,
    )
    assert c.mark_prices({"BTC": 200.0}) == 0
    assert c.snapshot()["open"] == 1
