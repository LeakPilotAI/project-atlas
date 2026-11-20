"""Explicit offline label updates; original forecasts and refused cases stay fixed."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import PurePosixPath

from app.backtest.forecast_artifacts import artifact_bytes, publish_research_text
from app.backtest.forecast_dataset import _fields, _json
from app.backtest.forecast_outcomes import preview_outcome
from app.backtest.forecast_report import (
    BundleReader,
    ForecastHistory,
    _prepare_accountability_bundle,
    browser_export,
    build_accountability_report,
    render_accountability_report,
    run_bundle,
)
from app.investment.offline_research import ResearchInputRefused, aware

from scripts.observation_runtime.chart_archive import FLAGS, _pin, _read
from scripts.observation_runtime.daily_afi_export import verify_daily_export
from scripts.observation_runtime.daily_holdout_accountability import (
    verify_holdout_continuation,
)


def _committed(reader, name, digest):
    pin = _pin(digest)
    raw = _read(reader, name)
    if PurePosixPath(name).name != pin+'.json' or hashlib.sha256(raw).hexdigest() != pin:
        raise ResearchInputRefused('Exact continuation/update content identity required')
    return raw


def _plan(reader, request_name):
    raw = _read(reader, request_name)
    if PurePosixPath(request_name).name != hashlib.sha256(raw).hexdigest()+'.json':
        raise ResearchInputRefused('Content-addressed explicit update request required')
    request = _json(raw)
    _fields(request, 'schema seed expected_seed_sha256 continuation expected_continuation_sha256 daily_export expected_daily_export_sha256 asof outcome_asof output_prefix')
    if request['schema'] != 'ATLAS_SYNTHETIC_HOLDOUT_UPDATE_REQUEST_V1':
        raise ResearchInputRefused('Explicit synthetic holdout label update request required')
    verify_holdout_continuation(bundle_root=reader.root, companion_name=request['seed'],
                                expected_companion_sha256=request['expected_seed_sha256'])
    seed = _json(_committed(reader, request['seed'], request['expected_seed_sha256']))
    initial = _json(_read(reader, seed['bundle']))
    previous_raw = _committed(reader, request['continuation'], request['expected_continuation_sha256'])
    previous = _json(previous_raw)
    asof, cutoff = aware(request['asof']), aware(request['outcome_asof'])
    if asof < aware(previous['asof']) or cutoff > asof:
        raise ResearchInputRefused('Update evidence/cutoff chronology contradiction')
    if len(previous['forecasts']) != len(initial['forecasts']):
        raise ResearchInputRefused('Update cannot change issued forecast population')
    _prepare_accountability_bundle(reader, previous)  # Existing exact heads/history, no writes.
    verify_daily_export(bundle_root=reader.root, binding_name=request['daily_export'],
                        expected_binding_sha256=request['expected_daily_export_sha256'])
    daily = _json(_committed(reader, request['daily_export'], request['expected_daily_export_sha256']))
    if aware(daily['request']['asof']) > asof:
        raise ResearchInputRefused('Update evidence cutoff predates supplied outcome archive')
    output = reader.path(request['output_prefix'], directory=True)
    forecasts = []
    for original, prior in zip(initial['forecasts'], previous['forecasts'], strict=True):
        fixed = ('artifact', 'dataset_manifest', 'dataset_records', 'source_archive')
        if (any(prior[key] != original[key] for key in fixed) or prior['append'] is not None
                or prior['history'][:len(original['history'])] != original['history']):
            raise ResearchInputRefused('Update cannot replace original forecasts or committed initial history')
        forecasts.append({**prior, 'append': {'dataset_manifest': daily['artifacts']['manifest'],
            'dataset_records': daily['artifacts']['records'], 'source_archive': None,
            'outcome_asof': cutoff.isoformat()}})
    bundle = {'schema': 'AFI_ACCOUNTABILITY_BUNDLE_V2', 'asof': asof.isoformat(), 'forecasts': forecasts}
    _prepare_accountability_bundle(reader, bundle)  # Includes all append previews before publishing.
    return raw, request, seed, bundle, output


def _signed_preview(row, record):
    """Descriptive label impact only; both inputs already passed evidence validation."""
    current = row['actual'] if row['status'] == 'RESOLVED' else None
    observation = record['observation']
    proposed = observation['value'] if record['status'] == 'RESOLVED' else None
    point = row['forecast_point']
    old_error = point-current if current is not None else None
    new_error = point-proposed if proposed is not None else None
    difference = current-proposed if current is not None and proposed is not None else None
    state = ('CURRENT_UNRESOLVED' if current is None else
             'PROPOSED_UNRESOLVED' if proposed is None else 'FINITE')
    if any(v is not None and not math.isfinite(v) for v in (old_error, new_error, difference)):
        old_error = new_error = difference = None
        state = 'UNAVAILABLE_NUMERIC_RANGE'
    return {'definition':'FORECAST_MINUS_ACTUAL', 'state':state,
            'current_actual':current, 'proposed_actual':proposed,
            'current_signed_error':old_error, 'proposed_signed_error':new_error,
            'proposed_minus_current_signed_error':difference}


def preview_holdout_update(*, bundle_root, request_name):
    """Read-only proposed label transitions; never append or advance a head."""
    reader = BundleReader(bundle_root)
    raw, request, seed, bundle, output = _plan(reader, request_name)
    asof, entries, updates = _prepare_accountability_bundle(reader, bundle)
    before = build_accountability_report(entries, evidence_asof=asof)
    cases = []
    prior_rows = {row['forecast_sha256']:row for row in before['rows']}
    for entry, (review, source, cutoff) in zip(entries, updates, strict=True):
        record = preview_outcome(entry.forecast_path, entry.forecast_review, review,
            evidence_asof=asof, outcome_asof=cutoff, history=entry.history, expected_head=entry.expected_head,
            source_review=entry.source_review, outcome_source=source)
        cases.append({'forecast_sha256':record['forecast_sha256'], 'asset_id':record['asset_id'],
                      'target_at':record['target_at'], 'current_status':prior_rows[record['forecast_sha256']]['status'], 'proposed_status':record['status'],
                      'previous_head':entry.expected_head, 'proposed_head':record['artifact_sha256'],
                      'recorded_event':record['event'], 'would_append':record['artifact_sha256'] != entry.expected_head,
                      'signed_error_impact':_signed_preview(prior_rows[record['forecast_sha256']], record)})
    after_raw, after_request, after_seed, after_bundle, after_output = _plan(reader, request_name)
    if (raw != after_raw or request != after_request or seed != after_seed or bundle != after_bundle or output != after_output):
        raise ResearchInputRefused('Update inputs changed during read-only preview')
    return {'status':'SYNTHETIC_HOLDOUT_LABEL_UPDATE_PREVIEW', 'request':request_name,
            'request_sha256':hashlib.sha256(raw).hexdigest(), 'original_counts':seed['original_counts'],
            'refused_cases':seed['refused_cases'], 'current_issued_n':before['forecast_n'],
            'current_issued_states':dict(sorted(Counter(c['current_status'] for c in cases).items())),
            'proposed_issued_states':dict(sorted(Counter(c['proposed_status'] for c in cases).items())),
            'proposed_append_n':sum(c['would_append'] for c in cases),
            'proposed_append_events':dict(sorted(Counter(c['recorded_event'] for c in cases if c['would_append']).items())), 'cases':cases,
            'new_forecasts_created':0, 'published':False, 'independent_latest_head_established':False, **FLAGS}


def update_holdout_accountability(*, bundle_root, request_name):
    reader = BundleReader(bundle_root)
    raw, request, seed, bundle, output = _plan(reader, request_name)
    text = json.dumps(bundle, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    path = publish_research_text(output, text, extension='.json')
    if path.read_bytes() != text.encode():
        raise ResearchInputRefused('Update plan read-back mismatch')
    result = run_bundle(bundle_root=bundle_root, bundle_name=request['output_prefix']+'/'+path.name,
                        output_root=output, continuation_output_prefix=request['output_prefix'])
    report = _json(_read(reader, request['output_prefix']+'/'+result['report']))
    states = Counter(row['status'] for row in report['rows'])
    if report['forecast_n'] != seed['original_counts']['issued_n']:
        raise ResearchInputRefused('Updated report changed the issued population')
    # Source graph and explicit previous heads must still match after publication.
    after_raw, after_request, after_seed, after_bundle, after_output = _plan(reader, request_name)
    if (raw != after_raw or request != after_request or seed != after_seed
            or bundle != after_bundle or output != after_output):
        raise ResearchInputRefused('Update inputs changed during publication; preserve partial evidence')
    companion = {'schema': 'ATLAS_SYNTHETIC_HOLDOUT_UPDATE_RESULT_V1',
        'request': request_name, 'seed': request['seed'], 'previous_continuation': request['continuation'],
        'continuation': request['output_prefix']+'/'+result['continuation_bundle'],
        'accountability': result, 'output_prefix': request['output_prefix'],
        'original_counts': seed['original_counts'], 'refused_cases': seed['refused_cases'],
        'current_issued_states': dict(sorted(states.items())), 'current_issued_n': report['forecast_n'],
        'new_forecasts_created': 0, 'historical_execution_attested': False,
        'independent_latest_head_established': False, **FLAGS}
    text = json.dumps(companion, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    published = publish_research_text(output, text, extension='.json')
    if published.read_bytes() != text.encode():
        raise ResearchInputRefused('Update companion read-back mismatch')
    return {'status': 'SYNTHETIC_HOLDOUT_LABEL_UPDATE_COMPLETE',
            'companion': request['output_prefix']+'/'+published.name,
            'continuation': companion['continuation'], 'original_counts': seed['original_counts'],
            'current_issued_states': companion['current_issued_states'],
            'browser_export': request['output_prefix']+'/'+result['browser_export'], **FLAGS}



def verify_holdout_update(*, bundle_root, companion_name, expected_companion_sha256):
    """Reconstruct the selected branch and exact update outputs without publishers."""
    reader = BundleReader(bundle_root)
    raw = _committed(reader, companion_name, expected_companion_sha256)
    companion = _json(raw)
    request_raw, request, seed, bundle, _output = _plan(reader, companion['request'])
    prefix = request['output_prefix']
    plan_text = json.dumps(bundle, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    plan_name = hashlib.sha256(plan_text.encode()).hexdigest()+'.json'
    if _read(reader, prefix+'/'+plan_name) != plan_text.encode():
        raise ResearchInputRefused('Published update plan differs from explicit request')
    asof, entries, updates = _prepare_accountability_bundle(reader, bundle)
    final_entries, final_specs, heads = [], [], []
    for spec, entry, (review, source, cutoff) in zip(bundle['forecasts'], entries, updates, strict=True):
        record = preview_outcome(entry.forecast_path, entry.forecast_review, review,
            evidence_asof=asof, outcome_asof=cutoff, history=entry.history, expected_head=entry.expected_head,
            source_review=entry.source_review, outcome_source=source)
        name = prefix+'/'+record['artifact_sha256']+'.json'
        if _read(reader, name) != artifact_bytes(record):
            raise ResearchInputRefused('Updated outcome differs from no-write reconstruction')
        heads.append(record['artifact_sha256'])
        changed = record['artifact_sha256'] != entry.expected_head
        history = (*entry.history, (reader.path(name), review, source)) if changed else entry.history
        final_entries.append(ForecastHistory(entry.forecast_path, entry.forecast_review, history,
                                            record['artifact_sha256'], entry.source_review))
        portable_history = list(spec['history'])
        if changed:
            portable_history.append({**{key: value for key, value in spec['append'].items() if key != 'outcome_asof'},
                                     'artifact': name})
        final_specs.append({**spec, 'history': portable_history, 'expected_head': record['artifact_sha256'], 'append': None})
    report = build_accountability_report(final_entries, evidence_asof=asof)
    continuation = {**bundle, 'forecasts': final_specs}
    texts = (
        ('report', json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+'\n', '.json'),
        ('dashboard', render_accountability_report(report), '.html'),
        ('browser_export', browser_export(report), '.json'),
        ('continuation_bundle', json.dumps(continuation, sort_keys=True, indent=2, allow_nan=False)+'\n', '.json'),
    )
    outputs = {}
    for key, text, suffix in texts:
        name = hashlib.sha256(text.encode()).hexdigest()+suffix
        if _read(reader, prefix+'/'+name) != text.encode():
            raise ResearchInputRefused('Updated report/browser/history differs from reconstruction')
        outputs[key] = name
    result = {'status': 'OFFLINE_ACCOUNTABILITY_COMPLETE',
              **{key: outputs[key] for key in ('report', 'dashboard', 'browser_export')},
              'updated_heads': heads, 'forecast_n': report['forecast_n'], 'scored_n': report['score']['scored_n'],
              'production_approved': False, 'trading_authority': False,
              'continuation_bundle': outputs['continuation_bundle']}
    expected = {'schema': 'ATLAS_SYNTHETIC_HOLDOUT_UPDATE_RESULT_V1',
        'request': companion['request'], 'seed': request['seed'], 'previous_continuation': request['continuation'],
        'continuation': prefix+'/'+result['continuation_bundle'], 'accountability': result, 'output_prefix': prefix,
        'original_counts': seed['original_counts'], 'refused_cases': seed['refused_cases'],
        'current_issued_states': dict(sorted(Counter(row['status'] for row in report['rows']).items())),
        'current_issued_n': report['forecast_n'], 'new_forecasts_created': 0, 'historical_execution_attested': False,
        'independent_latest_head_established': False, **FLAGS}
    if raw != (json.dumps(expected, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode():
        raise ResearchInputRefused('Update companion differs from reconstructed evidence')
    after_raw, after_request, after_seed, after_bundle, _after_output = _plan(reader, companion['request'])
    if (after_raw != request_raw or after_request != request or after_seed != seed or after_bundle != bundle):
        raise ResearchInputRefused('Update source graph changed during verification')
    return {'status': 'SYNTHETIC_HOLDOUT_LABEL_UPDATE_REPRODUCED', 'companion': companion_name,
            'browser_export': prefix+'/'+result['browser_export'], 'original_counts': seed['original_counts'],
            'current_issued_states': expected['current_issued_states'], **FLAGS}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Explicit synthetic label updates; no providers, refitting or runtime')
    parser.add_argument('--bundle-root', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--request')
    mode.add_argument('--verify')
    mode.add_argument('--preview')
    parser.add_argument('--expected-companion-sha256')
    args = parser.parse_args(argv)
    if (args.verify is not None) != (args.expected_companion_sha256 is not None):
        parser.error('Verification requires an exact companion pin; publication takes only an explicit request')
    try:
        if args.preview is not None:
            result = preview_holdout_update(bundle_root=args.bundle_root,request_name=args.preview)
        elif args.verify is not None:
            result = verify_holdout_update(bundle_root=args.bundle_root, companion_name=args.verify,
                expected_companion_sha256=args.expected_companion_sha256)
        else:
            result = update_holdout_accountability(bundle_root=args.bundle_root, request_name=args.request)
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        parser.exit(2, 'Holdout update refused or incomplete; preserve all source/partial evidence.\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
