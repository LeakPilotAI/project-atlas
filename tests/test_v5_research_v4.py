from app.services.v5_research import build_v5_research_report
from app.services.validation_proof import build_validation_proof


def test_v5_report_is_descriptive_and_never_live():
    rows = [
        {"net_pnl_r": 1.0, "mfe_r": 1.2, "mae_r": 0.2, "side": "LONG", "regime": "TREND_UP", "signal_score": 82},
        {"net_pnl_r": -1.0, "mfe_r": 0.0, "mae_r": 1.1, "side": "LONG", "regime": "RANGE", "signal_score": 74},
        {"net_pnl_r": -0.5, "mfe_r": 0.1, "mae_r": 0.8, "side": "SHORT", "regime": "RANGE", "signal_score": 65},
    ]

    report = build_v5_research_report(rows, recent_n=2)

    assert report["strategy_frozen"] is True
    assert report["retuning_allowed"] is False
    assert report["live_capital_allowed"] is False
    assert report["closed_trades"] == 3
    assert report["by_regime"]["RANGE"]["n"] == 2
    assert report["by_score_bucket"]["80_PLUS"]["n"] == 1
    assert report["overall"]["zero_mfe_loss_rate"] == 0.5


def test_validation_proof_exposes_v5_research_without_unlocking_capital():
    rows = [{"net_pnl_r": -1.0, "mfe_r": 0.0, "mae_r": 1.0, "side": "LONG", "regime": "RANGE"}]

    proof = build_validation_proof(paper_rows=rows, opportunity_rows=[], outcome_rows=[])

    report = proof["perp_v5_research"]
    assert report["closed_trades"] == 1
    assert report["retuning_allowed"] is False
    assert report["live_capital_allowed"] is False
    assert proof["live_capital_allowed"] is False
