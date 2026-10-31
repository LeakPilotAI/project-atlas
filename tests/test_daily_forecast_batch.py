"""Real offline daily export -> batch engine -> immutable dashboard outputs."""
import hashlib
import json
from datetime import timedelta

import pytest
from app.backtest import forecast_artifacts
from app.backtest.forecast_baselines import PROBABILITY_METHOD
from app.backtest.forecast_report import ForecastBatchIncomplete
from test_daily_afi_bridge import POLICY, chart, days, encode, end, universe

from scripts.observation_runtime import daily_forecast_batch as workflow
from scripts.observation_runtime.daily_afi_export import export_daily_dataset


def inputs(root):
    calendar = days(16)
    receipt = end(calendar[-1])+timedelta(minutes=1)
    specs = []
    for kind in ['US_EQUITY', 'US_ETF']:
        raw = encode(chart(calendar, asset_class=kind))
        pin = hashlib.sha256(raw).hexdigest()
        (root/(pin+'.json')).write_bytes(raw)
        source = {'schema': 'ATLAS_SYNTHETIC_DAILY_EXPORT_REQUEST_V1',
                  'snapshots': [{'file': pin+'.json', 'sha256': pin, 'received_at': receipt.isoformat()}],
                  'symbol': 'AAPL' if kind == 'US_EQUITY' else 'SPY', 'asset_class': kind,
                  'universe': universe(kind), 'dataset_id': kind.lower()+'-daily', 'version': 'v1',
                  'asof': receipt.isoformat(), **POLICY}
        (root/'source-request.json').write_bytes(encode(source))
        exported = export_daily_dataset(bundle_root=root, request_name='source-request.json', output_root=root)
        for model in ['NO_CHANGE', 'ENDPOINT_DRIFT']:
            specs.append({'daily_export': exported['binding'], 'expected_daily_export_sha256': exported['binding'][:-5],
                          'asset_id': universe(kind)['asset_id'], 'issued_at': (receipt+timedelta(minutes=1)).isoformat(),
                          'method': model, 'lookback': 5, 'horizon': '1D', 'interval': None,
                          'probability_method': PROBABILITY_METHOD})
    request = {'schema': 'ATLAS_SYNTHETIC_DAILY_FORECAST_REQUEST_V1',
               'asof': (receipt+timedelta(minutes=1)).isoformat(), 'forecasts': specs}
    (root/'forecast-request.json').write_bytes(encode(request))
    return request


def run(root):
    return workflow.run_daily_forecast_batch(bundle_root=root, request_name='forecast-request.json', output_root=root)


