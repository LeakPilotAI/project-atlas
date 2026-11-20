import hashlib
import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.backtest.forecast_artifacts import (
    artifact_bytes,
    artifact_envelope,
    publish_forecast,
    read_forecast,
)
from app.backtest.forecast_baselines import (
    PROBABILITY_METHOD,
    fit_baseline,
    predict_baseline,
    predict_probability_baseline,
)
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from test_afi_baselines import ASOF, ASSET, fit, history
from test_afi_dataset_integrity import encode


def reviewed_values(transform):
    source=history();manifest=json.loads(source.manifest_bytes);payload=json.loads(source.payload_bytes)
    for i,row in enumerate(payload['records']):
        value=transform(i,row);row.update(value=value,raw_price=value)
    raw=encode(payload);manifest['content_sha256']=hashlib.sha256(raw).hexdigest()
    return review_dataset(encode(manifest),raw,asof=ASOF)


@pytest.mark.parametrize('transform,up,down,flat,probability',[
    (lambda i,r:100+i,4,0,0,5/6),
    (lambda i,r:200-i,0,4,0,1/6),
    (lambda i,r:100,0,0,4,1/6),
])
def test_fixed_smoothed_counts_use_only_training_transitions(transform,up,down,flat,probability):
    review=reviewed_values(transform);model=fit(review);forecast,audit=predict_probability_baseline(model,review,evidence_asof=ASOF)
    assert (audit['transition_n'],audit['up_n'],audit['down_n'],audit['flat_n'])==(4,up,down,flat)
    assert forecast.probability_up==probability and audit['probability_up']==probability
    assert audit['alpha']==audit['beta']==1 and not audit['calibration_established']
    assert forecast.point==predict_baseline(model,review,evidence_asof=ASOF).point


def test_future_price_changes_cannot_change_training_probability():
    original=history();cutoff=datetime(2026,10,1,0,1,tzinfo=UTC)
    altered=reviewed_values(lambda i,r:9999 if datetime.fromisoformat(r['observed_at'])>cutoff else r['value'])
    a,aa=predict_probability_baseline(fit(original),original,evidence_asof=ASOF)
    b,bb=predict_probability_baseline(fit(altered),altered,evidence_asof=ASOF)
    assert a.probability_up==b.probability_up and aa['training_sha256']==bb['training_sha256']
    assert a.model_configuration_sha256==b.model_configuration_sha256 and a.forecast_id!=b.forecast_id


def test_unavailable_later_revision_does_not_enter_probability_training():
    source=history();manifest=json.loads(source.manifest_bytes);payload=json.loads(source.payload_bytes)
    late=dict(payload['records'][20],record_id='late-revision',available_at='2026-10-19T00:00:00Z',revision='v2',value=10000,raw_price=10000)
    payload['records'].append(late);manifest['record_count']=len(payload['records']);raw=encode(payload);manifest['content_sha256']=hashlib.sha256(raw).hexdigest()
    revised=review_dataset(encode(manifest),raw,asof=ASOF)
    a,aa=predict_probability_baseline(fit(source),source,evidence_asof=ASOF)
    b,bb=predict_probability_baseline(fit(revised),revised,evidence_asof=ASOF)
    assert a.probability_up==b.probability_up and aa['training_sha256']==bb['training_sha256']


def test_unsupported_horizon_and_substituted_model_refuse():
    review=history()
    with pytest.raises(ForecastEvidenceRefused):predict_probability_baseline(fit(review,horizon='5D'),review,evidence_asof=ASOF)
    with pytest.raises(ForecastEvidenceRefused):predict_probability_baseline(replace(fit(review),reference_price=999),review,evidence_asof=ASOF)


@pytest.mark.parametrize('method',[True,{},'', 'MAGIC'])
def test_invalid_opt_in_never_publishes(method,tmp_path):
    review=history()
    with pytest.raises(ForecastEvidenceRefused):publish_forecast(tmp_path,review,fit(review),evidence_asof=ASOF,probability_method=method)
    assert not list(tmp_path.iterdir())


