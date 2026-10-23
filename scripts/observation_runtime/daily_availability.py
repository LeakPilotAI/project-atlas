"""Caller-receipt chronology, not provider latency or live-feed freshness."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from html import escape
from statistics import median

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _json
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused, aware

from scripts.observation_runtime.chart_archive import FLAGS, _pin, _read
from scripts.observation_runtime.daily_afi_export import verify_daily_export


def _distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {'n': 0, 'minimum_seconds': None, 'median_seconds': None, 'p95_seconds': None, 'maximum_seconds': None}
    return {'n': len(ordered), 'minimum_seconds': ordered[0], 'median_seconds': median(ordered),
            'p95_seconds': ordered[math.ceil(.95*len(ordered))-1], 'maximum_seconds': ordered[-1]}


def _pinned(reader, name):
    raw = _read(reader, name)
    if name != hashlib.sha256(raw).hexdigest()+'.json':
        raise ResearchInputRefused('Availability source artifact commitment changed')
    return raw


def daily_availability(*, bundle_root, binding_name, expected_binding_sha256, asof,
                       max_first_receipt_age_seconds):
    """Summaries use all recorded closes; display rows are capped explicitly.

    A new confirmation receipt never changes the first-known close timestamp.
    Elapsed ages include nights/weekends; they are not vendor delivery latency,
    market-session freshness, monitoring completeness or performance evidence.
    """
    cutoff = aware(asof)
    budget = max_first_receipt_age_seconds
    if type(budget) is not int or not 0 <= budget <= 1_000_000_000:
        raise ResearchInputRefused('Explicit bounded nonnegative caller receipt-age budget required')
    pin = _pin(expected_binding_sha256)
    verify_daily_export(bundle_root=bundle_root, binding_name=binding_name, expected_binding_sha256=pin)
    reader = BundleReader(bundle_root)
    binding = _json(_pinned(reader, binding_name))
    if aware(binding['request']['asof']) > cutoff:
        raise ResearchInputRefused('Availability cutoff predates the supplied export evidence')
    objects = {key: _json(_pinned(reader, name)) for key, name in binding['artifacts'].items()}
    groups = {}
    for record in objects['records']['records']:
        stamp, receipt = aware(record['observed_at']), aware(record['available_at'])
        if not stamp <= receipt <= cutoff:
            raise ResearchInputRefused('Close/receipt/cutoff chronology contradiction')
        groups.setdefault(stamp, []).append(receipt)
    if not groups:
        raise ResearchInputRefused('No supplied daily close observations')
    first_ages, revision_ages, since_first = [], [], []
    receipts, rows = Counter(), []
    for stamp, versions in sorted(groups.items()):
        versions.sort()
        first, latest = versions[0], versions[-1]
        first_age = (first-stamp).total_seconds()
        first_ages.append(first_age)
        revision_ages.extend((value-stamp).total_seconds() for value in versions[1:])
        since_first.extend((value-first).total_seconds() for value in versions[1:])
        receipts[first] += 1
        rows.append({'cash_close': stamp.isoformat(), 'first_known_receipt': first.isoformat(),
                     'latest_price_revision_receipt': latest.isoformat(), 'close_to_first_receipt_seconds': first_age,
                     'close_to_latest_revision_receipt_seconds': (latest-stamp).total_seconds(),
                     'price_revision_n': len(versions)-1, 'first_receipt_budget_exceeded': first_age > budget})
    audit = objects['audit']
    effective = audit['source_snapshots']
    seen, seen_payload_receipts = set(), 0
    for snapshot in effective:
        seen_payload_receipts += snapshot['sha256'] in seen
        seen.add(snapshot['sha256'])
    latest_close = max(groups)
    pattern = ('ONE_OBSERVATION_ONLY' if len(groups) == 1 else
               'SINGLE_RECEIPT_HISTORICAL_BATCH' if len(receipts) == 1 else
               'DISTINCT_FIRST_RECEIPTS' if len(receipts) == len(groups) else 'MIXED_RECEIPT_GROUPS')
    report = {'schema': 'ATLAS_SYNTHETIC_DAILY_AVAILABILITY_V1', 'mode': 'SYNTHETIC_REPLAY',
              'asof': cutoff.isoformat(), 'binding': binding_name, 'binding_sha256': pin,
              'source_artifacts': binding['artifacts'], 'dataset_status': binding['dataset_status'],
              'asset_id': binding['request']['universe']['asset_id'], 'receipt_pattern': pattern,
              'age_basis': 'CALENDAR_ELAPSED_CLOSE_TO_CALLER_RECEIPT_SECONDS',
              'percentile_method': 'NEAREST_RANK_CEIL_0_95_N', 'first_receipt_budget_seconds': budget,
              'first_receipt_budget_exceeded_n': sum(value > budget for value in first_ages),
              'observation_n': len(groups), 'price_record_n': len(objects['records']['records']),
              'price_revision_n': len(revision_ages), 'submitted_snapshot_n': len(binding['request']['snapshots']),
              'effective_receipt_n': len(effective),
              'exact_retry_n': len(binding['request']['snapshots'])-len(effective),
              'previously_seen_payload_receipt_n': seen_payload_receipts,
              'unchanged_close_confirmations_n': audit['repeated_close_n'],
              'first_receipt_age': _distribution(first_ages),
              'revision_receipt_age': _distribution(revision_ages),
              'revision_after_first_receipt_age': _distribution(since_first),
              'first_receipt_groups': [{'receipt': stamp.isoformat(), 'newly_known_close_n': n} for stamp, n in sorted(receipts.items())],
              'latest_cash_close': latest_close.isoformat(), 'latest_cash_close_age_seconds': (cutoff-latest_close).total_seconds(),
              'last_supplied_receipt': effective[-1]['received_at'],
              'time_since_last_supplied_receipt_seconds': (cutoff-aware(effective[-1]['received_at'])).total_seconds(),
              'displayed_observation_n': min(len(rows), 128), 'rows': rows[-128:],
              'provider_data_freshness': 'NOT_ESTABLISHED', 'provider_service_health': 'NOT_OBSERVED',
              'vendor_latency_verified': False, 'monitoring_completeness_verified': False,
              'history_completeness_verified': False, **FLAGS}
    verify_daily_export(bundle_root=bundle_root, binding_name=binding_name, expected_binding_sha256=pin)
    return report


def _render(report):
    def cell(value):
        return escape(str(value), quote=True)

    fields = ('cash_close', 'first_known_receipt', 'latest_price_revision_receipt',
              'close_to_first_receipt_seconds', 'price_revision_n', 'first_receipt_budget_exceeded')
    rows = ''.join('<tr>'+''.join('<td>'+cell(row[key])+'</td>' for key in fields)+'</tr>' for row in report['rows'])
    headings = ('Cash close UTC', 'First caller receipt UTC', 'Latest price revision receipt UTC',
                'First receipt age (seconds)', 'Later price revisions', 'Caller age budget exceeded')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>Daily source availability</title><style>body{{max-width:1250px;margin:auto;padding:30px;background:#080e17;color:#e7eef7;font:16px/1.6 system-ui,sans-serif}}section{{border:1px solid #53657d;padding:20px;margin:20px 0}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;border-bottom:1px solid #53657d;padding:10px;white-space:nowrap}}.pin{{overflow-wrap:anywhere}}</style></head><body><main>
<h1>Supplied daily source availability</h1><section><strong>Synthetic evidence only · production NO-GO</strong><p>Caller-recorded receipt ages include nights and weekends. They are not authenticated vendor latency, live freshness, completeness, trading permission or an independent archive witness. A recently received historical download is not a fresh live feed.</p></section>
<p>{cell(report['asset_id'])} · cutoff {cell(report['asof'])} · dataset {cell(report['dataset_status'])}</p>
<section><h2>Receipt chronology</h2><p>Pattern: {cell(report['receipt_pattern'])}. {report['observation_n']} unique closes, {report['price_revision_n']} later price revisions, {report['exact_retry_n']} exact retries, {report['unchanged_close_confirmations_n']} unchanged close confirmations.</p>
<p>First caller receipt ages: minimum {cell(report['first_receipt_age']['minimum_seconds'])}, median {cell(report['first_receipt_age']['median_seconds'])}, nearest-rank95th percentile {cell(report['first_receipt_age']['p95_seconds'])}, maximum {cell(report['first_receipt_age']['maximum_seconds'])} seconds.</p>
<p>{report['first_receipt_budget_exceeded_n']} first receipts exceed the caller's {report['first_receipt_budget_seconds']} second budget. This is a diagnostic threshold, not a provider-health or operational gate.</p>
<p>Latest supplied cash close age: {cell(report['latest_cash_close_age_seconds'])} seconds. Time since last supplied receipt: {cell(report['time_since_last_supplied_receipt_seconds'])} seconds. These describe different clocks.</p></section>
<div class="scroll" tabindex="0"><table><caption>Most recent {report['displayed_observation_n']} of {report['observation_n']} supplied closes; summaries use all records</caption><thead><tr>{''.join('<th scope="col">'+cell(label)+'</th>' for label in headings)}</tr></thead><tbody>{rows}</tbody></table></div>
<p class="pin">Supplied binding {cell(report['binding'])}. Provider freshness NOT_ESTABLISHED. Provider health NOT_OBSERVED. Native browser acceptance unestablished.</p></main></body></html>'''


def export_daily_availability(*, bundle_root, binding_name, expected_binding_sha256, asof,
                              max_first_receipt_age_seconds, output_root):
    if BundleReader(bundle_root).root != BundleReader(output_root).root:
        raise ResearchInputRefused('Retain diagnostic with its explicit isolated source bundle')
    report = daily_availability(bundle_root=bundle_root, binding_name=binding_name,
                                expected_binding_sha256=expected_binding_sha256, asof=asof,
                                max_first_receipt_age_seconds=max_first_receipt_age_seconds)
    raw = json.dumps(report, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    text = _render(report)
    paths = []
    for value, extension in [(raw, '.json'), (text, '.html')]:
        path = publish_research_text(output_root, value, extension=extension)
        if path.read_bytes() != value.encode():
            raise ResearchInputRefused('Availability publication read-back mismatch')
        paths.append(path.name)
    return {'status': 'SYNTHETIC_DAILY_AVAILABILITY_EXPORTED', 'report': paths[0], 'html': paths[1],
            'native_browser_acceptance': 'NOT_ESTABLISHED', **FLAGS}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Synthetic caller-receipt availability; no provider or runtime')
    for flag in ('bundle-root', 'binding', 'expected-binding-sha256', 'asof', 'output-root'):
        parser.add_argument('--'+flag, required=True)
    parser.add_argument('--max-first-receipt-age-seconds', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        result = export_daily_availability(bundle_root=args.bundle_root, binding_name=args.binding,
                                           expected_binding_sha256=args.expected_binding_sha256, asof=args.asof,
                                           max_first_receipt_age_seconds=args.max_first_receipt_age_seconds,
                                           output_root=args.output_root)
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        parser.exit(2, 'Availability input or publication refused; retain inputs and partial evidence.\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
