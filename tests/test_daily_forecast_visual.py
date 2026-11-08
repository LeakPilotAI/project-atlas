"""Issue-time chart histories and a separate inert visual publication contract."""
import hashlib
import html
import json
import math
import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from test_daily_afi_bridge import POLICY, chart, days, encode, end, universe
from test_daily_forecast_batch import inputs, run

from scripts.observation_runtime import daily_forecast_visual as visual
from scripts.observation_runtime.daily_afi_export import export_daily_dataset
from scripts.observation_runtime.daily_forecast_batch import run_daily_forecast_batch


def render(root, result, **kwargs):
    return visual.render_daily_forecast_visual(bundle_root=root, receipt_name=result['daily_receipt'],
                                               expected_receipt_sha256=result['daily_receipt'][:-5], **kwargs)


def prices(text):
    tables = re.findall(r'<tbody>(.*?)</tbody>', text)
    return [[float(html.unescape(re.findall(r'<td>(.*?)</td>', row)[2])) for row in re.findall(r'<tr>(.*?)</tr>', table)]
            for table in tables]


def single(root, calendar):
    stamp = end(calendar[-1])+timedelta(minutes=1)
    raw = encode(chart(calendar))
    pin = hashlib.sha256(raw).hexdigest()
    (root/(pin+'.json')).write_bytes(raw)
    source = {'schema': 'ATLAS_SYNTHETIC_DAILY_EXPORT_REQUEST_V1',
              'snapshots': [{'file': pin+'.json', 'sha256': pin, 'received_at': stamp.isoformat()}],
              'symbol': 'SPY', 'asset_class': 'US_ETF', 'universe': universe(), 'dataset_id': 'visual-series',
              'version': 'v1', 'asof': stamp.isoformat(), **POLICY}
    (root/'source-request.json').write_bytes(encode(source))
    exported = export_daily_dataset(bundle_root=root, request_name='source-request.json', output_root=root)
    spec = {'daily_export': exported['binding'], 'expected_daily_export_sha256': exported['binding'][:-5],
            'asset_id': 'ETF:SPY', 'issued_at': (stamp+timedelta(minutes=1)).isoformat(), 'method': 'NO_CHANGE',
            'lookback': 5, 'horizon': '1D', 'interval': None, 'probability_method': None}
    request = {'schema': 'ATLAS_SYNTHETIC_DAILY_FORECAST_REQUEST_V1', 'asof': spec['issued_at'], 'forecasts': [spec]}
    (root/'forecast-request.json').write_bytes(encode(request))
    return source, request


