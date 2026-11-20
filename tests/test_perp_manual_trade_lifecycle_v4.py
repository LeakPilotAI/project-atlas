from datetime import datetime, timezone

import pytest

from app.trading_core.perp_manual_trade_lifecycle import close_plan, enter_setup


def _setup(mark: float = 100.0):
    return {
        "setup_key": "BTC:LONG",
        "symbol": "BTC",
        "side": "LONG",
        "tier": "PRIME",
        "score": 88.0,
        "price": mark,
        "levels": {
            "l1": 100.0,
            "l2": 99.0,
            "l3": 98.0,
            "stop": 97.0,
            "tp1": 105.0,
            "tp2": 108.0,
            "target_rr": 1.8,
        },
    }


def test_entry_requires_explicit_call_and_records_actual_fill():
    now = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    plan = enter_setup(_setup(), fill_price=99.75, now=now)
    assert plan["status"] == "ENTERED"
    assert plan["entered"] is True
    assert plan["entry_price"] == 99.75
    assert plan["entered_at"] == now.isoformat()
    assert plan["source"] == "hyperliquid"
    assert plan["mode"] == "MANUAL_ONLY"


def test_entered_plan_can_report_tp_only_after_explicit_entry():
    plan = enter_setup(_setup(mark=106.0), fill_price=100.0)
    assert plan["state"] == "TP1_HIT"


def test_entry_rejects_malformed_setup():
    bad = _setup()
    bad.pop("setup_key")
    with pytest.raises(ValueError):
        enter_setup(bad)


def test_manual_close_records_exit_without_order_execution():
    entered = enter_setup(_setup(), fill_price=100.0)
    closed = close_plan(
        entered,
        exit_price=104.0,
        reason="USER_EXIT",
        now=datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc),
    )
    assert closed["status"] == "CLOSED"
    assert closed["entered"] is False
    assert closed["exit_price"] == 104.0
    assert closed["close_reason"] == "USER_EXIT"


def test_cannot_close_plan_that_was_never_entered():
    with pytest.raises(ValueError):
        close_plan({"status": "PLANNED"}, exit_price=100.0)
