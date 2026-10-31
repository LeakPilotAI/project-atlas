import pytest
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import directional_diagnostics


def row(point,actual,asset="CRYPTO:BTC-USD"):
    return {"asset_class":"CRYPTO","asset_id":asset,"horizon":"1D","model":"fixture","reference":100,"forecast_point":point,"actual":actual,"status":"RESOLVED" if actual is not None else "FORECAST_ONLY"}


def test_three_direction_matrix_and_false_positives_are_explicit():
    d=directional_diagnostics([row(110,120),row(110,90),row(110,100),row(90,120),row(100,100)])
    c=d["cohorts"][0]
    assert c["matrix"]["UP"]=={"DOWN":1,"FLAT":1,"UP":1}
    assert c["up"]["precision"]==1/3 and c["up"]["recall"]==.5
    assert c["up"]["false_positive_n"]==2 and c["up"]["false_negative_n"]==1
    assert c["correct_n"]==2 and c["directional_accuracy"]==.4
    assert not d["trade_opportunity_or_profitability_established"]


def test_pending_never_becomes_negative_or_zero_error_and_empty_denominators_refuse_precision():
    c=directional_diagnostics([row(110,None),row(90,None)])["cohorts"][0]
    assert c["pending_n"]==2 and c["resolved_n"]==0 and c["directional_accuracy"] is None
    assert c["up"]["precision"] is None and c["down"]["recall"] is None
    assert c["up"]["false_positive_n"]==0 and c["status"]=="INSUFFICIENT_EVIDENCE"


def test_assets_are_not_pooled_and_flat_baseline_is_not_an_up_prediction():
    d=directional_diagnostics([row(100,110),row(110,110,"CRYPTO:ETH-USD")])
    assert len(d["cohorts"])==2
    btc,eth=d["cohorts"]
    assert btc["matrix"]["FLAT"]["UP"]==1 and btc["up"]["precision"] is None
    assert eth["up"]["precision"]==1 and eth["resolved_n"]==1


@pytest.mark.parametrize("field,value",[("actual",float("nan")),("forecast_point",True),("reference",0),("status","UNKNOWN")])
def test_invalid_directional_evidence_refuses(field,value):
    r=row(110,120);r[field]=value
    with pytest.raises(ForecastEvidenceRefused):directional_diagnostics([r])
