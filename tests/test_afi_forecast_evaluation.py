from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.backtest.forecast_evaluation import (
    Forecast,
    ForecastEvidenceRefused,
    Observation,
    Outcome,
    ReplayWindow,
    forecast_fingerprint,
    score_forecasts,
    select_asof,
    walk_forward_plan,
)

T=datetime(2026,1,10,tzinfo=UTC)


def forecast(index=0,**kwargs):
    issued=T+timedelta(days=index)
    f=Forecast(f"f{index}","US_EQUITY:AAPL","US_EQUITY","1D",issued,issued+timedelta(days=1),
               issued-timedelta(hours=2),issued-timedelta(hours=1),issued-timedelta(minutes=30),
               100.,110.,"fixture-model","v1","fixture-data","a"*64,"b"*64,"SYNTHETIC",.8,105.,115.,.8)
    return replace(f,**kwargs)


def outcome(f,price=120.,**kwargs):
    return replace(Outcome(f.forecast_id,f.asset_id,f.asset_class,f.target_at,f.target_at,
                           f.target_at+timedelta(hours=1),price,"fixture-source","r1",f.evidence_class),**kwargs)


def observation(index=0,**kwargs):
    return replace(Observation(f"o{index}","US_EQUITY:AAPL","US_EQUITY",T,T+timedelta(hours=1),100.,"fixture","v1"),**kwargs)


def select(rows,**kwargs):
    return select_asof(rows,asset_id="US_EQUITY:AAPL",asset_class="US_EQUITY",cutoff=T+timedelta(hours=2),max_age=timedelta(days=1),**kwargs)


def test_asof_ignores_later_published_revisions():
    old=observation()
    corrected=observation(1,available_at=T+timedelta(days=1),value=200.,revision="v2")
    assert select([corrected,old])["record"]==old
    assert select_asof([old,corrected],asset_id=old.asset_id,asset_class=old.asset_class,
                       cutoff=T+timedelta(days=1),max_age=timedelta(days=2))["record"]==corrected


@pytest.mark.parametrize("rows", [[],[observation(available_at=T+timedelta(days=1))],[observation(observed_at=T+timedelta(days=1),available_at=T+timedelta(days=1))]])
def test_missing_or_future_asof_evidence_is_insufficient(rows):
    result=select(rows)
    assert result["status"]=="INSUFFICIENT_EVIDENCE" and result["record"] is None


def test_stale_and_different_asset_cannot_be_substituted():
    assert select([observation(observed_at=T-timedelta(days=2))])["reason"]=="STALE_OBSERVATION"
    assert select([observation(asset_id="CRYPTO:BTC",asset_class="CRYPTO")])["record"] is None


@pytest.mark.parametrize("rows", [[observation(),observation()], [observation(),observation(1)], [observation(available_at=T-timedelta(seconds=1))]])
def test_repeated_ambiguous_or_impossible_asof_evidence_refused(rows):
    with pytest.raises(ForecastEvidenceRefused):select(rows)


@pytest.mark.parametrize("kwargs", [{"value":True},{"value":float("nan")},{"observed_at":datetime(2026,1,10)}, # noqa: DTZ001 - intentionally invalid fixture
 {"source_id":""},{"asset_class":"FUTURES"}])
def test_invalid_asof_contract(kwargs):
    with pytest.raises(ForecastEvidenceRefused):select([observation(**kwargs)])


def test_freshness_boundary_inclusive_and_timezone_normalized():
    o=observation()
    result=select_asof([o],asset_id=o.asset_id,asset_class=o.asset_class,cutoff=T+timedelta(days=1),max_age=timedelta(days=1))
    assert result["record"]==o
    same=replace(o,observed_at=T.astimezone(timezone(timedelta(hours=-6))))
    assert select([same])["record"]==same


