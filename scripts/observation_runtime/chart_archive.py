"""Bounded synthetic chart archive and exact replay; no provider or runtime hooks."""
from __future__ import annotations

import argparse
import hashlib
import json

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _fields, _json
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused

from scripts.observation_runtime.chart_provenance import (
    chart_provenance,
    export_chart_provenance,
    render_chart_provenance,
)

FLAGS={'source_authenticated':False,'network_authorized':False,'startup_authorized':False,
       'recovery_authorized':False,'trading_authorized':False}


def _text(value):return json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n'


def _digest(raw):return hashlib.sha256(raw).hexdigest()


def _pin(value):
    if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ResearchInputRefused('Exact lowercase SHA-256 required')
    return value


def _read(reader,name):
    path=reader.path(name)
    if not path.is_file() or path.stat().st_nlink!=1:
        raise ResearchInputRefused('Unlinked regular archive input required')
    raw=reader.read(name)
    if not path.is_file() or path.stat().st_nlink!=1:
        raise ResearchInputRefused('Archive input identity ambiguous')
    return raw


def _review_subset(raw,report):
    """Archive only a reviewed synthetic subset, never arbitrary response fields."""
    payload=_json(raw);_fields(payload,'chart');chart=payload['chart'];_fields(chart,'result error')
    result=chart['result'][0];_fields(result,'meta timestamp indicators')
    meta=result['meta']
    required={'symbol','currency','dataGranularity'}
    allowed=required|{'exchangeTimezoneName','instrumentType','quoteType','exchangeDataDelayedBy'}
    if type(meta) is not dict or not required<=set(meta)<=allowed or meta['symbol']!=report['symbol']:
        raise ResearchInputRefused('Unreviewed source metadata cannot be archived')
    indicators=result['indicators']
    if type(indicators) is not dict or not {'quote'}<=set(indicators)<={'quote','adjclose'}:
        raise ResearchInputRefused('Unreviewed source indicators cannot be archived')
    _fields(indicators['quote'][0],'open high low close volume')
    arrays=list(indicators['quote'][0].values())
    if 'adjclose' in indicators:arrays.append(indicators['adjclose'][0]['adjclose'])
    if any(type(v) not in (int,float) for values in arrays for v in values):
        raise ResearchInputRefused('Exact JSON numeric source series required')


def _reference(name,raw):return {'name':name,'sha256':_digest(raw)}


def _referenced(reader,reference,extension):
    _fields(reference,'name sha256');identity=_pin(reference['sha256'])
    if reference['name']!=identity+extension:
        raise ResearchInputRefused('Content-addressed archive reference required')
    raw=_read(reader,reference['name'])
    if _digest(raw)!=identity:raise ResearchInputRefused('Archive content commitment mismatch')
    return raw


def _review_chart_archive(reader,receipt_name,expected_receipt_sha256):
    """Internal review with a caller-shared bounded reader; never resets budget."""
    expected=_pin(expected_receipt_sha256)
    if receipt_name!=expected+'.json':raise ResearchInputRefused('Exact receipt filename/pin required')
    raw=_read(reader,receipt_name)
    if _digest(raw)!=expected:raise ResearchInputRefused('Receipt commitment mismatch')
    receipt=_json(raw)
    _fields(receipt,'schema scope observed_at asset_class source report dashboard provenance '+ ' '.join(FLAGS))
    if (receipt['schema']!='ATLAS_CHART_ARCHIVE_V1' or receipt['scope']!='SYNTHETIC_REVIEWED_SUBSET_V1'
            or any(receipt[k] is not v for k,v in FLAGS.items())):
        raise ResearchInputRefused('Synthetic non-authorizing archive required')
    source=_referenced(reader,receipt['source'],'.json')
    report=chart_provenance(source,observed_at=receipt['observed_at'],asset_class=receipt['asset_class'],
                            expected_sha256=receipt['source']['sha256'])
    _review_subset(source,report)
    if receipt['observed_at']!=report['observed_at']:
        raise ResearchInputRefused('Canonical observation time required')
    expected_report=_text(report).encode();expected_html=render_chart_provenance(report).encode()
    provenance={'schema':'ATLAS_CHART_PROVENANCE_EXPORT_V1','source_sha256':report['source_sha256'],**FLAGS,
                'report_sha256':_digest(expected_report),'html_sha256':_digest(expected_html)}
    for key,extension,content in (('report','.json',expected_report),('dashboard','.html',expected_html),
                                  ('provenance','.json',_text(provenance).encode())):
        if _referenced(reader,receipt[key],extension)!=content:
            raise ResearchInputRefused('Derived evidence differs from source reproduction')
    if raw!=_text(receipt).encode():raise ResearchInputRefused('Canonical immutable receipt required')
    summary={'status':'SYNTHETIC_ARCHIVE_REPRODUCED','receipt_sha256':expected,
             'source_sha256':report['source_sha256'],'bar_n':report['bar_n'],**FLAGS}
    return summary,receipt,source


