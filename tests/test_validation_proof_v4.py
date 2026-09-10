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
    assert proof["investment_historical"]["domain"] == "EQUITY_INVESTMENT"
    assert proof["investment_freshness"]["domain"] == "EQUITY_INVESTMENT"
    assert proof["engineering_complete_is_not_edge"] is True
    assert proof["live_capital_allowed"] is False


def test_validation_proof_exposes_oos_cost_analysis_without_live_unlock():
    rows = [
        {"exit_timestamp": f"2026-01-{(i % 28) + 1:02d}T00:{i % 60:02d}:00+00:00", "net_pnl_r": 0.2, "side": "LONG", "regime": "TREND"}
        for i in range(60)
    ]
    proof = build_validation_proof(paper_rows=rows, opportunity_rows=[], outcome_rows=[])
    report = proof["perp_oos_cost"]
    assert report["domain"] == "HYPERLIQUID_PERPS"
    assert report["strategy_frozen"] is True
    assert report["live_capital_allowed"] is False
    assert "holdout" in report
    assert "rolling" in report
    assert "cost_stress" in report


def test_validation_proof_exposes_quality_dips_historical_analysis():
    observations = [{
        "observation_id": "o1",
        "symbol": "MSFT",
        "as_of": "2026-09-09T12:00:00+00:00",
        "classification": "ACCUMULATION",
        "research": {"opportunity_score": 80, "evidence_quality": "HIGH", "thesis": "INTACT"},
    }]
    outcomes = [{"observation_id": "o1", "symbol": "MSFT", "return_20d": 0.12, "enriched_at": "2026-09-10T12:00:00+00:00"}]
    proof = build_validation_proof(paper_rows=[], opportunity_rows=[], outcome_rows=outcomes, observation_rows=observations)
    report = proof["investment_historical"]
    assert report["matched_observations"] == 1
    assert report["by_horizon"]["20d"]["mean_return"] == 0.12
    assert report["strategy_frozen"] is True
    assert report["live_capital_allowed"] is False


def test_validation_proof_exposes_investment_freshness_without_live_unlock():
    readiness = {
        "status": "READY FOR RESEARCH",
        "checks": {
            name: {"ok": True, "detail": "ok"}
            for name in (
                "provider_reliability",
                "fundamental_completeness",
                "valuation_completeness",
                "historical_price_coverage",
                "point_in_time_integrity",
                "look_ahead",
            )
        },
    }
    proof = build_validation_proof(
        paper_rows=[], opportunity_rows=[], outcome_rows=[], investment_readiness=readiness
    )
    report = proof["investment_freshness"]
    assert report["quality_gate_passed"] is True
    assert report["strategy_frozen"] is True
    assert report["live_capital_allowed"] is False