def test_walk_forward_purges_unmatured_overlapping_labels_and_embargo():
    rows=[ReplayWindow(f"w{i}",T+timedelta(days=i),T+timedelta(days=i+2),T+timedelta(days=i+2,hours=1)) for i in range(7)]
    result=walk_forward_plan(rows,embargo=timedelta(hours=1))
    assert result["folds"][0]["status"]=="INSUFFICIENT_EVIDENCE"
    by_id={w.case_id:w for w in rows}
    for fold in result["folds"]:
        cutoff=datetime.fromisoformat(fold["label_cutoff_exclusive"])
        assert not set(fold["train_ids"]) & set(fold["test_ids"])
        for identity in fold["train_ids"]:
            assert by_id[identity].outcome_available_at < cutoff
            assert by_id[identity].target_at < cutoff
    assert result["production_approved"] is False and result["model_fitted"] is False
    assert walk_forward_plan(list(reversed(rows)))==walk_forward_plan(rows)


def test_equal_time_labels_and_unknown_outcomes_never_train():
    rows=[ReplayWindow(f"w{i}",T+timedelta(days=i),T+timedelta(days=i+1),T+timedelta(days=i+1)) for i in range(5)]
    result=walk_forward_plan(rows)
    assert "w1" not in result["folds"][0]["train_ids"]
    result=walk_forward_plan([replace(w,outcome_available_at=None) for w in rows])
    assert all(not f["train_ids"] for f in result["folds"])


@pytest.mark.parametrize("kwargs", [{"min_train":True},{"test_size":0},{"embargo":timedelta(seconds=-1)}])
def test_invalid_walkforward_requirements(kwargs):
    with pytest.raises(ForecastEvidenceRefused):walk_forward_plan([],**kwargs)


def test_invalid_or_duplicate_windows_refused_and_plan_bounded():
    w=ReplayWindow("x",T,T+timedelta(days=1),None)
    for rows in ([w,w],[replace(w,target_at=T)],[replace(w,outcome_available_at=T)]):
        with pytest.raises(ForecastEvidenceRefused):walk_forward_plan(rows)
    large=[replace(w,case_id=f"x{i}",issued_at=T+timedelta(days=i),target_at=T+timedelta(days=i+1)) for i in range(140)]
    with pytest.raises(ForecastEvidenceRefused,match="128"):walk_forward_plan(large)


def test_known_scoring_values_and_paired_baselines():
    a=forecast();b=forecast(1,point=90.,probability_up=.2,lower=85.,upper=95.)
    result=score_forecasts([a,b],[outcome(a),outcome(b,80.)],asof=T+timedelta(days=4),minimum_samples=2)
    c=result["cohorts"][0]
    assert c["n"]==2 and c["mae"]==c["rmse"]==10.
    assert c["no_change_mae"]==20. and c["directional_accuracy"]==1.
    assert c["brier"]==pytest.approx(.04)
    assert c["expected_calibration_error"]==pytest.approx(.2)
    assert c["uninformative_half_probability_brier"]==.25
    assert c["interval_coverage"]==0. and c["mean_interval_width"]==10.
    assert c["mean_interval_score"]==pytest.approx(60.)
    assert result["status"]=="DIAGNOSTIC_ONLY"
    assert result["calibration_established"] is result["dataset_authenticated"] is result["production_approved"] is result["trading_authority"] is False


def test_unmatured_missing_and_unavailable_outcomes_not_scored():
    a=forecast();b=forecast(1);c=forecast(2)
    result=score_forecasts([a,b,c],[outcome(a),outcome(b,available_at=T+timedelta(days=10))],asof=T+timedelta(days=4))
    assert (result["scored_n"],result["pending_n"])==(1,2)
    assert result["status"]=="INSUFFICIENT_EVIDENCE"
    pending=score_forecasts([a],[outcome(a)],asof=T+timedelta(hours=12))
    assert pending["cohorts"][0]["mae"] is None and pending["scored_n"]==0


def test_flat_direction_binary_definition_and_absent_uncertainty():
    a=forecast(point=100.,probability_up=0.,lower=None,upper=None,interval_level=None)
    c=score_forecasts([a],[outcome(a,100.)],asof=T+timedelta(days=2))["cohorts"][0]
    assert c["flat_outcome_n"]==1 and c["directional_accuracy"]==1. and c["brier"]==0.
    assert c["interval_coverage"] is None
    a=replace(a,probability_up=None)
    assert score_forecasts([a],[outcome(a)],asof=T+timedelta(days=2))["cohorts"][0]["brier"] is None


