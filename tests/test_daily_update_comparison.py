"""Source-bound updates compare original forecasts rather than adding samples."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from app.backtest import forecast_report
from test_daily_holdout_continuation import setup
from test_daily_holdout_update import correction_flow

from scripts.observation_runtime import daily_holdout_update as update


@pytest.fixture(scope='module')
def pair(tmp_path_factory):
    original = tmp_path_factory.mktemp('pair-source')
    exported, seed = setup(original)
    root, first, second = correction_flow(tmp_path_factory.mktemp('pair'), (original, exported, seed))
    return root, first, second


def verify(root, result):
    return update.verify_holdout_update(bundle_root=root, companion_name=result['companion'],
        expected_companion_sha256=result['companion'].split('/')[-1][:-5])


def test_both_actual_updates_verify_without_publishers(pair, monkeypatch):
    root, first, second = pair
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def forbidden(*a, **k):
        raise AssertionError('Read-only update verification called publisher')

    monkeypatch.setattr(update, 'publish_research_text', forbidden)
    monkeypatch.setattr(update, 'run_bundle', forbidden)
    monkeypatch.setattr(forecast_report, 'append_outcome', forbidden)
    assert verify(root, first)['current_issued_states'] == {'RESOLVED': 2}
    assert verify(root, second)['original_counts'] == first['original_counts']
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('field', ['current_issued_n', 'original_counts', 'startup_authorized'])
def test_rehashed_result_cannot_change_claims(pair, tmp_path, field):
    root, _, second = pair
    value = json.loads((root/second['companion']).read_bytes())
    if field == 'current_issued_n': value[field] += 1
    elif field == 'original_counts': value[field]['requested_n'] += 1
    else: value[field] = True
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()
    name = hashlib.sha256(raw).hexdigest()+'.json'
    # Derived forged evidence is a new file; originals remain immutable.
    path = root/'updates'/name
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        update.verify_holdout_update(bundle_root=root, companion_name='updates/'+name,
            expected_companion_sha256=name[:-5])


def test_existing_packet_exporter_preserves_matched_cases(pair, tmp_path):
    root, first, second = pair
    repo = Path(__file__).resolve().parents[1]
    packet = tmp_path/'comparison.json'
    script = repo/'frontend/offline/forecast-accountability/vintage-export.mjs'
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', str(script), '--export',
        str(root/first['browser_export']), str(root/second['browser_export']), str(packet)],
        capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    code = """import fs from 'node:fs';const api=await import(process.argv[1]);
const result=await api.verifyComparisonPacket(fs.readFileSync(process.argv[2],'utf8'));
process.stdout.write(JSON.stringify(result.comparison));"""
    verified = subprocess.run(['C:/Program Files/nodejs/node.exe', '--input-type=module', '-e', code,
        script.as_uri(), str(packet)], capture_output=True, text=True, timeout=15, check=False)
    assert verified.returncode == 0, verified.stderr
    report = json.loads(verified.stdout)
    assert report['matched_forecast_n'] == report['union_forecast_n'] == 2
    changed = [row for row in report['rows'] if row['left_actual'] != row['right_actual']]
    assert len(changed) == 1
    assert changed[0]['score_impact']['probability']['right_minus_left_brier'] != 0



def test_missing_committed_outcome_never_repairs_history(pair, tmp_path):
    root, _, second = pair
    copied = tmp_path/'copied-evidence'
    shutil.copytree(root, copied)
    value = json.loads((copied/second['companion']).read_bytes())
    name = 'updates/'+value['accountability']['updated_heads'][0]+'.json'
    path = copied/name
    path.rename(path.with_suffix('.retained'))
    before = {str(p.relative_to(copied)): p.read_bytes() for p in copied.rglob('*') if p.is_file()}
    with pytest.raises((ValueError, OSError)):
        verify(copied, second)
    assert before == {str(p.relative_to(copied)): p.read_bytes() for p in copied.rglob('*') if p.is_file()}
