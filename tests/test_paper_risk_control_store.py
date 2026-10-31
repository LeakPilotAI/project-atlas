import json

from app.services.paper_risk_controls import PaperRiskControlStore


def test_paper_risk_control_store_persists(tmp_path):
    path=tmp_path/"controls.json"
    store=PaperRiskControlStore(path)
    store.kill_switch=True
    store.session_net_r=-2.5
    store.save()
    loaded=PaperRiskControlStore(path)
    assert loaded.kill_switch is True
    assert loaded.session_net_r == -2.5
