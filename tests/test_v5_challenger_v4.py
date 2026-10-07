from app.services.v5_challenger import build_v5_challenger_report, classify_v5_candidate
from app.services.validation_proof import build_validation_proof


def _row(*, ts: str, score: float, regime: str, pnl: float, side: str = "LONG"):
    return {
        "entry_timestamp": ts,
        "signal_timestamp": ts,
        "signal_score": score,
        "regime_normalized": regime,
        "side": side,
        "net_pnl_r": pnl,
        "mfe_r": max(pnl, 0.0),
        "mae_r": abs(min(pnl, 0.0)),
    }


def test_v5_candidate_policy_is_locked_to_score_and_trend_regime():
    assert classify_v5_candidate(_row(ts="2026-09-11T09:00:00+00:00", score=80, regime="TREND_UP", pnl=1.0)) == (True, "QUALIFIED")
    assert classify_v5_candidate(_row(ts="2026-09-11T09:00:00+00:00", score=79.99, regime="TREND_UP", pnl=1.0)) == (False, "SCORE_BELOW_80")
    assert classify_v5_candidate(_row(ts="2026-09-11T09:00:00+00:00", score=95, regime="RANGE", pnl=1.0)) == (False, "NON_TREND_REGIME")


def test_v5_challenger_excludes_all_pre_cutoff_history():
    rows = [
        _row(ts="2026-09-11T08:29:59+00:00", score=99, regime="TREND_UP", pnl=5.0),
        _row(ts="2026-09-11T08:30:01+00:00", score=90, regime="TREND_UP", pnl=1.0),
        _row(ts="2026-09-11T08:31:00+00:00", score=75, regime="TREND_DOWN", pnl=-1.0),
        _row(ts="2026-09-11T08:32:00+00:00", score=90, regime="LOW_VOLATILITY", pnl=-1.0),
    ]

    report = build_v5_challenger_report(rows)

    assert report["baseline_future"]["n"] == 3
    assert report["challenger_future"]["n"] == 1
    assert report["challenger_future"]["total_r"] == 1.0
    assert report["rejected_reasons"] == {"NON_TREND_REGIME": 1, "SCORE_BELOW_80": 1}
    assert report["policy_locked"] is True
    assert report["changes_v4_execution"] is False
    assert report["live_capital_allowed"] is False


def test_v5_challenger_is_exposed_but_cannot_unlock_capital():
    proof = build_validation_proof(
        paper_rows=[_row(ts="2026-09-11T09:00:00+00:00", score=90, regime="TREND_DOWN", pnl=1.0)],
        opportunity_rows=[],
        outcome_rows=[],
    )

    challenger = proof["perp_v5_challenger"]
    assert challenger["mode"] == "FORWARD_SHADOW_COHORT_ONLY"
    assert challenger["challenger_future"]["n"] == 1
    assert challenger["retuning_allowed"] is False
    assert challenger["live_capital_allowed"] is False
    assert proof["live_capital_allowed"] is False
