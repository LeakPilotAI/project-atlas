"""Explicit synthetic holdout -> existing accountability/browser contracts."""
from __future__ import annotations

import argparse
import hashlib
import json

from app.backtest.forecast_artifacts import artifact_bytes, publish_research_text
from app.backtest.forecast_baselines import PROBABILITY_METHOD
from app.backtest.forecast_dataset import _json
from app.backtest.forecast_outcomes import preview_outcome
from app.backtest.forecast_report import (
    BundleReader,
    ForecastHistory,
    _prepare_accountability_bundle,
    browser_export,
    build_accountability_report,
    prepare_batch_accountability,
    render_accountability_report,
    run_bundle,
)
from app.investment.offline_research import ResearchInputRefused

from scripts.observation_runtime.chart_archive import FLAGS, _pin, _read
from scripts.observation_runtime.daily_availability import _pinned
from scripts.observation_runtime.daily_forecast_batch import (
    _prepare,
    run_daily_forecast_batch,
    verify_daily_forecast_receipt,
)
from scripts.observation_runtime.daily_probability_replay import (
    diagnose_daily_probability_holdout,
)


def _publish(root, value):
    text = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    path = publish_research_text(root, text, extension='.json')
    if path.read_bytes() != text.encode():
        raise ResearchInputRefused('Holdout workspace bridge read-back mismatch')
    return path.name



def _issued_population(replay):
    issued = replay['forecasts']
    if type(issued) is not list or not 1 <= len(issued) <= 32:
        raise ResearchInputRefused('Existing batch bridge requires 1 to 32 issued forecasts; never truncate or fabricate')
    return issued


def export_holdout_accountability(*, bundle_root, companion_name, expected_companion_sha256, output_root):
    reader = BundleReader(bundle_root)
    if BundleReader(output_root).root != reader.root:
        raise ResearchInputRefused('Retain bridge with its explicit isolated holdout bundle')
    diagnostic = diagnose_daily_probability_holdout(bundle_root=bundle_root, companion_name=companion_name,
                                                   expected_companion_sha256=expected_companion_sha256)
    companion = _json(_pinned(reader, companion_name))
    report = _json(_pinned(reader, companion['holdout_result']['report']))
    replay = report['replay']
    issued = _issued_population(replay)
    binding = _json(_pinned(reader, companion['daily_export']))
    request = {'schema': 'ATLAS_SYNTHETIC_DAILY_FORECAST_REQUEST_V1', 'asof': replay['asof'],
               'forecasts': [{'daily_export': companion['daily_export'],
                 'expected_daily_export_sha256': companion['expected_daily_export_sha256'],
                 'asset_id': replay['asset_id'], 'issued_at': forecast['issued_at'],
                 'method': replay['method'], 'lookback': replay['lookback'], 'horizon': replay['horizon'],
                 'interval': None, 'probability_method': PROBABILITY_METHOD} for forecast in issued]}
    _prepare(reader, request)  # Full existing fitting preflight before publication.
    request_name = _publish(output_root, request)
    batch = run_daily_forecast_batch(bundle_root=bundle_root, request_name=request_name, output_root=output_root)
    verify_daily_forecast_receipt(bundle_root=bundle_root, receipt_name=batch['daily_receipt'],
                                  expected_receipt_sha256=batch['daily_receipt'][:-5])
    index = _json(_pinned(reader, batch['index']))
    if len(index['items']) != len(issued):
        raise ResearchInputRefused('Bridge forecast count differs from original holdout')
    for item, expected in zip(index['items'], issued, strict=True):
        artifact = _json(_read(reader, item['artifact']))
        if artifact['forecast'] != expected:
            raise ResearchInputRefused('Reconstructed forecast differs from original holdout forecast')
    accounting = {'schema': 'AFI_BATCH_ACCOUNTABILITY_REQUEST_V1', 'asof': replay['asof'],
                  'batch_plan': batch['daily_batch_plan'], 'batch_index': batch['index'],
                  'expected_index_sha256': batch['index'][:-5],
                  'outcomes': [{'forecast_sha256': item['forecast_sha256'], 'history': [], 'expected_head': None,
                    'append': {'dataset_manifest': binding['artifacts']['manifest'],
                               'dataset_records': binding['artifacts']['records'], 'source_archive': None,
                               'outcome_asof': replay['outcome_asof']}} for item in index['items']]}
    accounting_name = _publish(output_root, accounting)
    prepared = prepare_batch_accountability(bundle_root=bundle_root, request_name=accounting_name, output_root=output_root)
    accountability = run_bundle(bundle_root=bundle_root, bundle_name=prepared['bundle'], output_root=output_root)
    browser = _json(_pinned(reader, accountability['report']))
    states = {row['issued_at']: row['status'] for row in browser['rows']}
    expected_states = {case['issued_at']: case['status'] for case in replay['cases'] if case['status'] != 'REFUSED'}
    if states != expected_states or accountability['scored_n'] != replay['resolved_n']:
        raise ResearchInputRefused('Accountability outcome states differ from original holdout')
    diagnose_daily_probability_holdout(bundle_root=bundle_root, companion_name=companion_name,
                                       expected_companion_sha256=expected_companion_sha256)
    bridge = {'schema': 'ATLAS_SYNTHETIC_HOLDOUT_ACCOUNTABILITY_BRIDGE_V1',
              'holdout_companion': companion_name, 'expected_holdout_sha256': expected_companion_sha256,
              'daily_receipt': batch['daily_receipt'], 'accounting_request': accounting_name,
              'accountability': accountability, 'counts': diagnostic['counts'],
              'refused_cases': [case for case in replay['cases'] if case['status'] == 'REFUSED'],
              'browser_scope': 'ISSUED_FORECASTS_ONLY; REFUSALS_RETAINED_IN_THIS_COMPANION',
              'historical_execution_attested': False, 'independently_unseen': False, **FLAGS}
    name = _publish(output_root, bridge)
    return {'status': 'SYNTHETIC_HOLDOUT_ACCOUNTABILITY_EXPORTED', 'bridge': name,
            'browser_export': accountability['browser_export'], 'counts': diagnostic['counts'], **FLAGS}