def test_two_assets_four_forecasts_actual_engine_dashboard_and_retry(tmp_path):
    request = inputs(tmp_path)
    result = run(tmp_path)
    assert result['forecast_n'] == 4 and result['unique_asset_n'] == 2
    assert result['startup_authorized'] is result['trading_authorized'] is False
    index = json.loads((tmp_path/result['index']).read_bytes())
    assert all(item['status'] == 'PUBLISHED_VERIFIED' for item in index['items'])
    assert index['pooled_price_error'] is index['ranking'] is None
    html = (tmp_path/result['dashboard']).read_text(encoding='utf-8')
    assert all(asset in html for asset in ['US_EQUITY:AAPL', 'ETF:SPY'])
    receipt = json.loads((tmp_path/result['daily_receipt']).read_bytes())
    assert receipt['request'] == request
    assert receipt['source_authenticated'] is receipt['history_completeness_verified'] is False
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert run(tmp_path) == result
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('fault', ['pin', 'identity', 'duplicate', 'future-issue', 'interval', 'method', 'over-budget', 'live', 'tampered-source'])
def test_entire_batch_refused_before_publication(tmp_path, fault):
    request = inputs(tmp_path)
    spec = request['forecasts'][0]
    if fault == 'pin': spec['expected_daily_export_sha256'] = '0'*64
    elif fault == 'identity': spec['asset_id'] = 'ETF:OTHER'
    elif fault == 'duplicate': request['forecasts'].append(dict(spec))
    elif fault == 'future-issue': spec['issued_at'] = '2027-01-01T00:00:00+00:00'
    elif fault == 'interval': spec['interval'] = '../outside.json'
    elif fault == 'method': spec['method'] = 'MAGIC'
    elif fault == 'over-budget': request['forecasts'] *= 9
    elif fault == 'live': request['live_authorized'] = True
    else:
        binding = json.loads((tmp_path/spec['daily_export']).read_bytes())
        (tmp_path/binding['request']['snapshots'][0]['file']).write_bytes(b'{}')
    (tmp_path/'forecast-request.json').write_bytes(encode(request))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError):
        run(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_second_forecast_failure_keeps_batch_failure_evidence(tmp_path, monkeypatch):
    inputs(tmp_path)
    original = forecast_artifacts.publish_forecast
    count = 0

    def fail(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError(28, 'synthetic full storage')
        return original(*args, **kwargs)

    monkeypatch.setattr(forecast_artifacts, 'publish_forecast', fail)
    with pytest.raises(ForecastBatchIncomplete) as exc:
        run(tmp_path)
    assert exc.value.__cause__.errno == 28
    result = exc.value.result
    assert result['status'] == 'INCOMPLETE'
    assert [item['status'] for item in result['items']] == ['PUBLISHED_VERIFIED', 'UNCERTAIN_PUBLICATION', 'NOT_ATTEMPTED', 'NOT_ATTEMPTED']
    assert (tmp_path/result['failure_report']).is_file()
    assert not any(json.loads(p.read_bytes()).get('schema') == 'ATLAS_SYNTHETIC_DAILY_FORECAST_RESULT_V1'
                   for p in tmp_path.glob('*.json'))


def test_final_receipt_failure_never_returns_success(tmp_path, monkeypatch):
    inputs(tmp_path)
    original = workflow.publish_research_text

    def fail(root, text, **kwargs):
        if json.loads(text).get('schema') == 'ATLAS_SYNTHETIC_DAILY_FORECAST_RESULT_V1':
            raise OSError('synthetic receipt failure')
        return original(root, text, **kwargs)

    monkeypatch.setattr(workflow, 'publish_research_text', fail)
    with pytest.raises(OSError, match='receipt failure'):
        run(tmp_path)
    assert any(json.loads(p.read_bytes()).get('schema') == 'AFI_FORECAST_BATCH_RESULT_V1' for p in tmp_path.glob('*.json'))


def test_cli_runs_only_with_explicit_roots(tmp_path, capsys):
    inputs(tmp_path)
    assert workflow.main(['--bundle-root', str(tmp_path), '--request', 'forecast-request.json', '--output-root', str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)['forecast_n'] == 4
    with pytest.raises(SystemExit) as exc:
        workflow.main([])
    assert exc.value.code == 2


def test_valid_manifest_substitution_after_source_verification_refuses(tmp_path, monkeypatch):
    request = inputs(tmp_path)
    original = workflow.verify_daily_export

    def change(**kwargs):
        result = original(**kwargs)
        binding = json.loads((tmp_path/request['forecasts'][0]['daily_export']).read_bytes())
        path = tmp_path/binding['artifacts']['manifest']
        manifest = json.loads(path.read_bytes())
        manifest['quality']['min_history_per_asset'] += 1
        path.write_bytes(encode(manifest))
        return result

    monkeypatch.setattr(workflow, 'verify_daily_export', change)
    before = set(tmp_path.iterdir())
    with pytest.raises(ValueError, match='changed after verification'):
        run(tmp_path)
    assert set(tmp_path.iterdir()) == before


def test_source_change_during_batch_never_returns_complete(tmp_path, monkeypatch):
    request = inputs(tmp_path)
    original = workflow.run_forecast_batch

    def change(**kwargs):
        result = original(**kwargs)
        binding = json.loads((tmp_path/request['forecasts'][0]['daily_export']).read_bytes())
        (tmp_path/binding['request']['snapshots'][0]['file']).write_bytes(b'{}')
        return result

    monkeypatch.setattr(workflow, 'run_forecast_batch', change)
    with pytest.raises(ValueError):
        run(tmp_path)
    assert not any(json.loads(p.read_bytes()).get('schema') == 'ATLAS_SYNTHETIC_DAILY_FORECAST_RESULT_V1'
                   for p in tmp_path.glob('*.json'))
