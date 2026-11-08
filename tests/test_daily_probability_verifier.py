"""No-write source replay reconstruction and refusal of forged companions."""
import hashlib
import json

import pytest
from app.backtest import forecast_cli
from test_daily_afi_bridge import encode
from test_daily_probability_replay import inputs, run

from scripts.observation_runtime import daily_probability_replay as replay


def verify(root, result):
    return replay.verify_daily_probability_replay(bundle_root=root, companion_name=result['daily_companion'],
                                                   expected_companion_sha256=result['daily_companion'][:-5])


def resign(root, value):
    raw = encode(value)+b'\n'
    name = hashlib.sha256(raw).hexdigest()+'.json'
    (root/name).write_bytes(raw)
    return name


def test_readonly_verification_does_not_publish_or_rely_on_mutable_entry_names(tmp_path, monkeypatch):
    inputs(tmp_path)
    result = run(tmp_path)
    (tmp_path/'replay-request.json').rename(tmp_path/'retained-mutable-replay-entry.json')
    (tmp_path/'source-request.json').rename(tmp_path/'retained-mutable-source-entry.json')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def forbidden(*args, **kwargs):
        raise AssertionError('Read-only verification cannot publish')

    monkeypatch.setattr(replay, 'publish_research_text', forbidden)
    monkeypatch.setattr(forecast_cli, 'publish_research_text', forbidden)
    checked = verify(tmp_path, result)
    assert checked['status'] == 'SYNTHETIC_SOURCE_DAILY_REPLAY_REPRODUCED'
    assert checked['requested_n'] == 15 and checked['refused_n'] == 3 and checked['resolved_n'] == 11
    assert checked['source_authenticated'] is checked['history_completeness_verified'] is False
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('target', ['source', 'issues', 'manifest', 'records', 'audit', 'request', 'report', 'html', 'companion'])
def test_missing_component_never_becomes_success(tmp_path, target):
    request = inputs(tmp_path)
    result = run(tmp_path)
    companion = json.loads((tmp_path/result['daily_companion']).read_bytes())
    source = json.loads((tmp_path/request['daily_export']).read_bytes())
    names = {'source': source['request']['snapshots'][0]['file'], 'issues': request['issues'],
             **source['artifacts'], 'request': companion['request_snapshot'], 'report': result['report'],
             'html': result['dashboard'], 'companion': result['daily_companion']}
    (tmp_path/names[target]).rename(tmp_path/'preserved-missing-component')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises((ValueError, OSError)):
        verify(tmp_path, result)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('fault', ['count', 'authority', 'history', 'unseen', 'source', 'request-config', 'unknown'])
def test_self_rehashed_companion_cannot_invent_evidence_or_authority(tmp_path, fault):
    inputs(tmp_path)
    result = run(tmp_path)
    companion = json.loads((tmp_path/result['daily_companion']).read_bytes())
    if fault == 'count': companion['replay_result']['requested_n'] += 1
    elif fault == 'authority': companion['startup_authorized'] = True
    elif fault == 'history': companion['history_completeness_verified'] = True
    elif fault == 'unseen': companion['independently_unseen'] = True
    elif fault == 'source': companion['expected_daily_export_sha256'] = '0'*64
    elif fault == 'unknown': companion['live_authorized'] = True
    else:
        request = json.loads((tmp_path/companion['request_snapshot']).read_bytes())
        request['method'] = 'ENDPOINT_DRIFT'
        new = resign(tmp_path, request)
        companion.update(request_snapshot=new, expected_request_sha256=new[:-5])
    name = resign(tmp_path, companion)
    with pytest.raises(ValueError):
        replay.verify_daily_probability_replay(bundle_root=tmp_path, companion_name=name, expected_companion_sha256=name[:-5])


def test_validly_hashed_fabricated_dashboard_is_not_renderer_evidence(tmp_path):
    inputs(tmp_path)
    result = run(tmp_path)
    companion = json.loads((tmp_path/result['daily_companion']).read_bytes())
    raw = b'<!doctype html><title>Fabricated replay success</title>'
    name = hashlib.sha256(raw).hexdigest()+'.html'
    (tmp_path/name).write_bytes(raw)
    companion['replay_result']['dashboard'] = name
    new = resign(tmp_path, companion)
    with pytest.raises(ValueError, match='reconstructed source evidence'):
        replay.verify_daily_probability_replay(bundle_root=tmp_path, companion_name=new, expected_companion_sha256=new[:-5])


def test_explicit_readonly_cli_forbids_output_root(tmp_path, capsys):
    inputs(tmp_path)
    result = run(tmp_path)
    args = ['--bundle-root', str(tmp_path), '--verify-companion', result['daily_companion'],
            '--expected-companion-sha256', result['daily_companion'][:-5]]
    assert replay.main(args) == 0
    assert json.loads(capsys.readouterr().out)['requested_n'] == 15
    with pytest.raises(SystemExit) as exc:
        replay.main(args+['--output-root', str(tmp_path)])
    assert exc.value.code == 2
    with pytest.raises(ValueError):
        replay.verify_daily_probability_replay(bundle_root=tmp_path, companion_name=result['daily_companion'],
                                               expected_companion_sha256='0'*64)
