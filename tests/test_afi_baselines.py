from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.backtest.forecast_baselines import (
    fit_baseline,
    model_fingerprint,
    predict_baseline,
)
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from test_afi_dataset_integrity import encode, fixture

ASOF = datetime(2026,10,20,tzinfo=UTC)
ASSET = "CRYPTO:BTC-USD"


def history():
    import hashlib
    m,p=fixture();a=m["assets"][0]
    a.update(asset_id=ASSET,asset_class="CRYPTO",timezone="UTC",calendar="CRYPTO_24_7",freshness_seconds=172800)
    p["universe"][0]["asset_id"]=ASSET
    start=datetime(2026,9,10,tzinfo=UTC)
    p["records"]=[{**p["records"][0],"record_id":f"r{i}","asset_id":ASSET,
                   "observed_at":(start+timedelta(days=i)).isoformat(),
                   "available_at":(start+timedelta(days=i)).isoformat(),
                   "raw_price":100+i+(i%3),"value":100+i+(i%3)} for i in range(40)]
    m.update(period_start=p["records"][0]["observed_at"],period_end=p["records"][-1]["observed_at"],
             acquired_at=p["records"][-1]["available_at"],generated_at=p["records"][-1]["available_at"],record_count=40)
    raw=encode(p);m["content_sha256"]=hashlib.sha256(raw).hexdigest()
    return review_dataset(encode(m),raw,asof=ASOF)


def fit(review=None,**kwargs):
    options={"asset_id":ASSET,"issued_at":datetime(2026,10,1,0,1,tzinfo=UTC),"evidence_asof":ASOF,"lookback":5}
    return fit_baseline(review or history(),**{**options,**kwargs})


@pytest.mark.parametrize("method",["NO_CHANGE","ENDPOINT_DRIFT"])
@pytest.mark.parametrize("horizon",["1D","5D"])
def test_deterministic_fit_forecast_and_training_provenance(method,horizon):
    r=history();model=fit(r,method=method,horizon=horizon)
    assert model==fit(r,method=method,horizon=horizon)
    assert len(model.training)==5 and max(x.available_at for x in model.training)<=model.issued_at
    assert model_fingerprint(model)==model_fingerprint(fit(r,method=method,horizon=horizon))
    f=predict_baseline(model,r,evidence_asof=ASOF)
    steps=1 if horizon=="1D" else 5
    assert f.point==model.reference_price+steps*model.drift_per_session
    assert f.target_at==datetime(2026,10,1,tzinfo=UTC)+timedelta(days=steps)
    assert not model.production_approved and f.evidence_class=="SYNTHETIC"


def test_future_prices_cannot_change_parameters_or_point():
    import hashlib
    import json
    r=history();m=json.loads(r.manifest_bytes);p=json.loads(r.payload_bytes)
    for row in p["records"]:
        if datetime.fromisoformat(row["observed_at"])>datetime(2026,10,1,0,1,tzinfo=UTC):row.update(raw_price=10000,value=10000)
    raw=encode(p);m["content_sha256"]=hashlib.sha256(raw).hexdigest()
    changed=review_dataset(encode(m),raw,asof=ASOF)
    a,b=fit(r,method="ENDPOINT_DRIFT"),fit(changed,method="ENDPOINT_DRIFT")
    assert a.training_sha256==b.training_sha256
    assert a.reference_price==b.reference_price and a.drift_per_session==b.drift_per_session
    assert predict_baseline(a,r,evidence_asof=ASOF).point==predict_baseline(b,changed,evidence_asof=ASOF).point
    assert model_fingerprint(a)!=model_fingerprint(b)  # full dataset lineage changed


@pytest.mark.parametrize("change",[{"lookback":1},{"lookback":True},{"lookback":10001},{"lookback":999},
                                    {"method":"MAGIC"},{"horizon":"1W"},{"asset_id":"CRYPTO:UNKNOWN"},
                                    {"issued_at":ASOF+timedelta(days=1)}])
def test_unaccepted_model_inputs_refuse(change):
    with pytest.raises(ForecastEvidenceRefused):fit(**change)


@pytest.mark.parametrize("change",[{"reference_price":1},{"drift_per_session":100},{"training_sha256":"a"*64},
                                    {"implementation_sha256":"a"*64},{"production_approved":True}])
def test_artifact_substitution_refuses_before_prediction(change):
    r=history();m=fit(r)
    with pytest.raises(ForecastEvidenceRefused):predict_baseline(replace(m,**change),r,evidence_asof=ASOF)


def test_late_training_record_cannot_be_used_or_silently_imputed():
    import hashlib
    import json
    r=history();m=json.loads(r.manifest_bytes);p=json.loads(r.payload_bytes)
    p["records"][19]["available_at"]="2026-10-10T00:00:00+00:00"
    raw=encode(p);m["content_sha256"]=hashlib.sha256(raw).hexdigest()
    r=review_dataset(encode(m),raw,asof=ASOF)
    with pytest.raises(ForecastEvidenceRefused,match="missing session"):fit(r)


def test_reordered_dataset_training_is_deterministic():
    import hashlib
    import json
    r=history();m=json.loads(r.manifest_bytes);p=json.loads(r.payload_bytes);p["records"].reverse()
    raw=encode(p);m["content_sha256"]=hashlib.sha256(raw).hexdigest();other=review_dataset(encode(m),raw,asof=ASOF)
    assert fit(r).training==fit(other).training
    assert fit(r).training_sha256==fit(other).training_sha256
