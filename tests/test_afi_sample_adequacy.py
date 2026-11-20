"""Synthetic adequacy checks never certify independent real-world samples."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from app.backtest.forecast_baselines import fingerprint
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_holdout_readiness import prepare_holdout_readiness
from app.backtest.forecast_sample_adequacy import assess_holdout_sample
from test_afi_holdout_readiness import ASOF as HISTORY_ASOF
from test_afi_holdout_readiness import FREEZE as HISTORY_FREEZE
from test_afi_holdout_readiness import cases

FREEZE = datetime(2026, 10, 19, tzinfo=UTC)
ASOF = datetime(2026, 10, 30, tzinfo=UTC)


def plan(*, assets=("US_EQUITY:A", "ETF:B"), overlap=False, excluded=False, all_excluded=False):
    cases = []
    for i, asset in enumerate(("US_EQUITY:S", *assets)):
        selection = i == 0
        issue = FREEZE - timedelta(days=3) if selection else FREEZE + timedelta(days=i)
        target = issue + timedelta(days=2)
        if overlap and i == 2:
            asset = assets[0]
            issue = FREEZE + timedelta(days=1, hours=12)
            target = issue + timedelta(days=2)
        cases.append({"forecast_sha256": f"{i + 1:064x}",
                      "partition": "SELECTION" if selection else "HOLDOUT",
                      "cohort": {"asset_class": asset.split(":")[0], "asset_id": asset,
                                 "horizon": "1D", "source_id": "fixture", "model": "baseline",
                                 "model_version": "v1", "model_configuration_sha256": None,
                                 "forecast_dataset_id": "fixture-v1", "release_source_sha256": None},
                      "issued_at": issue.isoformat(), "target_at": target.isoformat(),
                      "window_status": "PARTIAL" if i and (all_excluded or excluded and i == 2) else "COMPLETE",
                      "outcome_status": "PENDING" if i and (all_excluded or excluded and i == 2) else "RESOLVED",
                      "exclusion_reason": "OBSERVATION_PARTIAL" if i and (all_excluded or excluded and i == 2) else None})
    base = {"schema": "AFI_OFFLINE_HOLDOUT_READINESS_V1", "frozen_at": FREEZE.isoformat(),
            "asof": ASOF.isoformat(), "cases": cases, "selection_n": 1,
            "holdout_n": len(assets), "holdout_mature_n": 0 if all_excluded else len(assets) - int(excluded),
            "selection_partition_sha256": fingerprint([cases[0]["forecast_sha256"]]),
            "holdout_partition_sha256": fingerprint(sorted(c["forecast_sha256"] for c in cases[1:])),
            "authoritative_scored_n": 0, "sample_minimum_approved": False,
            "holdout_independently_unseen": False,
            "dataset_freeze_independently_witnessed": False}
    return {**base, "protocol_sha256": fingerprint(base)}


def hits(value):
    return {row["forecast_sha256"]: i % 2 == 0 for i, row in enumerate(value["cases"][1:])
            if row["exclusion_reason"] is None}


def test_diverse_synthetic_plan_has_only_assumption_bound_interval():
    value = plan()
    one = assess_holdout_sample(value, diagnostic_hits=hits(value))
    assert one == assess_holdout_sample(deepcopy(value), diagnostic_hits=hits(value))
    assert one["eligible_n"] == one["distinct_observation_n"] == 2
    assert one["max_asset_share"] == .5
    assert one["interval"]["status"] == "ASSUMPTION_BOUND_DIAGNOSTIC_ONLY"
    assert one["interval"]["lower"] < one["interval"]["upper"]
    assert not one["independent_samples_established"] and not one["production_approved"]


def test_real_stage20_plan_contract_round_trip(tmp_path):
    selection, holdout = cases(tmp_path)
    actual = prepare_holdout_readiness([selection], [holdout], frozen_at=HISTORY_FREEZE,
                                       evidence_asof=HISTORY_ASOF)
    result = assess_holdout_sample(actual)
    assert result["holdout_n"] == 1 and result["eligible_n"] == 0
    assert result["interval"] is None and result["authoritative_scored_n"] == 0


@pytest.mark.parametrize("kwargs,status", [
    ({"all_excluded": True}, "NO_ELIGIBLE_CASES"),
    ({"assets": ("US_EQUITY:A",)}, "STRUCTURAL_DEPENDENCE_OR_CONCENTRATION"),
    ({"assets": ("US_EQUITY:A", "US_EQUITY:A"), "overlap": True}, "STRUCTURAL_DEPENDENCE_OR_CONCENTRATION"),
    ({"excluded": True}, "STRUCTURAL_DEPENDENCE_OR_CONCENTRATION"),
])
def test_tiny_empty_correlated_and_missing_refuse_interval(kwargs, status):
    value = plan(**kwargs)
    result = assess_holdout_sample(value, diagnostic_hits=hits(value))
    assert result["status"] == status and result["interval"] is None
    assert result["effective_sample_n"] is None and result["authoritative_scored_n"] == 0


def test_missing_outcome_excluded_from_denominator():
    value = plan(excluded=True)
    result = assess_holdout_sample(value)
    assert result["holdout_n"] == 2 and result["eligible_n"] == 1
    assert result["excluded_n"] == 1
    assert result["exclusion_counts"] == {"OBSERVATION_PARTIAL": 1}


def test_different_horizons_never_pool_binary_interval():
    value = plan()
    value["cases"][2]["cohort"]["horizon"] = "5D"
    value["protocol_sha256"] = fingerprint({k: v for k, v in value.items() if k != "protocol_sha256"})
    result = assess_holdout_sample(value, diagnostic_hits=hits(value))
    assert result["horizon_counts"] == {"1D": 1, "5D": 1}
    assert result["interval_cohort_n"] == 2 and result["interval"] is None


@pytest.mark.parametrize("change", ["commitment", "authority", "duplicate", "partition", "source", "nonfinite-hit", "missing-hit"])
def test_malformed_or_contaminated_plan_refuses(change):
    value = plan()
    outcomes = hits(value)
    if change == "commitment":
        value["holdout_mature_n"] = 500
    elif change == "authority":
        value["sample_minimum_approved"] = True
    elif change == "duplicate":
        value["cases"][2]["forecast_sha256"] = value["cases"][1]["forecast_sha256"]
    elif change == "partition":
        value["cases"][1]["partition"] = "SELECTION"
    elif change == "source":
        value["cases"][1]["cohort"]["source_id"] = None
    elif change == "nonfinite-hit":
        outcomes[value["cases"][1]["forecast_sha256"]] = float("nan")
    else:
        outcomes.pop(value["cases"][1]["forecast_sha256"])
    with pytest.raises(ForecastEvidenceRefused):
        assess_holdout_sample(value, diagnostic_hits=outcomes)


def test_repeated_target_across_models_refuses_even_if_commitment_is_recomputed():
    value = plan(assets=("US_EQUITY:A", "US_EQUITY:A"))
    value["cases"][2]["target_at"] = value["cases"][1]["target_at"]
    value["protocol_sha256"] = fingerprint({k: v for k, v in value.items() if k != "protocol_sha256"})
    with pytest.raises(ForecastEvidenceRefused, match="Repeated observation"):
        assess_holdout_sample(value)


@pytest.mark.parametrize("nested,expected", [(True, 2), (False, 0)])
def test_overlap_checks_all_prior_windows_and_preserves_touching_boundary(nested, expected):
    value = plan(assets=("US_EQUITY:A",) * 3)
    spans = [(1, 9), (2, 3), (4, 5)] if nested else [(1, 2), (2, 3), (3, 4)]
    for row, (start, end) in zip(value["cases"][1:], spans, strict=True):
        row["issued_at"] = (FREEZE + timedelta(days=start)).isoformat()
        row["target_at"] = (FREEZE + timedelta(days=end)).isoformat()
    value["protocol_sha256"] = fingerprint({k: v for k, v in value.items() if k != "protocol_sha256"})
    result = assess_holdout_sample(value, diagnostic_hits=hits(value))
    assert result["overlapping_window_n"] == expected
    assert result["authoritative_scored_n"] == 0
    assert result["independent_samples_established"] is False
    value["cases"].reverse()
    value["protocol_sha256"] = fingerprint({k: v for k, v in value.items() if k != "protocol_sha256"})
    reordered = assess_holdout_sample(value)
    assert reordered["overlapping_window_n"] == expected


@pytest.mark.parametrize("damage", ["target-after-freeze", "partial-selection", "pending-selection", "excluded-selection"])
def test_recommitted_selection_cannot_leak_unavailable_labels(damage):
    value = plan()
    selected = value["cases"][0]
    if damage == "target-after-freeze":
        selected["target_at"] = (FREEZE + timedelta(days=2)).isoformat()
    elif damage == "partial-selection":
        selected["window_status"] = "PARTIAL"
    elif damage == "pending-selection":
        selected["outcome_status"] = "PENDING"
    else:
        selected["exclusion_reason"] = "PUBLICATION_ORDER_UNVERIFIED"
    value["protocol_sha256"] = fingerprint({k: v for k, v in value.items() if k != "protocol_sha256"})
    with pytest.raises(ForecastEvidenceRefused, match="Selection"):
        assess_holdout_sample(value)


@pytest.mark.parametrize("state", ["IMMATURE", "PARTIAL", "MISSING", "CONTRADICTORY", "UNVERIFIED"])
def test_every_incomplete_window_remains_in_holdout_denominator(state):
    value = plan()
    row = value["cases"][2]
    row["window_status"] = state
    value["holdout_mature_n"] = 1
    value["protocol_sha256"] = fingerprint({k: v for k, v in value.items() if k != "protocol_sha256"})
    result = assess_holdout_sample(value)
    assert result["holdout_n"] == result["eligible_n"] + result["excluded_n"] == 2
    assert result["eligible_n"] == 1
    assert result["exclusion_counts"] == {state: 1}
    assert result["authoritative_scored_n"] == 0
