"""Daily chart fixtures retain session-close/receipt provenance through AFI."""
import copy
import hashlib
import json
import subprocess
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from app.backtest.forecast_artifacts import publish_forecast, publish_research_text
from app.backtest.forecast_baselines import fit_baseline
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_outcomes import append_outcome
from app.backtest.forecast_report import (
    ForecastHistory,
    browser_export,
    build_accountability_report,
)
from app.investment.market_hours import ET, session_bounds

from scripts.observation_runtime.daily_afi_bridge import (
    build_daily_dataset,
    normalize_daily_chart,
)

POLICY = {'fixture_mode': 'SYNTHETIC_REPLAY', 'price_policy': 'UNADJUSTED', 'session_scope': 'REGULAR_ONLY'}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def chart(days, *, asset_class='US_ETF'):
    times = [int(session_bounds(datetime.combine(date.fromisoformat(day), time(12), ET))[0].timestamp()) for day in days]
    prices = [100+index for index in range(len(days))]
    return {'chart': {'error': None, 'result': [{'meta': {'symbol': 'SPY' if asset_class == 'US_ETF' else 'AAPL', 'currency': 'USD', 'dataGranularity': '1d',
                                                        'exchangeTimezoneName': 'America/New_York', 'instrumentType': 'ETF' if asset_class == 'US_ETF' else 'EQUITY'},
                                             'timestamp': times, 'indicators': {'quote': [{'open': prices, 'high': [p+1 for p in prices], 'low': [p-1 for p in prices], 'close': prices, 'volume': [1000]*len(days)}]}}]}}


def end(day):
    return session_bounds(datetime.combine(date.fromisoformat(day), time(12), ET))[1]


def snapshot(payload, receipt):
    raw = encode(payload)
    return {'payload_bytes': raw, 'sha256': hashlib.sha256(raw).hexdigest(), 'received_at': receipt}


def action_snapshot(actions, receipt, *, source_id='test-corporate-actions'):
    raw = encode({'schema': 'ATLAS_SYNTHETIC_CORPORATE_ACTIONS_V1',
                  'asset_id': 'ETF:SPY', 'actions': actions})
    return {'payload_bytes': raw, 'sha256': hashlib.sha256(raw).hexdigest(),
            'received_at': receipt, 'source_id': source_id}


def universe(asset_class='US_ETF'):
    return {'asset_id': ('ETF:SPY' if asset_class == 'US_ETF' else 'US_EQUITY:AAPL'),
            'listed_at': '2026-01-01T00:00:00+00:00', 'listing_available_at': '2026-01-01T00:00:00+00:00',
            'delisted_at': None, 'delisting_available_at': None}


def build(snapshots, *, asset_class='US_ETF', **changes):
    args = {'symbol': 'SPY' if asset_class == 'US_ETF' else 'AAPL', 'asset_class': asset_class, 'universe': universe(asset_class),
            'dataset_id': 'daily-fixture', 'version': 'v1', 'asof': snapshots[-1]['received_at'], **POLICY}
    return build_daily_dataset(snapshots, **{**args, **changes})


@pytest.mark.parametrize('day,expected', [('2026-10-30', '2026-10-30T20:00:00+00:00'), ('2026-11-02', '2026-11-02T21:00:00+00:00'), ('2026-11-27', '2026-11-27T18:00:00+00:00')])
def test_daily_event_uses_calendar_close_including_dst_and_early_close(day, expected):
    raw = encode(chart([day]))
    rows = normalize_daily_chart(raw, symbol='SPY', asset_class='US_ETF', received_at=end(day), **POLICY)
    assert rows[0]['timestamp'] == expected
    assert rows[0]['received_at'] == expected
    assert rows[0]['price_kind'] == 'DECLARED_UNADJUSTED_REGULAR_DAILY_CLOSE'


