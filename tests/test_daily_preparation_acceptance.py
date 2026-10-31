"""New request preparation preserves failure evidence and works after extraction."""
import json
import subprocess
import sys

import pytest
from test_daily_export_packaging import CHILD, extracted
from test_daily_request_preparation import selection

from scripts.observation_runtime import daily_forecast_batch as workflow


@pytest.mark.parametrize('fault', ['before_write','after_write','selection_change','binding_change','readback'])
def test_preparation_does_not_acknowledge_publication_or_input_failure(tmp_path,monkeypatch,fault):
    _,spec = selection(tmp_path)
    original = workflow.publish_research_text
    before = {p.name for p in tmp_path.iterdir()}
    error = OSError('synthetic publication failure')
    def fail(*args, **kwargs):
        if fault == 'before_write': raise error
        path = original(*args, **kwargs)
        if fault == 'after_write': raise error
        if fault == 'selection_change':
            target = tmp_path/'selection.json'
            target.write_bytes(target.read_bytes()+b' ')
        if fault == 'binding_change':
            target = tmp_path/spec['groups'][0]['daily_export']
            target.write_bytes(target.read_bytes()+b' ')
        if fault == 'readback': path.write_bytes(b'partial synthetic publication')
        return path
    monkeypatch.setattr(workflow,'publish_research_text',fail)
    with pytest.raises((ValueError,OSError)):
        workflow.prepare_daily_forecast_request(bundle_root=tmp_path,selection_name='selection.json',output_root=tmp_path)
    added = {p.name for p in tmp_path.iterdir()} - before
    assert len(added) == (0 if fault == 'before_write' else 1)
    if fault == 'after_write':
        monkeypatch.setattr(workflow,'publish_research_text',original)
        result = workflow.prepare_daily_forecast_request(bundle_root=tmp_path,selection_name='selection.json',output_root=tmp_path)
        assert result['request'] in added


def test_preparation_cli_runs_from_verified_clean_extraction(tmp_path,monkeypatch):
    clean,repo = extracted(tmp_path,monkeypatch)
    storage = clean/'synthetic-inputs'; storage.mkdir()
    selection(storage)
    child = CHILD.replace('daily_afi_export','daily_forecast_batch')
    def invoke(*arguments):
        return subprocess.run([sys.executable,'-I','-c',child,str(clean),str(repo),
                               '--bundle-root',str(storage),*arguments],cwd=clean,
                              capture_output=True,text=True,timeout=30,check=False)
    prepared = invoke('--prepare-selection','selection.json','--output-root',str(storage))
    assert prepared.returncode == 0, prepared.stdout+prepared.stderr
    result = json.loads(prepared.stdout)
    assert result['forecasts_published'] is False and result['planned_forecast_n'] == 4
    published = invoke('--request',result['request'],'--output-root',str(storage))
    assert published.returncode == 0, published.stdout+published.stderr
    receipt = json.loads(published.stdout)
    assert receipt['forecast_n'] == 4
    verified = invoke('--verify-receipt',receipt['daily_receipt'],'--expected-receipt-sha256',receipt['daily_receipt'][:-5])
    assert verified.returncode == 0, verified.stdout+verified.stderr
    assert json.loads(verified.stdout)['status'] == 'SYNTHETIC_DAILY_FORECAST_RECEIPT_REPRODUCED'