@pytest.mark.parametrize("kwargs", [
    {"point":True},{"point":float("nan")},{"reference_price":0},{"probability_up":True},
    {"probability_up":1.1},{"lower":None},{"lower":112.},{"interval_level":1.},
    {"target_at":T},{"training_available_through":T+timedelta(seconds=1)},
    {"input_available_at":T+timedelta(seconds=1)},{"input_observed_at":T},
    {"horizon":"2Q"},{"dataset_sha256":"bad"},{"code_sha256":"x"*64},
    {"issued_at":datetime(2026,1,10)}, # noqa: DTZ001 - intentionally invalid fixture{"evidence_class":"PRODUCTION_APPROVED"},
])
def test_invalid_or_leaking_forecasts_refused(kwargs):
    f=forecast(**kwargs)
    with pytest.raises(ForecastEvidenceRefused):score_forecasts([f],[],asof=T+timedelta(days=4))


@pytest.mark.parametrize("kwargs", [{"asset_id":"MSFT"},{"asset_class":"ETF"},{"observed_at":T},{"available_at":T},{"price":True},{"price":float("inf")},{"source_id":""},{"evidence_class":"PROSPECTIVE"}])
def test_invalid_target_or_outcome_provenance(kwargs):
    f=forecast()
    with pytest.raises(ForecastEvidenceRefused):score_forecasts([f],[outcome(f,**kwargs)],asof=T+timedelta(days=4))


def test_duplicate_ids_cases_and_outcomes_refuse_inflated_samples():
    a=forecast();o=outcome(a)
    for forecasts,outcomes in [([a,a],[o]),([a,replace(a,forecast_id="other")],[o]),([a],[o,o]),([a],[replace(o,forecast_id="unknown")])]:
        with pytest.raises(ForecastEvidenceRefused):score_forecasts(forecasts,outcomes,asof=T+timedelta(days=4))


def test_asset_horizon_model_dataset_and_evidence_are_not_pooled():
    a=forecast();variants=[{}, {"asset_id":"ETF:SPY","asset_class":"ETF"},{"asset_id":"CRYPTO:BTC","asset_class":"CRYPTO"},{"horizon":"1W"},{"model_version":"v2"},{"dataset_sha256":"c"*64},{"evidence_class":"HISTORICAL"},{"interval_level":.9}]
    forecasts=[replace(a,forecast_id=f"f{i}",**changes) for i,changes in enumerate(variants)]
    result=score_forecasts(forecasts,[outcome(f) for f in forecasts],asof=T+timedelta(days=4))
    assert len(result["cohorts"])==len(forecasts)
    assert all(c["n"]==1 for c in result["cohorts"])


def test_fingerprint_is_immutable_revision_sensitive_and_timezone_stable():
    f=forecast();fingerprint=forecast_fingerprint(f)
    assert len(fingerprint)==64
    with pytest.raises(FrozenInstanceError): f.point=99.
    assert forecast_fingerprint(replace(f,point=111.))!=fingerprint
    assert forecast_fingerprint(replace(f,issued_at=T.astimezone(timezone(timedelta(hours=-5)))))==fingerprint


def test_missing_evidence_never_becomes_zero_error_or_calibrated():
    result=score_forecasts([],[],asof=T)
    assert result["status"]=="INSUFFICIENT_EVIDENCE" and result["cohorts"]==[]
    with pytest.raises(ForecastEvidenceRefused):score_forecasts([],[],asof=T,minimum_samples=True)


def test_replay_and_scores_are_order_independent():
    a=forecast();b=forecast(1)
    assert score_forecasts([a,b],[outcome(a),outcome(b)],asof=T+timedelta(days=4))==score_forecasts([b,a],[outcome(b),outcome(a)],asof=T+timedelta(days=4))



def test_unresolved_cohort_preserves_metric_schema():
    a=forecast()
    unresolved=score_forecasts([a],[],asof=T+timedelta(days=2))["cohorts"][0]
    resolved=score_forecasts([a],[outcome(a)],asof=T+timedelta(days=2))["cohorts"][0]
    assert set(unresolved)==set(resolved)
    assert unresolved["expected_calibration_error"] is None


def test_numeric_overflow_refuses_instead_of_infinite_error():
    a=forecast(point=1e308,lower=None,upper=None,interval_level=None)
    with pytest.raises(ForecastEvidenceRefused):score_forecasts([a],[outcome(a)],asof=T+timedelta(days=2))