@pytest.mark.parametrize('fault', ['minute', 'midnight', 'incomplete', 'holiday', 'future', 'null', 'float-volume', 'unsafe-volume', 'bool-price', 'unsafe-price', 'ohlc', 'timezone', 'instrument', 'symbol', 'adjusted', 'extended', 'reversed', 'duplicate'])
def test_ambiguous_or_invalid_daily_sources_refuse_without_dropping_rows(fault):
    p = chart(['2026-10-15', '2026-10-16'])
    result = p['chart']['result'][0]
    receipt = end('2026-10-16')
    if fault == 'minute': result['meta']['dataGranularity'] = '1m'
    if fault == 'midnight': result['timestamp'][0] = int(datetime(2026, 10, 15, tzinfo=UTC).timestamp())
    if fault == 'incomplete': receipt -= timedelta(microseconds=1)
    if fault == 'holiday': result['timestamp'][0] = int(datetime(2026, 11, 26, 14, 30, tzinfo=UTC).timestamp())
    if fault == 'future': receipt = end('2026-10-15')
    if fault == 'null': result['indicators']['quote'][0]['close'][0] = None
    if fault == 'float-volume': result['indicators']['quote'][0]['volume'][0] = 1.5
    if fault == 'unsafe-volume': result['indicators']['quote'][0]['volume'][0] = 2**53
    if fault == 'bool-price': result['indicators']['quote'][0]['close'][0] = True
    if fault == 'unsafe-price': result['indicators']['quote'][0]['close'][0] = 2**53+1
    if fault == 'ohlc': result['indicators']['quote'][0]['high'][0] = 1
    if fault == 'timezone': result['meta']['exchangeTimezoneName'] = 'UTC'
    if fault == 'instrument': result['meta']['instrumentType'] = 'EQUITY'
    if fault == 'symbol': result['meta']['symbol'] = 'QQQ'
    if fault == 'adjusted': result['meta']['autoAdjust'] = True
    if fault == 'extended': result['meta']['includePrePost'] = True
    if fault == 'reversed': result['timestamp'].reverse()
    if fault == 'duplicate': result['timestamp'][1] = result['timestamp'][0]
    with pytest.raises(ForecastEvidenceRefused):
        normalize_daily_chart(encode(p), symbol='SPY', asset_class='US_ETF', received_at=receipt, **POLICY)


@pytest.mark.parametrize('field,value', [('fixture_mode', 'LIVE'), ('price_policy', 'SPLIT_ADJUSTED'), ('session_scope', 'ALL_SESSIONS')])
def test_no_implicit_real_or_adjusted_data_admission(field, value):
    with pytest.raises(ForecastEvidenceRefused):
        normalize_daily_chart(encode(chart(['2026-10-16'])), symbol='SPY', asset_class='US_ETF', received_at=end('2026-10-16'), **{**POLICY, field: value})


def test_bridge_preserves_first_receipts_and_appends_value_reverts():
    p = chart(['2026-10-15', '2026-10-16'])
    receipt = end('2026-10-16')+timedelta(minutes=1)
    correction = copy.deepcopy(p)
    correction['chart']['result'][0]['indicators']['quote'][0]['close'][0] += .25
    inputs = [snapshot(p, receipt), snapshot(p, receipt), snapshot(correction, receipt+timedelta(minutes=1)), snapshot(p, receipt+timedelta(minutes=2))]
    before = copy.deepcopy(inputs)
    result = build(inputs)
    records = json.loads(result.payload_bytes)['records']
    assert result.review.status == 'ACCEPTED_SYNTHETIC' and len(records) == 4
    assert len({row['revision'] for row in records}) == 4
    assert records[0]['available_at'] == receipt.isoformat()
    assert records[0]['source_sha256'] == inputs[0]['sha256']
    assert [row['value'] for row in records if row['observed_at'] == end('2026-10-15').isoformat()] == [100, 100.25, 100]
    audit = json.loads(result.audit_bytes)
    assert len(audit['source_snapshots']) == 3 and audit['repeated_close_n'] == 2
    assert audit['source_authenticated'] is audit['universe_truth_verified'] is False
    assert audit['full_session_completeness_verified'] is False
    assert inputs == before


