"""Source receipt histories cannot be converted into invented past forecasts."""
import hashlib
import json
from datetime import timedelta

import pytest
from app.backtest import forecast_cli
from app.backtest.forecast_baselines import PROBABILITY_METHOD
from test_daily_afi_bridge import POLICY, chart, days, encode, end, universe

from scripts.observation_runtime import daily_probability_replay as replay
from scripts.observation_runtime.daily_afi_export import export_daily_dataset


def inputs(root, *, incremental=True, target='PENDING_TARGET', lookback=5, asset_class='US_ETF'):
    calendar = days(17)
    snapshots = []
    indices = range(16) if incremental else [15]
    for index in indices:
        raw = encode(chart(calendar[:index+1], asset_class=asset_class))
        pin = hashlib.sha256(raw).hexdigest()
        (root/(pin+'.json')).write_bytes(raw)
        snapshots.append({'file': pin+'.json', 'sha256': pin, 'received_at': (end(calendar[index])+timedelta(minutes=1)).isoformat()})
    asof = end(calendar[15])+timedelta(minutes=2)
    outcome_asof = asof
    if target == 'PENDING_PUBLICATION':
        raw = encode(chart(calendar, asset_class=asset_class))
        pin = hashlib.sha256(raw).hexdigest()
        (root/(pin+'.json')).write_bytes(raw)
        late = end(calendar[16])+timedelta(hours=1)
        snapshots.append({'file': pin+'.json', 'sha256': pin, 'received_at': late.isoformat()})
        asof, outcome_asof = late+timedelta(minutes=1), late-timedelta(minutes=30)
    elif target == 'MISSING_OUTCOME':
        asof = outcome_asof = end(calendar[16])+timedelta(hours=1)
    source = {'schema': 'ATLAS_SYNTHETIC_DAILY_EXPORT_REQUEST_V1', 'snapshots': snapshots,
              'symbol': 'SPY' if asset_class == 'US_ETF' else 'AAPL', 'asset_class': asset_class,
              'universe': universe(asset_class), 'dataset_id': 'daily-replay-fixture',
              'version': 'v1', 'asof': snapshots[-1]['received_at'], **POLICY}
    (root/'source-request.json').write_bytes(encode(source))
    binding = export_daily_dataset(bundle_root=root, request_name='source-request.json', output_root=root)['binding']
    issues = [end(calendar[index])+timedelta(minutes=2) for index in range(1, 16)]
    issue_raw = encode([value.isoformat() for value in issues])
    issue_pin = hashlib.sha256(issue_raw).hexdigest()
    (root/(issue_pin+'.json')).write_bytes(issue_raw)
    request = {'schema': 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_REPLAY_REQUEST_V1', 'daily_export': binding,
               'expected_daily_export_sha256': binding[:-5], 'issues': issue_pin+'.json', 'expected_issues_sha256': issue_pin,
               'asof': asof.isoformat(), 'outcome_asof': outcome_asof.isoformat(), 'method': 'NO_CHANGE',
               'lookback': lookback, 'horizon': '1D', 'probability_method': PROBABILITY_METHOD}
    (root/'replay-request.json').write_bytes(encode(request))
    return request


def run(root):
    return replay.export_daily_probability_replay(bundle_root=root, request_name='replay-request.json', output_root=root)


