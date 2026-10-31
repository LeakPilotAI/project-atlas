"""Original holdout forecasts reach the existing offline viewer without changing scope."""
import json
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from test_daily_afi_bridge import days, end
from test_daily_holdout_diagnostics import evaluate
from test_daily_probability_protocol import _freeze

from scripts.observation_runtime import daily_holdout_accountability as bridge


def args(root, *, pending=False):
    source, frozen = _freeze(root)
    cutoff = (end(days(17)[14])+timedelta(minutes=3)).isoformat() if pending else None
    result = evaluate(root, source, frozen, cutoff)
    return {'bundle_root': root, 'companion_name': result['daily_holdout'],
            'expected_companion_sha256': result['daily_holdout'][:-5], 'output_root': root}


@pytest.mark.parametrize('pending', [False, True])
def test_holdout_to_browser_preserves_forecasts_states_and_existing_inputs(tmp_path, pending):
    arguments = args(tmp_path, pending=pending)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = bridge.export_holdout_accountability(**arguments)
    assert all((tmp_path/name).read_bytes() == raw for name, raw in before.items())
    record = json.loads((tmp_path/result['bridge']).read_bytes())
    assert record['counts']['requested_n'] == 2
    assert record['accountability']['forecast_n'] == 2
    assert record['accountability']['scored_n'] == (1 if pending else 2)
    assert record['historical_execution_attested'] is record['startup_authorized'] is False
    assert record['refused_cases'] == []
    browser = tmp_path/result['browser_export']
    viewer = Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    code = """const fs=require('fs'),api=require(process.argv[1]);
api.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8')).then(r=>{
process.stdout.write(JSON.stringify({forecast_n:r.forecast_n,states:r.rows.map(x=>x.status),scored_n:r.score.scored_n}));
}).catch(e=>{console.error(e);process.exitCode=1});"""
    checked = subprocess.run(['C:/Program Files/nodejs/node.exe', '-e', code, str(viewer), str(browser)],
                             capture_output=True, text=True, timeout=15, check=False)
    assert checked.returncode == 0, checked.stderr
    imported = json.loads(checked.stdout)
    assert imported['forecast_n'] == 2 and imported['scored_n'] == (1 if pending else 2)
    assert imported['states'].count('PENDING_TARGET') == int(pending)
    assert bridge.export_holdout_accountability(**arguments) == result


def test_wrong_pin_and_foreign_output_refuse_before_publication(tmp_path):
    arguments = args(tmp_path)
    arguments['expected_companion_sha256'] = '0'*64
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError):
        bridge.export_holdout_accountability(**arguments)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    foreign = tmp_path/'foreign'
    foreign.mkdir()
    arguments['output_root'] = foreign
    with pytest.raises(ValueError):
        bridge.export_holdout_accountability(**arguments)
    assert list(foreign.iterdir()) == []


def test_failure_retains_partial_artifacts_without_success_bridge(tmp_path, monkeypatch):
    arguments = args(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def failed(**kwargs):
        raise OSError('synthetic accountability publication failure')

    monkeypatch.setattr(bridge, 'run_bundle', failed)
    with pytest.raises(OSError, match='publication failure'):
        bridge.export_holdout_accountability(**arguments)
    assert all((tmp_path/name).read_bytes() == raw for name, raw in before.items())
    assert len(list(tmp_path.iterdir())) > len(before)
    for p in tmp_path.glob('*.json'):
        value = json.loads(p.read_bytes())
        assert not (isinstance(value, dict) and value.get('schema') == 'ATLAS_SYNTHETIC_HOLDOUT_ACCOUNTABILITY_BRIDGE_V1')


@pytest.mark.parametrize('split_minute', [1, -1])
def test_split_refusal_scope_and_empty_batch_refusal(tmp_path, split_minute):
    import hashlib

    from test_daily_afi_bridge import action_snapshot, encode
    from test_daily_probability_protocol import _freeze_request

    from scripts.observation_runtime.daily_afi_export import export_daily_dataset
    from scripts.observation_runtime.daily_probability_replay import (
        export_daily_probability_protocol,
    )

    source, request = _freeze_request(tmp_path)
    source_request = json.loads((tmp_path/'source-request.json').read_bytes())
    event = {'action_id': 'between-holdout-issues', 'kind': 'SPLIT',
             'effective_at': (end(days(17)[14])+timedelta(minutes=split_minute)).isoformat(),
             'amount': 2, 'economic_unit': 'NEW_SHARES_PER_OLD_SHARE'}
    action = action_snapshot([event], end(days(17)[14])+timedelta(seconds=30))
    raw = action['payload_bytes']
    pin = hashlib.sha256(raw).hexdigest()
    (tmp_path/(pin+'.json')).write_bytes(raw)
    source_request['action_snapshots'] = [{'file': pin+'.json', 'sha256': pin,
        'received_at': action['received_at'].isoformat(), 'source_id': action['source_id']}]
    (tmp_path/'source-actions.json').write_bytes(encode(source_request))
    binding = export_daily_dataset(bundle_root=tmp_path, request_name='source-actions.json', output_root=tmp_path)['binding']
    for value in (source, request):
        value['daily_export'] = binding
        value['expected_daily_export_sha256'] = binding[:-5]
    (tmp_path/'protocol-request.json').write_bytes(encode(request))
    frozen = export_daily_probability_protocol(bundle_root=tmp_path, request_name='protocol-request.json', output_root=tmp_path)
    held = evaluate(tmp_path, source, frozen)
    if split_minute == -1:
        before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
        with pytest.raises(ValueError, match='1 to 32'):
            bridge.export_holdout_accountability(bundle_root=tmp_path, companion_name=held['daily_holdout'],
                expected_companion_sha256=held['daily_holdout'][:-5], output_root=tmp_path)
        assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
        return
    result = bridge.export_holdout_accountability(bundle_root=tmp_path, companion_name=held['daily_holdout'],
        expected_companion_sha256=held['daily_holdout'][:-5], output_root=tmp_path)
    record = json.loads((tmp_path/result['bridge']).read_bytes())
    assert record['counts']['requested_n'] == 2
    assert record['counts']['refused_n'] == record['accountability']['forecast_n'] == 1
    assert len(record['refused_cases']) == 1
    assert 'Cross-split' in record['refused_cases'][0]['reason']
    assert 'ISSUED_FORECASTS_ONLY' in record['browser_scope']


@pytest.mark.parametrize('n', [0, 33, 128])
def test_issued_population_never_truncates(n):
    forecasts = [{} for _ in range(n)]
    with pytest.raises(ValueError, match='never truncate'):
        bridge._issued_population({'forecasts': forecasts})
    assert len(forecasts) == n
