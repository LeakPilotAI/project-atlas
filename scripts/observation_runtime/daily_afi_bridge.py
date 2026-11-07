"""Pure synthetic daily-chart and explicit action receipts -> existing AFI contracts.

No transport, credentials, default storage, startup or trading imports. Caller
receipts are NOT authenticated vendor publication times or proof of completeness.
Separate action receipts accept only explicit split ratios and USD/share dividends;
prices remain unadjusted and price-return evaluation excludes dividends.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.backtest.forecast_dataset import (
    DatasetReview,
    _fields,
    _hash,
    _json,
    _number,
    review_dataset,
)
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, _identity
from app.investment.market_hours import session_bounds
from app.investment.offline_research import aware, symbol_identity, validated_candles


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def _clock(value):
    try:
        return aware(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ForecastEvidenceRefused('Explicit receipt/cutoff clock required') from error


def _symbol(value):
    try:
        return symbol_identity(value)
    except (TypeError, ValueError) as error:
        raise ForecastEvidenceRefused('Explicit supported symbol required') from error


def normalize_daily_chart(raw, *, symbol, asset_class, received_at, fixture_mode, price_policy, session_scope):
    """Opening-index, USD daily quote.close subset only; adjusted closes unused."""
    if (fixture_mode != 'SYNTHETIC_REPLAY' or price_policy != 'UNADJUSTED'
            or session_scope != 'REGULAR_ONLY' or type(asset_class) is not str or asset_class not in {'US_EQUITY', 'US_ETF'}):
        raise ForecastEvidenceRefused('Explicit synthetic unadjusted regular-session policy required')
    if type(raw) is not bytes or len(raw) > 1_000_000:
        raise ForecastEvidenceRefused('Bounded daily chart bytes required')
    try:
        receipt, expected = _clock(received_at), _symbol(symbol)
        chart = _json(raw)['chart']
        if type(chart) is not dict:
            raise ValueError('Chart object required')
        results = chart['result']
        if chart.get('error') is not None or type(results) is not list or len(results) != 1:
            raise ValueError('One successful chart required')
        result = results[0]
        if type(result) is not dict:
            raise ValueError('Chart result object required')
        if result.get('events') not in (None, {}):
            raise ValueError('Corporate-action metadata needs a separately reviewed mapping')
        meta = result['meta']
        if type(meta) is not dict:
            raise ValueError('Metadata object required')
        if (_symbol(meta['symbol']) != expected or meta['currency'] != 'USD'
                or meta['dataGranularity'] != '1d' or meta['exchangeTimezoneName'] != 'America/New_York'
                or meta['instrumentType'] != ('ETF' if asset_class == 'US_ETF' else 'EQUITY')
                or meta.get('quoteType', meta['instrumentType']) != meta['instrumentType']
                or meta.get('includePrePost', False) is not False or meta.get('autoAdjust', False) is not False):
            raise ValueError('Daily identity or declared semantics contradict fixture policy')
        if 'exchangeDataDelayedBy' in meta and (type(meta['exchangeDataDelayedBy']) is not int or not 0 <= meta['exchangeDataDelayedBy'] <= 86400):
            raise ValueError('Malformed delay metadata')
        times, quotes = result['timestamp'], result['indicators']['quote']
        if type(times) is not list or not 1 <= len(times) <= 10000 or type(quotes) is not list or len(quotes) != 1:
            raise ValueError('Bounded single series required')
        quote, names = quotes[0], ('open', 'high', 'low', 'close', 'volume')
        if type(quote) is not dict:
            raise ValueError('Quote object required')
        if any(type(quote[key]) is not list or len(quote[key]) != len(times) for key in names):
            raise ValueError('Aligned daily OHLCV required')
        candles, closes, previous = [], {}, None
        for index, stamp in enumerate(times):
            if type(stamp) is not int:
                raise ValueError('Integer opening timestamp required')
            opening = datetime.fromtimestamp(stamp, UTC)
            bounds = session_bounds(opening)
            if not bounds or bounds[0] != opening or bounds[1] > receipt or (previous is not None and opening <= previous):
                raise ValueError('Incomplete, unsupported or unordered daily session')
            values = {key: quote[key][index] for key in names}
            if any(type(values[key]) not in (int, float) or (type(values[key]) is int and abs(values[key]) > 2**53-1) for key in names[:-1]):
                raise ValueError('Exact numeric price fields required')
            if type(values['volume']) is not int or not 0 <= values['volume'] <= 2**53-1:
                raise ValueError('Bounded integral share volume required')
            candles.append({'timestamp': opening, **{key.title(): values[key] for key in names}})
            closes[opening] = bounds[1]
            previous = opening
        normalized = validated_candles(expected, candles, now=receipt)
    except (KeyError, TypeError, ValueError, OverflowError, OSError) as error:
        raise ForecastEvidenceRefused('Daily chart fixture refused') from error
    source_hash = hashlib.sha256(raw).hexdigest()
    return [{'symbol': expected, 'asset_class': asset_class, 'currency': 'USD',
             'source': 'YAHOO_DAILY_CHART_SHAPED_FIXTURE', 'data_mode': 'SYNTHETIC_REPLAY',
             'price_kind': 'DECLARED_UNADJUSTED_REGULAR_DAILY_CLOSE',
             'source_sha256': source_hash, 'source_authenticated': False,
             'vendor_publication_time_verified': False, 'full_session_completeness_verified': False,
             'bar_start': row['timestamp'].isoformat(), 'timestamp': closes[row['timestamp']].isoformat(),
             'received_at': receipt.isoformat(), 'close': row['Close'], 'volume': row['Volume']}
            for row in normalized]


@dataclass(frozen=True)
class DailyDataset:
    manifest_bytes: bytes
    payload_bytes: bytes
    audit_bytes: bytes
    review: DatasetReview


def _action_receipts(action_snapshots, *, asset_id, cutoff):
    if type(action_snapshots) is not list or len(action_snapshots) > 64:
        raise ForecastEvidenceRefused('Bounded explicit corporate-action receipts required')
    receipts, actions, identities, source_clocks = [], {}, {}, {}
    total, event_n, repeated = 0, 0, 0
    previous = None
    for snapshot in action_snapshots:
        _fields(snapshot, 'payload_bytes sha256 received_at source_id')
        raw, digest = snapshot['payload_bytes'], snapshot['sha256']
        _hash(digest)
        if type(raw) is not bytes or not 1 <= len(raw) <= 2_000_000 or hashlib.sha256(raw).hexdigest() != digest:
            raise ForecastEvidenceRefused('Corporate-action source commitment mismatch')
        total += len(raw)
        if total > 8_000_000:
            raise ForecastEvidenceRefused('Corporate-action source byte budget exceeded')
        source_id = snapshot['source_id']
        _identity(source_id)
        received = _clock(snapshot['received_at'])
        if received > cutoff or (previous is not None and received < previous):
            raise ForecastEvidenceRefused('Corporate-action receipt order or cutoff contradiction')
        prior_source = source_clocks.get(source_id)
        if prior_source is not None and received == prior_source[0] and digest != prior_source[1]:
            raise ForecastEvidenceRefused('Conflicting corporate-action snapshots at one source receipt time')
        source_clocks[source_id] = (received, digest)
        value = _json(raw)
        _fields(value, 'schema asset_id actions')
        if value['schema'] != 'ATLAS_SYNTHETIC_CORPORATE_ACTIONS_V1' or value['asset_id'] != asset_id:
            raise ForecastEvidenceRefused('Corporate-action source identity or asset mismatch')
        if type(value['actions']) is not list or len(value['actions']) > 512:
            raise ForecastEvidenceRefused('Bounded corporate-action rows required')
        event_n += len(value['actions'])
        if event_n > 2048:
            raise ForecastEvidenceRefused('Corporate-action event budget exceeded')
        for event in value['actions']:
            _fields(event, 'action_id kind effective_at amount economic_unit')
            action_id = event['action_id']
            _identity(action_id)
            kind = event['kind']
            if type(kind) is not str:
                raise ForecastEvidenceRefused('Explicit corporate-action kind required')
            amount = _number(event['amount'], positive=True)
            effective = _clock(event['effective_at'])
            expected_unit = {'SPLIT': 'NEW_SHARES_PER_OLD_SHARE',
                             'DIVIDEND': 'USD_PER_SHARE'}.get(kind)
            if expected_unit is None or event['economic_unit'] != expected_unit:
                raise ForecastEvidenceRefused('Unsupported corporate-action kind or economic unit')
            canonical = (kind, effective.isoformat(), amount, expected_unit)
            prior = identities.get(action_id)
            if prior is not None:
                if prior['source_id'] != source_id or prior['canonical'] != canonical:
                    raise ForecastEvidenceRefused('Corporate-action correction or source conflict is unsupported')
                repeated += 1
                continue
            identities[action_id] = {'source_id': source_id, 'canonical': canonical}
            actions[action_id] = {
                'action_id': action_id, 'asset_id': asset_id, 'kind': kind,
                'effective_at': effective.isoformat(), 'available_at': received.isoformat(),
                'amount': amount, 'economic_unit': expected_unit, 'source_id': source_id,
                'source_sha256': digest,
            }
        receipts.append({'source_id': source_id, 'sha256': digest, 'received_at': received.isoformat(),
                         'event_n': len(value['actions'])})
        previous = received
    provenance = [
        {'action_id': action_id, 'source_id': identities[action_id]['source_id'],
         'first_received_at': action['available_at'],
         'source_sha256': action['source_sha256']}
        for action_id, action in actions.items()
    ]
    return list(actions.values()), receipts, provenance, repeated, total


def build_daily_dataset(snapshots, *, symbol, asset_class, universe, dataset_id, version, asof,
                        fixture_mode, price_policy, session_scope, action_snapshots=None):
    """No inferred listing, adjustments or earlier publication availability.

    Duplicate close confirmations preserve the first receipt. Value changes/reverts
    append distinct receipt-bound revisions. Audit binds every supplied snapshot;
    it is not an independent archive witness or source-authenticity guarantee.
    Optional action snapshots are exact byte/hash/receipt/source_id mappings whose
    payload has schema ATLAS_SYNTHETIC_CORPORATE_ACTIONS_V1, the exact AFI asset_id,
    and actions with action_id, kind, effective_at, amount and economic_unit fields.
    Supported units are NEW_SHARES_PER_OLD_SHARE for SPLIT and USD_PER_SHARE for
    DIVIDEND; corrections and all implied adjustment/reinvestment semantics refuse.
    """
    if type(snapshots) is not list or not 1 <= len(snapshots) <= 64:
        raise ForecastEvidenceRefused('Bounded explicit daily snapshots required')
    cutoff = _clock(asof)
    _identity(dataset_id)
    _identity(version)
    _fields(universe, 'asset_id listed_at listing_available_at delisted_at delisting_available_at')
    total = sum(len(row.get('payload_bytes', b'')) if type(row) is dict and type(row.get('payload_bytes')) is bytes else 8_000_001 for row in snapshots)
    if total > 8_000_000:
        raise ForecastEvidenceRefused('Daily source byte budget exceeded')
    observations, sources, retained = [], [], {}
    previous, previous_hash, repeated, work = None, None, 0, 0
    if type(asset_class) is not str:
        raise ForecastEvidenceRefused('Explicit stock/ETF class required')
    afi_class = {'US_EQUITY': 'US_EQUITY', 'US_ETF': 'ETF'}.get(asset_class)
    if afi_class is None:
        raise ForecastEvidenceRefused('Explicit stock/ETF class required')
    asset_id = afi_class+':'+_symbol(symbol)
    for snapshot in snapshots:
        _fields(snapshot, 'payload_bytes sha256 received_at')
        raw, identity = snapshot['payload_bytes'], snapshot['sha256']
        _hash(identity)
        if hashlib.sha256(raw).hexdigest() != identity:
            raise ForecastEvidenceRefused('Source snapshot digest mismatch')
        receipt = _clock(snapshot['received_at'])
        if receipt > cutoff or (previous is not None and receipt < previous) or (receipt == previous and identity != previous_hash):
            raise ForecastEvidenceRefused('Ambiguous or future source receipt sequence')
        if receipt == previous:
            continue
        rows = normalize_daily_chart(raw, symbol=symbol, asset_class=asset_class, received_at=receipt,
                                     fixture_mode=fixture_mode, price_policy=price_policy, session_scope=session_scope)
        work += len(rows)
        if work > 50000:
            raise ForecastEvidenceRefused('Daily receipt work budget exceeded')
        sources.append({'sha256': identity, 'received_at': receipt.isoformat()})
        for row in rows:
            stamp, value = row['timestamp'], row['close']
            if stamp in retained and retained[stamp] == value:
                repeated += 1
                continue
            revision = hashlib.sha256(_encoded({'asset_id': asset_id, 'observed_at': stamp,
                                                'received_at': receipt.isoformat(), 'value': value,
                                                'source_sha256': identity})).hexdigest()
            observations.append({'record_id': revision, 'asset_id': asset_id, 'observed_at': stamp,
                                 'available_at': receipt.isoformat(), 'raw_price': value, 'value': value,
                                 'source_id': 'daily-chart-fixture', 'revision': revision,
                                 'source_sha256': identity, 'applied_action_ids': []})
            retained[stamp] = value
        previous, previous_hash = receipt, identity
    action_snapshots = [] if action_snapshots is None else action_snapshots
    if not isinstance(action_snapshots, list):
        raise ForecastEvidenceRefused('Explicit corporate-action receipt list required')
    actions, action_sources, action_provenance, repeated_actions, action_bytes = _action_receipts(
        action_snapshots, asset_id=asset_id, cutoff=cutoff)
    if total + action_bytes > 8_000_000:
        raise ForecastEvidenceRefused('Combined daily and corporate-action source byte budget exceeded')
    acquired = max([previous, *(_clock(row['received_at']) for row in action_snapshots)])
    payload = {'schema': 'AFI_PRICE_RECORDS_V1', 'records': observations, 'actions': actions, 'universe': [dict(universe)]}
    payload_bytes = _encoded(payload)
    manifest = {'schema': 'AFI_DATASET_MANIFEST_V1', 'dataset_id': dataset_id, 'version': version, 'evidence_class': 'SYNTHETIC',
                'source': {'id': 'daily-chart-fixture', 'provider': 'SYNTHETIC', 'license_id': 'SYNTHETIC_FIXTURE',
                           'license_sha256': hashlib.sha256(b'SYNTHETIC_FIXTURE_ONLY').hexdigest(), 'permission_status': 'SYNTHETIC_ONLY', 'permissions': ['OFFLINE_RESEARCH']},
                'acquired_at': acquired.isoformat(), 'generated_at': cutoff.isoformat(),
                'period_start': min(row['observed_at'] for row in observations), 'period_end': max(row['observed_at'] for row in observations),
                'content_sha256': hashlib.sha256(payload_bytes).hexdigest(), 'record_count': len(observations),
                'assets': [{'asset_id': asset_id, 'asset_class': afi_class, 'currency': 'USD', 'timezone': 'America/New_York',
                            'calendar': 'ATLAS_US_CASH_2026_2028', 'granularity': 'DAILY_CLOSE', 'price_policy': 'UNADJUSTED',
                            'dividend_policy': 'EXCLUDED_FROM_PRICE_RETURN', 'freshness_seconds': 345600}],
                'quality': {'max_missing_fraction': 0, 'min_history_per_asset': 2},
                'revision_policy': 'AS_PUBLISHED_APPEND_ONLY', 'availability_basis': 'AS_PUBLISHED_ARCHIVE', 'universe_policy': 'POINT_IN_TIME_WITH_DELISTED'}
    manifest_bytes = _encoded(manifest)
    if len(payload_bytes) > 2_000_000:
        raise ForecastEvidenceRefused('Daily dataset exceeds existing publication byte bound')
    review = review_dataset(manifest_bytes, payload_bytes, asof=cutoff)
    audit = {'schema': 'ATLAS_SYNTHETIC_DAILY_AFI_BRIDGE_V1', 'source_snapshots': sources, 'receipt_bar_work': work,
             'repeated_close_n': repeated, 'record_n': len(observations), 'manifest_sha256': review.manifest_sha256,
             'payload_sha256': review.content_sha256, 'dataset_status': review.status,
             'corporate_action_snapshots': action_sources, 'corporate_action_provenance': action_provenance,
             'corporate_action_event_n': len(actions), 'repeated_corporate_action_n': repeated_actions,
             'corporate_action_source_bytes': action_bytes,
             'availability_basis': 'CALLER_RECORDED_RECEIPTS_NOT_AUTHENTICATED_VENDOR_PUBLICATION',
             'source_authenticated': False, 'universe_truth_verified': False, 'corporate_actions_reconciled': False,
             'full_session_completeness_verified': False, 'provider_delay_semantics_verified': False,
             'declared_price_policy': price_policy, 'declared_session_scope': session_scope, 'production_approved': False, 'trading_authority': False}
    return DailyDataset(manifest_bytes, payload_bytes, _encoded(audit), review)
