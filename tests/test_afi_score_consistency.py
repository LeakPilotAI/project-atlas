import json
from copy import deepcopy
from pathlib import Path

import pytest
from app.backtest.forecast_baselines import fingerprint
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import browser_export, render_accountability_report


def legacy():
    return json.loads((Path(__file__).parent/'fixtures/afi-legacy-v1/accountability-interval-unpartitioned.json').read_bytes())


def rehash(report):
    report['report_sha256']=fingerprint({k:v for k,v in report.items() if k!='report_sha256'})
    return report


@pytest.mark.parametrize('mutation',['forecast-count','correction-count','issued','scored','pending','cohort-count','fractional-count','boolean-count','mae','rmse','direction','false-authority','cohort-identity','duplicate-cohort'])
def test_rehashed_unsupported_score_evidence_refuses(mutation):
    report=legacy();score=report['score'];cohort=score['cohorts'][0]
    if mutation=='forecast-count':report['forecast_n']=9
    if mutation=='correction-count':report['correction_n']=9
    if mutation=='issued':score['issued_n']=9
    if mutation=='scored':score['scored_n']=9
    if mutation=='pending':score['pending_n']=9
    if mutation=='cohort-count':cohort['n']=9
    if mutation=='fractional-count':cohort['n']=1.0000000000000002
    if mutation=='boolean-count':cohort['n']=True
    if mutation=='mae':cohort['mae']=0
    if mutation=='rmse':cohort['rmse']=0
    if mutation=='direction':cohort['directional_accuracy']=1
    if mutation=='false-authority':score['trading_authority']=True
    if mutation=='cohort-identity':cohort['cohort']['asset_id']='CRYPTO:ETH-USD'
    if mutation=='duplicate-cohort':score['cohorts'].append(deepcopy(cohort))
    with pytest.raises(ForecastEvidenceRefused):render_accountability_report(rehash(report))
    with pytest.raises(ForecastEvidenceRefused):browser_export(report)



def bound_report(probability=None,actual=140):
    from app.backtest.forecast_report import (
        _row_metrics,
        directional_diagnostics,
        interval_diagnostics,
    )
    report=legacy();row=report['rows'][0];meta=deepcopy(report['score']['cohorts'][0]['cohort'])
    report.update(score_rows_contract='ROW_BOUND_SCORE_V1',diagnostic_partition='DATASET_RELEASE_V1')
    row.update(probability_up=probability,score_cohort=meta,actual=actual,forecast_code_sha256=meta['code_sha256'],forecast_dataset_id=meta['dataset_id'],forecast_dataset_version=meta['dataset_version'],forecast_dataset_manifest_sha256=meta['dataset_manifest_sha256'])
    report['score']['cohorts']=[{'cohort':meta,**_row_metrics([row])}]
    report['directional_diagnostics']=directional_diagnostics(report['rows']);report['interval_diagnostics']=interval_diagnostics(report['rows'])
    return rehash(report)


def test_same_forecast_case_under_new_hash_is_not_a_second_sample():
    from app.backtest.forecast_report import (
        _row_metrics,
        directional_diagnostics,
        interval_diagnostics,
    )
    report=bound_report();row=deepcopy(report['rows'][0]);row['forecast_sha256']='d'*64;report['rows'].append(row)
    report['forecast_n']=2;report['score'].update(issued_n=2,scored_n=2);report['score']['cohorts'][0].update(_row_metrics(report['rows']))
    report['directional_diagnostics']=directional_diagnostics(report['rows']);report['interval_diagnostics']=interval_diagnostics(report['rows'])
    with pytest.raises(ForecastEvidenceRefused):browser_export(rehash(report))



@pytest.mark.parametrize('probability',[0,.1,.5,1])
@pytest.mark.parametrize('actual',[130,138,143])
def test_original_probability_scores_match_hand_calculation_and_actual_viewer(tmp_path,probability,actual):
    import subprocess
    report=bound_report(probability,actual);cohort=report['score']['cohorts'][0];outcome=int(actual>138)
    assert cohort['brier']==pytest.approx((probability-outcome)**2)
    assert cohort['probability_n']==1 and cohort['flat_outcome_n']==int(actual==138)
    assert cohort['calibration_bins'][0]['bin']==min(int(probability*10),9)
    assert cohort['calibration_bins'][0]['observed_up_fraction']==outcome
    export=tmp_path/'probability-browser.json';export.write_text(browser_export(report),encoding='utf-8')
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const fs=require('node:fs'),c=require('node:crypto'),v=require(process.argv[1]);v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8'),t=>c.createHash('sha256').update(t).digest('hex')).then(r=>console.log(r.score.cohorts[0].brier)).catch(e=>{console.error(e.message);process.exit(2)});"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(export)],capture_output=True,text=True,timeout=10,check=True)
    assert float(result.stdout)==pytest.approx((probability-outcome)**2)


