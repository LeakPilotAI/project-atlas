import copy
import json
import math
from datetime import UTC, datetime

import pytest
from test_afi_paired_comparison import row

from scripts.observation_runtime.forecast_paired_log_loss import (
    paired_log_loss_diagnostics,
)

ASOF=datetime(2026,10,20,tzinfo=UTC)


def compare(rows):
    result=paired_log_loss_diagnostics(rows,asof=ASOF)
    return result['comparisons'][0]


def pair(a=.8,b=.6,**changes):return [row(5,probability_up=a,**changes),row(10,probability_up=b,**changes)]


def test_only_exact_shared_recorded_probabilities_enter_paired_loss():
    rows=pair()+[row(5,2,probability_up=.9)];before=copy.deepcopy(rows);p=compare(rows)
    assert p['probability_paired_n']==1 and p['b_only_n']==1
    assert p['a_mean_log_loss']==-math.log(.6) and p['b_mean_log_loss']==-math.log(.8)
    # Model IDs are ordered by the existing canonical-context policy, not lookback.
    assert json.loads(p['a'])['lookback']==10
    assert p['a_minus_b_mean_log_loss']==-math.log(.6)+math.log(.8)
    assert p['status']=='INSUFFICIENT_EVIDENCE' and rows==before


@pytest.mark.parametrize('a,b,actual,expected',[(0,.5,104,'POSITIVE_INFINITY'),(.5,0,104,'NEGATIVE_INFINITY'),(0,0,104,'UNDEFINED_BOTH_INFINITE'),(1,1,100,'UNDEFINED_BOTH_INFINITE')])
def test_infinite_difference_states_never_become_numeric_ties(a,b,actual,expected):
    # Explicit role selection keeps the requested A/B roles independent of ID sorting.
    rows=pair(a,b,actual=actual);initial=paired_log_loss_diagnostics(rows,asof=ASOF)
    ids={json.loads(k)['lookback']:k for k in (initial['comparisons'][0]['a'],initial['comparisons'][0]['b'])}
    p=paired_log_loss_diagnostics(rows,asof=ASOF,model_pairs=[(ids[5],ids[10])])['comparisons'][0]
    assert p['difference_state']==expected and p['a_minus_b_mean_log_loss'] is None
    assert p['cases'][0]['difference_state']==expected and p['cases'][0]['a_minus_b_log_loss'] is None
    assert p['probability_paired_n']==1 and p['half_probability_mean_log_loss']==math.log(2)


def test_both_aggregate_infinite_even_when_failures_occur_on_different_cases():
    p=compare(pair(0,.5)+[row(5,2,probability_up=.5),row(10,2,probability_up=0)])
    assert p['a_infinite_loss_n']==p['b_infinite_loss_n']==1 and p['undefined_difference_n']==0
    assert p['difference_state']=='UNDEFINED_BOTH_INFINITE' and p['a_minus_b_mean_log_loss'] is None
    assert p['positive_infinite_difference_n']==p['negative_infinite_difference_n']==1


def test_equal_recorded_probabilities_allow_exact_finite_ties():
    p=compare(pair(.8,.8));assert p['difference_state']=='FINITE' and p['a_minus_b_mean_log_loss']==0


def test_balanced_opposite_losses_do_not_establish_precision_or_winner():
    p=compare(pair(.8,.2)+[row(5,2,probability_up=.2),row(10,2,probability_up=.8)])
    assert p['finite_difference_n']==2 and p['difference_state']=='UNAVAILABLE_NUMERIC_RANGE'
    assert p['a_minus_b_mean_log_loss'] is None


def test_near_equal_float_probabilities_are_not_a_false_zero_difference():
    p=compare(pair(.8,math.nextafter(.8,1)))
    assert p['numeric_range_difference_n']==1 and p['difference_state']=='UNAVAILABLE_NUMERIC_RANGE'


@pytest.mark.parametrize('fault',['pending','missing','outcome','reference','dataset'])
def test_pending_missing_and_conflicting_inputs_preserve_denominators(fault):
    rows=pair()
    if fault=='pending':rows[1].update(status='FORECAST_ONLY',actual=None,source_revision=None,source_available_at=None,last_reconciled_asof=None,outcome_dataset_sha256=None)
    if fault=='missing':del rows[1]['probability_up']
    if fault=='outcome':rows[1]['source_revision']='v2'
    if fault=='reference':rows[1]['reference']=99
    if fault=='dataset':rows[1]['forecast_dataset_manifest_sha256']='9'*64
    p=compare(rows);assert p['shared_n']==1 and p['probability_paired_n']==0
    assert p['a_mean_log_loss'] is p['b_mean_log_loss'] is p['a_minus_b_mean_log_loss'] is None
    field={'pending':'pending_shared_n','missing':'missing_probability_n','outcome':'outcome_conflict_n','reference':'reference_conflict_n','dataset':'unassessed_shared_n'}[fault]
    assert p[field]==1


