from copy import deepcopy

import pytest
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import interval_diagnostics
from test_afi_directional_diagnostics import row


def interval_row(actual=110,**changes):
    r=row(110,actual);r['interval']={'lower':100,'upper':120,'level':.8};r.update(changes);return r


@pytest.mark.parametrize('actual,covered,below,above,score',[(100,1,0,0,20),(120,1,0,0,20),(90,0,1,0,120),(130,0,0,1,120)])
def test_inclusive_boundaries_and_winkler_miss_penalty(actual,covered,below,above,score):
    c=interval_diagnostics([interval_row(actual)])['cohorts'][0]
    assert (c['covered_n'],c['below_n'],c['above_n'])==(covered,below,above)
    assert c['mean_interval_score']==pytest.approx(score) and c['status']=='INSUFFICIENT_EVIDENCE'


@pytest.mark.parametrize('n,status',[(19,'INSUFFICIENT_EVIDENCE'),(20,'DIAGNOSTIC_ONLY')])
def test_sample_boundary_is_diagnostic_never_calibration(n,status):
    d=interval_diagnostics([interval_row() for _ in range(n)]);assert d['cohorts'][0]['status']==status
    assert not d['calibration_established'] and not d['coverage_guarantee']


def test_pending_and_no_interval_are_not_false_misses():
    d=interval_diagnostics([interval_row(None),row(110,120)])
    assert d['without_interval_n']==1
    c=d['cohorts'][0];assert c['resolved_n']==0 and c['pending_n']==1
    assert c['coverage'] is None and c['mean_interval_score'] is None


def test_asset_model_horizon_and_level_are_not_pooled():
    rows=[interval_row(),interval_row(asset_id='CRYPTO:ETH-USD'),interval_row(model='other'),interval_row(horizon='5D')]
    r=interval_row();r['interval']['level']=.9;rows.append(r)
    assert len(interval_diagnostics(rows)['cohorts'])==5


@pytest.mark.parametrize('interval',[{}, {'lower':0,'upper':120}, {'lower':True,'upper':120,'level':.8}, {'lower':120,'upper':100,'level':.8}, {'lower':100,'upper':120,'level':1}, {'lower':100,'upper':float('inf'),'level':.8}, {'lower':-1,'upper':120,'level':.8}])
def test_invalid_intervals_refuse(interval):
    with pytest.raises(ForecastEvidenceRefused):interval_diagnostics([interval_row(interval=deepcopy(interval))])


def test_overflow_and_boolean_minimum_refuse():
    r=interval_row(1e308);r['interval']={'lower':0,'upper':120,'level':.999999999999}
    with pytest.raises(ForecastEvidenceRefused):interval_diagnostics([r])
    with pytest.raises(ForecastEvidenceRefused):interval_diagnostics([interval_row()],minimum_samples=True)


def test_published_interval_pending_resolution_correction_and_actual_viewer(tmp_path):
    import json
    import subprocess
    from datetime import UTC, datetime
    from pathlib import Path

    from app.backtest.forecast_artifacts import publish_forecast
    from app.backtest.forecast_baselines import fit_baseline
    from app.backtest.forecast_report import (
        ForecastHistory,
        browser_export,
        build_accountability_report,
        render_accountability_report,
    )
    from test_afi_baselines import ASOF, ASSET, history
    from test_afi_outcomes import CORRECTED, PENDING, RESOLVED, append, changed_review
    from test_afi_uncertainty import interval
    r=history();i=interval();selection=i['selection'];issued=datetime(2026,10,17,0,1,tzinfo=UTC)
    m=fit_baseline(r,asset_id=ASSET,issued_at=issued,evidence_asof=ASOF,method=selection['selected_method'],lookback=selection['lookback'],horizon=selection['horizon'])
    f=publish_forecast(tmp_path,r,m,evidence_asof=ASOF,interval=i);original=f.read_bytes()
    out=tmp_path/'outcomes';out.mkdir()
    p,a=append(out,f,r,outcome_asof=PENDING)
    pending=build_accountability_report([ForecastHistory(f,r,((p,r),),a['artifact_sha256'])],evidence_asof=ASOF)
    c=pending['interval_diagnostics']['cohorts'][0];assert c['pending_n']==1 and c['coverage'] is None
    q,b=append(out,f,r,outcome_asof=RESOLVED,history=[(p,r)],expected_head=a['artifact_sha256'])
    revised=changed_review(r)
    t,d=append(out,f,r,revised,outcome_asof=CORRECTED,history=[(p,r),(q,r)],expected_head=b['artifact_sha256'])
    report=build_accountability_report([ForecastHistory(f,r,((p,r),(q,r),(t,revised)),d['artifact_sha256'])],evidence_asof=ASOF)
    c=report['interval_diagnostics']['cohorts'][0]
    assert c['resolved_n']==1 and c['pending_n']==0 and report['correction_n']==1
    assert report['rows'][0]['interval']==pending['rows'][0]['interval'] and f.read_bytes()==original
    bounds=report['rows'][0]['interval'];assert c['mean_interval_score']==pytest.approx(bounds['upper']-bounds['lower']+2*max(155-bounds['upper'],bounds['lower']-155,0)/(1-bounds['level']))
    before_render = deepcopy(report)
    html = render_accountability_report(report)
    assert 'Interval outcome diagnostics' in html
    assert 'Distinct recorded targets' in html and 'RECORDED_TARGETS_ONLY' in html
    assert 'do not establish independence' in html and report == before_render
    export=tmp_path/'interval-browser.json';export.write_text(browser_export(report),encoding='utf-8')
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const v=require(process.argv[1]),fs=require('node:fs'),c=require('node:crypto');v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8'),t=>c.createHash('sha256').update(t).digest('hex')).then(r=>{console.log(JSON.stringify(r.interval_diagnostics));}).catch(e=>{console.error(e.message);process.exit(2);});"
    actual=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(export)],capture_output=True,text=True,timeout=10,check=True)
    assert json.loads(actual.stdout)['cohorts'][0]['resolved_n']==1


