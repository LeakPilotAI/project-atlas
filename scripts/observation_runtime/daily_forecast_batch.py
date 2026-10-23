"""Verified synthetic daily exports into the existing offline forecast batch."""
from __future__ import annotations

import argparse
import hashlib
import json

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _fields, _json
from app.backtest.forecast_report import (
    BundleReader,
    _prepare_forecast_batch,
    _verified_batch,
    run_forecast_batch,
)
from app.investment.offline_research import ResearchInputRefused

from scripts.observation_runtime.chart_archive import FLAGS, _pin, _read
from scripts.observation_runtime.daily_afi_export import verify_daily_export


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _prepare(reader, request):
    _fields(request, 'schema asof forecasts')
    if request['schema'] != 'ATLAS_SYNTHETIC_DAILY_FORECAST_REQUEST_V1':
        raise ResearchInputRefused('Explicit synthetic daily forecast request required')
    specs = request['forecasts']
    if type(specs) is not list or not 1 <= len(specs) <= 32:
        raise ResearchInputRefused('Bounded daily forecast list required')
    bindings, forecasts, committed = {}, [], {}
    for spec in specs:
        _fields(spec, 'daily_export expected_daily_export_sha256 asset_id issued_at method lookback horizon interval probability_method')
        pin = _pin(spec['expected_daily_export_sha256'])
        if spec['daily_export'] != pin+'.json':
            raise ResearchInputRefused('Exact daily export binding required')
        if pin not in bindings:
            if len(bindings) >= 8:
                raise ResearchInputRefused('At most eight distinct daily exports per batch')
            verify_daily_export(bundle_root=reader.root, binding_name=spec['daily_export'], expected_binding_sha256=pin)
            binding = _json(_read(reader, spec['daily_export']))
            # Recheck the bytes actually used, not just a preceding observation.
            if hashlib.sha256(_encoded(binding)).hexdigest() != pin:
                raise ResearchInputRefused('Daily binding changed after verification')
            for artifact_name in binding['artifacts'].values():
                artifact_raw = _read(reader, artifact_name)
                if artifact_name != hashlib.sha256(artifact_raw).hexdigest()+'.json':
                    raise ResearchInputRefused('Daily artifact changed after verification')
                committed[artifact_name] = artifact_raw
            bindings[pin] = binding
        binding = bindings[pin]
        asset = binding['request']['universe']['asset_id']
        if asset != spec['asset_id']:
            raise ResearchInputRefused('Forecast asset differs from verified daily universe')
        forecasts.append({key: spec[key] for key in ('asset_id', 'issued_at', 'method', 'lookback', 'horizon', 'interval', 'probability_method')} |
                         {'dataset_manifest': binding['artifacts']['manifest'],
                          'dataset_records': binding['artifacts']['records'], 'source_archive': None})
    plan = {'schema': 'AFI_FORECAST_BATCH_V1', 'asof': request['asof'], 'forecasts': forecasts}
    raw = _encoded(plan)
    name = hashlib.sha256(raw).hexdigest()+'.json'

    class PlannedReader:
        # Validate the entire batch before publishing even its plan. Existing
        # dataset/interval/source reads retain the shared reader's byte budget.
        def read(self, key):
            if key == name:
                return raw
            return committed[key] if key in committed else reader.read(key)

        dataset = BundleReader.dataset
        source = BundleReader.source

    _prepare_forecast_batch(PlannedReader(), name)
    return plan, name, raw