def test_action_receipts_preserve_source_chronology_units_and_unadjusted_prices():
    dates = days(3)
    receipt = end(dates[-1])+timedelta(minutes=1)
    bars = snapshot(chart(dates), receipt)
    action = {'action_id': 'split-2026-10', 'kind': 'SPLIT',
              'effective_at': end(dates[1]).isoformat(), 'amount': 2,
              'economic_unit': 'NEW_SHARES_PER_OLD_SHARE'}
    first_receipt = receipt+timedelta(minutes=1)
    actions = [action_snapshot([action], first_receipt),
               action_snapshot([action], first_receipt+timedelta(minutes=1))]
    result = build([bars], action_snapshots=actions, asof=first_receipt+timedelta(minutes=1))
    payload = json.loads(result.payload_bytes)
    audit = json.loads(result.audit_bytes)
    assert result.review.status == 'ACCEPTED_SYNTHETIC'
    assert payload['actions'] == [{'action_id': 'split-2026-10', 'asset_id': 'ETF:SPY',
                                   'kind': 'SPLIT', 'effective_at': end(dates[1]).isoformat(),
                                   'available_at': first_receipt.isoformat(), 'amount': 2.0,
                                   'economic_unit': 'NEW_SHARES_PER_OLD_SHARE',
                                   'source_id': 'test-corporate-actions',
                                   'source_sha256': actions[0]['sha256']}]
    assert [row['value'] for row in payload['records']] == [100, 101, 102]
    assert all(row['source_sha256'] == bars['sha256'] for row in payload['records'])
    manifest = json.loads(result.manifest_bytes)
    assert manifest['assets'][0]['price_policy'] == 'UNADJUSTED'
    assert manifest['assets'][0]['dividend_policy'] == 'EXCLUDED_FROM_PRICE_RETURN'
    assert audit['corporate_action_provenance'][0]['source_id'] == 'test-corporate-actions'
    assert audit['corporate_action_provenance'][0]['source_sha256'] == actions[0]['sha256']
    assert audit['corporate_action_snapshots'][1]['received_at'] == (first_receipt+timedelta(minutes=1)).isoformat()
    assert audit['repeated_corporate_action_n'] == 1
    assert audit['corporate_actions_reconciled'] is False
    with pytest.raises(ForecastEvidenceRefused, match='Cross-split'):
        fit_baseline(result.review, asset_id='ETF:SPY', issued_at=receipt+timedelta(minutes=2),
                     evidence_asof=receipt+timedelta(minutes=2), lookback=3)


def test_dividend_receipt_is_not_reinvested_or_added_to_price_returns():
    dates = days(3)
    price_receipt = end(dates[-1])+timedelta(minutes=1)
    action_receipt = price_receipt+timedelta(minutes=1)
    dividend = {'action_id': 'dividend-1', 'kind': 'DIVIDEND',
                'effective_at': end(dates[1]).isoformat(), 'amount': 0.5,
                'economic_unit': 'USD_PER_SHARE'}
    result = build([snapshot(chart(dates), price_receipt)],
                   action_snapshots=[action_snapshot([dividend], action_receipt)],
                   asof=action_receipt)
    payload = json.loads(result.payload_bytes)
    manifest = json.loads(result.manifest_bytes)
    assert payload['actions'][0]['kind'] == 'DIVIDEND'
    assert payload['actions'][0]['available_at'] == action_receipt.isoformat()
    assert payload['actions'][0]['economic_unit'] == 'USD_PER_SHARE'
    assert payload['actions'][0]['source_sha256'] == action_snapshot([dividend], action_receipt)['sha256']
    assert [row['value'] for row in payload['records']] == [100, 101, 102]
    assert all(row['applied_action_ids'] == [] for row in payload['records'])
    assert manifest['assets'][0]['dividend_policy'] == 'EXCLUDED_FROM_PRICE_RETURN'


