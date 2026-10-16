from fastapi.testclient import TestClient

from app.main import app
from app.services.perp_manual_service import perp_manual_service


def test_manual_board_api_projects_setups(monkeypatch):
    monkeypatch.setattr(perp_manual_service, "last_snapshot", {
        "source": "hyperliquid",
        "mode": "MANUAL_ONLY",
        "updated_at": "2026-09-10T00:00:00+00:00",
        "setups": [{
            "setup_key": "BTC:LONG",
            "symbol": "BTC",
            "side": "LONG",
            "tier": "PRIME",
            "state": "PREPARE",
            "score": 88.0,
            "price": 100000.0,
            "alert_eligible": True,
            "next_action": "Prepare L1.",
            "levels": {"l1": 99500.0, "l2": 99000.0, "l3": 98500.0, "stop": 97500.0, "tp1": 103000.0, "tp2": 106000.0},
        }],
        "plans": [],
    })
    client = TestClient(app)
    response = client.get("/api/perps/manual/board")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "hyperliquid"
    assert data["count"] == 1
    assert data["alert_count"] == 1
    assert data["board"][0]["symbol"] == "BTC"
    assert data["board"][0]["tier"] == "PRIME"


def test_alert_ack_api(monkeypatch):
    monkeypatch.setattr(perp_manual_service, "acknowledge_alert", lambda key: key == "BTC:LONG")
    client = TestClient(app)
    ok = client.post("/api/perps/manual/alerts/BTC:LONG/ack")
    assert ok.status_code == 200
    assert ok.json()["status"] == "COOLDOWN_ACTIVE"

    missing = client.post("/api/perps/manual/alerts/NOPE/ack")
    assert missing.status_code == 404
