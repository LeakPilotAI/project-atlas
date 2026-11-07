"""Read-only reconstruction refuses missing, tampered and self-resigned evidence."""
import hashlib
import json

import pytest
from app.backtest import forecast_artifacts, forecast_report
from test_daily_afi_bridge import encode
from test_daily_forecast_batch import inputs, run

from scripts.observation_runtime import daily_forecast_batch as workflow


def verify(root, result):
    return workflow.verify_daily_forecast_receipt(bundle_root=root, receipt_name=result['daily_receipt'],
                                                  expected_receipt_sha256=result['daily_receipt'][:-5])


def resign(root, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    name = hashlib.sha256(raw).hexdigest()+'.json'
    (root/name).write_bytes(raw)
    return name


def test_readonly_reconstruction_never_invokes_publishers(tmp_path, monkeypatch):
    inputs(tmp_path)
    result = run(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def forbidden(*args, **kwargs):
        raise AssertionError('Verification cannot publish')

    monkeypatch.setattr(workflow, 'publish_research_text', forbidden)
    monkeypatch.setattr(forecast_report, 'publish_research_text', forbidden)
    monkeypatch.setattr(forecast_artifacts, 'publish_forecast', forbidden)
    checked = verify(tmp_path, result)
    assert checked['status'] == 'SYNTHETIC_DAILY_FORECAST_RECEIPT_REPRODUCED'
    assert checked['forecast_n'] == 4 and checked['unique_asset_n'] == 2
    assert checked['startup_authorized'] is checked['history_completeness_verified'] is False
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('target', ['source', 'manifest', 'records', 'audit', 'plan', 'forecast', 'html', 'index', 'receipt'])
def test_every_required_evidence_component_is_checked(tmp_path, target):
    request = inputs(tmp_path)
    result = run(tmp_path)
    binding = json.loads((tmp_path/request['forecasts'][0]['daily_export']).read_bytes())
    index = json.loads((tmp_path/result['index']).read_bytes())
    names = {'source': binding['request']['snapshots'][0]['file'], 'plan': result['daily_batch_plan'],
             'forecast': index['items'][0]['artifact'], 'html': result['dashboard'], 'index': result['index'],
             'receipt': result['daily_receipt'], **binding['artifacts']}
    (tmp_path/names[target]).rename(tmp_path/'preserved-missing-evidence')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises((ValueError, OSError)):
        verify(tmp_path, result)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('fault', ['count', 'authority', 'history', 'plan-pin', 'unknown-field', 'index-type'])
def test_newly_rehashed_receipt_cannot_invent_claims(tmp_path, fault):
    inputs(tmp_path)
    result = run(tmp_path)
    receipt = json.loads((tmp_path/result['daily_receipt']).read_bytes())
    if fault == 'count': receipt['batch_result']['forecast_n'] += 1
    elif fault == 'authority': receipt['startup_authorized'] = True
    elif fault == 'history': receipt['history_completeness_verified'] = True
    elif fault == 'plan-pin': receipt['batch_plan_sha256'] = '0'*64
    elif fault == 'index-type': receipt['batch_result']['index'] = None
    else: receipt['activated'] = True
    name = resign(tmp_path, receipt)
    with pytest.raises(ValueError):
        workflow.verify_daily_forecast_receipt(bundle_root=tmp_path, receipt_name=name, expected_receipt_sha256=name[:-5])


def test_self_resigned_html_and_index_must_match_actual_renderer(tmp_path):
    inputs(tmp_path)
    result = run(tmp_path)
    html = b'<!doctype html><title>Fabricated success</title>'
    name = hashlib.sha256(html).hexdigest()+'.html'
    (tmp_path/name).write_bytes(html)
    index = json.loads((tmp_path/result['index']).read_bytes())
    index['dashboard'] = name
    raw = encode(index)+b'\n'
    index_name = hashlib.sha256(raw).hexdigest()+'.json'
    (tmp_path/index_name).write_bytes(raw)
    receipt = json.loads((tmp_path/result['daily_receipt']).read_bytes())
    receipt['batch_result'].update(index=index_name, dashboard=name)
    receipt_name = resign(tmp_path, receipt)
    with pytest.raises(ValueError, match='dashboard differs'):
        workflow.verify_daily_forecast_receipt(bundle_root=tmp_path, receipt_name=receipt_name, expected_receipt_sha256=receipt_name[:-5])


def test_cli_verification_and_no_output_root(tmp_path, capsys):
    inputs(tmp_path)
    result = run(tmp_path)
    args = ['--bundle-root', str(tmp_path), '--verify-receipt', result['daily_receipt'],
            '--expected-receipt-sha256', result['daily_receipt'][:-5]]
    assert workflow.main(args) == 0
    assert json.loads(capsys.readouterr().out)['forecast_n'] == 4
    with pytest.raises(SystemExit) as exc:
        workflow.main(args+['--output-root', str(tmp_path)])
    assert exc.value.code == 2
    with pytest.raises(ValueError, match='Caller-retained'):
        workflow.verify_daily_forecast_receipt(bundle_root=tmp_path, receipt_name=result['daily_receipt'], expected_receipt_sha256='0'*64)