@pytest.mark.parametrize('fault', [
    'changed-correction', 'other-source', 'ambiguous-unit', 'unsupported-kind',
    'late', 'receipt-order', 'tampered-source', 'same-time-conflict', 'ambiguous-amount',
])
def test_corporate_action_receipts_refuse_unsupported_or_unavailable_evidence(fault):
    dates = days(3)
    price_receipt = end(dates[-1])+timedelta(minutes=1)
    action_receipt = price_receipt+timedelta(minutes=1)
    action = {'action_id': 'event-1', 'kind': 'DIVIDEND',
              'effective_at': end(dates[1]).isoformat(), 'amount': 1,
              'economic_unit': 'USD_PER_SHARE'}
    source = action_snapshot([action], action_receipt)
    action_sources = [source]
    changes = {'asof': action_receipt}
    if fault == 'changed-correction':
        changed = {**action, 'amount': 2}
        action_sources.append(action_snapshot([changed], action_receipt+timedelta(minutes=1)))
        changes['asof'] += timedelta(minutes=1)
    elif fault == 'other-source':
        action_sources.append(action_snapshot([action], action_receipt+timedelta(minutes=1),
                                              source_id='second-source'))
        changes['asof'] += timedelta(minutes=1)
    elif fault == 'ambiguous-unit':
        action['economic_unit'] = 'SHARES'
        source = action_snapshot([action], action_receipt)
        action_sources = [source]
    elif fault == 'unsupported-kind':
        action['kind'] = 'RETURN_OF_CAPITAL'
        source = action_snapshot([action], action_receipt)
        action_sources = [source]
    elif fault == 'late':
        changes['asof'] = action_receipt-timedelta(seconds=1)
    elif fault == 'receipt-order':
        action_sources.append(action_snapshot([action], action_receipt-timedelta(seconds=1)))
    elif fault == 'tampered-source':
        source['payload_bytes'] += b' '
    elif fault == 'same-time-conflict':
        changed = {**action, 'amount': 2}
        action_sources.append(action_snapshot([changed], action_receipt))
    elif fault == 'ambiguous-amount':
        action['amount'] = True
        source = action_snapshot([action], action_receipt)
        action_sources = [source]
    with pytest.raises(ForecastEvidenceRefused):
        build([snapshot(chart(dates), price_receipt)], action_snapshots=action_sources, **changes)


@pytest.mark.parametrize('fault', ['digest', 'receipt-order', 'same-receipt-conflict', 'future-receipt', 'universe', 'byte-budget'])
def test_bridge_missing_or_contradictory_evidence_refuses(fault):
    p = chart(['2026-10-15', '2026-10-16'])
    receipt = end('2026-10-16')+timedelta(minutes=1)
    inputs = [snapshot(p, receipt)]
    changes = {}
    if fault == 'digest': inputs[0]['sha256'] = '0'*64
    if fault == 'receipt-order': inputs += [snapshot(p, receipt-timedelta(seconds=1))]
    if fault == 'same-receipt-conflict':
        q = copy.deepcopy(p);q['chart']['result'][0]['indicators']['quote'][0]['volume'][0] += 1
        inputs += [snapshot(q, receipt)]
    if fault == 'future-receipt': changes['asof'] = receipt-timedelta(seconds=1)
    if fault == 'universe': changes['universe'] = {'asset_id': 'ETF:SPY'}
    if fault == 'byte-budget': inputs[0]['payload_bytes'] = b'x'*8_000_001
    with pytest.raises(ForecastEvidenceRefused): build(inputs, **changes)


def test_gap_and_short_history_remain_insufficient_not_imputed():
    for days in [['2026-10-16'], ['2026-10-14', '2026-10-16']]:
        result = build([snapshot(chart(days), end(days[-1]))])
        assert result.review.status == 'INSUFFICIENT_EVIDENCE'
        assert len(json.loads(result.payload_bytes)['records']) == len(days)
        with pytest.raises(ForecastEvidenceRefused):
            fit_baseline(result.review, asset_id='ETF:SPY', issued_at=end(days[-1])+timedelta(minutes=1), evidence_asof=end(days[-1])+timedelta(minutes=1), lookback=2)


def days(n):
    result, day = [], date(2026, 9, 21)
    while len(result) < n:
        if session_bounds(datetime.combine(day, time(12), ET)): result.append(day.isoformat())
        day += timedelta(days=1)
    return result


