from fastapi.testclient import TestClient

from app.main import app
from app.services.paper_risk_controls import paper_risk_controls


def test_paper_risk_api_exposes_and_updates_kill_switch(tmp_path, monkeypatch):
    path = tmp_path / "controls.json"
    original_path = paper_risk_controls.path
    original_kill_switch = paper_risk_controls.kill_switch
    original_session_net_r = paper_risk_controls.session_net_r
    monkeypatch.setattr(paper_risk_controls, "path", path)
    try:
        paper_risk_controls.kill_switch = False
        paper_risk_controls.session_net_r = 0.0
        client = TestClient(app)
        r = client.get("/api/perps/paper-risk")
        assert r.status_code == 200
        assert r.json()["live_execution"] is False
        r = client.post("/api/perps/paper-risk/kill-switch?enabled=true")
        assert r.status_code == 200
        assert r.json()["kill_switch"] is True
    finally:
        paper_risk_controls.kill_switch = original_kill_switch
        paper_risk_controls.session_net_r = original_session_net_r
        paper_risk_controls.path = original_path