def prepare_daily_forecast_request(*, bundle_root, selection_name, output_root):
    """Expand explicit source groups; preflight without publishing forecasts."""
    reader = BundleReader(bundle_root)
    if BundleReader(output_root).root != reader.root:
        raise ResearchInputRefused('Retain selection and request in the same explicit isolated bundle')
    selection_raw = _read(reader, selection_name)
    selection = _json(selection_raw)
    _fields(selection, 'schema asof groups')
    if selection['schema'] != 'ATLAS_SYNTHETIC_DAILY_FORECAST_SELECTION_V1':
        raise ResearchInputRefused('Explicit grouped daily forecast selection required')
    groups = selection['groups']
    if type(groups) is not list or not 1 <= len(groups) <= 8:
        raise ResearchInputRefused('Bounded explicit source groups required')
    forecasts = []
    for group in groups:
        _fields(group, 'daily_export expected_daily_export_sha256 asset_id forecasts')
        if type(group['forecasts']) is not list or not 1 <= len(group['forecasts']) <= 32:
            raise ResearchInputRefused('Bounded explicit model choices required')
        for model in group['forecasts']:
            _fields(model, 'issued_at method lookback horizon interval probability_method')
            forecasts.append({key:group[key] for key in ('daily_export','expected_daily_export_sha256','asset_id')} | model)
            if len(forecasts) > 32:
                raise ResearchInputRefused('At most 32 explicit forecasts per request')
    request = {'schema':'ATLAS_SYNTHETIC_DAILY_FORECAST_REQUEST_V1', 'asof':selection['asof'], 'forecasts':forecasts}
    _prepare(reader, request)
    raw = _encoded(request)
    if _read(reader, selection_name) != selection_raw:
        raise ResearchInputRefused('Selection changed during preparation')
    path = publish_research_text(output_root, raw.decode(), extension='.json')
    if path.read_bytes() != raw or path.name != hashlib.sha256(raw).hexdigest()+'.json':
        raise ResearchInputRefused('Prepared request read-back mismatch')
    _prepare(reader, request)
    if _read(reader, selection_name) != selection_raw:
        raise ResearchInputRefused('Selection changed across request publication')
    return {'status':'OFFLINE_DAILY_REQUEST_PREPARED', 'request':path.name,
            'request_sha256':hashlib.sha256(raw).hexdigest(), 'selection_sha256':hashlib.sha256(selection_raw).hexdigest(),
            'planned_forecast_n':len(forecasts), 'forecasts_published':False, 'source_authenticated':False, **FLAGS}


def run_daily_forecast_batch(*, bundle_root, request_name, output_root):
    reader = BundleReader(bundle_root)
    if BundleReader(output_root).root != reader.root:
        raise ResearchInputRefused('Retain daily source and forecasts in the same explicit isolated bundle')
    request = _json(_read(reader, request_name))
    plan, name, raw = _prepare(reader, request)
    path = publish_research_text(output_root, raw.decode(), extension='.json')
    if path.name != name or path.read_bytes() != raw:
        raise ResearchInputRefused('Daily forecast plan read-back mismatch')
    result = run_forecast_batch(bundle_root=bundle_root, batch_name=name, output_root=output_root)
    # Detect ordinary input changes across publication, without claiming
    # exclusion of hostile same-account or privileged concurrent writers.
    if _read(reader, name) != raw:
        raise ResearchInputRefused('Daily forecast plan changed during publication')
    _prepare(reader, request)
    # Reuse the batch's checked forecasts/dashboard/index and retain exact input
    # settings. This receipt is not external archive or runtime attestation.
    receipt = {'schema': 'ATLAS_SYNTHETIC_DAILY_FORECAST_RESULT_V1', 'request': request,
               'batch_plan': name, 'batch_plan_sha256': hashlib.sha256(_encoded(plan)).hexdigest(),
               'batch_result': result, 'source_authenticated': False,
               'history_completeness_verified': False, **FLAGS}
    receipt_raw = _encoded(receipt)
    receipt_path = publish_research_text(output_root, receipt_raw.decode(), extension='.json')
    if receipt_path.read_bytes() != receipt_raw:
        raise ResearchInputRefused('Daily forecast receipt read-back mismatch')
    return {**result, 'daily_receipt': receipt_path.name, 'daily_batch_plan': name, **FLAGS}


