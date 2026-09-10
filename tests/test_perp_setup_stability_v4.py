from datetime import datetime, timedelta, timezone

from app.trading_core.perp_setup_lifecycle import reconcile_setups


def _row(*, price=100.0, l1=99.5, state="PREPARE"):
    return {
        "symbol": "BTC",
        "side": "LONG",
        "score": 85.0,
        "price": price,
        "state": state,
        "next_action": "prepare",
        "levels": {
            "l1": l1,
            "l2": l1 - 0.5,
            "l3": l1 - 1.0,
            "stop": l1 - 2.0,
            "tp1": l1 + 3.0,
            "tp2": l1 + 6.0,
            "target_rr": 1.8,
        },
    }


def test_reconcile_freezes_published_levels_when_market_refreshes():
    now = datetime(2026, 9, 10, 13, 30, tzinfo=timezone.utc)
    first = reconcile_setups([_row(price=100.0, l1=99.5)], now=now)[0]
    refreshed = _row(price=101.0, l1=100.5)
    second = reconcile_setups([refreshed], previous=[first], now=now + timedelta(seconds=20))[0]
    assert second["levels"]["l1"] == 99.5
    assert second["levels"]["l2"] == 99.0
    assert second["levels_frozen"] is True
    assert second["price"] == 101.0


def test_temporarily_missing_setup_is_retained_but_not_actionable():
    now = datetime(2026, 9, 10, 13, 30, tzinfo=timezone.utc)
    first = reconcile_setups([_row()], now=now)[0]
    retained = reconcile_setups([], previous=[first], now=now + timedelta(seconds=20))[0]
    assert retained["symbol"] == "BTC"
    assert retained["levels"]["l1"] == 99.5
    assert retained["discovery_stale"] is True
    assert retained["state"] == "WAIT"
    assert retained["alert_eligible"] is False
    assert "do not add/chase" in retained["next_action"]


def test_missing_setup_expires_after_retention_window():
    now = datetime(2026, 9, 10, 13, 30, tzinfo=timezone.utc)
    first = reconcile_setups([_row()], now=now)[0]
    gone = reconcile_setups([], previous=[first], now=now + timedelta(minutes=11))
    assert gone == []


def test_rediscovered_setup_clears_stale_marker_and_keeps_levels():
    now = datetime(2026, 9, 10, 13, 30, tzinfo=timezone.utc)
    first = reconcile_setups([_row()], now=now)[0]
    stale = reconcile_setups([], previous=[first], now=now + timedelta(seconds=20))[0]
    rediscovered = reconcile_setups([_row(price=100.2, l1=100.0)], previous=[stale], now=now + timedelta(seconds=40))[0]
    assert rediscovered["discovery_stale"] is False
    assert rediscovered["levels"]["l1"] == 99.5