def test_one_sided_correction_is_conflict_then_both_reconcile_once():
    rows=pair();rows[0].update(actual=90,source_revision='v2',outcome_dataset_sha256='9'*64)
    assert compare(rows)['probability_paired_n']==0
    rows[1].update(actual=90,source_revision='v2',outcome_dataset_sha256='9'*64)
    assert compare(rows)['probability_paired_n']==1


def test_overlapping_targets_and_authority_flags_are_unchanged():
    rows=[]
    for i in range(20):
        for lookback in (5,10):rows.append(row(lookback,probability_up=.6 if lookback==5 else .7,forecast_sha256=f'{lookback*1000+i:064x}',issued_at=f'2026-10-01T00:{i+1:02d}:00Z'))
    result=paired_log_loss_diagnostics(rows,asof=ASOF);p=result['comparisons'][0]
    assert p['probability_paired_n']==20 and p['distinct_target_n']==1 and p['status']=='OVERLAPPING_TARGET_EVIDENCE'
    for flag in ('winner_established','calibration_established','independent_samples_established','predictive_skill_established','production_approved','trading_authority'):assert result[flag] is False


def test_invalid_probabilities_and_duplicate_cases_refuse():
    for rows in [pair(True,.5),pair()+[row(5,probability_up=.8)]]:
        with pytest.raises(ValueError):paired_log_loss_diagnostics(rows,asof=ASOF)


def make_paired_reports(tmp_path):
    import hashlib

    from app.backtest.forecast_artifacts import publish_forecast
    from app.backtest.forecast_baselines import PROBABILITY_METHOD
    from app.backtest.forecast_dataset import review_dataset
    from app.backtest.forecast_outcomes import append_outcome
    from app.backtest.forecast_report import (
        ForecastHistory,
        build_accountability_report,
    )
    from test_afi_baselines import ASOF as evidence_asof
    from test_afi_baselines import fit, history
    from test_afi_dataset_integrity import encode
    from test_afi_outcomes import CORRECTED, RESOLVED, changed_review

    original=history();corrected=changed_review(original);manifest=json.loads(corrected.manifest_bytes);payload=json.loads(corrected.payload_bytes)
    next(r for r in payload['records'] if r['revision']=='v2').update(value=90,raw_price=90)
    raw=encode(payload);manifest['content_sha256']=hashlib.sha256(raw).hexdigest();corrected=review_dataset(encode(manifest),raw,asof=evidence_asof)
    first=[];latest=[];forecast_bytes={}
    for lookback in (5,10):
        root=tmp_path/str(lookback);root.mkdir()
        forecast=publish_forecast(root,original,fit(original,lookback=lookback,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC)),evidence_asof=evidence_asof,probability_method=PROBABILITY_METHOD)
        forecast_bytes[forecast]=forecast.read_bytes()
        outcome,a=append_outcome(root,forecast,original,original,outcome_asof=RESOLVED,evidence_asof=evidence_asof)
        first.append(ForecastHistory(forecast,original,((outcome,original),),a['artifact_sha256']))
        revision,b=append_outcome(root,forecast,original,corrected,outcome_asof=CORRECTED,evidence_asof=evidence_asof,history=((outcome,original),),expected_head=a['artifact_sha256'])
        latest.append(ForecastHistory(forecast,original,((outcome,original),(revision,corrected)),b['artifact_sha256']))
    reports=[build_accountability_report(entries,evidence_asof=evidence_asof) for entries in (first,[latest[0],first[1]],latest)]
    assert all(path.read_bytes()==content for path,content in forecast_bytes.items())
    return reports


def export(tmp_path,report,model_pairs=None):
    import hashlib

    from scripts.observation_runtime.forecast_log_loss import export_log_loss
    raw=(json.dumps(report,sort_keys=True)+'\n').encode();(tmp_path/'report.json').write_bytes(raw)
    request={'schema':'AFI_LOG_LOSS_REQUEST_V2','report':'report.json','expected_report_sha256':hashlib.sha256(raw).hexdigest(),
             'minimum_samples':20,'model_pairs':model_pairs}
    (tmp_path/'request.json').write_text(json.dumps(request));out=tmp_path/'output';out.mkdir(exist_ok=True)
    return export_log_loss(bundle_root=tmp_path,request_name='request.json',output_root=out)


def test_actual_probability_artifacts_correction_and_v2_export_keep_matched_denominator(tmp_path):
    reports=make_paired_reports(tmp_path)
    assert [paired_log_loss_diagnostics(r['rows'],asof=ASOF)['comparisons'][0]['probability_paired_n'] for r in reports]==[1,0,1]
    result=export(tmp_path,reports[-1]);envelope=json.loads((tmp_path/'output'/result['browser_export']).read_bytes())
    diagnostic=json.loads(envelope['diagnostics_json']);p=diagnostic['paired_log_loss_diagnostics']['comparisons'][0]
    assert envelope['schema']=='AFI_LOG_LOSS_BROWSER_V2' and envelope['model_pairs'] is None
    assert p['probability_paired_n']==1 and p['status']=='INSUFFICIENT_EVIDENCE'
    assert reports[-1]['forecast_n']==2 and reports[-1]['correction_n']==2
    assert 'Matched-case logarithmic loss' in (tmp_path/'output'/result['dashboard']).read_text()