def verify_holdout_accountability(*, bundle_root, bridge_name, expected_bridge_sha256):
    """Reconstruct committed forecasts, outcome records and browser bytes without writes."""
    pin = _pin(expected_bridge_sha256)
    if bridge_name != pin+'.json':
        raise ResearchInputRefused('Exact caller-retained workspace bridge pin required')
    reader = BundleReader(bundle_root)
    raw = _pinned(reader, bridge_name)
    bridge = _json(raw)
    diagnostic = diagnose_daily_probability_holdout(bundle_root=bundle_root,
        companion_name=bridge['holdout_companion'], expected_companion_sha256=bridge['expected_holdout_sha256'])
    companion = _json(_pinned(reader, bridge['holdout_companion']))
    holdout = _json(_pinned(reader, companion['holdout_result']['report']))['replay']
    _issued_population(holdout)
    binding = _json(_pinned(reader, companion['daily_export']))
    verify_daily_forecast_receipt(bundle_root=bundle_root, receipt_name=bridge['daily_receipt'],
                                  expected_receipt_sha256=bridge['daily_receipt'][:-5])
    receipt = _json(_pinned(reader, bridge['daily_receipt']))
    request = {'schema': 'ATLAS_SYNTHETIC_DAILY_FORECAST_REQUEST_V1', 'asof': holdout['asof'],
               'forecasts': [{'daily_export': companion['daily_export'],
                 'expected_daily_export_sha256': companion['expected_daily_export_sha256'],
                 'asset_id': holdout['asset_id'], 'issued_at': forecast['issued_at'],
                 'method': holdout['method'], 'lookback': holdout['lookback'], 'horizon': holdout['horizon'],
                 'interval': None, 'probability_method': PROBABILITY_METHOD} for forecast in holdout['forecasts']]}
    if receipt['request'] != request:
        raise ResearchInputRefused('Workspace batch differs from committed holdout forecasts')
    plan = _json(_pinned(reader, receipt['batch_plan']))
    index = _json(_pinned(reader, receipt['batch_result']['index']))
    if len(index['items']) != len(holdout['forecasts']):
        raise ResearchInputRefused('Workspace bridge population changed')
    for item, forecast in zip(index['items'], holdout['forecasts'], strict=True):
        if _json(_read(reader, item['artifact']))['forecast'] != forecast:
            raise ResearchInputRefused('Workspace forecast differs from original holdout')
    accounting = {'schema': 'AFI_BATCH_ACCOUNTABILITY_REQUEST_V1', 'asof': holdout['asof'],
                  'batch_plan': receipt['batch_plan'], 'batch_index': receipt['batch_result']['index'],
                  'expected_index_sha256': receipt['batch_result']['index'][:-5],
                  'outcomes': [{'forecast_sha256': item['forecast_sha256'], 'history': [], 'expected_head': None,
                    'append': {'dataset_manifest': binding['artifacts']['manifest'],
                               'dataset_records': binding['artifacts']['records'], 'source_archive': None,
                               'outcome_asof': holdout['outcome_asof']}} for item in index['items']]}
    accounting_raw = (json.dumps(accounting, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    if _pinned(reader, bridge['accounting_request']) != accounting_raw:
        raise ResearchInputRefused('Workspace outcome instructions changed')
    bundle = {'schema': 'AFI_ACCOUNTABILITY_BUNDLE_V2', 'asof': holdout['asof'],
              'forecasts': [{'artifact': item['artifact'],
                **{key: spec[key] for key in ('dataset_manifest', 'dataset_records', 'source_archive')},
                **{key: instruction[key] for key in ('history', 'expected_head', 'append')}}
                for spec, item, instruction in zip(plan['forecasts'], index['items'], accounting['outcomes'], strict=True)]}
    asof, entries, updates = _prepare_accountability_bundle(reader, bundle)
    verified_entries, heads = [], []
    for entry, (review, source, cutoff) in zip(entries, updates, strict=True):
        record = preview_outcome(entry.forecast_path, entry.forecast_review, review,
            evidence_asof=asof, outcome_asof=cutoff, history=(), expected_head=None,
            source_review=entry.source_review, outcome_source=source)
        name = record['artifact_sha256']+'.json'
        if _read(reader, name) != artifact_bytes(record):
            raise ResearchInputRefused('Workspace outcome record differs from reconstruction')
        heads.append(record['artifact_sha256'])
        verified_entries.append(ForecastHistory(entry.forecast_path, entry.forecast_review,
            ((reader.path(name), review, source),), record['artifact_sha256'], entry.source_review))
    report = build_accountability_report(verified_entries, evidence_asof=asof)
    outputs = {}
    for key, text, extension in (
            ('report', json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+'\n', '.json'),
            ('dashboard', render_accountability_report(report), '.html'),
            ('browser_export', browser_export(report), '.json')):
        name = hashlib.sha256(text.encode()).hexdigest()+extension
        if _read(reader, name) != text.encode():
            raise ResearchInputRefused('Workspace report/browser bytes differ from reconstruction')
        outputs[key] = name
    result = {'status': 'OFFLINE_ACCOUNTABILITY_COMPLETE', **outputs, 'updated_heads': heads,
              'forecast_n': report['forecast_n'], 'scored_n': report['score']['scored_n'],
              'production_approved': False, 'trading_authority': False}
    expected = {'schema': 'ATLAS_SYNTHETIC_HOLDOUT_ACCOUNTABILITY_BRIDGE_V1',
              'holdout_companion': bridge['holdout_companion'], 'expected_holdout_sha256': bridge['expected_holdout_sha256'],
              'daily_receipt': bridge['daily_receipt'], 'accounting_request': bridge['accounting_request'],
              'accountability': result, 'counts': diagnostic['counts'],
              'refused_cases': [case for case in holdout['cases'] if case['status'] == 'REFUSED'],
              'browser_scope': 'ISSUED_FORECASTS_ONLY; REFUSALS_RETAINED_IN_THIS_COMPANION',
              'historical_execution_attested': False, 'independently_unseen': False, **FLAGS}
    if raw != (json.dumps(expected, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode():
        raise ResearchInputRefused('Workspace bridge differs from reconstructed accountability')
    diagnose_daily_probability_holdout(bundle_root=bundle_root, companion_name=bridge['holdout_companion'],
                                       expected_companion_sha256=bridge['expected_holdout_sha256'])
    return {'status': 'SYNTHETIC_HOLDOUT_ACCOUNTABILITY_REPRODUCED', 'bridge': bridge_name,
            'browser_export': outputs['browser_export'], 'counts': diagnostic['counts'], **FLAGS}



def _continuation_plan(reader, bridge_name, expected_bridge_sha256):
    verify_holdout_accountability(bundle_root=reader.root, bridge_name=bridge_name,
                                  expected_bridge_sha256=expected_bridge_sha256)
    bridge = _json(_pinned(reader, bridge_name))
    receipt = _json(_pinned(reader, bridge['daily_receipt']))
    plan = _json(_pinned(reader, receipt['batch_plan']))
    index = _json(_pinned(reader, receipt['batch_result']['index']))
    accounting = _json(_pinned(reader, bridge['accounting_request']))
    forecasts = []
    for spec, item, head in zip(plan['forecasts'], index['items'], bridge['accountability']['updated_heads'], strict=True):
        references = {key: spec[key] for key in ('dataset_manifest', 'dataset_records', 'source_archive')}
        forecasts.append({'artifact': item['artifact'], **references,
            'history': [{'artifact': head+'.json', **references}], 'expected_head': head, 'append': None})
    bundle = {'schema': 'AFI_ACCOUNTABILITY_BUNDLE_V2', 'asof': accounting['asof'], 'forecasts': forecasts}
    asof, entries, updates = _prepare_accountability_bundle(reader, bundle)
    report = build_accountability_report(entries, evidence_asof=asof)
    expected_report = (json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    if any(update is not None for update in updates) or _pinned(reader, bridge['accountability']['report']) != expected_report:
        raise ResearchInputRefused('Continuation does not preserve the original bridge history')
    return bridge, bundle


def prepare_holdout_continuation(*, bundle_root, bridge_name, expected_bridge_sha256, output_root):
    reader = BundleReader(bundle_root)
    if BundleReader(output_root).root != reader.root:
        raise ResearchInputRefused('Retain continuation in its explicit isolated source bundle')
    bridge, bundle = _continuation_plan(reader, bridge_name, expected_bridge_sha256)
    name = _publish(output_root, bundle)
    companion = {'schema': 'ATLAS_SYNTHETIC_HOLDOUT_CONTINUATION_V1', 'bridge': bridge_name,
                 'expected_bridge_sha256': expected_bridge_sha256, 'bundle': name,
                 'original_counts': bridge['counts'], 'refused_cases': bridge['refused_cases'],
                 'outcome_appends_performed': 0, 'forecast_writes_performed': 0,
                 'historical_execution_attested': False, **FLAGS}
    published = _publish(output_root, companion)
    return {'status': 'SYNTHETIC_HOLDOUT_CONTINUATION_PREPARED', 'companion': published,
            'bundle': name, 'original_counts': bridge['counts'], 'outcome_appends_performed': 0, **FLAGS}


def verify_holdout_continuation(*, bundle_root, companion_name, expected_companion_sha256):
    pin = _pin(expected_companion_sha256)
    if companion_name != pin+'.json':
        raise ResearchInputRefused('Exact continuation companion pin required')
    reader = BundleReader(bundle_root)
    raw = _pinned(reader, companion_name)
    companion = _json(raw)
    bridge, bundle = _continuation_plan(reader, companion['bridge'], companion['expected_bridge_sha256'])
    text = json.dumps(bundle, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    name = hashlib.sha256(text.encode()).hexdigest()+'.json'
    expected = {'schema': 'ATLAS_SYNTHETIC_HOLDOUT_CONTINUATION_V1', 'bridge': companion['bridge'],
                'expected_bridge_sha256': companion['expected_bridge_sha256'], 'bundle': name,
                'original_counts': bridge['counts'], 'refused_cases': bridge['refused_cases'],
                'outcome_appends_performed': 0, 'forecast_writes_performed': 0,
                'historical_execution_attested': False, **FLAGS}
    if (raw != (json.dumps(expected, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
            or _pinned(reader, name) != text.encode()):
        raise ResearchInputRefused('Continuation differs from reconstructed bridge history')
    return {'status': 'SYNTHETIC_HOLDOUT_CONTINUATION_REPRODUCED', 'companion': companion_name,
            'bundle': name, 'original_counts': bridge['counts'], **FLAGS}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Explicit synthetic holdout export to existing offline forecast viewer')
    parser.add_argument('--bundle-root', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--companion')
    mode.add_argument('--verify-bridge')
    mode.add_argument('--prepare-continuation')
    mode.add_argument('--verify-continuation')
    parser.add_argument('--expected-companion-sha256', required=True)
    parser.add_argument('--output-root')
    args = parser.parse_args(argv)
    publishing = args.companion is not None or args.prepare_continuation is not None
    if publishing != (args.output_root is not None):
        parser.error('Export requires output root; read-only bridge verification forbids it')
    try:
        if args.prepare_continuation is not None:
            result = prepare_holdout_continuation(bundle_root=args.bundle_root, bridge_name=args.prepare_continuation,
                expected_bridge_sha256=args.expected_companion_sha256, output_root=args.output_root)
        elif args.verify_continuation is not None:
            result = verify_holdout_continuation(bundle_root=args.bundle_root, companion_name=args.verify_continuation,
                expected_companion_sha256=args.expected_companion_sha256)
        elif args.verify_bridge is not None:
            result = verify_holdout_accountability(bundle_root=args.bundle_root, bridge_name=args.verify_bridge,
                expected_bridge_sha256=args.expected_companion_sha256)
        else:
            result = export_holdout_accountability(bundle_root=args.bundle_root, companion_name=args.companion,
                expected_companion_sha256=args.expected_companion_sha256, output_root=args.output_root)
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        parser.exit(2, 'Holdout accountability bridge refused or incomplete; preserve all partial evidence.\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
