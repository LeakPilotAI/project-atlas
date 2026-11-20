"""Explicit local synthetic daily dataset export and exact reconstruction."""
from __future__ import annotations

import argparse
import hashlib
import json

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _fields, _json
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused

from scripts.observation_runtime.chart_archive import FLAGS, _pin, _read
from scripts.observation_runtime.daily_afi_bridge import build_daily_dataset


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _plan(reader, request):
    required = 'schema snapshots symbol asset_class universe dataset_id version asof fixture_mode price_policy session_scope'
    if type(request) is dict and 'action_snapshots' in request:
        _fields(request, required+' action_snapshots')
    else:
        _fields(request, required)
    if request['schema'] != 'ATLAS_SYNTHETIC_DAILY_EXPORT_REQUEST_V1':
        raise ResearchInputRefused('Explicit synthetic daily export request required')
    specs = request['snapshots']
    if type(specs) is not list or not 1 <= len(specs) <= 64:
        raise ResearchInputRefused('Bounded source list required')
    snapshots = []
    total = 0
    for spec in specs:
        _fields(spec, 'file sha256 received_at')
        pin = _pin(spec['sha256'])
        if spec['file'] != pin+'.json':
            raise ResearchInputRefused('Content-addressed source name required')
        raw = _read(reader, spec['file'])
        total += len(raw)
        if total > 8_000_000 or hashlib.sha256(raw).hexdigest() != pin:
            raise ResearchInputRefused('Source commitment or combined budget refused')
        snapshots.append({'payload_bytes': raw, 'sha256': pin, 'received_at': spec['received_at']})
    action_snapshots = []
    action_specs = request.get('action_snapshots', [])
    if type(action_specs) is not list or len(action_specs) > 64:
        raise ResearchInputRefused('Bounded corporate-action source list required')
    for spec in action_specs:
        _fields(spec, 'file sha256 received_at source_id')
        pin = _pin(spec['sha256'])
        if spec['file'] != pin+'.json':
            raise ResearchInputRefused('Content-addressed corporate-action source name required')
        raw = _read(reader, spec['file'])
        total += len(raw)
        if total > 8_000_000 or hashlib.sha256(raw).hexdigest() != pin:
            raise ResearchInputRefused('Corporate-action source commitment or combined budget refused')
        action_snapshots.append({'payload_bytes': raw, 'sha256': pin, 'received_at': spec['received_at'],
                                 'source_id': spec['source_id']})
    kwargs = {key: value for key, value in request.items()
              if key not in ('schema', 'snapshots', 'action_snapshots')}
    dataset = build_daily_dataset(snapshots, action_snapshots=action_snapshots, **kwargs)
    artifacts = {}
    references = {}
    for label, raw in (('manifest', dataset.manifest_bytes), ('records', dataset.payload_bytes), ('audit', dataset.audit_bytes)):
        name = hashlib.sha256(raw).hexdigest()+'.json'
        artifacts[name] = raw
        references[label] = name
    binding = {'schema': 'ATLAS_SYNTHETIC_DAILY_EXPORT_V1', 'request': request,
               'artifacts': references, 'dataset_status': dataset.review.status,
               'history_completeness_verified': False, **FLAGS}
    raw = _encode(binding)
    if len(raw) > 2_000_000:
        raise ResearchInputRefused('Binding byte limit exceeded')
    name = hashlib.sha256(raw).hexdigest()+'.json'
    return artifacts, name, raw



