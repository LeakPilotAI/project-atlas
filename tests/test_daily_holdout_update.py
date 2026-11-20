"""Explicit label updates cannot mutate the frozen forecast population."""
import hashlib
import json
import shutil
from datetime import timedelta

import pytest
from test_daily_afi_bridge import chart, days, encode, end
from test_daily_holdout_continuation import setup

from scripts.observation_runtime import daily_holdout_update as update
from scripts.observation_runtime.daily_afi_export import export_daily_dataset


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    root = tmp_path_factory.mktemp('update-source')
    exported, seed = setup(root)
    return root, exported, seed


def fixture(tmp_path, original):
    source, exported, seed = original
    root = tmp_path/'evidence'
    shutil.copytree(source, root)
    (root/'updates').mkdir()
    bridge = json.loads((root/exported['bridge']).read_bytes())
    receipt = json.loads((root/bridge['daily_receipt']).read_bytes())
    daily = receipt['request']['forecasts'][0]['daily_export']
    bundle = json.loads((root/seed['bundle']).read_bytes())
    request = {'schema': 'ATLAS_SYNTHETIC_HOLDOUT_UPDATE_REQUEST_V1', 'seed': seed['companion'],
        'expected_seed_sha256': seed['companion'][:-5], 'continuation': seed['bundle'],
        'expected_continuation_sha256': seed['bundle'][:-5], 'daily_export': daily,
        'expected_daily_export_sha256': daily[:-5], 'asof': bundle['asof'],
        'outcome_asof': bundle['asof'], 'output_prefix': 'updates'}
    return root, request


def write(root, request):
    raw = encode(request)
    name = hashlib.sha256(raw).hexdigest()+'.json'
    (root/name).write_bytes(raw)
    return name


def run(root, request):
    return update.update_holdout_accountability(bundle_root=root, request_name=write(root, request))


def test_pending_resolution_and_idempotent_explicit_request(tmp_path, original):
    root, request = fixture(tmp_path, original)
    before = {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}
    result = run(root, request)
    assert result['original_counts']['pending_target_n'] == 1
    assert result['current_issued_states'] == {'RESOLVED': 2}
    assert result['startup_authorized'] is False
    snapshot = {p.name: p.read_bytes() for p in (root/'updates').iterdir()}
    assert run(root, request) == result
    assert snapshot == {p.name: p.read_bytes() for p in (root/'updates').iterdir()}
    assert all((root/name).read_bytes() == raw for name, raw in before.items())


def correction_flow(tmp_path, original):
    root, request = fixture(tmp_path, original)
    first = run(root, request)
    request['continuation'] = first['continuation']
    request['expected_continuation_sha256'] = first['continuation'].split('/')[-1][:-5]
    old = json.loads((root/request['daily_export']).read_bytes())
    source = old['request']
    stamp = end(days(17)[15])+timedelta(hours=1)
    payload = chart(days(17)[:16])
    quotes = payload['chart']['result'][0]['indicators']['quote'][0]
    quotes['close'][-1] -= 10
    quotes['low'][-1] = quotes['close'][-1]-1
    raw = encode(payload)
    pin = hashlib.sha256(raw).hexdigest()
    (root/(pin+'.json')).write_bytes(raw)
    source['snapshots'].append({'file': pin+'.json', 'sha256': pin, 'received_at': stamp.isoformat()})
    source['version'], source['asof'] = 'label-correction-v2', stamp.isoformat()
    (root/'new-source.json').write_bytes(encode(source))
    binding = export_daily_dataset(bundle_root=root, request_name='new-source.json', output_root=root)['binding']
    request.update(daily_export=binding, expected_daily_export_sha256=binding[:-5],
                   asof=stamp.isoformat(), outcome_asof=stamp.isoformat())
    second = run(root, request)
    companion = json.loads((root/second['companion']).read_bytes())
    report = json.loads((root/'updates'/companion['accountability']['report']).read_bytes())
    assert report['correction_n'] == 1 and report['forecast_n'] == report['score']['scored_n'] == 2
    assert companion['new_forecasts_created'] == 0
    assert companion['independent_latest_head_established'] is False
    assert second['original_counts'] == first['original_counts']
    return root, first, second


def test_later_correction_retains_forecasts_and_original_counts(tmp_path, original):
    correction_flow(tmp_path, original)


@pytest.mark.parametrize('fault', ['head', 'source-pin', 'future', 'directory', 'stale'])
def test_invalid_update_refuses_before_any_publication(tmp_path, original, fault):
    root, request = fixture(tmp_path, original)
    if fault == 'head': request['expected_continuation_sha256'] = '0'*64
    if fault == 'source-pin': request['expected_daily_export_sha256'] = '0'*64
    if fault == 'future': request['outcome_asof'] = '2028-01-01T00:00:00+00:00'
    if fault == 'directory': request['output_prefix'] = 'missing'
    if fault == 'stale':
        prior = json.loads((root/request['continuation']).read_bytes())
        head = prior['forecasts'][-1]['expected_head']
        record = json.loads((root/(head+'.json')).read_bytes())
        request['outcome_asof'] = (update.aware(record['outcome_asof'])-timedelta(minutes=1)).isoformat()
    with pytest.raises((ValueError, OSError)):
        run(root, request)
    assert list((root/'updates').iterdir()) == []



def test_new_archive_cannot_remove_committed_observations(tmp_path, original):
    root, request = fixture(tmp_path, original)
    source = json.loads((root/request['daily_export']).read_bytes())['request']
    source['snapshots'] = source['snapshots'][-1:]
    source['version'] = 'rewritten-history-v2'
    (root/'rewritten-source.json').write_bytes(encode(source))
    binding = export_daily_dataset(bundle_root=root, request_name='rewritten-source.json', output_root=root)['binding']
    request.update(daily_export=binding, expected_daily_export_sha256=binding[:-5])
    with pytest.raises(ValueError, match='removed or rewritten'):
        run(root, request)
    assert list((root/'updates').iterdir()) == []
