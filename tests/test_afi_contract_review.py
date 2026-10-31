from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.backtest.forecast_evaluation import (
    Forecast,
    Observation,
    Outcome,
    forecast_fingerprint,
    score_forecasts,
    select_asof,
)

T = datetime(2026,10,19,20,tzinfo=UTC)


def forecast(**kwargs):
    f=Forecast("f1","US_EQUITY:AAPL","US_EQUITY","1D",T+timedelta(minutes=1),T+timedelta(days=1),T,T,T,
               100.,110.,"fixture-model","v1","fixture-data","a"*64,"b"*64,"SYNTHETIC",.8,90.,120.,.8)
    return replace(f,**kwargs)


def test_asset_class_cannot_conflict_with_asset_identity():
    with pytest.raises(ValueError):forecast_fingerprint(forecast(asset_class="ETF"))


def test_reusing_revision_identity_for_changed_history_is_refused():
    a=Observation("a","US_EQUITY:AAPL","US_EQUITY",T,T,100.,"fixture","v1")
    b=replace(a,record_id="b",available_at=T+timedelta(hours=1),value=120.)
    with pytest.raises(ValueError):
        select_asof([a,b],asset_id=a.asset_id,asset_class=a.asset_class,cutoff=T+timedelta(hours=2),max_age=timedelta(days=1))


def test_relative_error_and_same_sample_baseline_reported_without_skill_grant():
    f=forecast();o=Outcome(f.forecast_id,f.asset_id,f.asset_class,f.target_at,f.target_at,f.target_at,120.,"fixture","v1","SYNTHETIC")
    r=score_forecasts([f],[o],asof=T+timedelta(days=2))
    c=r["cohorts"][0]
    assert c["mape_percent"]==pytest.approx(100*10/120)
    assert c["mae_ratio_to_no_change"]==.5
    assert c["status"]=="INSUFFICIENT_EVIDENCE"
    assert r["calibration_established"] is False
