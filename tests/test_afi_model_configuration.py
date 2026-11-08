from dataclasses import replace
from datetime import timedelta

import pytest
from app.backtest.forecast_baselines import predict_baseline
from app.backtest.forecast_evaluation import (
    ForecastEvidenceRefused,
    forecast_fingerprint,
    score_forecasts,
)
from test_afi_baselines import ASOF, fit, history


def forecasts():
    review=history();return review,[predict_baseline(fit(review,method='ENDPOINT_DRIFT',lookback=n),review,evidence_asof=ASOF) for n in (5,10)]


def test_distinct_fitted_configuration_is_scored_separately():
    _,cases=forecasts();assert [f.point for f in cases]==[121.5,122.0]
    assert cases[0].model_configuration_sha256!=cases[1].model_configuration_sha256
    score=score_forecasts(cases,[],asof=ASOF);assert len(score['cohorts'])==2 and score['pending_n']==2
    assert all(c['n']==0 for c in score['cohorts'])


def test_configuration_is_stable_across_training_dates():
    r,cases=forecasts();model=fit(r,method='ENDPOINT_DRIFT',lookback=5,issued_at=cases[0].issued_at+timedelta(days=1))
    other=predict_baseline(model,r,evidence_asof=ASOF)
    assert cases[0].forecast_id!=other.forecast_id
    assert cases[0].model_configuration_sha256==other.model_configuration_sha256


@pytest.mark.parametrize('value',[True,'bad','z'*64])
def test_invalid_configuration_refuses(value):
    _,cases=forecasts()
    with pytest.raises(ForecastEvidenceRefused):forecast_fingerprint(replace(cases[0],model_configuration_sha256=value))


def test_same_configuration_case_cannot_change_id_to_add_sample():
    _,cases=forecasts()
    with pytest.raises(ForecastEvidenceRefused):score_forecasts([cases[0],replace(cases[0],forecast_id='another-id')],[],asof=ASOF)


def test_legacy_unknown_configuration_cannot_claim_independence_from_bound_case():
    _,cases=forecasts();legacy=replace(cases[0],forecast_id='legacy-id',model_configuration_sha256=None)
    with pytest.raises(ForecastEvidenceRefused):score_forecasts([legacy,cases[0]],[],asof=ASOF)



def test_frozen_preconfiguration_interval_and_outcome_chain_survive_readback():
    import hashlib
    import json
    from pathlib import Path

    from app.backtest.forecast_artifacts import read_forecast
    from app.backtest.forecast_outcomes import verify_outcome_history
    root=Path(__file__).parent/'fixtures/afi-legacy-v1';prov=json.loads((root/'configuration-compatibility-provenance.json').read_bytes())
    for name,digest in prov['hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
    f=root/'6d71c50f04f3873d1c1b6df090253f10a0fc05efe6c21104cd428973ad58df86.json';p=root/'a383937fb1a294f6740098d7bbc2369a42c94d7794f4712296a0533bd7a24cd0.json';r=history()
    raw=f.read_bytes();data=read_forecast(f,r,evidence_asof=ASOF)
    assert 'model_configuration_sha256' not in data['forecast'] and f.read_bytes()==raw
    checked=verify_outcome_history(f,r,evidence_asof=ASOF,history=[(p,r)],expected_head=json.loads(p.read_bytes())['artifact_sha256'])
    assert checked['records'][0]['status']=='RESOLVED'


@pytest.mark.parametrize('bound',[False,True])
def test_multi_configuration_actual_artifacts_report_and_viewer(tmp_path,bound):
    import json
    import subprocess
    from pathlib import Path

    import app
    from app.backtest.forecast_artifacts import publish_forecast, read_forecast
    from app.backtest.forecast_outcomes import append_outcome
    from app.backtest.forecast_report import (
        ForecastHistory,
        browser_export,
        build_accountability_report,
    )
    from app.backtest.forecast_source import package_source, review_source_archive
    r=history();source=None
    if bound:
        packages=tmp_path/'packages';packages.mkdir();manifest=package_source(Path(app.__file__).resolve().parent.parent,packages,release_id='configuration-test',include=['app/backtest/forecast_outcomes.py','app/backtest/forecast_report.py']);source=review_source_archive((packages/manifest['archive']).read_bytes())
    entries=[];original={}
    for lookback in (5,10):
        root=tmp_path/str(lookback);root.mkdir();m=fit(r,method='ENDPOINT_DRIFT',lookback=lookback,source_review=source)
        f=publish_forecast(root,r,m,evidence_asof=ASOF,source_review=source);original[f]=f.read_bytes()
        p,a=append_outcome(root,f,r,r,outcome_asof=ASOF,evidence_asof=ASOF,source_review=source,outcome_source=source)
        data=read_forecast(f,r,evidence_asof=ASOF,source_review=source);assert data['forecast']['model_configuration_sha256']
        entries.append(ForecastHistory(f,r,((p,r,source),),a['artifact_sha256'],source))
    report=build_accountability_report(entries,evidence_asof=ASOF)
    assert report['score_rows_contract']=='ROW_BOUND_SCORE_V2' and report['score']['scored_n']==2
    assert len(report['score']['cohorts'])==2 and all(c['n']==1 for c in report['score']['cohorts'])
    assert len(report['directional_diagnostics']['cohorts'])==2
    out=tmp_path/'viewer.json';out.write_text(browser_export(report),encoding='utf-8');viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const fs=require('node:fs'),c=require('node:crypto'),v=require(process.argv[1]);v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8'),t=>c.createHash('sha256').update(t).digest('hex')).then(r=>console.log(JSON.stringify(r.score.cohorts.map(c=>c.cohort.model_configuration_sha256)))).catch(e=>{console.error(e.message);process.exit(2)});"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(out)],capture_output=True,text=True,timeout=10,check=True)
    assert len(set(json.loads(checked.stdout)))==2
    assert all(f.read_bytes()==raw for f,raw in original.items())


@pytest.mark.parametrize('value',[None,'a'*64,True])
def test_rehashed_forged_configuration_artifact_refuses(tmp_path,value):
    import json

    from app.backtest.forecast_artifacts import artifact_envelope, read_forecast
    from app.backtest.forecast_baselines import fingerprint
    r=history();data=artifact_envelope(r,fit(r,method='ENDPOINT_DRIFT',lookback=5),evidence_asof=ASOF)
    data['forecast']['model_configuration_sha256']=value;data['artifact_sha256']=fingerprint({k:v for k,v in data.items() if k!='artifact_sha256'})
    path=tmp_path/(data['artifact_sha256']+'.json');path.write_text(json.dumps(data,sort_keys=True,separators=(',',':'),default=lambda v:v.isoformat())+'\n',encoding='utf-8')
    with pytest.raises(ForecastEvidenceRefused):read_forecast(path,r,evidence_asof=ASOF)