@pytest.mark.parametrize('field',['probability_up','score_cohort'])
def test_missing_original_bound_score_input_is_not_inferred(field):
    report=bound_report();del report['rows'][0][field]
    with pytest.raises(ForecastEvidenceRefused):browser_export(rehash(report))


def test_pending_probability_is_validated_even_without_outcome(tmp_path):
    from app.backtest.forecast_report import (
        ForecastHistory,
        build_accountability_report,
    )
    from test_afi_baselines import ASOF
    from test_afi_outcomes import setup
    r,_,f,_=setup(tmp_path);report=build_accountability_report([ForecastHistory(f,r)],evidence_asof=ASOF)
    report['rows'][0]['probability_up']=True
    with pytest.raises(ForecastEvidenceRefused):browser_export(rehash(report))



def verify_in_viewer(tmp_path,report):
    import subprocess
    export=tmp_path/'complete-browser.json';export.write_text(browser_export(report),encoding='utf-8')
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const fs=require('node:fs'),c=require('node:crypto'),v=require(process.argv[1]);v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8'),t=>c.createHash('sha256').update(t).digest('hex')).then(r=>console.log(JSON.stringify(r.score))).catch(e=>{console.error(e.message);process.exit(2)});"
    return json.loads(subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(export)],capture_output=True,text=True,timeout=10,check=True).stdout)


def test_weighted_probability_bins_and_sample_threshold_match_actual_viewer(tmp_path):
    from app.backtest.forecast_report import (
        _row_metrics,
        directional_diagnostics,
        interval_diagnostics,
    )
    report=bound_report(.5);base=report['rows'][0];rows=[]
    for i in range(20):
        row=deepcopy(base);row.update(forecast_sha256=f'{i+1:064x}',issued_at=f'2026-10-17T00:{i+1:02d}:00+00:00',actual=139 if i%2 else 137);rows.append(row)
    report['rows']=rows;report['forecast_n']=20;report['score'].update(issued_n=20,scored_n=20,status='DIAGNOSTIC_ONLY');report['score']['cohorts'][0].update(_row_metrics(rows))
    report['directional_diagnostics']=directional_diagnostics(rows);report['interval_diagnostics']=interval_diagnostics(rows)
    c=report['score']['cohorts'][0];assert c['brier']==.25 and c['expected_calibration_error']==0
    assert c['calibration_bins']==[{'bin':5,'n':20,'mean_probability':.5,'observed_up_fraction':.5,'status':'DIAGNOSTIC_ONLY'}]
    assert verify_in_viewer(tmp_path,rehash(report))==report['score']
    assert report['calibration_established'] is False  # Reused synthetic target is not independent calibration evidence.


def test_pending_complete_score_has_unknown_errors_in_actual_viewer(tmp_path):
    from app.backtest.forecast_report import (
        ForecastHistory,
        build_accountability_report,
    )
    from test_afi_baselines import ASOF
    from test_afi_outcomes import setup
    r,_,f,_=setup(tmp_path);report=build_accountability_report([ForecastHistory(f,r)],evidence_asof=ASOF)
    score=verify_in_viewer(tmp_path,report);assert score['scored_n']==0 and score['pending_n']==1
    assert score['cohorts'][0]['mae'] is None and score['cohorts'][0]['brier'] is None



@pytest.mark.parametrize('where',['cohort','legacy-bin'])
def test_deep_nested_authority_claim_cannot_escape_static_or_browser_checks(where):
    report=legacy()
    if where=='cohort':report['score']['cohorts'][0]['cohort']['recovery_authorized']=True
    else:report['score']['cohorts'][0]['calibration_bins']=[{'production_approved':True}]
    with pytest.raises(ForecastEvidenceRefused):browser_export(rehash(report))



def test_removing_score_contract_cannot_downgrade_recorded_inputs():
    report=bound_report();del report['score_rows_contract']
    with pytest.raises(ForecastEvidenceRefused):browser_export(rehash(report))


def test_legacy_duplicate_case_is_not_a_second_sample():
    from app.backtest.forecast_report import (
        _row_metrics,
        directional_diagnostics,
        interval_diagnostics,
    )
    report=legacy();row=deepcopy(report['rows'][0]);row['forecast_sha256']='d'*64;report['rows'].append(row)
    report['forecast_n']=2;report['score'].update(issued_n=2,scored_n=2);report['score']['cohorts'][0].update(_row_metrics(report['rows']))
    report['directional_diagnostics']=directional_diagnostics(report['rows'],bind_provenance=False);report['interval_diagnostics']=interval_diagnostics(report['rows'],bind_provenance=False)
    with pytest.raises(ForecastEvidenceRefused):browser_export(rehash(report))
