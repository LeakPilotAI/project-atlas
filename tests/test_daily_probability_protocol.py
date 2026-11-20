"""Daily receipt archives bind pre-freeze selection and later holdout evaluation."""
import hashlib
import json
import shutil
from datetime import timedelta

import pytest
from app.backtest import forecast_cli
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from test_daily_afi_bridge import days, encode, end
from test_daily_probability_replay import inputs

from scripts.observation_runtime import daily_probability_replay as replay
from scripts.observation_runtime.daily_probability_replay import (
    export_daily_probability_holdout,
    export_daily_probability_protocol,
    main,
    verify_daily_probability_holdout,
)


def _content_addressed(root, value):
    raw = encode(value)
    name = hashlib.sha256(raw).hexdigest()+'.json'
    (root/name).write_bytes(raw)
    return name, hashlib.sha256(raw).hexdigest()


def _freeze_request(root, *, incremental=True, lookback=5):
    source = inputs(root, incremental=incremental)
    issues = json.loads((root/source['issues']).read_bytes())
    plan = {
        'selection_issues': [issues[8], issues[9]],
        'holdout_issues': [issues[12], issues[13]],
        'frozen_at': issues[11],
        'lookback': lookback,
        'embargo_seconds': 0,
    }
    plan_name, plan_pin = _content_addressed(root, plan)
    request = {
        'schema': 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_PROTOCOL_REQUEST_V1',
        'daily_export': source['daily_export'],
        'expected_daily_export_sha256': source['expected_daily_export_sha256'],
        'plan': plan_name,
        'expected_plan_sha256': plan_pin,
        'asof': source['asof'],
    }
    (root/'protocol-request.json').write_bytes(encode(request))
    return source, request


def _freeze(root, **kwargs):
    source, _request = _freeze_request(root, **kwargs)
    result = export_daily_probability_protocol(
        bundle_root=root, request_name='protocol-request.json', output_root=root)
    return source, result


def _holdout_request(root, source, protocol_result, *, export=None, outcome_asof=None):
    daily_export = source['daily_export'] if export is None else export
    value = {
        'schema': 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_HOLDOUT_REQUEST_V1',
        'daily_export': daily_export,
        'expected_daily_export_sha256': daily_export[:-5],
        'daily_protocol': protocol_result['daily_protocol'],
        'expected_daily_protocol_sha256': protocol_result['daily_protocol'][:-5],
        'evidence_asof': source['asof'],
        'outcome_asof': outcome_asof or source['asof'],
    }
    (root/'holdout-request.json').write_bytes(encode(value))


def test_incremental_receipts_bind_selection_protocol_and_holdout(tmp_path):
    source, frozen = _freeze(tmp_path)
    protocol_companion = json.loads((tmp_path/frozen['daily_protocol']).read_bytes())
    protocol_raw = (tmp_path/protocol_companion['protocol_result']['protocol']).read_bytes()
    protocol = json.loads(protocol_raw)
    selection = protocol['selection']
    freeze_at = selection['frozen_at']
    binding = json.loads((tmp_path/source['daily_export']).read_bytes())

    assert frozen['status'] == 'OFFLINE_SYNTHETIC_PROTOCOL_COMPLETE'
    assert protocol['schema'] == 'AFI_PROBABILITY_PROTOCOL_V1'
    assert protocol['protocol_sha256'] == frozen['protocol_sha256']
    assert selection['dataset_sha256'] == binding['artifacts']['records'][:-5]
    assert selection['manifest_sha256'] == binding['artifacts']['manifest'][:-5]
    assert max(selection['selection_issues']) < freeze_at
    assert min(protocol['holdout_issues']) >= freeze_at
    assert set(selection['selection_issues']).isdisjoint(protocol['holdout_issues'])
    assert protocol['independently_unseen'] is False
    assert protocol_companion['expected_daily_export_sha256'] == source['daily_export'][:-5]

    _holdout_request(tmp_path, source, frozen)
    result = export_daily_probability_holdout(
        bundle_root=tmp_path, request_name='holdout-request.json', output_root=tmp_path)
    report = json.loads((tmp_path/result['report']).read_bytes())
    holdout = report['replay']
    assert result['status'] == 'OFFLINE_SYNTHETIC_HOLDOUT_COMPLETE'
    assert holdout['requested_n'] == 2
    assert holdout['resolved_n'] == 2
    assert holdout['refused_n'] == 0
    assert result['independently_unseen'] is False
    assert result['predictive_skill_established'] is False
    assert json.loads((tmp_path/result['daily_holdout']).read_bytes())['protocol_sha256'] == frozen['protocol_sha256']


def test_bulk_late_downloads_cannot_create_pre_freeze_selection_evidence(tmp_path):
    _source, _request = _freeze_request(tmp_path, incremental=False)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}

    with pytest.raises(ForecastEvidenceRefused, match='Selection includes unavailable'):
        export_daily_probability_protocol(
            bundle_root=tmp_path, request_name='protocol-request.json', output_root=tmp_path)

    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}


def test_insufficient_selection_window_refuses_before_protocol_publication(tmp_path):
    _freeze_request(tmp_path, lookback=1000)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    with pytest.raises(ValueError):
        export_daily_probability_protocol(
            bundle_root=tmp_path, request_name='protocol-request.json', output_root=tmp_path)

    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir()}


