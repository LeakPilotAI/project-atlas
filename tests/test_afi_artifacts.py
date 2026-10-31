import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from app.backtest.forecast_artifacts import (
    audit_expected_history,
    publish_forecast,
    read_forecast,
)
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from test_afi_baselines import ASOF, fit, history


def test_exclusive_idempotent_publication_readback_and_expected_history(tmp_path):
    r=history();m=fit(r);p=publish_forecast(tmp_path,r,m,evidence_asof=ASOF);raw=p.read_bytes()
    assert read_forecast(p,r,evidence_asof=ASOF)["production_approved"] is False
    assert publish_forecast(tmp_path,r,m,evidence_asof=ASOF)==p and p.read_bytes()==raw
    result=audit_expected_history(tmp_path,[p.stem,"a"*64],r,evidence_asof=ASOF)
    assert result["missing"]==["a"*64] and not result["history_completeness_verified"]


def test_concurrent_publication_never_truncates_evidence(tmp_path):
    r=history();m=fit(r)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures=[executor.submit(publish_forecast,tmp_path,r,m,evidence_asof=ASOF) for _ in range(2)]
        outcomes=[]
        for f in futures:
            try:outcomes.append(f.result())
            except ForecastEvidenceRefused:pass  # observing an in-progress partial file must refuse
    assert outcomes
    read_forecast(outcomes[0],r,evidence_asof=ASOF)


@pytest.mark.parametrize("failure",["write","partial","flush","fsync","parent"])
def test_required_persistence_failures_never_acknowledge_success(tmp_path,failure):
    r=history();m=fit(r)
    original_open=type(tmp_path).open
    class FaultStream:
        def __init__(self,handle):self.handle=handle
        def __enter__(self):return self
        def __exit__(self,*args):self.handle.close()
        def write(self,text):
            if failure=="write":raise OSError("write")
            if failure=="partial":self.handle.write(text[:10]);return 10
            return self.handle.write(text)
        def flush(self):
            if failure=="flush":raise OSError("flush")
            self.handle.flush()
        def fileno(self):return self.handle.fileno()
    def fault_open(path,*args,**kwargs):
        stream=original_open(path,*args,**kwargs)
        return FaultStream(stream) if args and args[0]=="x" else stream
    if failure in ("write","partial","flush"):
        context=patch.object(type(tmp_path),'open',fault_open)
    elif failure=="fsync":context=patch('app.backtest.forecast_artifacts.os.fsync',side_effect=OSError('fsync'))
    else:context=patch('app.backtest.forecast_artifacts.sync_parent',side_effect=OSError('parent'))
    with context,pytest.raises(OSError):publish_forecast(tmp_path,r,m,evidence_asof=ASOF)
    existing=list(tmp_path.glob('*.json'));assert len(existing)==1
    before=existing[0].read_bytes()
    if failure in ("write","partial"):
        with pytest.raises(ForecastEvidenceRefused):publish_forecast(tmp_path,r,m,evidence_asof=ASOF)
        assert existing[0].read_bytes()==before
    else:
        assert publish_forecast(tmp_path,r,m,evidence_asof=ASOF)==existing[0]


def test_corruption_unknown_fields_and_renaming_are_not_accepted(tmp_path):
    r=history();m=fit(r);p=publish_forecast(tmp_path,r,m,evidence_asof=ASOF);raw=p.read_bytes()
    p.write_bytes(raw.replace(b'"production_approved":false',b'"production_approved":true'))
    with pytest.raises(ForecastEvidenceRefused):read_forecast(p,r,evidence_asof=ASOF)
    p.write_bytes(raw[:-5])
    with pytest.raises(ForecastEvidenceRefused):read_forecast(p,r,evidence_asof=ASOF)


def test_hardlinked_output_is_refused(tmp_path):
    r=history();m=fit(r);p=publish_forecast(tmp_path,r,m,evidence_asof=ASOF)
    os.link(p,tmp_path/'alias')
    with pytest.raises(ForecastEvidenceRefused):publish_forecast(tmp_path,r,m,evidence_asof=ASOF)
    with pytest.raises(ForecastEvidenceRefused):read_forecast(p,r,evidence_asof=ASOF)

def test_interval_from_another_asset_cannot_authorize_forecast_artifact():
    import hashlib
    import json
    from datetime import UTC, datetime

    from app.backtest.forecast_artifacts import artifact_envelope
    from app.backtest.forecast_baselines import fit_baseline
    from app.backtest.forecast_dataset import review_dataset
    from app.backtest.forecast_replay import freeze_selection
    from app.backtest.forecast_uncertainty import fit_interval
    from test_afi_dataset_integrity import encode
    from test_afi_replay import issue
    from test_afi_uncertainty import CALIBRATION, FREEZE
    r=history();m=json.loads(r.manifest_bytes);p=json.loads(r.payload_bytes)
    second="CRYPTO:ETH-USD"
    m["assets"].append({**m["assets"][0],"asset_id":second})
    p["universe"].append({**p["universe"][0],"asset_id":second})
    p["records"] += [{**x,"asset_id":second,"record_id":"eth-"+x["record_id"]} for x in list(p["records"])]
    raw=encode(p);m.update(content_sha256=hashlib.sha256(raw).hexdigest(),record_count=len(p["records"]))
    r=review_dataset(encode(m),raw,asof=ASOF)
    selection=freeze_selection(r,asset_id="CRYPTO:BTC-USD",selection_issues=[issue(20),issue(21)],
                               frozen_at=issue(24),evidence_asof=ASOF,lookback=5)
    interval=fit_interval(r,selection,calibration_issues=CALIBRATION,calibrated_at=FREEZE,evidence_asof=ASOF)
    model=fit_baseline(r,asset_id=second,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=ASOF,
                       lookback=5,method=selection["selected_method"])
    with pytest.raises(ForecastEvidenceRefused):artifact_envelope(r,model,evidence_asof=ASOF,interval=interval)
