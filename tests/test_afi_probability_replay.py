import hashlib
import json
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_baselines import PROBABILITY_METHOD
from app.backtest.forecast_cli import main, run_probability_replay
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_replay import evaluate_holdout, replay_baselines
from test_afi_baselines import ASOF, ASSET, history
from test_afi_dataset_integrity import encode
from test_afi_replay import frozen, issue


def replay(review=None, **kwargs):
    return replay_baselines(review or history(),asset_id=ASSET,issued_times=kwargs.pop('issued_times',[issue(20),issue(21),issue(22)]),
                            evidence_asof=ASOF,probability_method=PROBABILITY_METHOD,lookback=5,**kwargs)


def revised(review,mutate):
    manifest=json.loads(review.manifest_bytes);payload=json.loads(review.payload_bytes);mutate(payload)
    raw=encode(payload);manifest.update(content_sha256=hashlib.sha256(raw).hexdigest(),record_count=len(payload['records']))
    return review_dataset(encode(manifest),raw,asof=ASOF)


def test_actual_refit_probabilities_and_brier_denominator():
    result=replay();metrics=result['probability_diagnostics']
    assert result['requested_n']==result['issued_n']==result['resolved_n']==metrics['probability_n']==3
    assert result['refused_n']==result['unscored_n']==0 and metrics['distinct_target_n']==3
    expected=sum((f.probability_up-int(o.price>f.reference_price))**2 for f,o in zip(result['forecasts'],result['outcomes'],strict=True))/3
    assert metrics['brier']==pytest.approx(expected) and metrics['uninformative_baseline_brier']==.25
    assert metrics['ratio_to_baseline']==pytest.approx(expected/.25)
    assert all(f.training_available_through<=f.issued_at for f in result['forecasts'])


def test_refusals_remain_in_requested_denominator():
    result=replay(issued_times=[issue(10),issue(20),issue(21)])
    assert result['requested_n']==3 and result['refused_n']==1 and result['resolved_n']==2
    assert result['requested_n']==result['refused_n']+result['issued_n']
    assert result['cases'][0]['status']=='REFUSED'


def test_pending_target_has_no_score_or_inferred_miss():
    result=replay(issued_times=[issue(20)],outcome_asof=issue(20))
    assert result['pending_target_n']==result['unscored_n']==1 and result['resolved_n']==0
    assert result['probability_diagnostics']['brier'] is None and result['probability_diagnostics']['uninformative_baseline_brier'] is None


def test_unpublished_target_is_distinct_from_missing_target():
    def delay(payload):
        for row in payload['records']:
            if row['observed_at'].startswith('2026-09-21'):row['available_at']='2026-09-23T00:00:00+00:00'
    review=revised(history(),delay);result=replay(review,issued_times=[issue(20)],outcome_asof=issue(22))
    assert result['pending_publication_n']==1 and result['missing_outcome_n']==0
    def remove(payload):payload['records']=[r for r in payload['records'] if not r['observed_at'].startswith('2026-09-21')]
    with pytest.raises(ForecastEvidenceRefused):replay(revised(history(),remove),issued_times=[issue(20)],outcome_asof=issue(22))
    missing=replay(issued_times=[datetime(2026,10,19,0,1,tzinfo=UTC)])
    assert missing['missing_outcome_n']==1 and missing['pending_publication_n']==0


def test_vintage_correction_changes_labels_not_original_issue_probabilities():
    def correct(payload):
        row=next(r for r in payload['records'] if r['observed_at'].startswith('2026-09-21'))
        payload['records'].append(dict(row,record_id='revised-label',revision='v2',available_at='2026-10-19T00:00:00+00:00',value=50,raw_price=50))
    review=revised(history(),correct)
    before=replay(review,issued_times=[issue(20)],outcome_asof=issue(22));after=replay(review,issued_times=[issue(20)])
    assert before['forecasts']==after['forecasts'] and before['resolved_n']==after['resolved_n']==1
    assert before['cases'][0]['source_revision']!='v2' and after['cases'][0]['source_revision']=='v2'
    assert before['cases'][0]['actual_up']!=after['cases'][0]['actual_up']


