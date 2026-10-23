import json
from datetime import datetime, timezone

import pytest
from app.api import perp_manual as manual_api
from app.main import app
from app.services.perp_manual_service import perp_manual_service
from app.services.perp_setup_paper_mirror import PerpSetupPaperMirror
from fastapi.testclient import TestClient


def test_manual_board_api_projects_setups(monkeypatch):
    # This API projection test must not seed the global PAPER mirror from the
    # operator's retained pending journal. Its replay/refusal contract has
    # dedicated isolated persistence tests.
    monkeypatch.setattr(manual_api.perp_setup_paper_mirror, "status", lambda: {"pending_count": 0, "open_count": 0})
    monkeypatch.setattr(manual_api, "build_paper_observability", lambda setups: {})
    monkeypatch.setattr(perp_manual_service, "last_snapshot", {
        "source": "hyperliquid",
        "mode": "MANUAL_ONLY",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "markets": [{"symbol": "BTC", "timestamp": datetime.now(timezone.utc).isoformat()}],
        "setups": [{
            "setup_key": "BTC:LONG",
            "mark_timestamp": datetime.now(timezone.utc).isoformat(),
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


def test_rearmed_paper_identity_refuses_without_rewriting_evidence(tmp_path, monkeypatch):
    import app.services.perp_setup_paper_mirror as mirror_module

    instance = 'BTC:LONG|first|epoch'
    pending = tmp_path / 'pending.jsonl'
    rows = [
        {'event': 'armed', 'setup_instance_id': instance},
        {'event': 'cancelled', 'setup_instance_id': instance},
        {'event': 'armed', 'setup_instance_id': instance},
    ]
    original = ''.join(json.dumps(row) + '\n' for row in rows).encode()
    pending.write_bytes(original)
    empty_paper = tmp_path / 'paper.jsonl'
    monkeypatch.setattr(mirror_module, 'JOURNAL_PATH', empty_paper)
    mirror = PerpSetupPaperMirror(pending_path=pending)
    monkeypatch.setattr(manual_api, 'perp_setup_paper_mirror', mirror)
    with pytest.raises(ValueError, match='rearmed after terminal evidence'):
        mirror.status()
    assert pending.read_bytes() == original
