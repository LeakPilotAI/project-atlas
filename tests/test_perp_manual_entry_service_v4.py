import pytest

from app.services.perp_manual_service import PerpManualService
from app.trading_core.perp_board import build_perp_board


def _setup():
    return {
        "setup_key": "ETH:SHORT",
        "symbol": "ETH",
        "side": "SHORT",
        "tier": "QUALIFIED",
        "score": 75.0,
        "price": 2000.0,
        "state": "PREPARE",
        "next_action": "Prepare manual limits.",
        "alert_eligible": True,
        "levels": {
            "l1": 2005.0,
            "l2": 2010.0,
            "l3": 2015.0,
            "stop": 2025.0,
            "tp1": 1975.0,
            "tp2": 1940.0,
            "target_rr": 1.8,
        },
    }


def test_service_entry_is_explicit_and_idempotent():
    service = PerpManualService()
    service.last_snapshot["setups"] = [_setup()]
    first = service.enter_discovered_setup("ETH:SHORT", fill_price=2006.5)
    second = service.enter_discovered_setup("ETH:SHORT", fill_price=1999.0)
    assert first["status"] == "ENTERED"
    assert first["entry_price"] == 2006.5
    assert second["entry_price"] == 2006.5
    assert len(service.last_snapshot["plans"]) == 1


def test_service_close_changes_only_entered_plan():
    service = PerpManualService()
    service.last_snapshot["setups"] = [_setup()]
    service.enter_discovered_setup("ETH:SHORT", fill_price=2006.5)
    closed = service.close_entered_plan("ETH:SHORT", exit_price=1988.0, reason="MANUAL_TP")
    assert closed["status"] == "CLOSED"
    assert closed["exit_price"] == 1988.0
    assert service.last_snapshot["setups"][0]["trade_status"] == "CLOSED"
    with pytest.raises(ValueError):
        service.close_entered_plan("ETH:SHORT", exit_price=1980.0)


def test_board_exposes_entry_lifecycle_fields():
    setup = _setup()
    setup["trade_status"] = "ENTERED"
    setup["entry_price"] = 2006.5
    setup["entered_at"] = "2026-09-10T08:00:00+00:00"
    board = build_perp_board([setup])
    assert board[0]["setup_key"] == "ETH:SHORT"
    assert board[0]["trade_status"] == "ENTERED"
    assert board[0]["entry_price"] == 2006.5
    assert board[0]["entered_at"] == "2026-09-10T08:00:00+00:00"


def test_unknown_setup_cannot_be_invented_as_entered():
    service = PerpManualService()
    with pytest.raises(ValueError):
        service.enter_discovered_setup("MSFT:LONG", fill_price=100.0)
