"""Read-only diagnostics distinguish refusal, unavailable labels and scored outcomes."""
import hashlib
import json
from datetime import timedelta

import pytest
from test_daily_afi_bridge import action_snapshot, days, encode, end
from test_daily_probability_protocol import _freeze, _freeze_request, _holdout_request

from scripts.observation_runtime import daily_probability_replay as replay
from scripts.observation_runtime.daily_afi_export import export_daily_dataset


def evaluate(root, source, frozen, outcome=None):
    _holdout_request(root, source, frozen, outcome_asof=outcome)
    return replay.export_daily_probability_holdout(bundle_root=root, request_name='holdout-request.json', output_root=root)


def diagnose(root, result):
    return replay.diagnose_daily_probability_holdout(bundle_root=root, companion_name=result['daily_holdout'],
                                                    expected_companion_sha256=result['daily_holdout'][:-5])


def test_resolved_diagnostic_is_readonly_and_reconciled(tmp_path, monkeypatch):
    source, frozen = _freeze(tmp_path)
    result = evaluate(tmp_path, source, frozen)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr(replay, 'publish_research_text', lambda *a, **k: pytest.fail('diagnostic published'))
    report = diagnose(tmp_path, result)
    assert report['counts']['requested_n'] == report['counts']['resolved_n'] == 2
    assert report['refusal_reasons'] == []
    assert report['distinct_resolved_targets'] == 2
    assert report['sample_status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['startup_authorized'] is report['predictive_skill_established'] is False
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_pending_target_is_not_error_or_missing_event(tmp_path):
    source, frozen = _freeze(tmp_path)
    result = evaluate(tmp_path, source, frozen, (end(days(17)[14])+timedelta(minutes=3)).isoformat())
    report = diagnose(tmp_path, result)
    assert report['counts']['resolved_n'] == report['counts']['pending_target_n'] == 1
    assert report['counts']['unscored_n'] == 1
    case = report['cases'][-1]
    assert case['status'] == 'PENDING_TARGET' and case['brier'] is None
    missing = next(v for v in report['states'] if v['status'] == 'MISSING_OUTCOME')
    assert 'does not prove a missed market event' in missing['meaning']


def test_split_holdout_refusals_keep_requested_denominator(tmp_path):
    source, protocol_request = _freeze_request(tmp_path)
    request = json.loads((tmp_path/'source-request.json').read_bytes())
    event = {'action_id': 'holdout-split', 'kind': 'SPLIT',
             'effective_at': end(days(17)[13]).isoformat(), 'amount': 2,
             'economic_unit': 'NEW_SHARES_PER_OLD_SHARE'}
    action = action_snapshot([event], end(days(17)[13])+timedelta(seconds=30))
    raw = action['payload_bytes']
    pin = hashlib.sha256(raw).hexdigest()
    (tmp_path/(pin+'.json')).write_bytes(raw)
    request['action_snapshots'] = [{'file': pin+'.json', 'sha256': pin,
                                   'received_at': action['received_at'].isoformat(),
                                   'source_id': action['source_id']}]
    (tmp_path/'action-source.json').write_bytes(encode(request))
    binding = export_daily_dataset(bundle_root=tmp_path, request_name='action-source.json', output_root=tmp_path)['binding']
    for value in (source, protocol_request):
        value['daily_export'] = binding
        value['expected_daily_export_sha256'] = binding[:-5]
    (tmp_path/'protocol-request.json').write_bytes(encode(protocol_request))
    frozen = replay.export_daily_probability_protocol(bundle_root=tmp_path, request_name='protocol-request.json', output_root=tmp_path)
    report = diagnose(tmp_path, evaluate(tmp_path, source, frozen))
    assert report['counts']['requested_n'] == report['counts']['refused_n'] == 2
    assert report['counts']['issued_n'] == report['counts']['resolved_n'] == 0
    assert report['refusal_reasons'] == [{'reason': 'Cross-split training units not accepted', 'n': 2}]
    assert all(c['status'] == 'REFUSED' for c in report['cases'])


def test_cli_is_explicit_and_forbids_output_root(tmp_path, capsys):
    source, frozen = _freeze(tmp_path)
    result = evaluate(tmp_path, source, frozen)
    args = ['--bundle-root', str(tmp_path), '--diagnose-holdout', result['daily_holdout'],
            '--expected-companion-sha256', result['daily_holdout'][:-5]]
    assert replay.main(args) == 0
    assert json.loads(capsys.readouterr().out)['counts']['requested_n'] == 2
    with pytest.raises(SystemExit) as error:
        replay.main(args+['--output-root', str(tmp_path)])
    assert error.value.code == 2


def test_corrupt_report_refuses_without_diagnostic_success(tmp_path):
    source, frozen = _freeze(tmp_path)
    result = evaluate(tmp_path, source, frozen)
    (tmp_path/result['report']).write_bytes(b'{}')
    with pytest.raises(ValueError):
        diagnose(tmp_path, result)


def test_pending_publication_distinguishes_record_existence_from_available_label(tmp_path):
    source, frozen = _freeze(tmp_path)
    cutoff = (end(days(17)[15])+timedelta(seconds=30)).isoformat()
    report = diagnose(tmp_path, evaluate(tmp_path, source, frozen, cutoff))
    assert report['counts']['resolved_n'] == report['counts']['pending_publication_n'] == 1
    assert report['counts']['missing_outcome_n'] == 0
    assert report['cases'][-1]['status'] == 'PENDING_PUBLICATION'
    assert report['cases'][-1]['actual'] is None


def test_wrong_retained_companion_pin_refuses(tmp_path):
    source, frozen = _freeze(tmp_path)
    result = evaluate(tmp_path, source, frozen)
    with pytest.raises(ValueError):
        replay.diagnose_daily_probability_holdout(bundle_root=tmp_path,
            companion_name=result['daily_holdout'], expected_companion_sha256='0'*64)


def test_elapsed_target_without_supplied_record_remains_missing(tmp_path):
    source, request = _freeze_request(tmp_path)
    issues = json.loads((tmp_path/source['issues']).read_bytes())
    plan = json.loads((tmp_path/request['plan']).read_bytes())
    plan['holdout_issues'] = [issues[13], issues[14]]
    raw = encode(plan)
    pin = hashlib.sha256(raw).hexdigest()
    (tmp_path/(pin+'.json')).write_bytes(raw)
    request['plan'], request['expected_plan_sha256'] = pin+'.json', pin
    (tmp_path/'protocol-request.json').write_bytes(encode(request))
    frozen = replay.export_daily_probability_protocol(bundle_root=tmp_path, request_name='protocol-request.json', output_root=tmp_path)
    cutoff = (end(days(17)[16])+timedelta(minutes=3)).isoformat()
    _holdout_request(tmp_path, source, frozen, outcome_asof=cutoff)
    evaluation = json.loads((tmp_path/'holdout-request.json').read_bytes())
    evaluation['evidence_asof'] = cutoff
    (tmp_path/'holdout-request.json').write_bytes(encode(evaluation))
    result = replay.export_daily_probability_holdout(bundle_root=tmp_path, request_name='holdout-request.json', output_root=tmp_path)
    report = diagnose(tmp_path, result)
    assert report['counts']['requested_n'] == report['counts']['issued_n'] == 2
    assert report['counts']['resolved_n'] == report['counts']['missing_outcome_n'] == 1
    assert report['counts']['pending_target_n'] == report['counts']['pending_publication_n'] == 0
    assert report['cases'][-1]['actual'] is report['cases'][-1]['brier'] is None


def test_mutation_after_first_verification_cannot_yield_success(tmp_path, monkeypatch):
    source, frozen = _freeze(tmp_path)
    result = evaluate(tmp_path, source, frozen)
    original = replay.verify_daily_probability_holdout
    calls = 0

    def change_after_verifying(**kwargs):
        nonlocal calls
        verified = original(**kwargs)
        calls += 1
        if calls == 1:
            path = tmp_path/result['report']
            raw = path.read_bytes()
            (tmp_path/'original-report-retained').write_bytes(raw)
            path.write_bytes(b'{}')
        return verified

    monkeypatch.setattr(replay, 'verify_daily_probability_holdout', change_after_verifying)
    with pytest.raises(ValueError):
        diagnose(tmp_path, result)
    assert calls == 1
