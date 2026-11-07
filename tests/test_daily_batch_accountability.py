"""Daily receipt archives reach immutable, correction-aware batch accountability."""
import copy
import hashlib
import json
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from app.backtest.forecast_report import prepare_batch_accountability, run_bundle
from test_daily_afi_bridge import chart, days, encode, end
from test_daily_forecast_batch import inputs, run

from scripts.observation_runtime.daily_afi_export import export_daily_dataset


def setup(root):
    request = inputs(root)
    result = run(root)
    plan = json.loads((root/result['daily_batch_plan']).read_bytes())
    index = json.loads((root/result['index']).read_bytes())
    accounting = {'schema': 'AFI_BATCH_ACCOUNTABILITY_REQUEST_V1', 'asof': request['asof'],
                  'batch_plan': result['daily_batch_plan'], 'batch_index': result['index'],
                  'expected_index_sha256': result['index'][:-5],
                  'outcomes': [{'forecast_sha256': item['forecast_sha256'], 'history': [], 'expected_head': None,
                                'append': None} for item in index['items']]}
    (root/'prepared').mkdir()
    (root/'reports').mkdir()
    return request, result, plan, accounting


def execute(root, accounting):
    (root/'accounting-request.json').write_bytes(encode(accounting))
    prepared = prepare_batch_accountability(bundle_root=root, request_name='accounting-request.json', output_root=root/'prepared')
    assert prepared['outcome_appends_performed'] == 0
    return run_bundle(bundle_root=root, bundle_name='prepared/'+prepared['bundle'], output_root=root/'reports',
                      continuation_output_prefix='reports')


def new_versions(root, original_request, *, correction=False, latest_only=False):
    calendar = days(17)
    stamp = end(calendar[-1])+timedelta(minutes=1)
    correction_stamp = stamp+timedelta(hours=1)
    cutoff = correction_stamp if correction else stamp
    exported = {}
    for spec in original_request['forecasts']:
        asset = spec['asset_id']
        if asset in exported:
            continue
        binding = json.loads((root/spec['daily_export']).read_bytes())
        source = copy.deepcopy(binding['request'])
        payload = chart(calendar, asset_class=source['asset_class'])
        raw = encode(payload)
        pin = hashlib.sha256(raw).hexdigest()
        (root/(pin+'.json')).write_bytes(raw)
        new = {'file': pin+'.json', 'sha256': pin, 'received_at': stamp.isoformat()}
        source['snapshots'] = [new] if latest_only else source['snapshots']+[new]
        if correction:
            quote = payload['chart']['result'][0]['indicators']['quote'][0]
            quote['close'][-1] -= 10
            quote['low'][-1] = quote['close'][-1]-1
            raw = encode(payload)
            pin = hashlib.sha256(raw).hexdigest()
            (root/(pin+'.json')).write_bytes(raw)
            source['snapshots'].append({'file': pin+'.json', 'sha256': pin, 'received_at': correction_stamp.isoformat()})
        source.update(version='v3' if correction else 'v2', asof=cutoff.isoformat())
        (root/'new-source-request.json').write_bytes(encode(source))
        result = export_daily_dataset(bundle_root=root, request_name='new-source-request.json', output_root=root)
        new_binding = json.loads((root/result['binding']).read_bytes())
        exported[asset] = {'dataset_manifest': new_binding['artifacts']['manifest'],
                           'dataset_records': new_binding['artifacts']['records'], 'source_archive': None}
    return exported, cutoff


def advance(root, accounting, plan, prior, references):
    for instruction, spec, head in zip(accounting['outcomes'], plan['forecasts'], prior['updated_heads'], strict=True):
        if head != instruction['expected_head']:
            instruction['history'].append({**references[spec['asset_id']], 'artifact': 'reports/'+head+'.json'})
        instruction['expected_head'] = head


