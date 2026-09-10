from datetime import datetime, timezone

from app.services.validation_proof import build_investment_proof, build_perp_proof, build_validation_proof


def _close(r):
    return {"net_pnl_r": r, "mfe_r": max(r, 0), "mae_r": abs(min(r, 0))}


def test_perp_proof_never_unlocks_live_capital():
    rows = [_close(1.0)] * 80 + [_close(-0.5)] * 20
    proof = build_perp_proof(rows)
    assert proof["domain"] == "HYPERLIQUID_PERPS"
    assert proof["closed_trades"] == 100
    assert proof["live_capital_allowed"] is False
    assert "expectancy_ci95" in proof
    assert "max_drawdown_r" in proof


def test_investment_proof_reports_dataset_maturity_not_edge():
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    research = [{"symbol": "MSFT", "timestamp": "2026-09-09T12:00:00+00:00"}, {"symbol": "AAPL", "timestamp": "2026-09-09T13:00:00+00:00"}]
    outcomes = [{"symbol": "MSFT", "timestamp": "2026-09-10T00:00:00+00:00"}]
    proof = build_investment_proof(research, outcomes, now=now)
    assert proof["domain"] == "EQUITY_INVESTMENT"
    assert proof["outcome_symbol_coverage"] == 0.5
    assert proof["live_capital_allowed"] is False
    assert "predictive edge" in proof["note"]


def test_validation_orchestration_keeps_domains_separate():
    proof = build_validation_proof(paper_rows=[_close(1.0)], opportunity_rows=[{"symbol": "MSFT"}], outcome_rows=[])
    assert proof["domain"] == "VALIDATION_ORCHESTRATION"
    assert proof["perps"]["domain"] == "HYPERLIQUID_PERPS"
    assert proof["investments"]["domain"] == "EQUITY_INVESTMENT"
    assert proof["engineering_complete_is_not_edge"] is True
    assert proof["live_capital_allowed"] is False
