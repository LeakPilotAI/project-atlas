from datetime import datetime, timezone

from app.investment.historical_validation import build_historical_validation


def _obs(i, cls="WATCH", score=50, evidence="MEDIUM", thesis="INTACT"):
    return {
        "observation_id": f"o{i}",
        "symbol": f"S{i}",
        "as_of": "2026-09-09T12:00:00+00:00",
        "classification": cls,
        "research": {
            "opportunity_score": score,
            "evidence_quality": evidence,
            "thesis": thesis,
        },
    }


def _outcome(i, **returns):
    return {
        "observation_id": f"o{i}",
        "symbol": f"S{i}",
        "enriched_at": "2026-09-10T12:00:00+00:00",
        "look_ahead_protected": True,
        **returns,
    }


def test_historical_validation_joins_by_observation_id_and_reports_horizons():
    report = build_historical_validation(
        [_obs(1), _obs(2)],
        [_outcome(1, return_1d=0.10, return_20d=0.20), _outcome(2, return_1d=-0.05, return_20d=0.10)],
        now=datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    )
    assert report["matched_observations"] == 2
    assert report["outcome_coverage"] == 1.0
    assert report["by_horizon"]["1d"]["n"] == 2
    assert report["by_horizon"]["20d"]["mean_return"] == 0.15


def test_historical_validation_keeps_classification_evidence_and_thesis_strata_separate():
    obs = [_obs(1, "ACCUMULATION", 80, "HIGH", "STRONG"), _obs(2, "WATCH", 40, "LOW", "UNDER_PRESSURE")]
    outs = [_outcome(1, return_20d=0.30), _outcome(2, return_20d=-0.10)]
    report = build_historical_validation(obs, outs)
    assert "ACCUMULATION" in report["by_classification"]
    assert "WATCH" in report["by_classification"]
    assert "HIGH" in report["by_evidence_quality"]
    assert "STRONG" in report["by_thesis"]


def test_score_signal_compares_high_and_low_scores_without_calling_score_probability():
    obs = [_obs(1, score=20), _obs(2, score=30), _obs(3, score=80), _obs(4, score=90)]
    outs = [
        _outcome(1, return_20d=-0.10),
        _outcome(2, return_20d=0.00),
        _outcome(3, return_20d=0.20),
        _outcome(4, return_20d=0.30),
    ]
    report = build_historical_validation(obs, outs)
    assert report["score_signal"]["20d"]["higher_score_outperformed"] is True
    assert report["score_is_probability"] is False


def test_freshness_flag_is_explicit_and_does_not_unlock_live_capital():
    report = build_historical_validation(
        [_obs(1)],
        [_outcome(1, return_1d=0.1)],
        now=datetime(2026, 9, 12, 12, tzinfo=timezone.utc),
        stale_after_hours=36,
    )
    assert report["research_stale"] is True
    assert report["strategy_frozen"] is True
    assert report["live_capital_allowed"] is False


def test_latest_outcome_row_wins_for_reenriched_observation():
    report = build_historical_validation(
        [_obs(1)],
        [
            {**_outcome(1, return_20d=0.10), "enriched_at": "2026-09-10T10:00:00+00:00"},
            {**_outcome(1, return_20d=0.25), "enriched_at": "2026-09-11T10:00:00+00:00"},
        ],
    )
    assert report["by_horizon"]["20d"]["mean_return"] == 0.25