def test_default_artifact_bytes_unchanged_and_opt_in_is_distinct(tmp_path):
    review=history();model=fit(review);before=artifact_bytes(artifact_envelope(review,model,evidence_asof=ASOF))
    old=publish_forecast(tmp_path,review,model,evidence_asof=ASOF)
    new=publish_forecast(tmp_path,review,model,evidence_asof=ASOF,probability_method=PROBABILITY_METHOD);raw=new.read_bytes()
    assert old.read_bytes()==before and old!=new
    data=read_forecast(new,review,evidence_asof=ASOF)
    assert data['schema']=='AFI_SYNTHETIC_FORECAST_ARTIFACT_V3' and data['forecast']['probability_up'] is not None
    assert data['forecast']['model_configuration_sha256']!=json.loads(before)['forecast']['model_configuration_sha256']
    assert publish_forecast(tmp_path,review,model,evidence_asof=ASOF,probability_method=PROBABILITY_METHOD)==new and new.read_bytes()==raw


@pytest.mark.parametrize('field',['probability_training','forecast','probability_method','schema'])
def test_rehashed_probability_artifact_tampering_refuses(tmp_path,field):
    from app.backtest.forecast_baselines import fingerprint
    review=history();data=artifact_envelope(review,fit(review),evidence_asof=ASOF,probability_method=PROBABILITY_METHOD)
    if field=='probability_training':data[field]['up_n']+=1
    elif field=='forecast':data[field]['probability_up']=.123456789
    elif field=='probability_method':del data[field]
    else:data[field]='AFI_SYNTHETIC_FORECAST_ARTIFACT_V1'
    data['artifact_sha256']=fingerprint({k:v for k,v in data.items() if k!='artifact_sha256'})
    path=tmp_path/(data['artifact_sha256']+'.json');path.write_bytes(artifact_bytes(data))
    with pytest.raises(ForecastEvidenceRefused):read_forecast(path,review,evidence_asof=ASOF)


def test_interval_and_probability_are_jointly_reconstructed(tmp_path):
    from test_afi_uncertainty import interval
    review=history();i=interval();selection=i['selection']
    model=fit_baseline(review,asset_id=ASSET,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=ASOF,
                       method=selection['selected_method'],lookback=selection['lookback'])
    plain=artifact_envelope(review,model,evidence_asof=ASOF,interval=i)
    path=publish_forecast(tmp_path,review,model,evidence_asof=ASOF,interval=i,probability_method=PROBABILITY_METHOD)
    data=read_forecast(path,review,evidence_asof=ASOF)
    for key in ('lower','upper','interval_level','point','reference_price'):assert data['forecast'][key]==plain['forecast'][key]
    assert data['forecast']['forecast_id']!=plain['forecast']['forecast_id']