def test_daily_source_pending_resolved_corrected_and_browser_comparison(tmp_path):
    original_request, batch, plan, accounting = setup(tmp_path)
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    initial = execute(tmp_path, accounting)
    assert initial['forecast_n'] == 4 and initial['scored_n'] == 0
    references = {spec['asset_id']: {key: spec[key] for key in ('dataset_manifest', 'dataset_records', 'source_archive')}
                  for spec in plan['forecasts']}
    for instruction, spec in zip(accounting['outcomes'], plan['forecasts'], strict=True):
        instruction['append'] = {**references[spec['asset_id']], 'outcome_asof': accounting['asof']}
    pending = execute(tmp_path, accounting)
    assert pending['scored_n'] == 0
    advance(tmp_path, accounting, plan, pending, references)
    resolved_versions, stamp = new_versions(tmp_path, original_request)
    accounting['asof'] = stamp.isoformat()
    for instruction, spec in zip(accounting['outcomes'], plan['forecasts'], strict=True):
        instruction['append'] = {**resolved_versions[spec['asset_id']], 'outcome_asof': stamp.isoformat()}
    resolved = execute(tmp_path, accounting)
    assert resolved['scored_n'] == 4
    resolved_original = {p.name: p.read_bytes() for p in (tmp_path/'reports').iterdir()}
    advance(tmp_path, accounting, plan, resolved, resolved_versions)
    corrected_versions, stamp = new_versions(tmp_path, original_request, correction=True)
    accounting['asof'] = stamp.isoformat()
    for instruction, spec in zip(accounting['outcomes'], plan['forecasts'], strict=True):
        instruction['append'] = {**corrected_versions[spec['asset_id']], 'outcome_asof': stamp.isoformat()}
    final = execute(tmp_path, accounting)
    report = json.loads((tmp_path/'reports'/final['report']).read_bytes())
    assert report['forecast_n'] == report['score']['scored_n'] == report['correction_n'] == 4
    assert report['calibration_established'] is report['history_completeness_verified'] is False
    pairs = [pair for pair in report['paired_model_diagnostics']['comparisons'] if pair['paired_n']]
    assert len(pairs) == 2 and all(pair['paired_n'] == 1 and pair['status'] == 'INSUFFICIENT_EVIDENCE' for pair in pairs)
    assert all(row['latest_event'] == 'CORRECTION' and row['actual'] < row['reference'] for row in report['rows'])
    assert all((tmp_path/name).read_bytes() == raw for name, raw in original.items())
    assert all((tmp_path/'reports'/name).read_bytes() == raw for name, raw in resolved_original.items())
    # Portable continuation re-reads the exact immutable histories without append.
    repeated = run_bundle(bundle_root=tmp_path, bundle_name='reports/'+final['continuation_bundle'], output_root=tmp_path/'reports')
    assert repeated['updated_heads'] == final['updated_heads']
    assert repeated['report'] == final['report']
    viewer = Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    code = """const fs=require('fs'),v=require(process.argv[1]);
Promise.all(process.argv.slice(2).map(p=>v.verifyEnvelope(fs.readFileSync(p,'utf8')))).then(([a,b])=>{
if(a.score.scored_n!==4||b.correction_n!==4)throw Error('daily history');
const c=v.compareReportVintages(a,b);process.stdout.write(JSON.stringify(c));
}).catch(e=>{console.error(e);process.exitCode=1});"""
    checked = subprocess.run(['C:/Program Files/nodejs/node.exe', '-e', code, str(viewer),
                              str(tmp_path/'reports'/resolved['browser_export']), str(tmp_path/'reports'/final['browser_export'])],
                             capture_output=True, text=True, timeout=15, check=False)
    assert checked.returncode == 0, checked.stderr
    comparison = json.loads(checked.stdout)
    assert comparison['production_approved'] is False
    assert comparison['union_forecast_n'] == 4
    assert comparison['status_counts'] == {'OUTCOME_VALUE_CHANGED': 4}
    assert all(row['score_impact']['probability']['right_minus_left_log_loss'] > 0
               and row['score_impact']['probability']['log_loss_difference_state'] == 'FINITE'
               and row['score_impact']['interval']['state'] == 'NO_INTERVAL'
               for row in comparison['rows'])
    (tmp_path/'daily-accountability-receipt.json').write_text(json.dumps({
        'batch': batch, 'pending': pending, 'resolved': resolved, 'corrected': final,
        'comparison': comparison, 'synthetic_only': True, 'production_approved': False}, sort_keys=True), encoding='utf-8')


@pytest.mark.parametrize('fault', ['latest-only', 'stale-cutoff', 'missing-source', 'foreign-label'])
def test_daily_batch_bad_label_evidence_refused_before_outcome_publication(tmp_path, fault):
    original_request, _, plan, accounting = setup(tmp_path)
    versions, stamp = new_versions(tmp_path, original_request, latest_only=fault == 'latest-only')
    accounting['asof'] = stamp.isoformat()
    for instruction, spec in zip(accounting['outcomes'], plan['forecasts'], strict=True):
        instruction['append'] = {**versions[spec['asset_id']], 'outcome_asof': stamp.isoformat()}
    if fault == 'stale-cutoff': accounting['outcomes'][-1]['append']['outcome_asof'] = (stamp+timedelta(days=1)).isoformat()
    elif fault == 'missing-source':
        first = accounting['outcomes'][0]['append']['dataset_records']
        (tmp_path/first).rename(tmp_path/'preserved-missing-records.json')
    elif fault == 'foreign-label':
        accounting['outcomes'][0]['append'] = dict(accounting['outcomes'][-1]['append'])
    with pytest.raises((ValueError, OSError)):
        execute(tmp_path, accounting)
    assert not list((tmp_path/'reports').iterdir())
