from app.services.perp_manual_service import PerpManualService


def test_acknowledge_alert_starts_cooldown_and_removes_candidate():
    service = PerpManualService()
    setup = {
        "setup_key": "BTC:LONG",
        "symbol": "BTC",
        "side": "LONG",
        "score": 85.0,
        "tier": "PRIME",
        "state": "PREPARE",
        "alert_eligible": True,
        "last_alert_at": None,
    }
    service.last_snapshot["setups"] = [setup]
    service.last_snapshot["alert_candidates"] = [setup]

    assert service.acknowledge_alert("BTC:LONG") is True
    assert setup["last_alert_at"] is not None
    assert setup["alert_eligible"] is False
    assert service.last_snapshot["alert_candidates"] == []


def test_acknowledge_unknown_setup_is_noop():
    service = PerpManualService()
    assert service.acknowledge_alert("NOPE:LONG") is False