def test_cli_outcome_corrections_and_viewer_use_published_probabilities(tmp_path):
    from app.backtest.forecast_cli import run
    from app.backtest.forecast_outcomes import append_outcome
    from app.backtest.forecast_report import (
        ForecastHistory,
        browser_export,
        build_accountability_report,
    )
    from test_afi_outcomes import CORRECTED, RESOLVED, changed_review

    review=history();revised=changed_review(review);manifest=tmp_path/'manifest.json';records=tmp_path/'records.json'
    manifest.write_bytes(review.manifest_bytes);records.write_bytes(review.payload_bytes);entries=[];original={}
    for lookback in (5,10):
        output=tmp_path/str(lookback);output.mkdir()
        result=run(manifest=manifest,records=records,output_root=output,asset_id=ASSET,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=ASOF,
                   method='ENDPOINT_DRIFT',lookback=lookback,probability_method=PROBABILITY_METHOD)
        forecast=output/result['forecast_artifact'];original[forecast]=forecast.read_bytes()
        assert 'EMPIRICAL_UP_LAPLACE_V1' in (output/result['dashboard']).read_text(encoding='utf-8')
        p,a=append_outcome(output,forecast,review,review,evidence_asof=ASOF,outcome_asof=RESOLVED)
        q,b=append_outcome(output,forecast,review,revised,evidence_asof=ASOF,outcome_asof=CORRECTED,history=[(p,review)],expected_head=a['artifact_sha256'])
        entries.append(ForecastHistory(forecast,review,((p,review),(q,revised)),b['artifact_sha256']))
    report=build_accountability_report(entries,evidence_asof=ASOF);pair=report['paired_probability_diagnostics']['comparisons'][0]
    assert pair['probability_paired_n']==1 and pair['missing_probability_n']==0 and report['correction_n']==2
    path=tmp_path/'probability-browser.json';path.write_text(browser_export(report),encoding='utf-8')
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const v=require(process.argv[1]),f=require('node:fs'),c=require('node:crypto');v.verifyEnvelope(f.readFileSync(process.argv[2],'utf8'),s=>c.createHash('sha256').update(s).digest('hex')).then(r=>console.log(JSON.stringify(r.paired_probability_diagnostics))).catch(e=>{console.error(e.message);process.exit(2)});"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(path)],capture_output=True,text=True,timeout=10,check=True)
    from app.backtest.forecast_report import _same_score
    assert _same_score(report['paired_probability_diagnostics'],json.loads(checked.stdout))
    assert all(path.read_bytes()==raw for path,raw in original.items())


def test_configuration_is_stable_across_dates_but_distinguishes_lookback():
    review=history()
    a,_=predict_probability_baseline(fit(review),review,evidence_asof=ASOF)
    later=fit_baseline(review,asset_id=ASSET,issued_at=datetime(2026,10,2,0,1,tzinfo=UTC),evidence_asof=ASOF,lookback=5)
    b,_=predict_probability_baseline(later,review,evidence_asof=ASOF)
    other=fit_baseline(review,asset_id=ASSET,issued_at=later.issued_at,evidence_asof=ASOF,lookback=10)
    c,_=predict_probability_baseline(other,review,evidence_asof=ASOF)
    assert a.model_configuration_sha256==b.model_configuration_sha256!=c.model_configuration_sha256
    assert a.forecast_id!=b.forecast_id and a.code_sha256==b.code_sha256==c.code_sha256


def test_source_bound_probability_reconstructs_only_with_exact_archive(tmp_path):
    import app
    from app.backtest.forecast_source import package_source, review_source_archive
    review=history();source_root=tmp_path/'source';source_root.mkdir()
    package=package_source(Path(app.__file__).resolve().parent.parent,source_root,release_id='probability-offline-20261020')
    source=review_source_archive((source_root/package['archive']).read_bytes())
    model=fit_baseline(review,asset_id=ASSET,issued_at=datetime(2026,10,1,0,1,tzinfo=UTC),evidence_asof=ASOF,lookback=5,source_review=source)
    path=publish_forecast(tmp_path,review,model,evidence_asof=ASOF,source_review=source,probability_method=PROBABILITY_METHOD)
    data=read_forecast(path,review,evidence_asof=ASOF,source_review=source)
    assert data['release_source_sha256']==source.release_sha256 and data['schema']=='AFI_SYNTHETIC_FORECAST_ARTIFACT_V3'
    with pytest.raises(ForecastEvidenceRefused):read_forecast(path,review,evidence_asof=ASOF)


def test_smallest_training_window_has_one_transition_not_two_labels():
    review=reviewed_values(lambda i,r:100+i)
    model=fit_baseline(review,asset_id=ASSET,issued_at=datetime(2026,10,1,0,1,tzinfo=UTC),evidence_asof=ASOF,lookback=2)
    forecast,audit=predict_probability_baseline(model,review,evidence_asof=ASOF)
    assert audit['transition_n']==audit['up_n']==1 and forecast.probability_up==2/3
