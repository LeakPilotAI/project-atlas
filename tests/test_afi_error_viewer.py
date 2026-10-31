"""Actual immutable synthetic artifacts -> browser export -> visible error evidence."""
import json
import subprocess
from pathlib import Path

import pytest
from app.backtest.forecast_artifacts import publish_forecast
from app.backtest.forecast_outcomes import append_outcome
from app.backtest.forecast_report import (
    ForecastHistory,
    browser_export,
    build_accountability_report,
)
from test_afi_baselines import ASOF, fit, history


def viewed(tmp_path,report,query='',state='ALL'):
    path=tmp_path/'errors-browser.json';path.write_text(browser_export(report),encoding='utf-8')
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const fs=require('node:fs'),c=require('node:crypto'),v=require(process.argv[1]);v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8'),t=>c.createHash('sha256').update(t).digest('hex')).then(r=>console.log(JSON.stringify(v.visibleErrors(r,process.argv[3],process.argv[4])))).catch(e=>{console.error(e.message);process.exit(2)});"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(path),query,state],capture_output=True,text=True,timeout=10,check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize('resolved',[False,True])
def test_actual_parameter_comparisons_have_filtered_honest_errors(tmp_path,resolved):
    r=history();entries=[];original={}
    for lookback in (5,10):
        root=tmp_path/str(lookback);root.mkdir();f=publish_forecast(root,r,fit(r,method='ENDPOINT_DRIFT',lookback=lookback),evidence_asof=ASOF);original[f]=f.read_bytes()
        if resolved:
            p,a=append_outcome(root,f,r,r,outcome_asof=ASOF,evidence_asof=ASOF);entries.append(ForecastHistory(f,r,((p,r),),a['artifact_sha256']))
        else:entries.append(ForecastHistory(f,r))
    report=build_accountability_report(entries,evidence_asof=ASOF);before=json.dumps(report,sort_keys=True)
    evidence=viewed(tmp_path,report);assert evidence['visible_n']==2 and len(evidence['cohorts'])==2
    cases={c['cohort']['lookback']:c for c in evidence['cohorts']}
    for lookback,c in cases.items():
        assert c['issued_n']==1 and c['n']==int(resolved) and c['pending_n']==int(not resolved)
        assert c['status']=='INSUFFICIENT_EVIDENCE' and c['recorded_probability_n']==0 and c['missing_probability_n']==0 and c['brier'] is None
        if resolved:
            assert c['mae']==(1.5 if lookback==5 else 1.0)
            assert c['no_change_mae']==2.0 and c['mae_ratio_to_no_change']==(.75 if lookback==5 else .5)
        else:assert c['mae'] is None and c['rmse'] is None and c['mae_ratio_to_no_change'] is None
    assert viewed(tmp_path,report,query='ETH')['status']=='NO_VISIBLE_CASES'
    assert json.dumps(report,sort_keys=True)==before and all(f.read_bytes()==raw for f,raw in original.items())


def test_actual_frozen_legacy_report_preserves_price_evidence_and_missing_inputs(tmp_path):
    fixture=Path(__file__).parent/'fixtures/afi-legacy-v1/accountability-interval-unpartitioned.json';raw=fixture.read_bytes();report=json.loads(raw)
    evidence=viewed(tmp_path,report);c=evidence['cohorts'][0]
    assert evidence['status']=='PARTIAL_LEGACY_INPUTS' and c['mae']==2 and c['no_change_mae']==2
    assert c['missing_probability_n']==1 and c['probability_n'] is None and c['brier'] is None
    assert fixture.read_bytes()==raw
