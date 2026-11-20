"""Source-reproduced synthetic vintage companion. No real storage or collection."""
from __future__ import annotations

import hashlib
import json
import sqlite3

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _fields, _json
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused, aware, symbol_identity

from scripts.observation_runtime.bar_vintages import BarVintageStore
from scripts.observation_runtime.chart_archive import (
    FLAGS,
    _pin,
    _read,
    _review_chart_archive,
)
from scripts.observation_runtime.research_replay import encoded, fingerprint


def _build(reader,request):
    _fields(request,'schema symbol asof archives')
    if (request['schema']!='ATLAS_SOURCE_VINTAGES_REQUEST_V1' or type(request['archives']) is not list
            or not 1<=len(request['archives'])<=32):raise ResearchInputRefused('Bounded explicit source vintage request required')
    symbol=symbol_identity(request['symbol']);clock=aware(request['asof'])
    if request['symbol']!=symbol or request['asof']!=clock.isoformat():
        raise ResearchInputRefused('Canonical symbol and UTC clock required')
    reviewed=[];seen=set();prior=None;asset=None;bar_work=0
    for spec in request['archives']:
        _fields(spec,'receipt expected_sha256');identity=_pin(spec['expected_sha256'])
        if identity in seen:raise ResearchInputRefused('Duplicate source archive request')
        seen.add(identity)
        summary,receipt,raw=_review_chart_archive(reader,spec['receipt'],identity)
        stamp=aware(receipt['observed_at']);payload=_json(raw)
        if (stamp>clock or (prior is not None and stamp<=prior) or
                payload['chart']['result'][0]['meta']['symbol']!=symbol or
                (asset is not None and receipt['asset_class']!=asset)):
            raise ResearchInputRefused('Source identity, order or observation scope contradiction')
        prior=stamp;asset=receipt['asset_class'];bar_work+=summary['bar_n']
        if bar_work>10000:raise ResearchInputRefused('Source-normalization work bound exceeded')
        reviewed.append((summary,receipt,payload))
    entries=[];next_sequence=1;previous='0'*64
    with sqlite3.connect(':memory:') as db:
        store=BarVintageStore(db)
        for summary,receipt,payload in reviewed:
            committed=store.ingest(payload,observed_at=receipt['observed_at'],asset_class=receipt['asset_class'])
            if committed!=summary['bar_n']:raise ResearchInputRefused('Source/derived receipt count disagreement')
            # Strictly increasing source clocks make each range disjoint and unambiguous.
            snapshot=store.archive(symbol,now=receipt['observed_at']);head=snapshot['head']
            entries.append({'source_receipt_sha256':summary['receipt_sha256'],'source_sha256':summary['source_sha256'],
                'observed_at':receipt['observed_at'],'first_sequence':next_sequence,
                'last_sequence':next_sequence+committed-1,'record_n':committed,'previous_head':previous,'head':head})
            next_sequence+=committed;previous=head
        archive=store.archive(symbol,now=clock)
    return {'schema':'ATLAS_SOURCE_BACKED_BAR_VINTAGES_V1','mode':'SYNTHETIC_REPLAY',
        'request':json.loads(encoded(request)),'request_sha256':fingerprint(request),'source_n':len(entries),
        'source_entries':entries,'archive':archive,'sources_reproduced':True,
        'monitoring_completeness_verified':False,**FLAGS}


def build_source_vintages(*,bundle_root,request_name):
    reader=BundleReader(bundle_root)
    return _build(reader,_json(_read(reader,request_name)))


def verify_source_vintages(*,bundle_root,companion_name,expected_sha256):
    expected=_pin(expected_sha256);reader=BundleReader(bundle_root)
    if companion_name!=expected+'.json':raise ResearchInputRefused('Exact companion filename/pin required')
    raw=_read(reader,companion_name)
    if hashlib.sha256(raw).hexdigest()!=expected:raise ResearchInputRefused('Companion hash mismatch')
    value=_json(raw)
    _fields(value,'schema mode request request_sha256 source_n source_entries archive sources_reproduced monitoring_completeness_verified '+' '.join(FLAGS))
    rebuilt=_build(reader,value['request'])
    if raw!=encoded(rebuilt):raise ResearchInputRefused('Companion differs from retained source reproduction')
    return {'status':'SYNTHETIC_SOURCE_VINTAGES_REPRODUCED','source_n':rebuilt['source_n'],
            'record_n':rebuilt['archive']['record_n'],'head':rebuilt['archive']['head'],**FLAGS}


def export_source_vintages(*,bundle_root,request_name,output_root):
    if BundleReader(output_root).root!=BundleReader(bundle_root).root:
        raise ResearchInputRefused('Companion must remain with its explicit retained source bundle')
    value=build_source_vintages(bundle_root=bundle_root,request_name=request_name);raw=encoded(value)
    if len(raw)>2_000_000:raise ResearchInputRefused('Companion output budget exceeded')
    path=publish_research_text(output_root,raw.decode(),extension='.json')
    if path.read_bytes()!=raw:raise ResearchInputRefused('Companion publication uncertain; retain evidence')
    verify_source_vintages(bundle_root=bundle_root,companion_name=path.name,expected_sha256=hashlib.sha256(raw).hexdigest())
    return {'status':'SYNTHETIC_SOURCE_VINTAGES_EXPORTED','companion':path.name,
            'source_n':value['source_n'],'record_n':value['archive']['record_n'],**FLAGS}