def test_rehashed_interval_diagnostics_cannot_claim_calibration(tmp_path):
    from app.backtest.forecast_baselines import fingerprint
    from app.backtest.forecast_report import (
        ForecastHistory,
        build_accountability_report,
        render_accountability_report,
    )
    from test_afi_baselines import ASOF
    from test_afi_outcomes import setup
    r,_,f,_=setup(tmp_path);report=build_accountability_report([ForecastHistory(f,r)],evidence_asof=ASOF)
    report['interval_diagnostics']['calibration_established']=True
    report['report_sha256']=fingerprint({k:v for k,v in report.items() if k!='report_sha256'})
    with pytest.raises(ForecastEvidenceRefused):render_accountability_report(report)


def test_zero_width_original_interval_has_zero_score_only_for_exact_match():
    r=interval_row(110,interval={'lower':110,'upper':110,'level':.8})
    c=interval_diagnostics([r])['cohorts'][0]
    assert c['coverage']==1 and c['mean_width']==0 and c['mean_interval_score']==0


@pytest.mark.parametrize('change',[{'model_version':'v2','lookback':5},{'model_version':'v1','lookback':20}])
def test_model_versions_and_configurations_do_not_pool(change):
    from app.backtest.forecast_report import directional_diagnostics
    rows=[interval_row(model_version='v1',lookback=5),interval_row(**change)]
    assert len(interval_diagnostics(rows)['cohorts'])==2
    assert len(directional_diagnostics(rows)['cohorts'])==2


def test_incomplete_model_config_binding_refuses():
    with pytest.raises(ForecastEvidenceRefused):interval_diagnostics([interval_row(model_version='v1')])


def test_actual_older_accountability_report_remains_usable_with_unknown_intervals():
    import hashlib
    import json
    from pathlib import Path

    from app.backtest.forecast_report import render_accountability_report
    fixture=Path(__file__).parent/'fixtures/afi-legacy-v1/accountability-v1.json';raw=fixture.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='376daa1303b4e42611ba2f15d78f48da85aaa6dc482eedafe82e14a84f17354b'
    html=render_accountability_report(json.loads(raw));assert 'Legacy report did not record original intervals' in html


def test_rehashed_new_report_cannot_drop_interval_diagnostics(tmp_path):
    from app.backtest.forecast_baselines import fingerprint
    from app.backtest.forecast_report import (
        ForecastHistory,
        build_accountability_report,
        render_accountability_report,
    )
    from test_afi_baselines import ASOF
    from test_afi_outcomes import setup
    r,_,f,_=setup(tmp_path);report=build_accountability_report([ForecastHistory(f,r)],evidence_asof=ASOF)
    report.pop('interval_diagnostics');report['report_sha256']=fingerprint({k:v for k,v in report.items() if k!='report_sha256'})
    with pytest.raises(ForecastEvidenceRefused):render_accountability_report(report)