@pytest.mark.parametrize('asset_class', ['US_EQUITY', 'US_ETF'])
def test_daily_fixture_to_persisted_afi_forecast_outcome_and_browser_report(tmp_path, asset_class):
    calendar = days(16)
    receipt = end(calendar[-2])+timedelta(minutes=1)
    first = snapshot(chart(calendar[:-1], asset_class=asset_class), receipt)
    original = build([first], asset_class=asset_class)
    issue = receipt+timedelta(minutes=1)
    asset = universe(asset_class)['asset_id']
    with pytest.raises(ForecastEvidenceRefused):
        fit_baseline(original.review, asset_id=asset, issued_at=end(calendar[-2])-timedelta(seconds=1), evidence_asof=issue, lookback=5)
    model = fit_baseline(original.review, asset_id=asset, issued_at=issue, evidence_asof=issue, lookback=5)
    root = tmp_path/'evidence';root.mkdir()
    for raw in [original.manifest_bytes, original.payload_bytes, original.audit_bytes]:
        path = publish_research_text(root, raw.decode(), extension='.json')
        assert path.read_bytes() == raw
        assert publish_research_text(root, raw.decode(), extension='.json') == path
    forecast = publish_forecast(root, original.review, model, evidence_asof=issue)
    final_receipt = end(calendar[-1])+timedelta(minutes=1)
    final = build([first, snapshot(chart(calendar, asset_class=asset_class), final_receipt)], asset_class=asset_class, version='v2')
    latest_only = build([snapshot(chart(calendar, asset_class=asset_class), final_receipt)], asset_class=asset_class, version='v2')
    before_refusal = {path.name for path in root.iterdir()}
    with pytest.raises(ForecastEvidenceRefused, match='removed or rewritten'):
        append_outcome(root, forecast, original.review, latest_only.review, outcome_asof=final_receipt, evidence_asof=final_receipt)
    assert {path.name for path in root.iterdir()} == before_refusal
    outcome, record = append_outcome(root, forecast, original.review, final.review, outcome_asof=final_receipt, evidence_asof=final_receipt)
    report = build_accountability_report([ForecastHistory(forecast, original.review, ((outcome, final.review),), record['artifact_sha256'])], evidence_asof=final_receipt)
    assert report['forecast_n'] == report['score']['scored_n'] == 1 and report['correction_n'] == 0
    browser = publish_research_text(root, browser_export(report), extension='.json')
    source = Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    code = "const fs=require('fs'),v=require(process.argv[1]);v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8')).then(r=>{if(r.forecast_n!==1||r.score.scored_n!==1||r.production_approved!==false)throw Error('contract');process.stdout.write('PASS')}).catch(e=>{console.error(e);process.exitCode=1});"
    checked = subprocess.run(['C:/Program Files/nodejs/node.exe', '-e', code, str(source), str(browser)], capture_output=True, text=True, timeout=10, check=False)
    assert checked.returncode == 0, checked.stderr
    assert checked.stdout == 'PASS'
    archived = []
    for source_snapshot in [first, snapshot(chart(calendar, asset_class=asset_class), final_receipt)]:
        path = publish_research_text(root, source_snapshot['payload_bytes'].decode(), extension='.json')
        assert path.read_bytes() == source_snapshot['payload_bytes']
        archived.append({'file': path.name, 'sha256': source_snapshot['sha256'], 'received_at': source_snapshot['received_at'].isoformat()})
    bundles = {}
    for name, dataset in [('original', original), ('final', final)]:
        bundles[name] = {kind: publish_research_text(root, raw.decode(), extension='.json').name
                         for kind, raw in [('manifest', dataset.manifest_bytes), ('payload', dataset.payload_bytes), ('audit', dataset.audit_bytes)]}
    summary = {'schema': 'ATLAS_SYNTHETIC_DAILY_AFI_DEMO_V1', 'asset_class': asset_class,
               'symbol': 'SPY' if asset_class == 'US_ETF' else 'AAPL', 'universe': universe(asset_class),
               'snapshots': archived, 'datasets': bundles, 'forecast': forecast.name,
               'outcome': outcome.name, 'browser_report': browser.name,
               'source_authenticated': False, 'production_approved': False, 'runtime_provenance_verified': False}
    summary_path = publish_research_text(root, json.dumps(summary, sort_keys=True), extension='.json')
    (tmp_path/'integration-receipt.json').write_text(json.dumps({'summary': summary_path.name, 'evidence_root': str(root)}, sort_keys=True), encoding='utf8')