def _legacy_no_actions(artifacts, current_binding):
    """Reproduce the exact original V1 serialization, never publish or erase evidence.

    This profile predates per-record source hashes and action receipt support.
    Explicit action configuration (including an empty list) cannot use it.
    """
    binding = _json(current_binding)
    if 'action_snapshots' in binding['request']:
        raise ResearchInputRefused('Action-aware requests cannot use legacy serialization')
    objects = {key: _json(artifacts[name]) for key, name in binding['artifacts'].items()}
    payload, audit, manifest = objects['records'], objects['audit'], objects['manifest']
    if payload['actions']:
        raise ResearchInputRefused('Legacy profile cannot contain corporate-action evidence')
    for row in payload['records']:
        row.pop('source_sha256')
        revision = hashlib.sha256(_encode({'asset_id': row['asset_id'],
            'observed_at': row['observed_at'], 'received_at': row['available_at'],
            'value': row['value']})+b'\n').hexdigest()
        row['record_id'] = row['revision'] = revision
    for key in ('corporate_action_snapshots', 'corporate_action_provenance',
                'corporate_action_event_n', 'repeated_corporate_action_n',
                'corporate_action_source_bytes'):
        audit.pop(key)
    payload_raw = _encode(payload)+b'\n'
    payload_pin = hashlib.sha256(payload_raw).hexdigest()
    manifest['content_sha256'] = payload_pin
    manifest_raw = _encode(manifest)+b'\n'
    audit['payload_sha256'] = payload_pin
    audit['manifest_sha256'] = hashlib.sha256(manifest_raw).hexdigest()
    old_artifacts, references = {}, {}
    for key, raw in (('records', payload_raw), ('manifest', manifest_raw), ('audit', _encode(audit)+b'\n')):
        name = hashlib.sha256(raw).hexdigest()+'.json'
        old_artifacts[name] = raw
        references[key] = name
    binding['artifacts'] = references
    raw = _encode(binding)
    return old_artifacts, hashlib.sha256(raw).hexdigest()+'.json', raw


def verify_daily_export(*, bundle_root, binding_name, expected_binding_sha256):
    pin = _pin(expected_binding_sha256)
    if binding_name != pin+'.json':
        raise ResearchInputRefused('Exact export binding pin required')
    reader = BundleReader(bundle_root)
    raw = _read(reader, binding_name)
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ResearchInputRefused('Export binding commitment mismatch')
    binding = _json(raw)
    _fields(binding, 'schema request artifacts dataset_status history_completeness_verified '+' '.join(FLAGS))
    artifacts, rebuilt_name, rebuilt = _plan(reader, binding['request'])
    if rebuilt_name != binding_name or rebuilt != raw:
        artifacts, rebuilt_name, rebuilt = _legacy_no_actions(artifacts, rebuilt)
        if rebuilt_name != binding_name or rebuilt != raw:
            raise ResearchInputRefused('Export binding does not reconstruct')
    for name, expected in artifacts.items():
        if _read(reader, name) != expected:
            raise ResearchInputRefused('Export artifact does not reconstruct')
    return {'status': 'SYNTHETIC_DAILY_EXPORT_REPRODUCED', 'binding': binding_name, **FLAGS}


def export_daily_dataset(*, bundle_root, request_name, output_root):
    reader = BundleReader(bundle_root)
    if BundleReader(output_root).root != reader.root:
        raise ResearchInputRefused('Keep retained inputs and outputs in one explicit isolated bundle')
    artifacts, name, raw = _plan(reader, _json(_read(reader, request_name)))
    # Publish success binding last. On failure preserve every partial artifact;
    # a binding alone is never success authority: verification reconstructs all.
    for content in (*artifacts.values(), raw):
        publish_research_text(output_root, content.decode('utf-8'), extension='.json')
    return verify_daily_export(bundle_root=bundle_root, binding_name=name, expected_binding_sha256=name[:-5])


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline synthetic daily AFI export; no provider or runtime')
    parser.add_argument('--bundle-root', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--request')
    mode.add_argument('--verify-binding')
    parser.add_argument('--output-root')
    parser.add_argument('--expected-binding-sha256')
    args = parser.parse_args(argv)
    if ((args.request is not None and (args.output_root is None or args.expected_binding_sha256 is not None)) or
            (args.verify_binding is not None and (args.output_root is not None or args.expected_binding_sha256 is None))):
        parser.error('Export requires output root; verification requires exact binding pin only')
    try:
        result = (export_daily_dataset(bundle_root=args.bundle_root, request_name=args.request, output_root=args.output_root)
                  if args.request is not None else verify_daily_export(bundle_root=args.bundle_root,
                      binding_name=args.verify_binding, expected_binding_sha256=args.expected_binding_sha256))
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        parser.exit(2, 'Daily export refused; preserve inputs and partial outputs.\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
