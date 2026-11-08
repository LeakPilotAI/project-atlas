"""Portable seeds preserve original forecasts and immutable outcome history."""
import hashlib
import json
from datetime import timedelta

import pytest
from app.backtest import forecast_report
from test_daily_afi_bridge import chart, days, encode, end
from test_daily_holdout_accountability import args

from scripts.observation_runtime import daily_holdout_accountability as bridge
from scripts.observation_runtime.daily_afi_export import export_daily_dataset


def setup(root):
    exported = bridge.export_holdout_accountability(**args(root, pending=True))
    seed = bridge.prepare_holdout_continuation(bundle_root=root, bridge_name=exported['bridge'],
        expected_bridge_sha256=exported['bridge'][:-5], output_root=root)
    return exported, seed


def test_seed_is_no_append_idempotent_and_verifies_without_publishers(tmp_path, monkeypatch):
    exported, seed = setup(tmp_path)
    assert seed['outcome_appends_performed'] == 0
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert bridge.prepare_holdout_continuation(bundle_root=tmp_path, bridge_name=exported['bridge'],
        expected_bridge_sha256=exported['bridge'][:-5], output_root=tmp_path) == seed

    def forbidden(*a, **k):
        raise AssertionError('Verification cannot publish or append')

    monkeypatch.setattr(bridge, 'publish_research_text', forbidden)
    monkeypatch.setattr(forecast_report, 'append_outcome', forbidden)
    checked = bridge.verify_holdout_continuation(bundle_root=tmp_path, companion_name=seed['companion'],
        expected_companion_sha256=seed['companion'][:-5])
    assert checked['original_counts']['pending_target_n'] == 1
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_pending_resolved_corrected_history_does_not_add_forecasts(tmp_path):
    exported, seed = setup(tmp_path)
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    value = json.loads((tmp_path/seed['bundle']).read_bytes())
    original_ids = [v['artifact'] for v in value['forecasts']]
    holdout_bridge = json.loads((tmp_path/exported['bridge']).read_bytes())
    receipt = json.loads((tmp_path/holdout_bridge['daily_receipt']).read_bytes())
    for spec in value['forecasts']:
        spec['append'] = {key: spec[key] for key in ('dataset_manifest', 'dataset_records', 'source_archive')}
        spec['append']['outcome_asof'] = value['asof']
    (tmp_path/'resolve-request.json').write_bytes(encode(value))
    output = tmp_path/'updates'
    output.mkdir()
    resolved = forecast_report.run_bundle(bundle_root=tmp_path, bundle_name='resolve-request.json', output_root=output,
                                         continuation_output_prefix='updates')
    assert resolved['forecast_n'] == resolved['scored_n'] == 2
    continuation = json.loads((output/resolved['continuation_bundle']).read_bytes())
    source = json.loads((tmp_path/receipt['request']['forecasts'][0]['daily_export']).read_bytes())['request']
    source['version'] = 'correction-v2'
    stamp = end(days(17)[15])+timedelta(hours=1)
    source['asof'] = stamp.isoformat()
    prices = chart(days(17)[:16])
    quotes = prices['chart']['result'][0]['indicators']['quote'][0]
    quotes['close'][-1] -= 10
    quotes['low'][-1] = quotes['close'][-1]-1
    raw = encode(prices)
    pin = hashlib.sha256(raw).hexdigest()
    (tmp_path/(pin+'.json')).write_bytes(raw)
    source['snapshots'].append({'file': pin+'.json', 'sha256': pin, 'received_at': stamp.isoformat()})
    (tmp_path/'corrected-source.json').write_bytes(encode(source))
    new = export_daily_dataset(bundle_root=tmp_path, request_name='corrected-source.json', output_root=tmp_path)
    binding = json.loads((tmp_path/new['binding']).read_bytes())
    continuation['asof'] = stamp.isoformat()
    for spec in continuation['forecasts']:
        spec['append'] = {'dataset_manifest': binding['artifacts']['manifest'],
                          'dataset_records': binding['artifacts']['records'], 'source_archive': None,
                          'outcome_asof': stamp.isoformat()}
    (tmp_path/'correction-request.json').write_bytes(encode(continuation))
    corrected = forecast_report.run_bundle(bundle_root=tmp_path, bundle_name='correction-request.json', output_root=output,
                                           continuation_output_prefix='updates')
    report = json.loads((output/corrected['report']).read_bytes())
    assert report['forecast_n'] == report['score']['scored_n'] == 2
    assert report['correction_n'] == 1
    assert {r['forecast_sha256'] for r in report['rows']} == {r['forecast_sha256'] for r in json.loads((output/resolved['report']).read_bytes())['rows']}
    portable = json.loads((output/corrected['continuation_bundle']).read_bytes())
    assert [v['artifact'] for v in portable['forecasts']] == original_ids
    assert all(spec['append'] is None for spec in portable['forecasts'])
    assert all((tmp_path/name).read_bytes() == raw for name, raw in original.items())


def test_rehashed_seed_cannot_clear_original_population(tmp_path):
    _, seed = setup(tmp_path)
    value = json.loads((tmp_path/seed['companion']).read_bytes())
    value['original_counts']['requested_n'] = 0
    raw = encode(value)
    name = hashlib.sha256(raw).hexdigest()+'.json'
    (tmp_path/name).write_bytes(raw)
    with pytest.raises(ValueError):
        bridge.verify_holdout_continuation(bundle_root=tmp_path, companion_name=name, expected_companion_sha256=name[:-5])


def test_removed_committed_history_refuses_before_new_output(tmp_path):
    _, seed = setup(tmp_path)
    value = json.loads((tmp_path/seed['bundle']).read_bytes())
    value['forecasts'][0]['history'] = []
    (tmp_path/'broken-chain.json').write_bytes(encode(value))
    output = tmp_path/'refused-updates'
    output.mkdir()
    with pytest.raises(ValueError):
        forecast_report.run_bundle(bundle_root=tmp_path, bundle_name='broken-chain.json', output_root=output)
    assert list(output.iterdir()) == []