def test_foreign_protocol_source_and_stale_protocol_pin_refuse_holdout(tmp_path):
    source, frozen = _freeze(tmp_path)
    other = tmp_path/'other'
    other.mkdir()
    foreign_source, _ = _freeze_request(other, incremental=False)
    for path in other.iterdir():
        if len(path.name) == 69 and path.name.endswith('.json'):
            destination = tmp_path/path.name
            if not destination.exists():
                shutil.copyfile(path, destination)

    _holdout_request(tmp_path, source, frozen, export=foreign_source['daily_export'])
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    with pytest.raises(ValueError, match='different or unsupported source evidence'):
        export_daily_probability_holdout(
            bundle_root=tmp_path, request_name='holdout-request.json', output_root=tmp_path)
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}

    _holdout_request(tmp_path, source, frozen)
    request = json.loads((tmp_path/'holdout-request.json').read_bytes())
    request['expected_daily_protocol_sha256'] = '0'*64
    (tmp_path/'holdout-request.json').write_bytes(encode(request))
    with pytest.raises(ValueError):
        export_daily_probability_holdout(
            bundle_root=tmp_path, request_name='holdout-request.json', output_root=tmp_path)


def test_source_receipt_artifact_change_refuses_holdout_without_rewriting_evidence(tmp_path):
    source, frozen = _freeze(tmp_path)
    _holdout_request(tmp_path, source, frozen)
    binding = json.loads((tmp_path/source['daily_export']).read_bytes())
    audit_path = tmp_path/binding['artifacts']['audit']
    audit = json.loads(audit_path.read_bytes())
    audit['record_n'] += 1
    audit_path.write_bytes(encode(audit))
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    with pytest.raises((ValueError, OSError)):
        export_daily_probability_holdout(
            bundle_root=tmp_path, request_name='holdout-request.json', output_root=tmp_path)

    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir()}


def test_explicit_cli_freezes_then_evaluates_the_same_daily_source(tmp_path, capsys):
    source, _request = _freeze_request(tmp_path)
    assert main(['--bundle-root', str(tmp_path), '--freeze-protocol', 'protocol-request.json',
                 '--output-root', str(tmp_path)]) == 0
    frozen = json.loads(capsys.readouterr().out)
    _holdout_request(tmp_path, source, frozen)

    assert main(['--bundle-root', str(tmp_path), '--evaluate-holdout', 'holdout-request.json',
                 '--output-root', str(tmp_path)]) == 0
    evaluated = json.loads(capsys.readouterr().out)
    assert evaluated['status'] == 'OFFLINE_SYNTHETIC_HOLDOUT_COMPLETE'
    assert evaluated['protocol_sha256'] == frozen['protocol_sha256']

    verify_args = ['--bundle-root', str(tmp_path), '--verify-holdout', evaluated['daily_holdout'],
                   '--expected-companion-sha256', evaluated['daily_holdout'][:-5]]
    assert main(verify_args) == 0
    assert json.loads(capsys.readouterr().out)['resolved_n'] == 2
    with pytest.raises(SystemExit) as exc:
        main(verify_args+['--output-root', str(tmp_path)])
    assert exc.value.code == 2


def test_holdout_verifier_reconstructs_exact_source_without_publication(tmp_path, monkeypatch):
    source, frozen = _freeze(tmp_path)
    _holdout_request(tmp_path, source, frozen)
    result = export_daily_probability_holdout(
        bundle_root=tmp_path, request_name='holdout-request.json', output_root=tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError('Read-only holdout verification cannot publish')

    monkeypatch.setattr(replay, 'publish_research_text', forbidden)
    monkeypatch.setattr(forecast_cli, 'publish_research_text', forbidden)
    checked = verify_daily_probability_holdout(
        bundle_root=tmp_path, companion_name=result['daily_holdout'],
        expected_companion_sha256=result['daily_holdout'][:-5])
    assert checked['status'] == 'SYNTHETIC_DAILY_PROBABILITY_HOLDOUT_REPRODUCED'
    assert checked['requested_n'] == 2 and checked['resolved_n'] == 2
    assert checked['history_completeness_verified'] is False
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}


def test_holdout_verifier_refuses_rehashed_authority_and_missing_dashboard(tmp_path):
    source, frozen = _freeze(tmp_path)
    _holdout_request(tmp_path, source, frozen)
    result = export_daily_probability_holdout(
        bundle_root=tmp_path, request_name='holdout-request.json', output_root=tmp_path)
    companion = json.loads((tmp_path/result['daily_holdout']).read_bytes())
    companion['live_authorized'] = True
    forged, forged_pin = _content_addressed(tmp_path, companion)
    with pytest.raises(ValueError):
        verify_daily_probability_holdout(bundle_root=tmp_path, companion_name=forged,
                                         expected_companion_sha256=forged_pin)

    dashboard = result['dashboard']
    (tmp_path/dashboard).rename(tmp_path/'preserved-missing-dashboard')
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    with pytest.raises((ValueError, OSError)):
        verify_daily_probability_holdout(
            bundle_root=tmp_path, companion_name=result['daily_holdout'],
            expected_companion_sha256=result['daily_holdout'][:-5])
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}


def test_later_holdout_cutoff_keeps_unpublished_and_future_labels_in_denominator(tmp_path):
    source, frozen = _freeze(tmp_path)
    cutoff = end(days(17)[14])+timedelta(minutes=3)
    _holdout_request(tmp_path, source, frozen, outcome_asof=cutoff.isoformat())

    result = export_daily_probability_holdout(
        bundle_root=tmp_path, request_name='holdout-request.json', output_root=tmp_path)
    report = json.loads((tmp_path/result['report']).read_bytes())
    replay_report = report['replay']
    statuses = [case['status'] for case in replay_report['cases']]
    assert replay_report['requested_n'] == 2
    assert replay_report['issued_n'] == 2
    assert replay_report['resolved_n'] == 1
    assert replay_report['unscored_n'] == 1
    assert replay_report['pending_publication_n'] == 0
    assert replay_report['pending_target_n'] == 1
    assert statuses == ['RESOLVED', 'PENDING_TARGET']
