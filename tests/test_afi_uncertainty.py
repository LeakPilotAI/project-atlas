from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_uncertainty import fit_interval, predict_interval
from test_afi_baselines import ASOF, history
from test_afi_replay import frozen, issue

CALIBRATION=[issue(25)+timedelta(days=i) for i in range(20)]
FREEZE=datetime(2026,10,16,tzinfo=UTC)


def interval():
    return fit_interval(history(),frozen(),calibration_issues=CALIBRATION,calibrated_at=FREEZE,evidence_asof=ASOF)


def test_finite_sample_interval_is_frozen_reproducible_and_not_a_coverage_claim():
    a=interval();assert a==interval() and a["n"]==20 and a["rank"]==17
    assert not a["exchangeability_established"] and not a["calibration_established"]
    f=predict_interval(history(),a,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=ASOF)
    assert f.lower<=f.point<=f.upper and f.interval_level==.8
    assert f==predict_interval(history(),a,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=ASOF)


@pytest.mark.parametrize("changes",[{"level":.999},{"level":0},{"level":True},
                                    {"calibration_issues":CALIBRATION[:3]},
                                    {"calibrated_at":datetime(2026,10,10,tzinfo=UTC)},
                                    {"calibration_issues":[issue(20)]+CALIBRATION}])
def test_insufficient_contaminated_or_nonfinite_quantile_refuses(changes):
    args={"calibration_issues":CALIBRATION,"calibrated_at":FREEZE,"evidence_asof":ASOF}
    with pytest.raises(ForecastEvidenceRefused):fit_interval(history(),frozen(),**{**args,**changes})


@pytest.mark.parametrize("key,value",[("absolute_error_quantile",0),("residuals_sha256","a"*64),
                                      ("production_approved",True),("n",200)])
def test_interval_substitution_refused(key,value):
    a=deepcopy(interval());a[key]=value
    with pytest.raises(ForecastEvidenceRefused):
        predict_interval(history(),a,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=ASOF)


def test_interval_cannot_retroactively_apply_before_calibration():
    with pytest.raises(ForecastEvidenceRefused):predict_interval(history(),interval(),issued_at=issue(30),evidence_asof=ASOF)

def test_calibration_uses_only_revision_known_before_calibration_freeze():
    import hashlib
    import json

    from app.backtest.forecast_dataset import review_dataset
    from app.backtest.forecast_replay import freeze_selection
    from test_afi_baselines import ASSET
    from test_afi_dataset_integrity import encode
    r=history();m=json.loads(r.manifest_bytes);p=json.loads(r.payload_bytes)
    row=p['records'][30]
    p['records'].append({**row,'record_id':'late-calibration-correction','revision':'v2','raw_price':8000,'value':8000,
                         'available_at':'2026-10-18T00:00:00+00:00'})
    raw=encode(p);m.update(content_sha256=hashlib.sha256(raw).hexdigest(),record_count=len(p['records']))
    revised=review_dataset(encode(m),raw,asof=ASOF)
    selection=freeze_selection(revised,asset_id=ASSET,selection_issues=[issue(20),issue(21)],frozen_at=issue(24),evidence_asof=ASOF,lookback=5)
    changed=fit_interval(revised,selection,calibration_issues=CALIBRATION,calibrated_at=FREEZE,evidence_asof=ASOF)
    assert changed['absolute_error_quantile']==interval()['absolute_error_quantile']
    assert changed['residuals_sha256']==interval()['residuals_sha256']
