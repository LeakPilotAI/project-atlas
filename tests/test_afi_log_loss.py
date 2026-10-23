import copy
import hashlib
import json
import math
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_artifacts import publish_forecast
from app.backtest.forecast_baselines import PROBABILITY_METHOD
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_outcomes import append_outcome
from app.backtest.forecast_report import ForecastHistory, build_accountability_report
from test_afi_baselines import ASOF, fit, history
from test_afi_dataset_integrity import encode
from test_afi_outcomes import CORRECTED, RESOLVED, changed_review
from test_afi_paired_comparison import row

import scripts.observation_runtime.forecast_log_loss as loss


def metric(rows,**kwargs):return loss.log_loss_diagnostics(rows,**kwargs)['cohorts'][0]


@pytest.mark.parametrize('probability,actual,state,expected',[(0,100,'FINITE',0),(1,104,'FINITE',0),(0,104,'INFINITE',None),(1,100,'INFINITE',None),(.5,104,'FINITE',math.log(2)),(.2,99,'FINITE',-math.log1p(-.2))])
def test_exact_boundaries_and_flat_is_not_up(probability,actual,state,expected):
    c=metric([row(5,probability_up=probability,actual=actual)])
    assert c['loss_state']==state and c['mean_log_loss']==expected
    assert c['infinite_loss_n']==int(state=='INFINITE') and c['probability_n']==1
    assert c['flat_outcome_n']==int(actual==100)
    assert c['half_probability_mean_log_loss']==math.log(2)


def test_impossible_event_never_disappears_into_finite_subset_mean():
    c=metric([row(5,probability_up=1,actual=90),row(5,2,probability_up=.8)])
    assert c['probability_n']==2 and c['finite_loss_n']==c['infinite_loss_n']==1
    assert c['mean_log_loss'] is None and c['mean_log_loss_minus_baseline'] is None
    assert c['cases'][0]['loss_state']=='INFINITE' and c['cases'][0]['log_loss'] is None


def test_extreme_finite_probabilities_are_not_clipped():
    tiny=math.nextafter(0,1);near_one=math.nextafter(1,0)
    a=metric([row(5,probability_up=tiny)]);b=metric([row(5,probability_up=near_one,actual=90)])
    assert a['mean_log_loss']==-math.log(tiny)>700 and b['mean_log_loss']==-math.log1p(-near_one)>30
    assert metric([row(5,probability_up=tiny,actual=90)])['mean_log_loss']==tiny


def test_pending_absent_and_none_keep_separate_denominators_without_mutation():
    rows=[row(5,probability_up=.8),row(5,2,probability_up=None),row(5,3),row(5,4,probability_up=.4,status='FORECAST_ONLY',actual=None)]
    before=copy.deepcopy(rows);c=metric(rows)
    assert (c['forecast_n'],c['resolved_n'],c['pending_n'],c['probability_n'])==(4,3,1,1)
    assert c['unrecorded_probability_n']==c['no_probability_n']==1
    assert [r['loss_state'] for r in c['cases']]==['FINITE','NO_PROBABILITY','UNRECORDED_PROBABILITY','PENDING']
    assert c['status']=='PARTIAL_LEGACY_INPUTS' and rows==before


def test_empty_recorded_sample_is_unknown_not_perfect():
    c=metric([row(5,probability_up=None)])
    assert c['loss_state']=='UNAVAILABLE' and c['mean_log_loss'] is c['half_probability_mean_log_loss'] is None
    assert c['finite_loss_n']==c['zero_loss_n']==0
    assert loss.log_loss_diagnostics([])['cohorts']==[]


def test_exact_cohorts_and_repeated_targets_keep_existing_safety_statuses():
    values=[row(5,probability_up=.8),row(10,probability_up=.8),row(5,2,probability_up=.8,forecast_dataset_manifest_sha256='9'*64),row(5,3,probability_up=.8,interval={'lower':100,'upper':104,'level':.8})]
    assert len(loss.log_loss_diagnostics(values)['cohorts'])==4
    repeated=[row(5,probability_up=.8,forecast_sha256=f'{i+3000:064x}',issued_at=f'2026-10-01T00:{i+1:02d}:00Z') for i in range(20)]
    c=metric(repeated);assert c['probability_n']==20 and c['distinct_target_n']==1 and c['status']=='OVERLAPPING_TARGET_EVIDENCE'
    for flag in ('calibration_established','predictive_skill_established','original_forecast_history_verified','independent_samples_established','production_approved','trading_authority'):assert loss.log_loss_diagnostics(values)[flag] is False


