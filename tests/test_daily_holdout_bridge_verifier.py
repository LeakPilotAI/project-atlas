"""Exact no-write reconstruction of holdout-to-workspace accountability."""
import hashlib
import json

import pytest
from app.backtest import forecast_report
from test_daily_holdout_accountability import args

from scripts.observation_runtime import daily_holdout_accountability as bridge


def build(root, pending=False):
    return bridge.export_holdout_accountability(**args(root, pending=pending))


def verify(root, result):
    return bridge.verify_holdout_accountability(bundle_root=root, bridge_name=result['bridge'],
                                                expected_bridge_sha256=result['bridge'][:-5])


@pytest.mark.parametrize('pending', [False, True])
def test_exact_reconstruction_without_any_publishers(tmp_path, monkeypatch, pending):
    result = build(tmp_path, pending)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def forbidden(*a, **k):
        raise AssertionError('Read-only verification called a publisher')

    for module in (bridge, forecast_report):
        monkeypatch.setattr(module, 'publish_research_text', forbidden)
    monkeypatch.setattr(bridge, 'run_bundle', forbidden)
    monkeypatch.setattr(bridge, 'prepare_batch_accountability', forbidden)
    monkeypatch.setattr(forecast_report, 'append_outcome', forbidden)
    checked = verify(tmp_path, result)
    assert checked['status'] == 'SYNTHETIC_HOLDOUT_ACCOUNTABILITY_REPRODUCED'
    assert checked['counts']['resolved_n'] == (1 if pending else 2)
    assert checked['browser_export'] == result['browser_export']
    assert checked['startup_authorized'] is False
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('field', ['counts', 'browser_scope', 'startup_authorized', 'refused_cases'])
def test_rehashed_bridge_cannot_change_population_or_authority(tmp_path, field):
    result = build(tmp_path)
    value = json.loads((tmp_path/result['bridge']).read_bytes())
    if field == 'counts': value[field]['requested_n'] += 1
    elif field == 'browser_scope': value[field] = 'ALL_REQUESTS'
    elif field == 'startup_authorized': value[field] = True
    else: value[field] = [{'reason': 'invented refusal'}]
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()
    name = hashlib.sha256(raw).hexdigest()+'.json'
    (tmp_path/name).write_bytes(raw)
    with pytest.raises(ValueError):
        bridge.verify_holdout_accountability(bundle_root=tmp_path, bridge_name=name, expected_bridge_sha256=name[:-5])


@pytest.mark.parametrize('member', ['browser_export', 'outcome', 'daily_receipt'])
def test_missing_member_refuses_without_repair(tmp_path, member):
    result = build(tmp_path)
    value = json.loads((tmp_path/result['bridge']).read_bytes())
    name = (value['daily_receipt'] if member == 'daily_receipt' else
            value['accountability']['updated_heads'][0]+'.json' if member == 'outcome' else
            value['accountability']['browser_export'])
    (tmp_path/name).rename(tmp_path/('retained-'+name))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises((ValueError, OSError)):
        verify(tmp_path, result)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_verification_cli_forbids_output_root(tmp_path, capsys):
    result = build(tmp_path)
    argv = ['--bundle-root', str(tmp_path), '--verify-bridge', result['bridge'],
            '--expected-companion-sha256', result['bridge'][:-5]]
    assert bridge.main(argv) == 0
    assert json.loads(capsys.readouterr().out)['counts']['requested_n'] == 2
    with pytest.raises(SystemExit) as error:
        bridge.main(argv+['--output-root', str(tmp_path)])
    assert error.value.code == 2