def has_companion(root):
    values = (json.loads(path.read_bytes()) for path in root.glob('*.json'))
    return any(type(value) is dict and value.get('schema') == 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_REPLAY_V1' for value in values)


def test_identical_issue_list_bulk_and_incremental_have_honest_availability_denominators(tmp_path):
    results = []
    pins = []
    for name, incremental in [('bulk', False), ('incremental', True)]:
        root = tmp_path/name
        root.mkdir()
        request = inputs(root, incremental=incremental)
        pins.append(request['expected_issues_sha256'])
        result = run(root)
        assert run(root) == result
        assert result['requested_n'] == result['issued_n']+result['refused_n'] == 15
        assert result['issued_n'] == result['resolved_n']+result['unscored_n']
        assert result['unscored_n'] == result['pending_target_n']+result['pending_publication_n']+result['missing_outcome_n']
        report = json.loads((root/result['report']).read_bytes())
        assert len(report['cases']) == 15
        assert report['predictive_skill_established'] is False
        assert result['startup_authorized'] is result['source_authenticated'] is False
        companion = json.loads((root/result['daily_companion']).read_bytes())
        assert (root/companion['request_snapshot']).read_bytes() == (root/'replay-request.json').read_bytes()
        assert companion['expected_issues_sha256'] == request['expected_issues_sha256']
        results.append(result)
    assert pins[0] == pins[1]
    assert (results[0]['refused_n'], results[0]['issued_n'], results[0]['resolved_n']) == (14, 1, 0)
    assert (results[1]['refused_n'], results[1]['issued_n'], results[1]['resolved_n']) == (3, 12, 11)


@pytest.mark.parametrize('target', ['PENDING_TARGET', 'PENDING_PUBLICATION', 'MISSING_OUTCOME'])
def test_unavailable_targets_remain_in_requested_denominator(tmp_path, target):
    inputs(tmp_path, target=target)
    result = run(tmp_path)
    report = json.loads((tmp_path/result['report']).read_bytes())
    assert report['cases'][-1]['status'] == target
    assert result['unscored_n'] == 1
    assert result[{'PENDING_TARGET': 'pending_target_n', 'PENDING_PUBLICATION': 'pending_publication_n',
                   'MISSING_OUTCOME': 'missing_outcome_n'}[target]] == 1


def test_valid_but_untrainable_configuration_records_all_refusals(tmp_path):
    inputs(tmp_path, lookback=1000)
    result = run(tmp_path)
    assert result['requested_n'] == result['refused_n'] == 15
    assert result['issued_n'] == result['resolved_n'] == result['unscored_n'] == 0
    report = json.loads((tmp_path/result['report']).read_bytes())
    assert all(row['status'] == 'REFUSED' for row in report['cases'])


@pytest.mark.parametrize('fault', ['source-pin', 'issue-pin', 'duplicate-issue', 'unordered-issues', 'future-issue',
                                  'naive-issue', 'method', 'lookback', 'horizon', 'probability', 'outcome-cutoff', 'unknown-field'])
def test_invalid_plan_refused_before_any_new_artifact(tmp_path, fault):
    request = inputs(tmp_path)
    if fault in ('duplicate-issue', 'unordered-issues', 'future-issue', 'naive-issue'):
        issues = json.loads((tmp_path/request['issues']).read_bytes())
        if fault == 'duplicate-issue': issues[1] = issues[0]
        elif fault == 'unordered-issues': issues.reverse()
        elif fault == 'future-issue': issues[-1] = '2028-01-01T00:00:00+00:00'
        else: issues[-1] = '2026-10-01T20:02:00'
        raw = encode(issues)
        pin = hashlib.sha256(raw).hexdigest()
        (tmp_path/(pin+'.json')).write_bytes(raw)
        request.update(issues=pin+'.json', expected_issues_sha256=pin)
    elif fault == 'source-pin': request['expected_daily_export_sha256'] = '0'*64
    elif fault == 'issue-pin': request['expected_issues_sha256'] = '0'*64
    elif fault == 'method': request['method'] = 'MAGIC'
    elif fault == 'lookback': request['lookback'] = True
    elif fault == 'horizon': request['horizon'] = '5D'
    elif fault == 'probability': request['probability_method'] = 'CERTAIN_UP'
    elif fault == 'outcome-cutoff': request['outcome_asof'] = '2028-01-01T00:00:00+00:00'
    else: request['live_authorized'] = True
    (tmp_path/'replay-request.json').write_bytes(encode(request))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError):
        run(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_failed_base_html_publication_retains_request_and_report_without_companion(tmp_path, monkeypatch):
    inputs(tmp_path)
    original = forecast_cli.publish_research_text

    def fail(root, text, **kwargs):
        if kwargs['extension'] == '.html':
            raise OSError('synthetic replay storage failure')
        return original(root, text, **kwargs)

    monkeypatch.setattr(forecast_cli, 'publish_research_text', fail)
    before = set(tmp_path.iterdir())
    with pytest.raises(OSError, match='storage failure'):
        run(tmp_path)
    added = set(tmp_path.iterdir())-before
    assert len(added) == 2
    assert not any(json.loads(path.read_bytes()).get('schema') == 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_REPLAY_V1' for path in added)


def test_final_companion_failure_does_not_become_success(tmp_path, monkeypatch):
    inputs(tmp_path)
    original = replay.publish_research_text

    def fail(root, text, **kwargs):
        if json.loads(text).get('schema') == 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_REPLAY_V1':
            raise OSError('synthetic companion failure')
        return original(root, text, **kwargs)

    monkeypatch.setattr(replay, 'publish_research_text', fail)
    with pytest.raises(OSError, match='companion failure'):
        run(tmp_path)


def test_cli_retains_explicit_case_counts(tmp_path, capsys):
    inputs(tmp_path)
    assert replay.main(['--bundle-root', str(tmp_path), '--request', 'replay-request.json', '--output-root', str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)['requested_n'] == 15
    with pytest.raises(SystemExit) as exc:
        replay.main([])
    assert exc.value.code == 2


def test_rehashed_but_wrong_producer_report_is_not_accepted(tmp_path, monkeypatch):
    inputs(tmp_path)
    original = replay.run_probability_replay

    def wrong(**kwargs):
        result = original(**kwargs)
        report = json.loads((tmp_path/result['report']).read_bytes())
        report['requested_n'] += 1
        raw = encode(report)+b'\n'
        name = hashlib.sha256(raw).hexdigest()+'.json'
        (tmp_path/name).write_bytes(raw)
        return {**result, 'report': name}

    monkeypatch.setattr(replay, 'run_probability_replay', wrong)
    with pytest.raises(ValueError, match='source-bound preflight'):
        run(tmp_path)
    assert not has_companion(tmp_path)


def test_source_change_after_base_publication_keeps_uncertain_partial_evidence(tmp_path, monkeypatch):
    request = inputs(tmp_path)
    original = replay.run_probability_replay

    def changed(**kwargs):
        result = original(**kwargs)
        binding = json.loads((tmp_path/request['daily_export']).read_bytes())
        path = tmp_path/binding['artifacts']['audit']
        value = json.loads(path.read_bytes())
        value['record_n'] += 1
        path.write_bytes(encode(value))
        return result

    monkeypatch.setattr(replay, 'run_probability_replay', changed)
    with pytest.raises(ValueError):
        run(tmp_path)
    assert any(path.suffix == '.html' for path in tmp_path.iterdir())
    assert not has_companion(tmp_path)


def test_snapshot_failure_prevents_base_replay_publication(tmp_path, monkeypatch):
    inputs(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    def fail(*args, **kwargs):
        raise OSError('synthetic request snapshot failure')

    def forbidden(**kwargs):
        raise AssertionError('Base publication must not start')

    monkeypatch.setattr(replay, 'publish_research_text', fail)
    monkeypatch.setattr(replay, 'run_probability_replay', forbidden)
    with pytest.raises(OSError, match='snapshot failure'):
        run(tmp_path)
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir()}


@pytest.mark.parametrize('asset_class,asset', [('US_EQUITY', 'US_EQUITY:AAPL'), ('US_ETF', 'ETF:SPY')])
def test_source_asset_identity_and_drift_model_stay_bound(tmp_path, asset_class, asset):
    request = inputs(tmp_path, asset_class=asset_class)
    request['method'] = 'ENDPOINT_DRIFT'
    (tmp_path/'replay-request.json').write_bytes(encode(request))
    result = run(tmp_path)
    report = json.loads((tmp_path/result['report']).read_bytes())
    assert report['asset_id'] == asset and report['method'] == 'ENDPOINT_DRIFT'
    assert all(row['asset_id'] == asset for row in report['forecasts'])
    assert result['requested_n'] == 15 and result['refused_n'] == 3