def test_separate_four_panel_visual_is_inert_accessible_and_deterministic(tmp_path):
    inputs(tmp_path)
    result = run(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    text = render(tmp_path, result, title='<img src=x onerror=alert(1)>')
    assert text == render(tmp_path, result, title='<img src=x onerror=alert(1)>')
    assert text.count('<svg ') == 4 and text.count('<table>') == 4
    assert text.count('role="img"') == 4
    assert len(set(re.findall(r'id="([^"]+)"', text))) == 12
    assert '<script' not in text and '<img' not in text
    assert '&lt;img src=x onerror=alert(1)&gt;' in text
    assert 'connect-src &#x27;none&#x27;' not in text
    assert "connect-src 'none'" in text and "default-src 'none'" in text
    assert all(values == list(range(100, 116)) for values in prices(text))
    assert 'coverage unverified' not in text  # No interval was fitted.
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_later_revision_and_target_price_cannot_leak_into_issue_time_history(tmp_path):
    calendar = days(17)
    source, request = single(tmp_path, calendar[:-1])
    stamp = end(calendar[-1])+timedelta(minutes=1)
    payload = chart(calendar)
    quote = payload['chart']['result'][0]['indicators']['quote'][0]
    quote['close'][0] = 777
    quote['high'][0] = 778
    quote['close'][-1] = 999
    quote['high'][-1] = 1000
    raw = encode(payload)
    pin = hashlib.sha256(raw).hexdigest()
    (tmp_path/(pin+'.json')).write_bytes(raw)
    source['snapshots'].append({'file': pin+'.json', 'sha256': pin, 'received_at': stamp.isoformat()})
    source.update(version='v2', asof=stamp.isoformat())
    (tmp_path/'source-request.json').write_bytes(encode(source))
    exported = export_daily_dataset(bundle_root=tmp_path, request_name='source-request.json', output_root=tmp_path)
    request['forecasts'][0].update(daily_export=exported['binding'], expected_daily_export_sha256=exported['binding'][:-5])
    request['asof'] = stamp.isoformat()
    (tmp_path/'forecast-request.json').write_bytes(encode(request))
    result = run_daily_forecast_batch(bundle_root=tmp_path, request_name='forecast-request.json', output_root=tmp_path)
    text = render(tmp_path, result)
    assert prices(text) == [list(range(100, 116))]
    issue = datetime.fromisoformat(request['forecasts'][0]['issued_at'])
    for row in re.findall(r'<tr>(.*?)</tr>', re.findall(r'<tbody>(.*?)</tbody>', text)[0]):
        cells = re.findall(r'<td>(.*?)</td>', row)
        assert datetime.fromisoformat(cells[1]) <= issue


def test_history_is_explicitly_capped_without_changing_original_forecasts(tmp_path):
    single(tmp_path, days(150))
    result = run(tmp_path)
    text = render(tmp_path, result)
    assert 'Showing 128 of 150 issue-time known closes' in text
    assert prices(text) == [list(range(122, 250))]


@pytest.mark.parametrize('values', [[0.0, 0.0], [1e308, 1e308], [1e-300, 2e-300], [1e307, 1e308]])
def test_chart_coordinates_remain_finite_at_numeric_boundaries(values):
    rows = [SimpleNamespace(value=value, observed_at=datetime(2026, 10, 19, tzinfo=UTC)) for value in values]
    text = visual._chart(rows, {'reference_price': values[-1], 'point': values[-1], 'lower': values[0], 'upper': values[-1], 'horizon': '1D'}, {}, 0)
    for token in re.findall(r'(?:cx|cy)="([^"]+)"', text):
        assert math.isfinite(float(token))
    assert 'nan' not in text.lower() and 'inf' not in text.lower()


def test_publish_failure_never_returns_success_or_changes_batch(tmp_path, monkeypatch):
    inputs(tmp_path)
    result = run(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def fail(*args, **kwargs):
        raise OSError('synthetic visual storage failure')

    monkeypatch.setattr(visual, 'publish_research_text', fail)
    with pytest.raises(OSError, match='storage failure'):
        visual.publish_daily_forecast_visual(bundle_root=tmp_path, receipt_name=result['daily_receipt'],
                                             expected_receipt_sha256=result['daily_receipt'][:-5], output_root=tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_visual_publication_is_append_only_and_requires_valid_receipt(tmp_path):
    inputs(tmp_path)
    result = run(tmp_path)
    args = {'bundle_root': tmp_path, 'receipt_name': result['daily_receipt'],
            'expected_receipt_sha256': result['daily_receipt'][:-5], 'output_root': tmp_path}
    published = visual.publish_daily_forecast_visual(**args)
    assert published['html'] != result['dashboard']
    assert published['native_browser_acceptance'] == 'NOT_ESTABLISHED'
    assert visual.publish_daily_forecast_visual(**args) == published
    assert hashlib.sha256((tmp_path/published['html']).read_bytes()).hexdigest() == published['html_sha256']
    args['expected_receipt_sha256'] = '0'*64
    with pytest.raises(ValueError):
        visual.publish_daily_forecast_visual(**args)


@pytest.mark.parametrize('title', [None, '', 'x'*121, 'untrusted\ntitle'])
def test_invalid_titles_refuse_before_any_bundle_access(tmp_path, title):
    with pytest.raises(ValueError, match='plain-text title'):
        visual.render_daily_forecast_visual(bundle_root=tmp_path/'not-created', receipt_name='unused',
                                             expected_receipt_sha256='0'*64, title=title)
    assert not list(tmp_path.iterdir())


def test_explicit_cli_publishes_without_launching_browser(tmp_path, capsys):
    inputs(tmp_path)
    result = run(tmp_path)
    args = ['--bundle-root', str(tmp_path), '--receipt', result['daily_receipt'],
            '--expected-receipt-sha256', result['daily_receipt'][:-5], '--output-root', str(tmp_path)]
    assert visual.main(args) == 0
    published = json.loads(capsys.readouterr().out)
    assert published['startup_authorized'] is False
    assert (tmp_path/published['html']).is_file()
    with pytest.raises(SystemExit) as exc:
        visual.main(args[:-2])
    assert exc.value.code == 2
    args[5] = '0'*64
    with pytest.raises(SystemExit) as exc:
        visual.main(args)
    assert exc.value.code == 2


def test_five_session_projection_uses_five_session_horizontal_spacing():
    rows = [SimpleNamespace(value=value, observed_at=datetime(2026, 10, 19, tzinfo=UTC)) for value in [100., 101.]]
    text = visual._chart(rows, {'reference_price': 101., 'point': 103., 'horizon': '5D'}, None, 0)
    match = re.search(r'class="projection" d="M([\d.]+) [\d.]+L([\d.]+) [\d.]+"', text)
    assert match
    assert float(match[1]) == 180.0 and float(match[2]) == 805.0


def test_five_session_forecast_receipt_reaches_visual_without_relabeling(tmp_path):
    _, request = single(tmp_path, days(16))
    request['forecasts'][0]['horizon'] = '5D'
    (tmp_path/'forecast-request.json').write_text(json.dumps(request), encoding='utf-8')
    result = run(tmp_path)
    text = render(tmp_path, result)
    assert 'horizon 5D' in text
    assert '5 cash sessions after the reference' in text
    assert prices(text) == [list(range(100, 116))]


@pytest.mark.parametrize('horizon', [None, '1W', [], True])
def test_ambiguous_visual_horizon_never_defaults_to_one_session(horizon):
    rows = [SimpleNamespace(value=100., observed_at=datetime(2026, 10, 19, tzinfo=UTC))]
    with pytest.raises(ValueError, match='projection horizon'):
        visual._chart(rows, {'reference_price': 100., 'point': 101., 'horizon': horizon}, None, 0)


def test_receipt_chronology_is_explicit_opt_in_and_not_a_feed_health_badge(tmp_path):
    inputs(tmp_path)
    result = run(tmp_path)
    original = render(tmp_path, result)
    assert 'Source receipt chronology at the report cutoff' not in original
    enriched = render(tmp_path, result, availability_budget_seconds=60)
    assert enriched.count('Source receipt chronology at the report cutoff') == 4
    assert enriched.count('SINGLE_RECEIPT_HISTORICAL_BATCH') == 4
    assert enriched.count('Provider freshness NOT_ESTABLISHED') == 4
    assert 'price chart still excludes anything unknown at its issue time' in enriched
    assert prices(enriched) == prices(original)
    assert render(tmp_path, result) == original
