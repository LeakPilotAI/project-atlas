from copy import deepcopy
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import paired_model_diagnostics

ASOF=datetime(2026,10,20,tzinfo=UTC)


def row(lookback,day=1,**changes):
    value={'asset_class':'CRYPTO','asset_id':'CRYPTO:BTC-USD','model':'ENDPOINT_DRIFT','model_version':'v1','lookback':lookback,'model_configuration_sha256':('a' if lookback==5 else 'b')*64,
           'horizon':'1D','forecast_point':101 if lookback==5 else 102,'reference':100,'actual':104,'status':'RESOLVED','interval':None,
           'forecast_sha256':f'{lookback*100+day:064x}','forecast_dataset_sha256':'c'*64,'forecast_dataset_manifest_sha256':'d'*64,'forecast_dataset_id':'fixture','forecast_dataset_version':'v1','forecast_code_sha256':'f'*64,'release_source_sha256':None,
           'issued_at':f'2026-10-{day:02d}T00:01:00Z','target_at':f'2026-10-{day+1:02d}T00:00:00Z','source_revision':'v1','source_available_at':f'2026-10-{day+1:02d}T00:00:00Z','last_reconciled_asof':'2026-10-20T00:00:00Z','outcome_dataset_sha256':'e'*64}
    value.update(changes);return value


def compare(rows,**kwargs):
    initial=paired_model_diagnostics(rows,asof=ASOF)
    by_lookback={m['cohort']['lookback']:m['id'] for m in initial['models']}
    return paired_model_diagnostics(rows,asof=ASOF,model_pairs=[(by_lookback[5],by_lookback[10])],**kwargs)['comparisons'][0]


def test_exact_shared_cases_use_paired_denominators_only():
    rows=[row(5),row(10),row(5,day=2)];before=deepcopy(rows);p=compare(rows)
    assert p['paired_n']==1 and p['a_only_n']==1 and p['b_only_n']==0
    assert p['a_mae']==3 and p['b_mae']==2 and p['a_minus_b_mae']==1
    assert p['baseline_mae']==4 and p['a_ratio_to_baseline']==.75 and p['b_ratio_to_baseline']==.5
    assert p['distinct_target_n']==1 and p['status']=='INSUFFICIENT_EVIDENCE' and rows==before


@pytest.mark.parametrize('change',[{'actual':105},{'source_revision':'v2'},{'outcome_dataset_sha256':'f'*64}])
def test_different_outcome_vintages_never_get_compared(change):
    p=compare([row(5),row(10,**change)])
    assert p['paired_n']==0 and p['outcome_conflict_n']==1 and p['a_mae'] is None


def test_pending_is_not_a_missing_models_loss_or_borrowed_outcome():
    p=compare([row(5),row(10,actual=None,status='FORECAST_ONLY',source_revision=None,source_available_at=None,last_reconciled_asof=None,outcome_dataset_sha256=None)])
    assert p['pending_shared_n']==1 and p['paired_n']==0 and p['b_mae'] is None


def test_reference_mismatch_is_not_a_fair_baseline_comparison():
    p=compare([row(5),row(10,reference=99)])
    assert p['reference_conflict_n']==1 and p['paired_n']==0


def test_equal_utc_instants_with_different_offsets_pair():
    p=compare([row(5),row(10,issued_at='2026-10-01T01:01:00+01:00',target_at='2026-10-02T01:00:00+01:00')])
    assert p['paired_n']==1


def test_dataset_metadata_difference_refuses_metrics():
    p=compare([row(5),row(10,forecast_dataset_manifest_sha256='9'*64)])
    assert p['status']=='INCOMPARABLE_FORECAST_DATA' and p['unassessed_shared_n']==1 and p['a_mae'] is None


def test_no_shared_cases_is_not_zero_error():
    p=compare([row(5),row(10,day=2)])
    assert p['shared_n']==0 and p['paired_n']==0 and p['a_mae'] is None


