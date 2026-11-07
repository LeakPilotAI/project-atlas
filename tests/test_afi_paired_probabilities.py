import json
import subprocess
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest
from app.backtest.forecast_baselines import fingerprint
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import (
    paired_model_diagnostics,
    paired_probability_diagnostics,
    render_accountability_report,
)
from test_afi_paired_comparison import ASOF, row


def rows():
    return [row(5,probability_up=.8),row(10,probability_up=.6)]


def compare(values, **kwargs):
    models=paired_model_diagnostics(values,asof=ASOF)['models'];ids={m['cohort']['lookback']:m['id'] for m in models}
    return paired_probability_diagnostics(values,asof=ASOF,model_pairs=[(ids[5],ids[10])],**kwargs)['comparisons'][0]


def test_brier_and_matched_uninformative_baseline_are_case_bound():
    values=rows();original=deepcopy(values);p=compare(values)
    assert p['probability_paired_n']==p['point_paired_n']==1 and p['actual_up_n']==1
    assert p['a_brier']==pytest.approx(.04) and p['b_brier']==pytest.approx(.16)
    assert p['a_minus_b_brier']==pytest.approx(-.12) and p['uninformative_baseline_brier']==.25
    assert p['a_ratio_to_baseline']==pytest.approx(.16) and p['b_ratio_to_baseline']==pytest.approx(.64)
    assert p['a_lower_brier_n']==1 and values==original


@pytest.mark.parametrize('actual',[100,99])
def test_flat_and_down_are_both_not_up_with_flat_count_kept(actual):
    values=rows()
    for value in values:value.update(actual=actual,probability_up=0)
    p=compare(values);assert p['actual_up_n']==0 and p['a_brier']==p['b_brier']==0
    assert p['flat_outcome_n']==int(actual==100) and p['tied_brier_n']==1


def test_unrecorded_and_explicit_absence_are_not_zero_probability():
    values=rows();del values[0]['probability_up'];values[1]['probability_up']=None;p=compare(values)
    assert p['missing_probability_n']==p['both_missing_probability_n']==1 and p['probability_paired_n']==0
    assert p['a_brier'] is p['uninformative_baseline_brier'] is None
    assert p['cases'][0]['a_probability_state']=='UNRECORDED' and p['cases'][0]['b_probability_state']=='NONE'


@pytest.mark.parametrize('invalid',[True,-.1,1.1,'0.5',float('nan')])
def test_malformed_probabilities_refuse_even_on_pending_cases(invalid):
    values=rows();values[1].update(probability_up=invalid,status='FORECAST_ONLY',actual=None,source_revision=None,source_available_at=None,last_reconciled_asof=None,outcome_dataset_sha256=None)
    with pytest.raises(ForecastEvidenceRefused):compare(values)


def test_no_borrowing_pending_or_conflicting_probabilities():
    values=rows();values[1]['source_revision']='v2';p=compare(values)
    assert p['outcome_conflict_n']==1 and p['probability_paired_n']==0
    values[0]['source_revision']='v2';assert compare(values)['probability_paired_n']==1
    values[1].update(status='FORECAST_ONLY',actual=None,source_revision=None,source_available_at=None,last_reconciled_asof=None,outcome_dataset_sha256=None)
    p=compare(values);assert p['pending_shared_n']==1 and p['probability_paired_n']==0


def test_matched_probability_denominator_and_missing_partitions():
    values=rows()+[row(5,2,probability_up=None),row(10,2,probability_up=.5),row(5,3,probability_up=1)]
    p=compare(values);assert p['probability_paired_n']==1 and p['missing_probability_n']==1 and p['a_only_n']==1
    assert p['a_missing_probability_n']==1 and p['b_missing_probability_n']==0
    assert p['point_paired_n']==p['probability_paired_n']+p['missing_probability_n']


def test_repeated_targets_are_not_independent_calibration():
    values=[]
    for index in range(20):
        for value in rows():
            value.update(forecast_sha256=f"{value['lookback']*1000+index:064x}",issued_at=f'2026-10-01T00:{index+1:02d}:00Z');values.append(value)
    p=compare(values);assert p['probability_paired_n']==20 and p['distinct_target_n']==1 and p['status']=='OVERLAPPING_TARGET_EVIDENCE'
    result=paired_probability_diagnostics(values,asof=ASOF)
    assert not any(result[k] for k in ('calibration_established','predictive_skill_established','winner_established','independent_samples_established','production_approved','trading_authority'))


@pytest.mark.parametrize('change',[{}, {'probability_up':None},{'actual':100},{'source_revision':'v2'}])
def test_probability_backend_browser_parity(change):
    values=rows();values[1].update(change);expected=paired_probability_diagnostics(values,asof=ASOF)
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const v=require(process.argv[1]);console.log(JSON.stringify(v.pairedProbabilityDiagnostics(JSON.parse(process.argv[2]),process.argv[3])));"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),json.dumps(values),ASOF.isoformat()],capture_output=True,text=True,timeout=10,check=True)
    from app.backtest.forecast_report import _same_score
    assert _same_score(expected,json.loads(checked.stdout))


def test_original_published_forecasts_without_probabilities_stay_unscored():
    path=Path(__file__).parent/'fixtures/afi-paired-v1/corrected-browser.json';original=path.read_bytes()
    report=json.loads(json.loads(original)['report_json']);report['paired_probability_contract']='MATCHED_PROBABILITY_V1'
    report['paired_probability_diagnostics']=paired_probability_diagnostics(report['rows'],asof=datetime.fromisoformat(report['asof']))
    pair=report['paired_probability_diagnostics']['comparisons'][0]
    assert pair['point_paired_n']==pair['missing_probability_n']==1 and pair['a_brier'] is None
    def rehash():report['report_sha256']=fingerprint({k:v for k,v in report.items() if k!='report_sha256'})
    rehash();assert 'Matched-case probability comparisons' in render_accountability_report(report)
    pair['probability_paired_n']=1;rehash()
    with pytest.raises(ForecastEvidenceRefused):render_accountability_report(report)
    assert path.read_bytes()==original