@pytest.mark.parametrize('probability',[True,float('nan'),-.1,1.1,'0.5'])
def test_malformed_recorded_probabilities_refuse_even_when_pending(probability):
    with pytest.raises(ValueError):loss.log_loss_diagnostics([row(5,probability_up=probability,status='FORECAST_ONLY',actual=None)])


def test_duplicate_or_equivalent_instant_case_refuses():
    a=row(5,probability_up=.8)
    for b in [copy.deepcopy(a),{**a,'forecast_sha256':'9'*64,'issued_at':'2026-10-01T01:01:00+01:00'}]:
        with pytest.raises(ValueError):loss.log_loss_diagnostics([a,b])


def make_reports(tmp_path):
    r=history();f=publish_forecast(tmp_path,r,fit(r,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC)),evidence_asof=ASOF,probability_method=PROBABILITY_METHOD)
    original=f.read_bytes();pending=build_accountability_report([ForecastHistory(f,r)],evidence_asof=ASOF)
    first,a=append_outcome(tmp_path,f,r,r,outcome_asof=RESOLVED,evidence_asof=ASOF)
    resolved=build_accountability_report([ForecastHistory(f,r,((first,r),),a['artifact_sha256'])],evidence_asof=ASOF)
    corrected=changed_review(r);m=json.loads(corrected.manifest_bytes);p=json.loads(corrected.payload_bytes)
    next(x for x in p['records'] if x['revision']=='v2').update(value=90,raw_price=90)
    raw=encode(p);m['content_sha256']=hashlib.sha256(raw).hexdigest();corrected=review_dataset(encode(m),raw,asof=ASOF)
    second,b=append_outcome(tmp_path,f,r,corrected,outcome_asof=CORRECTED,evidence_asof=ASOF,history=((first,r),),expected_head=a['artifact_sha256'])
    final=build_accountability_report([ForecastHistory(f,r,((first,r),(second,corrected)),b['artifact_sha256'])],evidence_asof=ASOF)
    assert f.read_bytes()==original
    return pending,resolved,final


def export(tmp_path,report,*,minimum=20):
    raw=(json.dumps(report,sort_keys=True)+'\n').encode();(tmp_path/'report.json').write_bytes(raw)
    request={'schema':'AFI_LOG_LOSS_REQUEST_V1','report':'report.json','expected_report_sha256':hashlib.sha256(raw).hexdigest(),'minimum_samples':minimum}
    (tmp_path/'request.json').write_text(json.dumps(request));out=tmp_path/'output';out.mkdir(exist_ok=True)
    return loss.export_log_loss(bundle_root=tmp_path,request_name='request.json',output_root=out)


def test_actual_immutable_forecasts_pending_resolved_and_corrected_keep_one_sample(tmp_path):
    pending,resolved,corrected=make_reports(tmp_path);before=[(p,p.read_bytes()) for p in tmp_path.glob('*.json')]
    a=loss.log_loss_diagnostics(pending['rows'])['cohorts'][0];b=loss.log_loss_diagnostics(resolved['rows'])['cohorts'][0];c=loss.log_loss_diagnostics(corrected['rows'])['cohorts'][0]
    assert a['probability_n']==0 and b['probability_n']==c['probability_n']==1
    probability=resolved['rows'][0]['probability_up'];assert probability!=.5
    assert b['mean_log_loss']==-math.log(probability) and c['mean_log_loss']==-math.log1p(-probability)
    assert c['cases'][0]['forecast_sha256']==b['cases'][0]['forecast_sha256']
    result=export(tmp_path,corrected);raw=json.loads((tmp_path/'output'/result['browser_export']).read_bytes())
    assert json.loads(raw['diagnostics_json'])==loss.log_loss_diagnostics(corrected['rows'])
    assert all(path.read_bytes()==content for path,content in before)
    assert 'Synthetic diagnostic only' in (tmp_path/'output'/result['dashboard']).read_text()


def test_export_exact_retry_and_source_pin_refusal(tmp_path):
    _,report,_=make_reports(tmp_path);result=export(tmp_path,report);out=tmp_path/'output';before={p.name:p.read_bytes() for p in out.iterdir()}
    assert export(tmp_path,report)==result and before=={p.name:p.read_bytes() for p in out.iterdir()}
    (tmp_path/'report.json').write_bytes((tmp_path/'report.json').read_bytes()+b' ')
    with pytest.raises(ValueError):loss.export_log_loss(bundle_root=tmp_path,request_name='request.json',output_root=out)
    assert before=={p.name:p.read_bytes() for p in out.iterdir()}


