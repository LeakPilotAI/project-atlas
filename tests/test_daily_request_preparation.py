"""Explicit grouped choices -> existing request -> actual forecast/verification workflow."""
import hashlib
import json

import pytest
from app.investment.offline_research import ResearchInputRefused
from test_daily_forecast_batch import inputs

from scripts.observation_runtime import daily_forecast_batch as workflow


def selection(root):
    request = inputs(root)
    groups = []
    for row in request['forecasts']:
        binding = {k:row[k] for k in ('daily_export','expected_daily_export_sha256','asset_id')}
        if not groups or any(groups[-1][k] != v for k,v in binding.items()):
            groups.append({**binding,'forecasts':[]})
        groups[-1]['forecasts'].append({k:row[k] for k in ('issued_at','method','lookback','horizon','interval','probability_method')})
    value = {'schema':'ATLAS_SYNTHETIC_DAILY_FORECAST_SELECTION_V1','asof':request['asof'],'groups':groups}
    (root/'selection.json').write_text(json.dumps(value),encoding='utf-8')
    return request,value


def test_prepare_exact_request_without_forecasts_and_retry_then_real_workflow(tmp_path,capsys):
    expected,_ = selection(tmp_path)
    before = {p.name:p.read_bytes() for p in tmp_path.iterdir()}
    assert workflow.main(['--bundle-root',str(tmp_path),'--prepare-selection','selection.json','--output-root',str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'OFFLINE_DAILY_REQUEST_PREPARED'
    assert result['planned_forecast_n'] == 4 and result['forecasts_published'] is False
    raw = (tmp_path/result['request']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == result['request_sha256']
    assert json.loads(raw) == expected
    assert {p.name for p in tmp_path.iterdir()} - set(before) == {result['request']}
    assert all((tmp_path/name).read_bytes() == data for name,data in before.items())
    retry = workflow.prepare_daily_forecast_request(bundle_root=tmp_path,selection_name='selection.json',output_root=tmp_path)
    assert retry == result
    published = workflow.run_daily_forecast_batch(bundle_root=tmp_path,request_name=result['request'],output_root=tmp_path)
    assert published['forecast_n'] == 4
    verified = workflow.verify_daily_forecast_receipt(bundle_root=tmp_path,receipt_name=published['daily_receipt'],
                                                     expected_receipt_sha256=published['daily_receipt'][:-5])
    assert verified['trading_authorized'] is False


@pytest.mark.parametrize('fault', ['pin','asset','missing','lookback','empty','budget'])
def test_bad_selection_fails_preflight_without_new_request(tmp_path,fault):
    _,value = selection(tmp_path)
    if fault == 'pin': value['groups'][0]['expected_daily_export_sha256'] = '0'*64
    if fault == 'asset': value['groups'][0]['asset_id'] = 'US_EQUITY:OTHER'
    if fault == 'missing': value['groups'][0]['forecasts'][0].pop('probability_method')
    if fault == 'lookback': value['groups'][0]['forecasts'][0]['lookback'] = 1
    if fault == 'empty': value['groups'] = []
    if fault == 'budget': value['groups'][0]['forecasts'] *= 17
    (tmp_path/'selection.json').write_text(json.dumps(value),encoding='utf-8')
    before = {p.name:p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises((ResearchInputRefused,ValueError)):
        workflow.prepare_daily_forecast_request(bundle_root=tmp_path,selection_name='selection.json',output_root=tmp_path)
    assert before == {p.name:p.read_bytes() for p in tmp_path.iterdir()}
