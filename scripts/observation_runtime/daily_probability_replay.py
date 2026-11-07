"""Explicit source-bound synthetic replay; no new forecast or scoring engine."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict
from datetime import timedelta

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_baselines import PROBABILITY_METHOD, canonical, fingerprint
from app.backtest.forecast_cli import (
    run_probability_holdout,
    run_probability_protocol,
    run_probability_replay,
)
from app.backtest.forecast_dashboard import (
    render_probability_holdout,
    render_probability_replay,
)
from app.backtest.forecast_dataset import _fields, _json, review_dataset
from app.backtest.forecast_replay import (
    evaluate_probability_holdout,
    freeze_probability_protocol,
    replay_baselines,
)
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused, aware

from scripts.observation_runtime.chart_archive import FLAGS, _pin, _read
from scripts.observation_runtime.daily_afi_export import verify_daily_export
from scripts.observation_runtime.daily_availability import _pinned


def _prepare(reader, raw):
    if len(raw) > 2_000_000:
        raise ResearchInputRefused('Replay request exceeds checked publication bound')
    request = _json(raw)
    _fields(request, 'schema daily_export expected_daily_export_sha256 issues expected_issues_sha256 asof outcome_asof method lookback horizon probability_method')
    if request['schema'] != 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_REPLAY_REQUEST_V1':
        raise ResearchInputRefused('Explicit synthetic daily probability replay request required')
    if (type(request['method']) is not str or request['method'] not in ('NO_CHANGE', 'ENDPOINT_DRIFT')
            or type(request['lookback']) is not int or not 2 <= request['lookback'] <= 10000
            or request['horizon'] != '1D' or request['probability_method'] != PROBABILITY_METHOD):
        raise ResearchInputRefused('Explicit supported next-close model configuration required')
    source_pin = _pin(request['expected_daily_export_sha256'])
    issue_pin = _pin(request['expected_issues_sha256'])
    if request['daily_export'] != source_pin+'.json' or request['issues'] != issue_pin+'.json':
        raise ResearchInputRefused('Exact source and issue-list identities required')
    verify_daily_export(bundle_root=reader.root, binding_name=request['daily_export'], expected_binding_sha256=source_pin)
    binding = _json(_pinned(reader, request['daily_export']))
    asof, outcome_asof = aware(request['asof']), aware(request['outcome_asof'])
    if asof < aware(binding['request']['asof']) or outcome_asof > asof:
        raise ResearchInputRefused('Replay evidence/outcome cutoff contradiction')
    issues_raw = _pinned(reader, request['issues'])
    issues = _json(issues_raw)
    if type(issues) is not list or not 1 <= len(issues) <= 128 or any(type(value) is not str for value in issues):
        raise ResearchInputRefused('Bounded explicit replay issue list required')
    arguments = {'asset_id': binding['request']['universe']['asset_id'], 'issued_times': [aware(value) for value in issues],
                 'evidence_asof': asof, 'outcome_asof': outcome_asof, 'method': request['method'],
                 'lookback': request['lookback'], 'horizon': request['horizon'], 'probability_method': request['probability_method']}
    manifest = _pinned(reader, binding['artifacts']['manifest'])
    records = _pinned(reader, binding['artifacts']['records'])
    review = review_dataset(manifest, records, asof=asof)
    report = replay_baselines(review, **arguments)
    snapshot = {**report, 'forecasts': [asdict(value) for value in report['forecasts']],
                'outcomes': [asdict(value) for value in report['outcomes']]}
    snapshot['report_sha256'] = fingerprint(snapshot)
    expected_raw = (json.dumps(snapshot, default=canonical, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    if len(expected_raw) > 2_000_000:
        raise ResearchInputRefused('Replay output exceeds checked publication bound')
    return request, binding, arguments, issues_raw, expected_raw, review


def _protocol_prepare(reader, raw):
    if len(raw) > 2_000_000:
        raise ResearchInputRefused('Probability protocol request exceeds checked bound')
    request = _json(raw)
    _fields(request, 'schema daily_export expected_daily_export_sha256 plan expected_plan_sha256 asof')
    if request['schema'] != 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_PROTOCOL_REQUEST_V1':
        raise ResearchInputRefused('Explicit source-bound probability protocol request required')
    source_pin, plan_pin = _pin(request['expected_daily_export_sha256']), _pin(request['expected_plan_sha256'])
    if request['daily_export'] != source_pin+'.json' or request['plan'] != plan_pin+'.json':
        raise ResearchInputRefused('Exact daily source and selection-plan identities required')
    verify_daily_export(bundle_root=reader.root, binding_name=request['daily_export'],
                        expected_binding_sha256=source_pin)
    binding = _json(_pinned(reader, request['daily_export']))
    evidence_asof = aware(request['asof'])
    if evidence_asof < aware(binding['request']['asof']):
        raise ResearchInputRefused('Protocol evidence cutoff precedes the daily source archive')
    plan_raw = _pinned(reader, request['plan'])
    plan = _json(plan_raw)
    _fields(plan, 'selection_issues holdout_issues frozen_at lookback embargo_seconds')
    if (any(type(plan[key]) is not list or not 1 <= len(plan[key]) <= 128
            or any(type(value) is not str for value in plan[key])
            for key in ('selection_issues', 'holdout_issues'))
            or type(plan['frozen_at']) is not str or type(plan['lookback']) is not int
            or not 2 <= plan['lookback'] <= 10000
            or type(plan['embargo_seconds']) not in (int, float)
            or plan['embargo_seconds'] < 0):
        raise ResearchInputRefused('Bounded, explicit source-bound selection and holdout plan required')
    try:
        if not math.isfinite(plan['embargo_seconds']):
            raise ResearchInputRefused('Finite selection embargo required')
        embargo = timedelta(seconds=plan['embargo_seconds'])
    except (OverflowError, ValueError) as error:
        raise ResearchInputRefused('Representable selection embargo required') from error
    selection_issues = [aware(value) for value in plan['selection_issues']]
    holdout_issues = [aware(value) for value in plan['holdout_issues']]
    frozen_at = aware(plan['frozen_at'])
    manifest = _pinned(reader, binding['artifacts']['manifest'])
    records = _pinned(reader, binding['artifacts']['records'])
    review = review_dataset(manifest, records, asof=evidence_asof)
    asset_id = binding['request']['universe']['asset_id']
    protocol = freeze_probability_protocol(
        review, asset_id=asset_id, selection_issues=selection_issues,
        holdout_issues=holdout_issues, frozen_at=frozen_at, evidence_asof=evidence_asof,
        lookback=plan['lookback'], embargo=embargo)
    protocol_raw = (json.dumps(protocol, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    if len(protocol_raw) > 2_000_000:
        raise ResearchInputRefused('Probability protocol exceeds checked publication bound')
    return request, binding, plan_raw, evidence_asof, asset_id, protocol, protocol_raw


def export_daily_probability_protocol(*, bundle_root, request_name, output_root):
    """Freeze selection only from source receipts available before the declared freeze."""
    reader = BundleReader(bundle_root)
    if BundleReader(output_root).root != reader.root:
        raise ResearchInputRefused('Retain protocol and exact daily sources in one isolated bundle')
    raw = _read(reader, request_name)
    request, binding, plan_raw, evidence_asof, asset_id, _protocol, expected_raw = _protocol_prepare(reader, raw)
    request_snapshot = publish_research_text(output_root, raw.decode('utf-8'), extension='.json')
    if request_snapshot.read_bytes() != raw:
        raise ResearchInputRefused('Probability protocol request snapshot read-back failed')
    result = run_probability_protocol(
        manifest=reader.path(binding['artifacts']['manifest']),
        records=reader.path(binding['artifacts']['records']), output_root=output_root,
        asset_id=asset_id, plan=reader.path(request['plan']), evidence_asof=evidence_asof)
    if _pinned(reader, result['protocol']) != expected_raw:
        raise ResearchInputRefused('Published protocol differs from source-bound preflight')
    if _pinned(reader, request['plan']) != plan_raw or _read(reader, request_name) != raw:
        raise ResearchInputRefused('Probability protocol inputs changed during publication')
    verify_daily_export(bundle_root=bundle_root, binding_name=request['daily_export'],
                        expected_binding_sha256=request['expected_daily_export_sha256'])
    companion = {
        'schema': 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_PROTOCOL_V1',
        'request_snapshot': request_snapshot.name,
        'expected_request_sha256': hashlib.sha256(raw).hexdigest(),
        'daily_export': request['daily_export'],
        'expected_daily_export_sha256': request['expected_daily_export_sha256'],
        'plan': request['plan'],
        'expected_plan_sha256': request['expected_plan_sha256'],
        'protocol_result': result,
        'source_authenticated': False,
        'history_completeness_verified': False,
        **FLAGS,
    }
    text = json.dumps(companion, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    path = publish_research_text(output_root, text, extension='.json')
    if path.read_bytes() != text.encode():
        raise ResearchInputRefused('Source-bound probability protocol companion read-back failed')
    return {**result, 'daily_protocol': path.name, 'request_snapshot': request_snapshot.name, **FLAGS}



def verify_daily_probability_protocol(*, bundle_root, companion_name, expected_companion_sha256):
    """Reconstruct a frozen selection commitment without evaluating or publishing holdout."""
    pin = _pin(expected_companion_sha256)
    if companion_name != pin+'.json':
        raise ResearchInputRefused('Exact caller-retained protocol companion identity required')
    reader = BundleReader(bundle_root)
    raw = _pinned(reader, companion_name)
    companion = _json(raw)
    _fields(companion, 'schema request_snapshot expected_request_sha256 daily_export expected_daily_export_sha256 plan expected_plan_sha256 protocol_result source_authenticated history_completeness_verified '+' '.join(FLAGS))
    request_pin = _pin(companion['expected_request_sha256'])
    if companion['request_snapshot'] != request_pin+'.json':
        raise ResearchInputRefused('Exact immutable protocol request snapshot required')
    request_raw = _pinned(reader, companion['request_snapshot'])
    request, _binding, plan_raw, _asof, _asset, protocol, protocol_raw = _protocol_prepare(reader, request_raw)
    protocol_name = hashlib.sha256(protocol_raw).hexdigest()+'.json'
    result = {
        'status': 'OFFLINE_SYNTHETIC_PROTOCOL_COMPLETE',
        'protocol': protocol_name,
        'protocol_sha256': protocol['protocol_sha256'],
        'holdout_n': len(protocol['holdout_issues']),
        'independently_unseen': False,
        'production_approved': False,
        'trading_authority': False,
    }
    expected = {
        'schema': 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_PROTOCOL_V1',
        'request_snapshot': request_pin+'.json',
        'expected_request_sha256': request_pin,
        'daily_export': request['daily_export'],
        'expected_daily_export_sha256': request['expected_daily_export_sha256'],
        'plan': request['plan'],
        'expected_plan_sha256': request['expected_plan_sha256'],
        'protocol_result': result,
        'source_authenticated': False,
        'history_completeness_verified': False,
        **FLAGS,
    }
    if (raw != (json.dumps(expected, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
            or _pinned(reader, protocol_name) != protocol_raw):
        raise ResearchInputRefused('Protocol companion differs from reconstructed source evidence')
    if _pinned(reader, request['plan']) != plan_raw:
        raise ResearchInputRefused('Protocol plan changed during verification')
    verify_daily_export(bundle_root=bundle_root, binding_name=request['daily_export'],
                        expected_binding_sha256=request['expected_daily_export_sha256'])
    return {'status': 'SYNTHETIC_DAILY_PROBABILITY_PROTOCOL_REPRODUCED',
            'companion': companion_name, 'protocol_sha256': protocol['protocol_sha256'],
            'holdout_n': result['holdout_n'], 'independently_unseen': False,
            'history_completeness_verified': False, **FLAGS}


def _holdout_prepare(reader, raw):
    if len(raw) > 2_000_000:
        raise ResearchInputRefused('Probability holdout request exceeds checked bound')
    request = _json(raw)
    _fields(request, 'schema daily_export expected_daily_export_sha256 daily_protocol expected_daily_protocol_sha256 evidence_asof outcome_asof')
    if request['schema'] != 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_HOLDOUT_REQUEST_V1':
        raise ResearchInputRefused('Explicit source-bound probability holdout request required')
    source_pin, protocol_pin = (_pin(request['expected_daily_export_sha256']),
                                _pin(request['expected_daily_protocol_sha256']))
    if request['daily_export'] != source_pin+'.json' or request['daily_protocol'] != protocol_pin+'.json':
        raise ResearchInputRefused('Exact daily source and frozen-protocol identities required')
    verify_daily_export(bundle_root=reader.root, binding_name=request['daily_export'],
                        expected_binding_sha256=source_pin)
    binding = _json(_pinned(reader, request['daily_export']))
    evidence_asof, outcome_asof = aware(request['evidence_asof']), aware(request['outcome_asof'])
    if evidence_asof < aware(binding['request']['asof']) or outcome_asof > evidence_asof:
        raise ResearchInputRefused('Holdout source/evaluation cutoff contradiction')
    protocol_companion_raw = _pinned(reader, request['daily_protocol'])
    companion = _json(protocol_companion_raw)
    _fields(companion, 'schema request_snapshot expected_request_sha256 daily_export expected_daily_export_sha256 plan expected_plan_sha256 protocol_result source_authenticated history_completeness_verified '+' '.join(FLAGS))
    protocol_result = companion['protocol_result']
    if (companion['schema'] != 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_PROTOCOL_V1'
            or companion['daily_export'] != request['daily_export']
            or companion['expected_daily_export_sha256'] != source_pin
            or type(protocol_result) is not dict
            or protocol_result.get('status') != 'OFFLINE_SYNTHETIC_PROTOCOL_COMPLETE'
            or any(companion[key] is not False for key in ('source_authenticated', 'history_completeness_verified'))
            or any(companion[key] is not value for key, value in FLAGS.items())):
        raise ResearchInputRefused('Frozen protocol belongs to different or unsupported source evidence')
    protocol_request_pin = _pin(companion['expected_request_sha256'])
    if companion['request_snapshot'] != protocol_request_pin+'.json':
        raise ResearchInputRefused('Frozen protocol request snapshot identity mismatch')
    protocol_request_raw = _pinned(reader, companion['request_snapshot'])
    (protocol_request, protocol_binding, plan_raw, protocol_asof, _protocol_asset,
     expected_protocol, expected_protocol_raw) = _protocol_prepare(reader, protocol_request_raw)
    if evidence_asof < protocol_asof:
        raise ResearchInputRefused('Holdout evidence cutoff predates the frozen protocol evidence')
    if (protocol_request['daily_export'] != request['daily_export']
            or protocol_request['expected_daily_export_sha256'] != source_pin
            or companion['daily_export'] != protocol_request['daily_export']
            or companion['expected_daily_export_sha256'] != protocol_request['expected_daily_export_sha256']
            or companion['plan'] != protocol_request['plan']
            or companion['expected_plan_sha256'] != protocol_request['expected_plan_sha256']
            or protocol_binding != binding):
        raise ResearchInputRefused('Frozen protocol request is foreign to the holdout source')
    expected_protocol_name = hashlib.sha256(expected_protocol_raw).hexdigest()+'.json'
    expected_protocol_result = {
        'status': 'OFFLINE_SYNTHETIC_PROTOCOL_COMPLETE',
        'protocol': expected_protocol_name,
        'protocol_sha256': expected_protocol['protocol_sha256'],
        'holdout_n': len(expected_protocol['holdout_issues']),
        'independently_unseen': False,
        'production_approved': False,
        'trading_authority': False,
    }
    if protocol_result != expected_protocol_result:
        raise ResearchInputRefused('Frozen protocol result differs from reconstructed source request')
    protocol_name = protocol_result.get('protocol')
    protocol_sha = protocol_result.get('protocol_sha256')
    if type(protocol_name) is not str or type(protocol_sha) is not str:
        raise ResearchInputRefused('Missing frozen protocol identity')
    protocol_raw = _pinned(reader, protocol_name)
    protocol = _json(protocol_raw)
    if (protocol_name != expected_protocol_name or protocol_raw != expected_protocol_raw
            or type(protocol) is not dict or protocol.get('schema') != 'AFI_PROBABILITY_PROTOCOL_V1'
            or protocol.get('protocol_sha256') != protocol_sha
            or protocol_result.get('protocol_sha256') != protocol_sha
            or protocol_result.get('independently_unseen') is not False
            or protocol_result.get('production_approved') is not False
            or protocol_result.get('trading_authority') is not False):
        raise ResearchInputRefused('Stale, substituted or foreign probability protocol')
    manifest = _pinned(reader, binding['artifacts']['manifest'])
    records = _pinned(reader, binding['artifacts']['records'])
    review = review_dataset(manifest, records, asof=evidence_asof)
    evaluated = evaluate_probability_holdout(
        review, protocol, expected_protocol_sha256=protocol_sha,
        evidence_asof=evidence_asof, outcome_asof=outcome_asof)
    if evaluated['protocol'] != protocol:
        raise ResearchInputRefused('Holdout evaluator reconstructed a different protocol')
    replay = evaluated['replay']
    snapshot = {**evaluated, 'replay': {**replay, 'forecasts': [asdict(value) for value in replay['forecasts']],
                                      'outcomes': [asdict(value) for value in replay['outcomes']]}}
    snapshot['report_sha256'] = fingerprint(snapshot)
    report_raw = (json.dumps(snapshot, default=canonical, sort_keys=True, separators=(',', ':'),
                             allow_nan=False)+'\n').encode()
    html_raw = render_probability_holdout(
        review, protocol, expected_protocol_sha256=protocol_sha,
        evidence_asof=evidence_asof, outcome_asof=outcome_asof).encode()
    if len(report_raw) > 2_000_000 or len(html_raw) > 2_000_000:
        raise ResearchInputRefused('Probability holdout outputs exceed checked publication bound')
    return (request, binding, protocol_companion_raw, protocol_request_raw, plan_raw,
            protocol_name, protocol_raw, protocol_sha, evidence_asof, outcome_asof,
            binding['request']['universe']['asset_id'], report_raw, html_raw)


def export_daily_probability_holdout(*, bundle_root, request_name, output_root):
    """Evaluate the exact pinned protocol against its bound daily receipt archive."""
    reader = BundleReader(bundle_root)
    if BundleReader(output_root).root != reader.root:
        raise ResearchInputRefused('Retain holdout and exact daily sources in one isolated bundle')
    raw = _read(reader, request_name)
    (request, binding, protocol_companion_raw, protocol_request_raw, plan_raw, protocol_name,
     protocol_raw, protocol_sha, evidence_asof, outcome_asof, asset_id, expected_report,
     expected_html) = _holdout_prepare(reader, raw)
    request_snapshot = publish_research_text(output_root, raw.decode('utf-8'), extension='.json')
    if request_snapshot.read_bytes() != raw:
        raise ResearchInputRefused('Probability holdout request snapshot read-back failed')
    result = run_probability_holdout(
        manifest=reader.path(binding['artifacts']['manifest']),
        records=reader.path(binding['artifacts']['records']), output_root=output_root,
        asset_id=asset_id, protocol_path=reader.path(protocol_name),
        expected_protocol_sha256=protocol_sha, evidence_asof=evidence_asof,
        outcome_asof=outcome_asof)
    if (_pinned(reader, result['report']) != expected_report
            or _read(reader, result['dashboard']) != expected_html
            or result['dashboard'] != hashlib.sha256(expected_html).hexdigest()+'.html'):
        raise ResearchInputRefused('Published holdout differs from source-bound preflight')
    if (_read(reader, request_name) != raw
            or _pinned(reader, request['daily_protocol']) != protocol_companion_raw
            or _pinned(reader, json.loads(protocol_companion_raw)['request_snapshot']) != protocol_request_raw
            or _pinned(reader, json.loads(protocol_companion_raw)['plan']) != plan_raw
            or _pinned(reader, protocol_name) != protocol_raw):
        raise ResearchInputRefused('Probability holdout inputs changed during publication')
    verify_daily_export(bundle_root=bundle_root, binding_name=request['daily_export'],
                        expected_binding_sha256=request['expected_daily_export_sha256'])
    companion = {
        'schema': 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_HOLDOUT_V1',
        'request_snapshot': request_snapshot.name,
        'expected_request_sha256': hashlib.sha256(raw).hexdigest(),
        'daily_export': request['daily_export'],
        'expected_daily_export_sha256': request['expected_daily_export_sha256'],
        'daily_protocol': request['daily_protocol'],
        'expected_daily_protocol_sha256': request['expected_daily_protocol_sha256'],
        'protocol': protocol_name,
        'protocol_sha256': protocol_sha,
        'holdout_result': result,
        'independently_unseen': False,
        'calibration_established': False,
        'predictive_skill_established': False,
        **FLAGS,
    }
    text = json.dumps(companion, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    path = publish_research_text(output_root, text, extension='.json')
    if path.read_bytes() != text.encode():
        raise ResearchInputRefused('Source-bound probability holdout companion read-back failed')
    return {**result, 'daily_holdout': path.name, 'request_snapshot': request_snapshot.name,
            'independently_unseen': False, 'calibration_established': False,
            'predictive_skill_established': False, **FLAGS}


def verify_daily_probability_holdout(*, bundle_root, companion_name, expected_companion_sha256):
    """Reconstruct the frozen protocol, source, holdout report and dashboard without writes."""
    pin = _pin(expected_companion_sha256)
    if companion_name != pin+'.json':
        raise ResearchInputRefused('Exact caller-retained holdout companion identity required')
    reader = BundleReader(bundle_root)
    raw = _pinned(reader, companion_name)
    companion = _json(raw)
    _fields(companion, 'schema request_snapshot expected_request_sha256 daily_export expected_daily_export_sha256 daily_protocol expected_daily_protocol_sha256 protocol protocol_sha256 holdout_result independently_unseen calibration_established predictive_skill_established '+' '.join(FLAGS))
    request_pin = _pin(companion['expected_request_sha256'])
    if companion['request_snapshot'] != request_pin+'.json':
        raise ResearchInputRefused('Exact immutable holdout request snapshot required')
    request_raw = _pinned(reader, companion['request_snapshot'])
    (request, _binding, _protocol_companion_raw, _protocol_request_raw, _plan_raw,
     protocol_name, _protocol_raw, protocol_sha, _evidence_asof, _outcome_asof,
     _asset_id, report_raw, html_raw) = _holdout_prepare(reader, request_raw)
    report_name = hashlib.sha256(report_raw).hexdigest()+'.json'
    dashboard_name = hashlib.sha256(html_raw).hexdigest()+'.html'
    report = _json(report_raw)
    replay = report['replay']
    result = {
        'status': 'OFFLINE_SYNTHETIC_HOLDOUT_COMPLETE',
        'report': report_name,
        'dashboard': dashboard_name,
        'protocol_sha256': protocol_sha,
        'requested_n': replay['requested_n'],
        'resolved_n': replay['resolved_n'],
        'refused_n': replay['refused_n'],
        'retuning_allowed': False,
        'independently_unseen': False,
        'calibration_established': False,
        'production_approved': False,
        'trading_authority': False,
        'predictive_skill_established': False,
    }
    expected = {
        'schema': 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_HOLDOUT_V1',
        'request_snapshot': request_pin+'.json',
        'expected_request_sha256': request_pin,
        'daily_export': request['daily_export'],
        'expected_daily_export_sha256': request['expected_daily_export_sha256'],
        'daily_protocol': request['daily_protocol'],
        'expected_daily_protocol_sha256': request['expected_daily_protocol_sha256'],
        'protocol': protocol_name,
        'protocol_sha256': protocol_sha,
        'holdout_result': result,
        'independently_unseen': False,
        'calibration_established': False,
        'predictive_skill_established': False,
        **FLAGS,
    }
    if raw != (json.dumps(expected, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode():
        raise ResearchInputRefused('Holdout companion differs from reconstructed source evidence')
    if (_pinned(reader, report_name) != report_raw
            or _read(reader, dashboard_name) != html_raw):
        raise ResearchInputRefused('Holdout outputs differ from reconstructed source evidence')
    verify_daily_export(bundle_root=bundle_root, binding_name=request['daily_export'],
                        expected_binding_sha256=request['expected_daily_export_sha256'])
    return {
        'status': 'SYNTHETIC_DAILY_PROBABILITY_HOLDOUT_REPRODUCED',
        'companion': companion_name,
        'requested_n': result['requested_n'],
        'resolved_n': result['resolved_n'],
        'refused_n': result['refused_n'],
        'history_completeness_verified': False,
        'independently_unseen': False,
        'calibration_established': False,
        'predictive_skill_established': False,
        **FLAGS,
    }



def diagnose_daily_probability_holdout(*, bundle_root, companion_name, expected_companion_sha256):
    """Read-only case coverage and refusal explanations from a reconstructed holdout."""
    verify_daily_probability_holdout(bundle_root=bundle_root, companion_name=companion_name,
                                    expected_companion_sha256=expected_companion_sha256)
    reader = BundleReader(bundle_root)
    companion = _json(_pinned(reader, companion_name))
    report = _json(_pinned(reader, companion['holdout_result']['report']))
    replay = report['replay']
    definitions = {
        'RESOLVED': 'A target label is supplied and available at the explicit outcome cutoff.',
        'REFUSED': 'No forecast was issued; the exact fitting or source refusal is retained.',
        'PENDING_TARGET': 'The forecast target is after the outcome cutoff; no outcome is scored.',
        'PENDING_PUBLICATION': 'A target record exists in the supplied archive but was unavailable at the outcome cutoff.',
        'MISSING_OUTCOME': 'The target has elapsed but no target record is supplied; this does not prove a missed market event.',
    }
    counts = Counter(case['status'] for case in replay['cases'])
    if set(counts)-set(definitions):
        raise ResearchInputRefused('Unknown holdout case state')
    expected = {
        'requested_n': len(replay['cases']), 'refused_n': counts['REFUSED'],
        'issued_n': len(replay['cases'])-counts['REFUSED'], 'resolved_n': counts['RESOLVED'],
        'pending_target_n': counts['PENDING_TARGET'], 'pending_publication_n': counts['PENDING_PUBLICATION'],
        'missing_outcome_n': counts['MISSING_OUTCOME'],
        'unscored_n': counts['PENDING_TARGET']+counts['PENDING_PUBLICATION']+counts['MISSING_OUTCOME'],
    }
    if any(replay[key] != value for key, value in expected.items()):
        raise ResearchInputRefused('Holdout case denominators do not reconcile')
    reasons = Counter(case['reason'] for case in replay['cases'] if case['status'] == 'REFUSED')
    result = {
        'schema': 'ATLAS_SYNTHETIC_DAILY_HOLDOUT_DIAGNOSTICS_V1',
        'companion': companion_name, 'report': companion['holdout_result']['report'],
        'daily_export': companion['daily_export'], 'protocol_sha256': companion['protocol_sha256'],
        'asset_id': replay['asset_id'], 'method': replay['method'], 'lookback': replay['lookback'],
        'evidence_asof': replay['asof'], 'outcome_asof': replay['outcome_asof'],
        'counts': expected,
        'states': [{'status': state, 'n': counts[state], 'meaning': meaning}
                   for state, meaning in definitions.items()],
        'refusal_reasons': [{'reason': reason, 'n': n} for reason, n in sorted(reasons.items())],
        'cases': replay['cases'],
        'sample_status': replay['probability_diagnostics']['status'],
        'distinct_resolved_targets': replay['probability_diagnostics']['distinct_target_n'],
        'denominator_policy': 'Refused and pending cases remain requested; only resolved labels are scored.',
        'independently_unseen': False, 'calibration_established': False,
        'predictive_skill_established': False, 'history_completeness_verified': False,
        **FLAGS,
    }
    # Recheck source graph after constructing the derived diagnostic; never repair it.
    verify_daily_probability_holdout(bundle_root=bundle_root, companion_name=companion_name,
                                    expected_companion_sha256=expected_companion_sha256)
    return result


def export_daily_probability_replay(*, bundle_root, request_name, output_root):
    reader = BundleReader(bundle_root)
    if BundleReader(output_root).root != reader.root:
        raise ResearchInputRefused('Retain replay and exact sources in one isolated bundle')
    raw = _read(reader, request_name)
    request, binding, arguments, issues_raw, expected_raw, _review = _prepare(reader, raw)
    request_snapshot = publish_research_text(output_root, raw.decode('utf-8'), extension='.json')
    if request_snapshot.read_bytes() != raw:
        raise ResearchInputRefused('Replay request snapshot read-back failed')
    result = run_probability_replay(manifest=reader.path(binding['artifacts']['manifest']),
                                    records=reader.path(binding['artifacts']['records']), output_root=output_root,
                                    issues=reader.path(request['issues']),
                                    **{key: value for key, value in arguments.items() if key != 'issued_times'})
    if _pinned(reader, result['report']) != expected_raw:
        raise ResearchInputRefused('Published replay differs from source-bound preflight')
    if _pinned(reader, request['issues']) != issues_raw:
        raise ResearchInputRefused('Replay issue list changed during publication')
    verify_daily_export(bundle_root=bundle_root, binding_name=request['daily_export'],
                        expected_binding_sha256=request['expected_daily_export_sha256'])
    companion = {'schema': 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_REPLAY_V1',
                 'request_snapshot': request_snapshot.name, 'expected_request_sha256': hashlib.sha256(raw).hexdigest(),
                 'daily_export': request['daily_export'], 'expected_daily_export_sha256': request['expected_daily_export_sha256'],
                 'issues': request['issues'], 'expected_issues_sha256': request['expected_issues_sha256'],
                 'replay_result': result, 'independently_unseen': False, 'history_completeness_verified': False, **FLAGS}
    text = json.dumps(companion, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n'
    path = publish_research_text(output_root, text, extension='.json')
    if path.read_bytes() != text.encode():
        raise ResearchInputRefused('Source-bound replay companion read-back failed')
    return {**result, 'daily_companion': path.name, 'request_snapshot': request_snapshot.name, **FLAGS}


def verify_daily_probability_replay(*, bundle_root, companion_name, expected_companion_sha256):
    """Refit supplied evidence and compare outputs without invoking publication."""
    pin = _pin(expected_companion_sha256)
    if companion_name != pin+'.json':
        raise ResearchInputRefused('Exact caller-retained replay companion identity required')
    reader = BundleReader(bundle_root)
    raw = _pinned(reader, companion_name)
    companion = _json(raw)
    _fields(companion, 'schema request_snapshot expected_request_sha256 daily_export expected_daily_export_sha256 issues expected_issues_sha256 replay_result independently_unseen history_completeness_verified '+' '.join(FLAGS))
    request_pin = _pin(companion['expected_request_sha256'])
    if companion['request_snapshot'] != request_pin+'.json':
        raise ResearchInputRefused('Exact immutable request snapshot required')
    request_raw = _pinned(reader, companion['request_snapshot'])
    request, _binding, arguments, issues_raw, report_raw, review = _prepare(reader, request_raw)
    report_name = hashlib.sha256(report_raw).hexdigest()+'.json'
    rendered = render_probability_replay(review, **arguments).encode()
    dashboard_name = hashlib.sha256(rendered).hexdigest()+'.html'
    snapshot = _json(report_raw)
    result = {'status': 'OFFLINE_SYNTHETIC_REPLAY_COMPLETE', 'report': report_name, 'dashboard': dashboard_name,
              **{key: snapshot[key] for key in ('requested_n', 'issued_n', 'refused_n', 'resolved_n', 'unscored_n',
                                               'pending_target_n', 'pending_publication_n', 'missing_outcome_n')},
              'production_approved': False, 'trading_authority': False,
              'calibration_established': False, 'predictive_skill_established': False}
    expected = {'schema': 'ATLAS_SYNTHETIC_DAILY_PROBABILITY_REPLAY_V1',
                'request_snapshot': request_pin+'.json', 'expected_request_sha256': request_pin,
                'daily_export': request['daily_export'], 'expected_daily_export_sha256': request['expected_daily_export_sha256'],
                'issues': request['issues'], 'expected_issues_sha256': request['expected_issues_sha256'],
                'replay_result': result, 'independently_unseen': False, 'history_completeness_verified': False, **FLAGS}
    if raw != (json.dumps(expected, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode():
        raise ResearchInputRefused('Replay companion differs from reconstructed source evidence')
    if _pinned(reader, report_name) != report_raw or _read(reader, dashboard_name) != rendered:
        raise ResearchInputRefused('Replay output differs from reconstructed source evidence')
    if _pinned(reader, request['issues']) != issues_raw:
        raise ResearchInputRefused('Replay issues changed during verification')
    verify_daily_export(bundle_root=bundle_root, binding_name=request['daily_export'],
                        expected_binding_sha256=request['expected_daily_export_sha256'])
    return {'status': 'SYNTHETIC_SOURCE_DAILY_REPLAY_REPRODUCED', 'companion': companion_name,
            **{key: result[key] for key in ('requested_n', 'issued_n', 'refused_n', 'resolved_n', 'unscored_n')},
            'history_completeness_verified': False, 'independently_unseen': False, **FLAGS}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Source-bound synthetic daily probability replay; no provider or runtime')
    parser.add_argument('--bundle-root', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--request')
    mode.add_argument('--freeze-protocol')
    mode.add_argument('--evaluate-holdout')
    mode.add_argument('--verify-holdout')
    mode.add_argument('--verify-protocol')
    mode.add_argument('--diagnose-holdout')
    mode.add_argument('--verify-companion')
    parser.add_argument('--expected-companion-sha256')
    parser.add_argument('--output-root')
    args = parser.parse_args(argv)
    publishing = args.request is not None or args.freeze_protocol is not None or args.evaluate_holdout is not None
    verifying = args.verify_holdout is not None or args.verify_companion is not None or args.verify_protocol is not None or args.diagnose_holdout is not None
    if ((publishing and (args.output_root is None or args.expected_companion_sha256 is not None)) or
            (verifying and (args.output_root is not None or args.expected_companion_sha256 is None))):
        parser.error('Export/evaluation requires output root; verification requires only an exact companion pin')
    try:
        if args.request is not None:
            result = export_daily_probability_replay(bundle_root=args.bundle_root, request_name=args.request, output_root=args.output_root)
        elif args.freeze_protocol is not None:
            result = export_daily_probability_protocol(bundle_root=args.bundle_root, request_name=args.freeze_protocol, output_root=args.output_root)
        elif args.evaluate_holdout is not None:
            result = export_daily_probability_holdout(bundle_root=args.bundle_root, request_name=args.evaluate_holdout, output_root=args.output_root)
        elif args.diagnose_holdout is not None:
            result = diagnose_daily_probability_holdout(bundle_root=args.bundle_root, companion_name=args.diagnose_holdout,
                expected_companion_sha256=args.expected_companion_sha256)
        elif args.verify_protocol is not None:
            result = verify_daily_probability_protocol(bundle_root=args.bundle_root, companion_name=args.verify_protocol,
                expected_companion_sha256=args.expected_companion_sha256)
        elif args.verify_holdout is not None:
            result = verify_daily_probability_holdout(bundle_root=args.bundle_root, companion_name=args.verify_holdout,
                expected_companion_sha256=args.expected_companion_sha256)
        else:
            result = verify_daily_probability_replay(bundle_root=args.bundle_root, companion_name=args.verify_companion,
                expected_companion_sha256=args.expected_companion_sha256)
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        parser.exit(2, 'Source-bound daily replay refused or incomplete; preserve inputs and partial evidence.\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
