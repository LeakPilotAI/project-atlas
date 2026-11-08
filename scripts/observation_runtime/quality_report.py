"""Explicit offline pinned-input quality report export; no collection or startup."""
from __future__ import annotations

import argparse
import hashlib
import json

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _fields, _json
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused, aware

from scripts.observation_runtime.quote_quality import (
    quote_quality,
    render_quote_quality,
)
from scripts.observation_runtime.retained_research import (
    render_retained_research,
    retained_research,
)
from scripts.observation_runtime.session_quality import (
    render_session_quality,
    session_quality,
)


def export_quality(*, bundle_root, request_name, output_root):
    """Retain validated outputs, without a multi-file transaction or recovery grant."""
    reader=BundleReader(bundle_root)
    request=_json(reader.read(request_name))
    _fields(request,'schema now history expected_history_sha256 lifecycle lifecycle_expected_head')
    if request['schema']!='ATLAS_SESSION_QUALITY_REQUEST_V1':
        raise ResearchInputRefused('Unsupported quality export request')
    raw=reader.read(request['history'])
    history_hash=hashlib.sha256(raw).hexdigest()
    if type(request['expected_history_sha256']) is not str or request['expected_history_sha256']!=history_hash:
        raise ResearchInputRefused('Caller history commitment mismatch')
    history=_json(raw)
    lifecycle,lifecycle_hash=None,None
    if request['lifecycle'] is not None:
        raw_lifecycle=reader.read(request['lifecycle'])
        lines=raw_lifecycle.splitlines()
        if len(lines)>2048:
            raise ResearchInputRefused('Bounded lifecycle export required')
        lifecycle=[_json(line) for line in lines]
        lifecycle_hash=hashlib.sha256(raw_lifecycle).hexdigest()
    report=session_quality(history,now=request['now'],lifecycle=lifecycle,
                           lifecycle_expected_head=request['lifecycle_expected_head'])
    provenance={'schema':'ATLAS_SESSION_QUALITY_EXPORT_V1','history_sha256':history_hash,
                'lifecycle_sha256':lifecycle_hash,'expected_lifecycle_head':request['lifecycle_expected_head'],
                'source_authenticated':False,'startup_authorized':False,'recovery_authorized':False,
                'trading_authorized':False,'network_authorized':False}
    result=_publish_outputs(report,provenance,output_root,render_session_quality)
    return {'status':'OFFLINE_QUALITY_EXPORTED',**result,'observed_bar_n':report['observed_bar_n'],
            'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}


def export_quote_quality(*, bundle_root, request_name, output_root):
    reader=BundleReader(bundle_root)
    request=_json(reader.read(request_name))
    _fields(request,'schema now snapshot expected_snapshot_sha256')
    if request['schema']!='ATLAS_QUOTE_QUALITY_REQUEST_V1':
        raise ResearchInputRefused('Unsupported quote-quality export request')
    raw=reader.read(request['snapshot']);snapshot_hash=hashlib.sha256(raw).hexdigest()
    if type(request['expected_snapshot_sha256']) is not str or request['expected_snapshot_sha256']!=snapshot_hash:
        raise ResearchInputRefused('Caller snapshot commitment mismatch')
    snapshot=_json(raw)
    _fields(snapshot,'schema mode asof network_authorized trading_enabled coverage rows quote_rows')
    if (snapshot['schema']!='ATLAS_MARKET_REPLAY_V1' or snapshot['mode']!='SYNTHETIC_REPLAY'
            or snapshot['network_authorized'] is not False or snapshot['trading_enabled'] is not False
            or snapshot['coverage']!='OBSERVED_BARS_ONLY_NO_GAP_IMPUTATION'
            or type(snapshot['rows']) is not list or len(snapshot['rows'])>100
            or aware(snapshot['asof'])!=aware(request['now'])):
        raise ResearchInputRefused('Quote export snapshot scope/clock mismatch')
    report=quote_quality(snapshot['quote_rows'],now=request['now'])
    provenance={'schema':'ATLAS_QUOTE_QUALITY_EXPORT_V1','snapshot_sha256':snapshot_hash,
                'scope':'QUOTE_ROWS_ONLY_BAR_EVIDENCE_NOT_AUDITED','source_asof':snapshot['asof'],
                'source_authenticated':False,'startup_authorized':False,'recovery_authorized':False,
                'trading_authorized':False,'network_authorized':False}
    result=_publish_outputs(report,provenance,output_root,render_quote_quality)
    return {'status':'OFFLINE_QUOTE_QUALITY_EXPORTED',**result,'reference_n':len(report['rows']),
            'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}


def _publish_outputs(report, provenance, output_root, renderer):
    text=json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n'
    html=renderer(report)
    report_path=publish_research_text(output_root,text,extension='.json')
    html_path=publish_research_text(output_root,html,extension='.html')
    provenance={**provenance,'report_sha256':hashlib.sha256(text.encode()).hexdigest(),
                'html_sha256':hashlib.sha256(html.encode()).hexdigest()}
    metadata=json.dumps(provenance,sort_keys=True,indent=2,allow_nan=False)+'\n'
    provenance_path=publish_research_text(output_root,metadata,extension='.json')
    for path,expected in ((report_path,text),(html_path,html),(provenance_path,metadata)):
        if path.read_text(encoding='utf-8')!=expected:
            raise ResearchInputRefused('Quality export readback failure; preserve partial evidence')
    return {'report':report_path.name,'dashboard':html_path.name,'provenance':provenance_path.name}


def export_retained_research(*, bundle_root, request_name, output_root):
    reader=BundleReader(bundle_root)
    request=_json(reader.read(request_name))
    _fields(request,'schema now history expected_history_sha256 reference expected_reference_sha256')
    if request['schema']!='ATLAS_RETAINED_RESEARCH_REQUEST_V1':
        raise ResearchInputRefused('Unsupported retained research export request')
    inputs={};hashes={}
    for key in ('history','reference'):
        raw=reader.read(request[key]);identity=hashlib.sha256(raw).hexdigest()
        expected=request['expected_'+key+'_sha256']
        if type(expected) is not str or identity!=expected:
            raise ResearchInputRefused('Caller research input commitment mismatch')
        inputs[key]=_json(raw);hashes[key+'_sha256']=identity
    report=retained_research(inputs['history'],inputs['reference'],now=request['now'])
    provenance={'schema':'ATLAS_RETAINED_RESEARCH_EXPORT_V1',**hashes,
                'scope':'SYNTHETIC_DESCRIPTIVE_NO_FORECAST_OR_CORPORATE_ACTION_RECONCILIATION',
                'source_authenticated':False,'startup_authorized':False,'recovery_authorized':False,
                'trading_authorized':False,'network_authorized':False}
    result=_publish_outputs(report,provenance,output_root,render_retained_research)
    return {'status':'OFFLINE_RETAINED_RESEARCH_EXPORTED',**result,'analysis_status':report['status'],
            'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Offline synthetic quality evidence only; no provider or startup')
    parser.add_argument('--bundle-root',required=True)
    parser.add_argument('--request',required=True)
    parser.add_argument('--output-root',required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--quote-quality',action='store_true',help='Explicit quote-reference mode; no collection or startup')
    mode.add_argument('--retained-research',action='store_true',help='Explicit descriptive research mode; no forecast or execution')
    args=parser.parse_args(argv)
    try:
        exporter=export_retained_research if args.retained_research else export_quote_quality if args.quote_quality else export_quality
        result=exporter(bundle_root=args.bundle_root,request_name=args.request,output_root=args.output_root)
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as error:
        print(json.dumps({'status':'REFUSED','error_type':type(error).__name__,
                          'message':'Quality input/publication refused; preserve partial evidence.',
                          'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