def test_v2_exact_retry_and_v1_frozen_bytes_still_reproduce(tmp_path):
    report=make_paired_reports(tmp_path)[-1];first=export(tmp_path,report)
    before={p.name:p.read_bytes() for p in (tmp_path/'output').iterdir()};assert export(tmp_path,report)==first
    assert before=={p.name:p.read_bytes() for p in (tmp_path/'output').iterdir()}


def test_export_request_rejects_unknown_pairs_before_publication(tmp_path):
    report=make_paired_reports(tmp_path)[-1]
    with pytest.raises(ValueError):export(tmp_path,report,model_pairs=[['UNVERIFIED','UNKNOWN']])
    assert list((tmp_path/'output').iterdir())==[]


def test_backend_frontend_matched_loss_parity_including_infinities():
    import subprocess
    from pathlib import Path

    from app.backtest.forecast_report import _same_score

    rows=pair(0,.5)+[row(5,2,probability_up=.5),row(10,2,probability_up=0)]
    expected=paired_log_loss_diagnostics(rows,asof=ASOF);viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const v=require(process.argv[1]);process.stdout.write(JSON.stringify(v.pairedLogLossDiagnostics(JSON.parse(process.argv[2]),process.argv[3])));"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),json.dumps(rows),ASOF.isoformat()],capture_output=True,text=True,timeout=10,check=True)
    assert _same_score(expected,json.loads(result.stdout))


def test_actual_v2_export_is_verified_by_native_frontend(tmp_path):
    import subprocess
    from pathlib import Path

    report=make_paired_reports(tmp_path)[-1];result=export(tmp_path,report)
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const v=require(process.argv[1]),fs=require('node:fs');v.verifyLogLossEnvelope(fs.readFileSync(process.argv[2],'utf8')).then(r=>{if(r.diagnostics.paired_log_loss_diagnostics.comparisons[0].probability_paired_n!==1)throw Error('contract');process.stdout.write('PASS')}).catch(e=>{process.stderr.write(e.message);process.exitCode=1});"
    p=json.loads(json.loads((tmp_path/'output'/result['browser_export']).read_bytes())['diagnostics_json'])['paired_log_loss_diagnostics']['comparisons'][0]
    explicit=export(tmp_path,report,model_pairs=[[p['b'],p['a']]])
    for produced in (result,explicit):
        checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(tmp_path/'output'/produced['browser_export'])],capture_output=True,text=True,timeout=10,check=False)
        assert checked.returncode==0 and checked.stdout=='PASS',checked.stderr


def test_explicit_role_export_reverses_only_the_declared_comparison(tmp_path):
    report=make_paired_reports(tmp_path)[-1];base=export(tmp_path,report)
    original=json.loads(json.loads((tmp_path/'output'/base['browser_export']).read_bytes())['diagnostics_json'])['paired_log_loss_diagnostics']['comparisons'][0]
    result=export(tmp_path,report,model_pairs=[[original['b'],original['a']]])
    paired=json.loads(json.loads((tmp_path/'output'/result['browser_export']).read_bytes())['diagnostics_json'])['paired_log_loss_diagnostics']
    assert paired['selection_mode']=='EXPLICIT' and paired['comparisons'][0]['a']==original['b']
    assert paired['comparisons'][0]['a_minus_b_mean_log_loss']==-original['a_minus_b_mean_log_loss']
    assert paired['comparisons'][0]['probability_paired_n']==original['probability_paired_n']==1


def test_large_model_set_requires_explicit_pairs_without_zero_score_claim():
    rows=[row(lookback,probability_up=.6,model_configuration_sha256=f'{lookback:064x}') for lookback in range(2,14)]
    result=paired_log_loss_diagnostics(rows,asof=ASOF)
    assert result['possible_pair_n']==66 and result['status']=='EXPLICIT_PAIR_SELECTION_REQUIRED' and result['comparisons']==[]


def test_v2_fixture_is_exact_actual_immutable_export(tmp_path):
    import hashlib
    from pathlib import Path

    report=make_paired_reports(tmp_path)[-1];result=export(tmp_path,report);raw=(tmp_path/'output'/result['browser_export']).read_bytes()
    fixture=Path(__file__).resolve().parents[1]/'tests/fixtures/afi-log-loss-v2'
    assert raw==(fixture/'corrected-browser.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==json.loads((fixture/'provenance.json').read_bytes())['sha256']


def test_bad_v2_schema_and_threshold_never_publish(tmp_path):
    from scripts.observation_runtime.forecast_log_loss import export_log_loss

    report=make_paired_reports(tmp_path)[-1];result=export(tmp_path,report);before={p.name:p.read_bytes() for p in (tmp_path/'output').iterdir()}
    request=json.loads((tmp_path/'request.json').read_bytes());request['minimum_samples']=1
    (tmp_path/'request.json').write_text(json.dumps(request))
    with pytest.raises(ValueError):export_log_loss(bundle_root=tmp_path,request_name='request.json',output_root=tmp_path/'output')
    assert before=={p.name:p.read_bytes() for p in (tmp_path/'output').iterdir()}
    assert result['outcome_appends_performed']==0
