from app.services.paper_risk import check_paper_risk


def test_paper_risk_blocks_fourth_position():
    opens=[{"trade_type":"PAPER"},{"trade_type":"PAPER"},{"trade_type":"PAPER"}]
    out=check_paper_risk(open_positions=opens,requested_risk_usd=1)
    assert out["allowed"] is False
    assert "max concurrent paper positions reached" in out["blockers"]


def test_paper_risk_blocks_excessive_per_trade_risk():
    out=check_paper_risk(open_positions=[],requested_risk_usd=30)
    assert out["allowed"] is False
    assert "per-trade paper risk ceiling exceeded" in out["blockers"]


def test_paper_risk_allows_small_simulated_risk():
    out=check_paper_risk(open_positions=[],requested_risk_usd=1)
    assert out["allowed"] is True
    assert out["automatic_real_money_execution"] is False