def test_partial_publication_keeps_evidence_without_success(tmp_path,monkeypatch):
    _,report,_=make_reports(tmp_path);publish=loss.publish_research_text;calls=0
    def fail(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:raise OSError('synthetic disk full')
        return publish(*args,**kwargs)
    monkeypatch.setattr(loss,'publish_research_text',fail)
    with pytest.raises(OSError):export(tmp_path,report)
    assert len(list((tmp_path/'output').iterdir()))==1


def test_unrepresentable_positive_mean_is_not_reported_as_perfect_zero():
    c=metric([row(5,probability_up=math.nextafter(0,1),actual=90),row(5,2,probability_up=0,actual=90)])
    assert c['zero_loss_n']==1 and c['finite_loss_n']==2 and c['loss_state']=='UNAVAILABLE_NUMERIC_RANGE'
    assert c['mean_log_loss'] is c['mean_log_loss_minus_baseline'] is None


def test_backend_frontend_full_log_loss_parity_and_tiny_values():
    import subprocess
    from pathlib import Path

    from app.backtest.forecast_report import _same_score

    values=[row(5,probability_up=0),row(5,2,probability_up=.8),row(10,3,probability_up=math.nextafter(0,1),actual=90),
            row(10,4,probability_up=0,actual=90),row(5,5,probability_up=None)]
    expected=loss.log_loss_diagnostics(values);viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    code="const v=require(process.argv[1]);process.stdout.write(JSON.stringify(v.logLossDiagnostics(JSON.parse(process.argv[2]))));"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(viewer),json.dumps(values)],capture_output=True,text=True,timeout=10,check=True)
    assert _same_score(expected,json.loads(result.stdout))


def test_actual_export_to_existing_frontend_source_and_score_verifier(tmp_path):
    import subprocess
    from pathlib import Path

    _,_,report=make_reports(tmp_path);result=export(tmp_path,report)
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    code="const fs=require('node:fs'),v=require(process.argv[1]);v.verifyLogLossEnvelope(fs.readFileSync(process.argv[2],'utf8')).then(r=>{if(r.diagnostics.cohorts[0].probability_n!==1||r.source_report.correction_n!==1)throw Error('contract');process.stdout.write('PASS')}).catch(e=>{process.stderr.write(e.message);process.exitCode=1});"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(viewer),str(tmp_path/'output'/result['browser_export'])],capture_output=True,text=True,timeout=10,check=False)
    assert checked.returncode==0 and checked.stdout=='PASS',checked.stderr


def test_checked_in_companion_is_actual_deterministic_export(tmp_path):
    from pathlib import Path

    _,_,report=make_reports(tmp_path);result=export(tmp_path,report)
    raw=(tmp_path/'output'/result['browser_export']).read_bytes();root=Path(__file__).resolve().parents[1]/'tests/fixtures/afi-log-loss-v1'
    assert raw==(root/'corrected-browser.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==json.loads((root/'provenance.json').read_bytes())['sha256']


def test_cli_and_bad_report_fail_before_publication(tmp_path,capsys):
    _,report,_=make_reports(tmp_path);result=export(tmp_path,report)
    assert loss.main(['--bundle-root',str(tmp_path),'--request','request.json','--output-root',str(tmp_path/'output')])==0
    assert json.loads(capsys.readouterr().out)['browser_export']==result['browser_export']
    report['forecast_n']=999;raw=json.dumps(report).encode();(tmp_path/'report.json').write_bytes(raw)
    request=json.loads((tmp_path/'request.json').read_bytes());request['expected_report_sha256']=hashlib.sha256(raw).hexdigest();(tmp_path/'request.json').write_text(json.dumps(request))
    before={p.name:p.read_bytes() for p in (tmp_path/'output').iterdir()}
    with pytest.raises(SystemExit) as error:loss.main(['--bundle-root',str(tmp_path),'--request','request.json','--output-root',str(tmp_path/'output')])
    assert error.value.code==2 and before=={p.name:p.read_bytes() for p in (tmp_path/'output').iterdir()}
    assert 'refused' in capsys.readouterr().err


def test_later_publication_cannot_hide_changed_earlier_artifact(tmp_path,monkeypatch):
    _,report,_=make_reports(tmp_path);publish=loss.publish_research_text;seen=[]
    def changed(*args,**kwargs):
        path=publish(*args,**kwargs);seen.append(path)
        if len(seen)==3:seen[0].write_bytes(b'SYNTHETIC_CHANGED_AFTER_FIRST_READ')
        return path
    monkeypatch.setattr(loss,'publish_research_text',changed)
    with pytest.raises(ValueError):export(tmp_path,report)
    assert len(seen)==3 and seen[0].read_bytes()==b'SYNTHETIC_CHANGED_AFTER_FIRST_READ'
