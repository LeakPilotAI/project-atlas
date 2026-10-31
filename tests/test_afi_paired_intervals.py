import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from app.backtest.forecast_report import (
    paired_interval_diagnostics,
    paired_model_diagnostics,
)
from test_afi_paired_comparison import ASOF, row


def interval_pair(rows, **kwargs):
    models=paired_model_diagnostics(rows,asof=ASOF)['models']
    ids={m['cohort']['lookback']:m['id'] for m in models}
    return paired_interval_diagnostics(rows,asof=ASOF,model_pairs=[(ids[5],ids[10])],**kwargs)['comparisons'][0]


def observations():
    return [row(5,interval={'lower':100,'upper':104,'level':.8}),
            row(10,interval={'lower':100,'upper':103,'level':.8})]


def test_interval_scores_use_same_actual_and_inclusive_boundaries():
    rows=observations();original=deepcopy(rows);p=interval_pair(rows)
    assert p['interval_paired_n']==1 and p['a_coverage']==1 and p['b_coverage']==0
    assert p['a_mean_interval_score']==4 and p['b_mean_interval_score']==pytest.approx(13)
    assert p['a_minus_b_interval_score']==pytest.approx(-9) and rows==original
    assert p['status']=='INSUFFICIENT_EVIDENCE'


@pytest.mark.parametrize('interval',[None,{'lower':100,'upper':103,'level':.9}])
def test_missing_or_mismatched_levels_never_become_coverage_misses(interval):
    rows=observations();rows[1]['interval']=interval;p=interval_pair(rows)
    assert p['point_paired_n']==1 and p['interval_paired_n']==0
    assert p['missing_interval_n']+p['level_mismatch_n']==1 and p['a_coverage'] is None


def test_pending_and_conflicting_outcomes_cannot_supply_interval_scores():
    rows=observations();rows[1].update(status='FORECAST_ONLY',actual=None,source_revision=None,source_available_at=None,last_reconciled_asof=None,outcome_dataset_sha256=None)
    p=interval_pair(rows);assert p['pending_shared_n']==1 and p['interval_paired_n']==0
    rows=observations();rows[1]['source_revision']='v2';p=interval_pair(rows)
    assert p['outcome_conflict_n']==1 and p['interval_paired_n']==0
    rows[0]['source_revision']='v2';assert interval_pair(rows)['interval_paired_n']==1


def test_unmatched_cases_do_not_expand_interval_denominator():
    rows=observations();rows.append(row(5,2,interval={'lower':100,'upper':104,'level':.8}))
    p=interval_pair(rows);assert p['a_only_n']==1 and p['interval_paired_n']==1


def test_repeated_targets_do_not_establish_independent_coverage():
    rows=[]
    for index in range(20):
        for value in observations():
            value.update(forecast_sha256=f"{value['lookback']*1000+index:064x}",issued_at=f'2026-10-01T00:{index+1:02d}:00Z');rows.append(value)
    p=interval_pair(rows);assert p['interval_paired_n']==20 and p['distinct_target_n']==1
    assert p['status']=='OVERLAPPING_TARGET_EVIDENCE'


def test_interval_threshold_with_distinct_targets_is_still_diagnostic_only():
    rows=[]
    for day in range(1,4):
        rows.extend([row(5,day,interval={'lower':100,'upper':104,'level':.8}),row(10,day,interval={'lower':100,'upper':103,'level':.8})])
    p=interval_pair(rows,minimum_samples=3);assert p['status']=='DIAGNOSTIC_ONLY'
    result=paired_interval_diagnostics(rows,asof=ASOF)
    for key in ('calibration_established','coverage_guarantee','independent_samples_established','winner_established','production_approved','trading_authority'):assert result[key] is False


@pytest.mark.parametrize('change',[{}, {'interval':None},{'interval':{'lower':100,'upper':103,'level':.9}},{'source_revision':'v2'}])
def test_backend_browser_interval_parity(change):
    rows=observations();rows[1].update(change)
    expected=paired_interval_diagnostics(rows,asof=ASOF)
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const v=require(process.argv[1]);console.log(JSON.stringify(v.pairedIntervalDiagnostics(JSON.parse(process.argv[2]),process.argv[3])));"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),json.dumps(rows),ASOF.isoformat()],capture_output=True,text=True,timeout=10,check=True)
    actual=json.loads(result.stdout)
    from app.backtest.forecast_report import _same_score
    assert _same_score(expected,actual)