def test_duplicate_model_case_and_duplicate_source_refuse():
    for duplicate in [row(5),row(5,forecast_sha256='9'*64)]:
        with pytest.raises(ForecastEvidenceRefused):paired_model_diagnostics([row(5),duplicate],asof=ASOF)


def test_one_sided_correction_is_conflict_then_both_reconcile_once():
    a=row(5,actual=105,source_revision='v2',outcome_dataset_sha256='9'*64,correction_n=1)
    assert compare([a,row(10)])['outcome_conflict_n']==1
    p=compare([a,row(10,actual=105,source_revision='v2',outcome_dataset_sha256='9'*64,correction_n=1)])
    assert p['paired_n']==1 and p['a_mae']==4 and p['b_mae']==3



def test_missing_metadata_and_missing_outcome_provenance_are_not_invented():
    a,b=row(5),row(10)
    for k in ('forecast_dataset_manifest_sha256','forecast_dataset_id','forecast_dataset_version'):a.pop(k)
    p=compare([a,b]);assert p['status']=='MISSING_FORECAST_DATA_BINDING' and p['unassessed_shared_n']==1
    p=compare([row(5),row(10,source_revision=None)])
    assert p['missing_provenance_n']==1 and p['paired_n']==0


def test_zero_baseline_ratio_is_unavailable_not_zero_or_infinity():
    p=compare([row(5,actual=100),row(10,actual=100)])
    assert p['baseline_mae']==0 and p['a_ratio_to_baseline'] is None and p['b_ratio_to_baseline'] is None


def test_many_issues_for_one_target_do_not_become_independent_samples():
    rows=[row(n,forecast_sha256=f'{n*1000+i:064x}',issued_at=f'2026-10-01T00:{i+1:02d}:00Z') for i in range(20) for n in (5,10)]
    p=compare(rows);assert p['paired_n']==20 and p['distinct_target_n']==1 and p['status']=='OVERLAPPING_TARGET_EVIDENCE'
    result=paired_model_diagnostics(rows,asof=ASOF);assert result['independent_samples_established'] is False and result['winner_established'] is False


def test_too_many_automatic_comparisons_require_explicit_selection():
    rows=[row(n,model_configuration_sha256=f'{n+1000:064x}',forecast_sha256=f'{n+2000:064x}') for n in range(2,15)]
    result=paired_model_diagnostics(rows,asof=ASOF);assert result['possible_pair_n']==78 and result['comparisons']==[] and result['status']=='EXPLICIT_PAIR_SELECTION_REQUIRED'
    pair=[m['id'] for m in result['models'][:2]]
    selected=paired_model_diagnostics(rows,asof=ASOF,model_pairs=[pair]);assert len(selected['comparisons'])==1 and selected['selection_mode']=='EXPLICIT'
    with pytest.raises(ForecastEvidenceRefused):paired_model_diagnostics(rows,asof=ASOF,model_pairs=[pair,pair[::-1]])


@pytest.mark.parametrize('change',[{'source_available_at':'2026-09-01T00:00:00Z'},{'issued_at':'2026-10-21T00:00:00Z'},{'source_revision':True},{'outcome_dataset_sha256':'bad'}])
def test_contradictory_pair_evidence_fails_closed(change):
    with pytest.raises(ForecastEvidenceRefused):paired_model_diagnostics([row(5),row(10,**change)],asof=ASOF)


def test_shared_case_partition_and_lower_error_counts_reconcile():
    rows=[row(5),row(10),row(5,2),row(10,2,actual=None,status='FORECAST_ONLY',source_revision=None,source_available_at=None,last_reconciled_asof=None,outcome_dataset_sha256=None),row(5,3),row(10,3,actual=105)]
    p=compare(rows)
    assert p['shared_n']==p['paired_n']+p['pending_shared_n']+p['reference_conflict_n']+p['outcome_conflict_n']+p['missing_provenance_n']+p['unassessed_shared_n']
    assert p['a_lower_error_n']+p['b_lower_error_n']+p['tied_error_n']==p['paired_n']
    assert len(p['cases'])==3


