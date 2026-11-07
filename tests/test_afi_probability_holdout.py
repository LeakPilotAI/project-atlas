import hashlib
import json
from datetime import timedelta

import pytest
from app.backtest.forecast_baselines import fingerprint, probability_algorithm
from app.backtest.forecast_cli import (
    main,
    run_probability_holdout,
    run_probability_protocol,
)
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_replay import (
    evaluate_probability_holdout,
    freeze_probability_protocol,
)
from test_afi_baselines import ASOF, ASSET, history
from test_afi_replay import frozen, issue


def protocol(review=None, **changes):
    arguments={'asset_id':ASSET,'selection_issues':[issue(20),issue(21)],'holdout_issues':[issue(25),issue(26)],
               'frozen_at':issue(24),'evidence_asof':ASOF,'lookback':5}
    arguments.update(changes)
    return freeze_probability_protocol(review or history(),**arguments)


def evaluate(value, **changes):
    arguments={'expected_protocol_sha256':value['protocol_sha256'],'evidence_asof':ASOF};arguments.update(changes)
    return evaluate_probability_holdout(history(),value,**arguments)


def test_reconstructs_existing_selection_and_fixed_probability_rules():
    p=protocol();assert p==protocol() and p['selection']==frozen()
    assert p['probability_algorithm']==probability_algorithm() and p['probability_algorithm']['alpha']==p['probability_algorithm']['beta']==1
    result=evaluate(p);replay=result['replay']
    assert replay['requested_n']==replay['resolved_n']==2 and replay['probability_diagnostics']['probability_n']==2
    assert result['selected_point_method']==p['selection']['selected_method']
    assert result['selection_basis']=='PRE_FREEZE_POINT_MAE_NOT_HOLDOUT_BRIER'
    for key in ('independently_unseen','retuning_allowed','calibration_established','predictive_skill_established','production_approved','trading_authority'):assert result[key] is False


@pytest.mark.parametrize('field',['probability_algorithm','holdout_issues','selection','independently_unseen','protocol_sha256'])
def test_rehashed_protocol_edits_cannot_pass_original_pin(field):
    p=protocol();original=p['protocol_sha256']
    if field=='probability_algorithm':p[field]['alpha']=2
    elif field=='holdout_issues':p[field]=[issue(27).isoformat()]
    elif field=='selection':p[field]['lookback']=10
    elif field=='independently_unseen':p[field]=True
    else:p[field]='a'*64
    if field!='protocol_sha256':p['protocol_sha256']=fingerprint({k:v for k,v in p.items() if k!='protocol_sha256'})
    with pytest.raises(ForecastEvidenceRefused):evaluate(p,expected_protocol_sha256=original)


def test_boolean_smoothing_is_not_equal_to_integer_declaration():
    p=protocol();p['probability_algorithm']['alpha']=True;p['protocol_sha256']=fingerprint({k:v for k,v in p.items() if k!='protocol_sha256'})
    with pytest.raises(ForecastEvidenceRefused):evaluate(p)


@pytest.mark.parametrize('pin',[None,True,'a'*64,'short'])
def test_missing_or_wrong_retained_pin_refuses(pin):
    with pytest.raises(ForecastEvidenceRefused):evaluate(protocol(),expected_protocol_sha256=pin)


@pytest.mark.parametrize('times',[[issue(20)],[issue(25),issue(25)],[issue(26),issue(25)],[]])
def test_overlap_pre_freeze_duplicate_or_empty_holdout_refuses(times):
    with pytest.raises(ForecastEvidenceRefused):protocol(holdout_issues=times)


def test_unavailable_selection_and_embargoed_labels_refuse():
    with pytest.raises(ForecastEvidenceRefused):protocol(frozen_at=issue(21))
    with pytest.raises(ForecastEvidenceRefused):protocol(embargo=timedelta(days=4))


def test_label_vintage_does_not_change_protocol_or_invent_scores():
    p=protocol();raw=json.dumps(p,sort_keys=True);pending=evaluate(p,outcome_asof=issue(26));resolved=evaluate(p)
    assert pending['replay']['resolved_n']==1 and pending['replay']['pending_target_n']==1
    assert resolved['replay']['resolved_n']==2 and json.dumps(p,sort_keys=True)==raw


def files(tmp_path):
    review=history();manifest=tmp_path/'manifest.json';records=tmp_path/'records.json';plan=tmp_path/'plan.json';output=tmp_path/'output';output.mkdir()
    manifest.write_bytes(review.manifest_bytes);records.write_bytes(review.payload_bytes)
    plan.write_text(json.dumps({'selection_issues':[issue(20).isoformat(),issue(21).isoformat()],
                    'holdout_issues':[issue(25).isoformat(),issue(26).isoformat()],'frozen_at':issue(24).isoformat(),'lookback':5,'embargo_seconds':0}),encoding='utf-8')
    return {'manifest':manifest,'records':records,'plan':plan,'output_root':output,'asset_id':ASSET,'evidence_asof':ASOF}


def test_actual_protocol_publication_and_holdout_are_idempotent(tmp_path):
    arguments=files(tmp_path);created=run_probability_protocol(**arguments);root=arguments['output_root'];path=root/created['protocol'];original=path.read_bytes()
    assert run_probability_protocol(**arguments)==created and path.read_bytes()==original
    arguments.pop('plan');arguments.update(protocol_path=path,expected_protocol_sha256=created['protocol_sha256'])
    result=run_probability_holdout(**arguments);before={p:p.read_bytes() for p in root.iterdir()}
    assert run_probability_holdout(**arguments)==result and all(p.read_bytes()==raw for p,raw in before.items())
    data=json.loads((root/result['report']).read_text(encoding='utf-8'))
    assert data['schema']=='AFI_PROBABILITY_HOLDOUT_V1' and data['replay']['resolved_n']==2
    assert 'Frozen-protocol probability holdout' in (root/result['dashboard']).read_text(encoding='utf-8')
    assert hashlib.sha256(original).hexdigest()==path.stem


def test_actual_cli_freeze_then_holdout_and_override_refusal(tmp_path,capsys):
    args=files(tmp_path);base=['--manifest',str(args['manifest']),'--records',str(args['records']),'--output-root',str(args['output_root']),
                             '--asset',ASSET,'--asof',ASOF.isoformat()]
    assert main(base+['--freeze-probability-plan',str(args['plan'])])==0
    created=json.loads(capsys.readouterr().out);command=base+['--probability-protocol',str(args['output_root']/created['protocol']),'--expected-protocol-sha256',created['protocol_sha256']]
    assert main(command)==0 and json.loads(capsys.readouterr().out)['resolved_n']==2
    before={p:p.read_bytes() for p in args['output_root'].iterdir()}
    assert main(command+['--lookback','10'])==2
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED' and all(p.read_bytes()==raw for p,raw in before.items())


def test_protocol_asset_conflict_never_publishes_holdout(tmp_path):
    args=files(tmp_path);created=run_probability_protocol(**args);root=args['output_root'];before={p:p.read_bytes() for p in root.iterdir()}
    args.pop('plan');args.update(asset_id='CRYPTO:ETH-USD',protocol_path=root/created['protocol'],expected_protocol_sha256=created['protocol_sha256'])
    with pytest.raises(ForecastEvidenceRefused):run_probability_holdout(**args)
    assert {p:p.read_bytes() for p in root.iterdir()}==before
