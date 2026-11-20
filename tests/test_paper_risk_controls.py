from app.services.paper_risk import check_paper_risk


def test_session_loss_stop_blocks_new_paper_risk():
    out = check_paper_risk(open_positions=[], requested_risk_usd=1, session_net_r=-3.0)
    assert out["allowed"] is False
    assert "paper session loss stop reached" in out["blockers"]


def test_kill_switch_blocks_new_paper_risk():
    out = check_paper_risk(open_positions=[], requested_risk_usd=1, kill_switch=True)
    assert out["allowed"] is False
    assert "operator kill switch enabled" in out["blockers"]