def test_report_interval_summary_cannot_be_rehashed_into_a_false_success():
    from datetime import datetime

    from app.backtest.forecast_baselines import fingerprint
    from app.backtest.forecast_evaluation import ForecastEvidenceRefused
    from app.backtest.forecast_report import render_accountability_report

    fixture=Path(__file__).parent/'fixtures/afi-paired-v1/corrected-browser.json'
    report=json.loads(json.loads(fixture.read_text(encoding='utf-8'))['report_json'])
    report['paired_interval_contract']='MATCHED_INTERVAL_V1'
    report['paired_interval_diagnostics']=paired_interval_diagnostics(report['rows'],asof=datetime.fromisoformat(report['asof']))
    def rehash(value):value['report_sha256']=fingerprint({k:v for k,v in value.items() if k!='report_sha256'})
    rehash(report);assert 'Matched-case interval comparisons' in render_accountability_report(report)
    report['paired_interval_diagnostics']['comparisons'][0]['interval_paired_n']=1;rehash(report)
    with pytest.raises(ForecastEvidenceRefused):render_accountability_report(report)


def test_published_two_configuration_intervals_reconcile_into_verified_browser_report(tmp_path):
    from datetime import UTC, datetime

    from app.backtest.forecast_artifacts import publish_forecast
    from app.backtest.forecast_baselines import fit_baseline
    from app.backtest.forecast_outcomes import append_outcome
    from app.backtest.forecast_replay import freeze_selection
    from app.backtest.forecast_report import (
        ForecastHistory,
        browser_export,
        build_accountability_report,
    )
    from app.backtest.forecast_uncertainty import fit_interval
    from test_afi_baselines import ASOF as EVIDENCE_ASOF
    from test_afi_baselines import ASSET, history
    from test_afi_outcomes import RESOLVED
    from test_afi_replay import issue
    from test_afi_uncertainty import CALIBRATION, FREEZE

    review=history();entries=[];original={}
    for lookback in (5,10):
        root=tmp_path/str(lookback);root.mkdir()
        selection=freeze_selection(review,asset_id=ASSET,selection_issues=[issue(20),issue(21)],frozen_at=issue(24),evidence_asof=EVIDENCE_ASOF,lookback=lookback)
        interval=fit_interval(review,selection,calibration_issues=CALIBRATION,calibrated_at=FREEZE,evidence_asof=EVIDENCE_ASOF)
        model=fit_baseline(review,asset_id=ASSET,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=EVIDENCE_ASOF,method=selection['selected_method'],lookback=lookback)
        forecast=publish_forecast(root,review,model,evidence_asof=EVIDENCE_ASOF,interval=interval);original[forecast]=forecast.read_bytes()
        outcome,metadata=append_outcome(root,forecast,review,review,outcome_asof=RESOLVED,evidence_asof=EVIDENCE_ASOF)
        entries.append(ForecastHistory(forecast,review,((outcome,review),),metadata['artifact_sha256']))
    report=build_accountability_report(entries,evidence_asof=EVIDENCE_ASOF)
    pair=report['paired_interval_diagnostics']['comparisons'][0]
    assert pair['point_paired_n']==pair['interval_paired_n']==pair['distinct_target_n']==1
    export=tmp_path/'published-browser.json';export.write_text(browser_export(report),encoding='utf-8')
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const v=require(process.argv[1]),fs=require('node:fs'),c=require('node:crypto');v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8'),s=>c.createHash('sha256').update(s).digest('hex')).then(r=>console.log(JSON.stringify(r.paired_interval_diagnostics))).catch(e=>{console.error(e.message);process.exit(2)});"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(export)],capture_output=True,text=True,check=True,timeout=10)
    from app.backtest.forecast_report import _same_score
    assert _same_score(report['paired_interval_diagnostics'],json.loads(checked.stdout))
    assert all(p.read_bytes()==raw for p,raw in original.items())