def test_rehashed_pair_counts_and_authority_refuse_in_actual_report(tmp_path):
    from app.backtest.forecast_baselines import fingerprint
    from app.backtest.forecast_report import (
        ForecastHistory,
        build_accountability_report,
        render_accountability_report,
    )
    from test_afi_baselines import ASOF as EVIDENCE_ASOF
    from test_afi_outcomes import setup
    r,_,f,_=setup(tmp_path);report=build_accountability_report([ForecastHistory(f,r)],evidence_asof=EVIDENCE_ASOF)
    for field,value in [('model_n',True),('winner_established',True)]:
        broken=deepcopy(report);broken['paired_model_diagnostics'][field]=value;broken['report_sha256']=fingerprint({k:v for k,v in broken.items() if k!='report_sha256'})
        with pytest.raises(ForecastEvidenceRefused):render_accountability_report(broken)



def test_actual_correction_chain_comparison_survives_backend_and_browser(tmp_path):
    import json
    import subprocess
    from pathlib import Path

    from app.backtest.forecast_artifacts import publish_forecast
    from app.backtest.forecast_baselines import fit_baseline
    from app.backtest.forecast_outcomes import append_outcome
    from app.backtest.forecast_report import (
        ForecastHistory,
        browser_export,
        build_accountability_report,
    )
    from test_afi_baselines import ASOF as EVIDENCE_ASOF
    from test_afi_baselines import ASSET, history
    from test_afi_outcomes import CORRECTED, RESOLVED, changed_review
    r=history();revised=changed_review(r);entries=[];facts=[];original={}
    for window in (5,10):
        root=tmp_path/str(window);root.mkdir();m=fit_baseline(r,asset_id=ASSET,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=EVIDENCE_ASOF,method='ENDPOINT_DRIFT',lookback=window)
        f=publish_forecast(root,r,m,evidence_asof=EVIDENCE_ASOF);original[f]=f.read_bytes();p,a=append_outcome(root,f,r,r,outcome_asof=RESOLVED,evidence_asof=EVIDENCE_ASOF)
        facts.append((root,f,p,a));entries.append(ForecastHistory(f,r,((p,r),),a['artifact_sha256']))
    root,f,p,a=facts[0];q,b=append_outcome(root,f,r,revised,outcome_asof=CORRECTED,evidence_asof=EVIDENCE_ASOF,history=[(p,r)],expected_head=a['artifact_sha256']);entries[0]=ForecastHistory(f,r,((p,r),(q,revised)),b['artifact_sha256'])
    conflict=build_accountability_report(entries,evidence_asof=EVIDENCE_ASOF);assert conflict['paired_model_diagnostics']['comparisons'][0]['outcome_conflict_n']==1
    root,f,p,a=facts[1];q,b=append_outcome(root,f,r,revised,outcome_asof=CORRECTED,evidence_asof=EVIDENCE_ASOF,history=[(p,r)],expected_head=a['artifact_sha256']);entries[1]=ForecastHistory(f,r,((p,r),(q,revised)),b['artifact_sha256'])
    final=build_accountability_report(entries,evidence_asof=EVIDENCE_ASOF);pair=final['paired_model_diagnostics']['comparisons'][0];assert pair['paired_n']==1 and final['correction_n']==2 and pair['distinct_target_n']==1
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs';script="const fs=require('node:fs'),c=require('node:crypto'),v=require(process.argv[1]);v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8'),t=>c.createHash('sha256').update(t).digest('hex')).then(r=>console.log(JSON.stringify(v.pairedDiagnostics(r.rows,r.asof)))).catch(e=>{console.error(e.message);process.exit(2)});"
    for name,report in [('conflict',conflict),('resolved',final)]:
        path=tmp_path/(name+'.json');path.write_text(browser_export(report),encoding='utf-8');checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(path)],capture_output=True,text=True,timeout=10,check=True)
        assert json.loads(checked.stdout)==report['paired_model_diagnostics']
    assert all(path.read_bytes()==raw for path,raw in original.items())