def test_same_target_multiple_issues_does_not_prove_independent_samples():
    times=[datetime(2026,9,20,0,i+1,tzinfo=UTC) for i in range(20)];result=replay(issued_times=times)
    assert result['resolved_n']==20 and result['probability_diagnostics']['distinct_target_n']==1
    assert result['probability_diagnostics']['status']=='OVERLAPPING_TARGET_EVIDENCE'
    for key in ('production_approved','trading_authority','calibration_established','predictive_skill_established','independent_samples_established','retuning_allowed'):assert result[key] is False


@pytest.mark.parametrize('times',[[issue(20),issue(20)],[issue(21),issue(20)],[issue(20).replace(tzinfo=None)],[]])
def test_invalid_or_duplicate_issue_sets_refuse(times):
    with pytest.raises(ForecastEvidenceRefused):replay(issued_times=times)


def test_probability_replay_cannot_change_existing_selection_and_holdout():
    review=history();selection=frozen();original=json.dumps(selection,sort_keys=True)
    replay(review,issued_times=[issue(25),issue(26)])
    holdout=evaluate_holdout(review,selection,holdout_issues=[issue(25),issue(26)],evidence_asof=ASOF)
    assert json.dumps(selection,sort_keys=True)==original and not holdout['retuning_allowed']
    assert all(f.probability_up is None for report in holdout['reports'].values() for f in report['forecasts'])


def inputs(tmp_path):
    review=history();manifest=tmp_path/'manifest.json';records=tmp_path/'records.json';issues=tmp_path/'issues.json';output=tmp_path/'output';output.mkdir()
    manifest.write_bytes(review.manifest_bytes);records.write_bytes(review.payload_bytes);issues.write_text(json.dumps([issue(20).isoformat(),issue(21).isoformat()]),encoding='utf-8')
    return {'manifest':manifest,'records':records,'issues':issues,'output_root':output,'asset_id':ASSET,'evidence_asof':ASOF,'lookback':5,'probability_method':PROBABILITY_METHOD}


def test_published_replay_is_idempotent_and_reconstructs_counts(tmp_path):
    arguments=inputs(tmp_path);result=run_probability_replay(**arguments);root=arguments['output_root'];original={p:p.read_bytes() for p in root.iterdir()}
    data=json.loads((root/result['report']).read_text(encoding='utf-8'))
    assert data['schema']=='AFI_SYNTHETIC_PROBABILITY_REPLAY_V1' and data['resolved_n']==2
    assert 'Fixed smoothing is not calibrated' in (root/result['dashboard']).read_text(encoding='utf-8')
    assert run_probability_replay(**arguments)==result and all(p.read_bytes()==raw for p,raw in original.items())


@pytest.mark.parametrize('change',[{'probability_method':None},{'probability_method':'MAGIC'},{'horizon':'5D'}])
def test_unsupported_replay_refuses_before_publication(tmp_path,change):
    arguments=inputs(tmp_path);arguments.update(change)
    with pytest.raises(ForecastEvidenceRefused):run_probability_replay(**arguments)
    assert not list(arguments['output_root'].iterdir())


def test_real_cli_mode_and_conflicting_input_refusal(tmp_path,capsys):
    arguments=inputs(tmp_path)
    command=['--manifest',str(arguments['manifest']),'--records',str(arguments['records']),'--output-root',str(arguments['output_root']),
             '--asset',ASSET,'--asof',ASOF.isoformat(),'--replay-issues',str(arguments['issues']),'--lookback','5','--probability-method',PROBABILITY_METHOD]
    assert main(command)==0;result=json.loads(capsys.readouterr().out);assert result['status']=='OFFLINE_SYNTHETIC_REPLAY_COMPLETE'
    assert main(command+['--interval','unsupported.json'])==2
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'