def verify_chart_archive(*,bundle_root,receipt_name,expected_receipt_sha256):
    """Reproduce every derived byte from retained source; no history completeness claim."""
    return _review_chart_archive(BundleReader(bundle_root),receipt_name,expected_receipt_sha256)[0]


def archive_chart_fixture(*,bundle_root,request_name,output_root):
    reader=BundleReader(bundle_root);request=_json(_read(reader,request_name))
    _fields(request,'schema source expected_source_sha256 observed_at asset_class')
    if request['schema']!='ATLAS_CHART_ARCHIVE_REQUEST_V1':raise ResearchInputRefused('Explicit chart archive request required')
    raw=_read(reader,request['source']);source_identity=_pin(request['expected_source_sha256'])
    report=chart_provenance(raw,observed_at=request['observed_at'],asset_class=request['asset_class'],expected_sha256=source_identity)
    _review_subset(raw,report)
    # Validate completely before publication. A later I/O failure preserves partial evidence.
    source=publish_research_text(output_root,raw.decode('utf-8'),extension='.json')
    if source.name!=source_identity+'.json' or source.read_bytes()!=raw:
        raise ResearchInputRefused('Source publication readback mismatch')
    derived=export_chart_provenance(raw,observed_at=request['observed_at'],asset_class=request['asset_class'],
                                    expected_sha256=source_identity,output_root=output_root)
    published=BundleReader(output_root)
    receipt={'schema':'ATLAS_CHART_ARCHIVE_V1','scope':'SYNTHETIC_REVIEWED_SUBSET_V1',
             'observed_at':report['observed_at'],'asset_class':report['asset_class'],
             'source':_reference(source.name,raw),**FLAGS}
    for key in ('report','dashboard','provenance'):
        receipt[key]=_reference(derived[key],_read(published,derived[key]))
    receipt_path=publish_research_text(output_root,_text(receipt),extension='.json')
    verified=verify_chart_archive(bundle_root=output_root,receipt_name=receipt_path.name,
                                  expected_receipt_sha256=_digest(_text(receipt).encode()))
    return {**verified,'receipt':receipt_path.name,'status':'SYNTHETIC_CHART_ARCHIVED'}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicit synthetic chart archive; no collection or startup')
    parser.add_argument('--bundle-root',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--request');mode.add_argument('--verify-receipt')
    parser.add_argument('--output-root');parser.add_argument('--expected-receipt-sha256')
    args=parser.parse_args(argv)
    if args.request:
        if not args.output_root or args.expected_receipt_sha256:parser.error('Archive requires only an explicit output root')
    elif args.output_root or not args.expected_receipt_sha256:parser.error('Verification requires only an exact receipt pin')
    try:
        result=(archive_chart_fixture(bundle_root=args.bundle_root,request_name=args.request,output_root=args.output_root)
                if args.request else verify_chart_archive(bundle_root=args.bundle_root,receipt_name=args.verify_receipt,
                                                          expected_receipt_sha256=args.expected_receipt_sha256))
    except (ValueError,OSError):
        parser.exit(2,'Synthetic chart archive refused; preserve supplied inputs and partial evidence.\n')
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