@pytest.mark.parametrize('fault', ['split-events', 'dividend-events', 'malformed-delay', 'quote-type'])
def test_known_unmapped_action_or_contradictory_metadata_is_not_silently_discarded(fault):
    p = chart(['2026-10-16'])
    result = p['chart']['result'][0]
    if fault == 'split-events': result['events'] = {'splits': {'one': {'splitRatio': '2:1'}}}
    if fault == 'dividend-events': result['events'] = {'dividends': {'one': {'amount': 1}}}
    if fault == 'malformed-delay': result['meta']['exchangeDataDelayedBy'] = True
    if fault == 'quote-type': result['meta']['quoteType'] = 'EQUITY'
    with pytest.raises(ForecastEvidenceRefused):
        normalize_daily_chart(encode(p), symbol='SPY', asset_class='US_ETF', received_at=end('2026-10-16'), **POLICY)


def test_delayed_historical_metadata_does_not_establish_live_or_publication_freshness():
    p = chart(['2026-10-15', '2026-10-16'])
    p['chart']['result'][0]['meta']['exchangeDataDelayedBy'] = 15
    result = build([snapshot(p, end('2026-10-16')+timedelta(hours=1))])
    audit = json.loads(result.audit_bytes)
    assert audit['provider_delay_semantics_verified'] is False
    assert audit['source_authenticated'] is audit['production_approved'] is False
    assert all(row['available_at'] == (end('2026-10-16')+timedelta(hours=1)).isoformat() for row in json.loads(result.payload_bytes)['records'])


def test_old_completed_daily_data_does_not_become_a_fresh_forecast_reference():
    calendar = days(15)
    receipt = end(calendar[-1])+timedelta(days=30)
    result = build([snapshot(chart(calendar), receipt)])
    assert result.review.status == 'ACCEPTED_SYNTHETIC'
    with pytest.raises(ForecastEvidenceRefused):
        fit_baseline(result.review, asset_id='ETF:SPY', issued_at=receipt, evidence_asof=receipt, lookback=5)

@pytest.mark.parametrize('part', ['chart', 'result', 'meta', 'quote'])
def test_malformed_chart_objects_fail_with_domain_refusal(part):
    p = chart(['2026-10-16'])
    if part == 'chart': p['chart'] = []
    if part == 'result': p['chart']['result'] = [[]]
    if part == 'meta': p['chart']['result'][0]['meta'] = []
    if part == 'quote': p['chart']['result'][0]['indicators']['quote'] = [[]]
    with pytest.raises(ForecastEvidenceRefused):
        normalize_daily_chart(encode(p), symbol='SPY', asset_class='US_ETF', received_at=end('2026-10-16'), **POLICY)


def test_unsupported_calendar_and_duplicate_json_fields_refuse():
    p = chart(['2026-10-16'])
    p['chart']['result'][0]['timestamp'][0] = int(datetime(2029, 10, 16, 13, 30, tzinfo=UTC).timestamp())
    with pytest.raises(ForecastEvidenceRefused):
        normalize_daily_chart(encode(p), symbol='SPY', asset_class='US_ETF', received_at=datetime(2029, 10, 17, tzinfo=UTC), **POLICY)
    raw = encode(chart(['2026-10-16'])).replace(b'"currency":', b'"currency":"EUR","currency":')
    with pytest.raises(ForecastEvidenceRefused):
        normalize_daily_chart(raw, symbol='SPY', asset_class='US_ETF', received_at=end('2026-10-16'), **POLICY)

@pytest.mark.parametrize('change', [{'asof': None}, {'asof': 'bad-clock'}, {'symbol': 7}])
def test_bad_public_clocks_or_identity_use_domain_refusal(change):
    receipt = end('2026-10-16')
    with pytest.raises(ForecastEvidenceRefused):
        build([snapshot(chart(['2026-10-15', '2026-10-16']), receipt)], **change)
