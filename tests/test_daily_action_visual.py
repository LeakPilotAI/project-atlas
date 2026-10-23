"""Action presentation preserves issue-time provenance and price-only semantics."""
import hashlib
from datetime import timedelta
from types import SimpleNamespace

import pytest
from test_daily_afi_bridge import action_snapshot, days, encode, end
from test_daily_forecast_visual import render, single

from scripts.observation_runtime import daily_forecast_visual as visual
from scripts.observation_runtime.daily_afi_export import export_daily_dataset
from scripts.observation_runtime.daily_forecast_batch import run_daily_forecast_batch


def row(identity='dividend-1', **changes):
    return {'action_id': identity, 'asset_id': 'ETF:SPY', 'kind': 'DIVIDEND',
            'effective_at': '2026-10-15T20:00:00+00:00',
            'available_at': '2026-10-14T20:00:00+00:00', 'amount': 0.5,
            'economic_unit': 'USD_PER_SHARE', 'source_id': 'fixture-action',
            'source_sha256': 'a'*64, **changes}


def context(actions):
    return visual._action_context(SimpleNamespace(payload_bytes=encode({'actions': actions})),
                                  SimpleNamespace(asset_id='ETF:SPY', issued_at=end('2026-10-15')))


def test_issue_cutoff_excludes_later_receipts_and_other_assets():
    text = context([row(), row('late-secret', available_at='2026-10-16T20:00:00+00:00'),
                    row('foreign-secret', asset_id='US_EQUITY:AAPL'),
                    row('announced', effective_at='2026-10-16T20:00:00+00:00')])
    assert 'Showing 2 of 2' in text
    assert 'late-secret' not in text and 'foreign-secret' not in text
    assert 'Effective by issue' in text and 'Announced; effective after issue' in text
    assert 'Dividends are excluded from price returns' in text
    assert 'not a price multiplier' in text


def test_empty_and_all_late_are_not_completeness_claims():
    assert context([]) == ''
    text = context([row(available_at='2026-10-16T20:00:00+00:00')])
    assert 'Showing 0 of 0' in text
    assert 'does not establish complete' in text
    assert 'dividend-1' not in text


def test_rows_bounded_and_source_text_escaped():
    text = context([row(str(i), source_id='<script>bad</script>') for i in range(130)])
    assert 'Showing 128 of 130' in text
    assert text.count('<td>DIVIDEND</td>') == 128
    assert '<script>' not in text and '&lt;script&gt;' in text


@pytest.mark.parametrize('bad', ['bad', '2026-10-15T20:00:00'])
def test_invalid_action_clock_refuses(bad):
    with pytest.raises(ValueError):
        context([row(available_at=bad)])


def test_source_export_forecast_visual_displays_verified_dividend(tmp_path):
    calendar = days(16)
    source, request = single(tmp_path, calendar)
    issued = end(calendar[-1])+timedelta(minutes=2)
    event = {'action_id': 'verified-dividend', 'kind': 'DIVIDEND',
             'effective_at': end(calendar[-2]).isoformat(), 'amount': .5,
             'economic_unit': 'USD_PER_SHARE'}
    snapshot = action_snapshot([event], issued-timedelta(seconds=30))
    raw = snapshot['payload_bytes']
    pin = hashlib.sha256(raw).hexdigest()
    (tmp_path/(pin+'.json')).write_bytes(raw)
    source['action_snapshots'] = [{'file': pin+'.json', 'sha256': pin,
                                  'received_at': snapshot['received_at'].isoformat(),
                                  'source_id': snapshot['source_id']}]
    source['asof'] = snapshot['received_at'].isoformat()
    (tmp_path/'action-source-request.json').write_bytes(encode(source))
    binding = export_daily_dataset(bundle_root=tmp_path, request_name='action-source-request.json',
                                   output_root=tmp_path)['binding']
    request['forecasts'][0]['daily_export'] = binding
    request['forecasts'][0]['expected_daily_export_sha256'] = binding[:-5]
    (tmp_path/'action-forecast-request.json').write_bytes(encode(request))
    result = run_daily_forecast_batch(bundle_root=tmp_path, request_name='action-forecast-request.json',
                                     output_root=tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    text = render(tmp_path, result)
    assert 'verified-dividend' in text and pin in text
    assert 'USD_PER_SHARE' in text and 'Prices remain unadjusted' in text
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_no_action_visual_bytes_match_prior_render_path(tmp_path, monkeypatch):
    single(tmp_path, days(16))
    result = run_daily_forecast_batch(bundle_root=tmp_path, request_name='forecast-request.json',
                                     output_root=tmp_path)
    current = render(tmp_path, result)
    monkeypatch.setattr(visual, '_action_context', lambda review, model: '')
    assert render(tmp_path, result) == current