def verify_daily_forecast_receipt(*, bundle_root, receipt_name, expected_receipt_sha256):
    """Reconstruct supplied inputs and outputs without acknowledging publication."""
    pin = _pin(expected_receipt_sha256)
    if receipt_name != pin+'.json':
        raise ResearchInputRefused('Caller-retained exact daily receipt identity required')
    reader = BundleReader(bundle_root)
    raw = _read(reader, receipt_name)
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ResearchInputRefused('Daily forecast receipt commitment mismatch')
    receipt = _json(raw)
    _fields(receipt, 'schema request batch_plan batch_plan_sha256 batch_result history_completeness_verified '+' '.join(FLAGS))
    plan, plan_name, plan_raw = _prepare(reader, receipt['request'])
    if receipt['batch_plan'] != plan_name or _read(reader, plan_name) != plan_raw:
        raise ResearchInputRefused('Daily receipt plan does not reconstruct')
    result = receipt['batch_result']
    _fields(result, 'status index dashboard forecast_n unique_asset_n production_approved trading_authority predictive_skill_established')
    if type(result['index']) is not str:
        raise ResearchInputRefused('Exact batch index identity required')
    index_pin = _pin(result['index'][:-5])
    if result['index'] != index_pin+'.json':
        raise ResearchInputRefused('Exact batch index identity required')
    _, _, _, ledger, _, _, index = _verified_batch(reader, {
        'batch_plan': plan_name, 'batch_index': result['index'], 'expected_index_sha256': index_pin,
    }, reproduce_dashboard=True)
    reconstructed_result = {'status': 'OFFLINE_FORECAST_BATCH_COMPLETE', 'index': result['index'],
                            'dashboard': index['dashboard'], 'forecast_n': len(ledger),
                            'unique_asset_n': len({item['asset_id'] for item in ledger}),
                            'production_approved': False, 'trading_authority': False, 'predictive_skill_established': False}
    expected = {'schema': 'ATLAS_SYNTHETIC_DAILY_FORECAST_RESULT_V1', 'request': receipt['request'],
                'batch_plan': plan_name, 'batch_plan_sha256': hashlib.sha256(_encoded(plan)).hexdigest(),
                'batch_result': reconstructed_result, 'history_completeness_verified': False, **FLAGS}
    if raw != _encoded(expected):
        raise ResearchInputRefused('Daily receipt contradicts reconstructed evidence')
    return {'status': 'SYNTHETIC_DAILY_FORECAST_RECEIPT_REPRODUCED', 'receipt': receipt_name,
            'forecast_n': len(ledger), 'unique_asset_n': reconstructed_result['unique_asset_n'],
            'source_authenticated': False, 'history_completeness_verified': False, **FLAGS}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Explicit synthetic daily bundles to offline forecast dashboard')
    parser.add_argument('--bundle-root', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--request')
    mode.add_argument('--verify-receipt')
    mode.add_argument('--prepare-selection')
    parser.add_argument('--output-root')
    parser.add_argument('--expected-receipt-sha256')
    args = parser.parse_args(argv)
    if (((args.request is not None or args.prepare_selection is not None) and (args.output_root is None or args.expected_receipt_sha256 is not None)) or
            (args.verify_receipt is not None and (args.output_root is not None or args.expected_receipt_sha256 is None))):
        parser.error('Publication requires output root; verification requires only an exact receipt pin')
    try:
        if args.prepare_selection is not None:
            result = prepare_daily_forecast_request(bundle_root=args.bundle_root,selection_name=args.prepare_selection,output_root=args.output_root)
        else:
            result = (run_daily_forecast_batch(bundle_root=args.bundle_root, request_name=args.request, output_root=args.output_root)
                  if args.request is not None else verify_daily_forecast_receipt(bundle_root=args.bundle_root,
                      receipt_name=args.verify_receipt, expected_receipt_sha256=args.expected_receipt_sha256))
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        parser.exit(2, 'Daily forecast batch refused or incomplete; preserve all inputs and partial evidence.\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
