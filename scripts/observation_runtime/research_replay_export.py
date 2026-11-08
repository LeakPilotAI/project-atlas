"""Immutable, self-contained descriptive replay evidence using the existing publisher."""
from __future__ import annotations

import argparse
import hashlib
import json

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _fields, _json
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused

from scripts.observation_runtime.bar_vintages import (
    browser_vintages,
    render_vintages,
    replay_vintages,
)
from scripts.observation_runtime.research_replay import (
    browser_replay,
    encoded,
    fingerprint,
    render_replay,
    replay_research,
)


def _read_artifact(reader,name,extension='.json'):
    if type(name) is not str or '/' in name or '\\' in name:
        raise ResearchInputRefused('Bare immutable artifact name required')
    raw=reader.read(name)
    if name!=hashlib.sha256(raw).hexdigest()+extension:
        raise ResearchInputRefused('Replay artifact content identity mismatch')
    return raw


def verify_replay(*, bundle_root, manifest_name, expected_manifest_sha256):
    reader=BundleReader(bundle_root)
    raw=_read_artifact(reader,manifest_name)
    if type(expected_manifest_sha256) is not str or hashlib.sha256(raw).hexdigest()!=expected_manifest_sha256:
        raise ResearchInputRefused('Explicit replay manifest commitment mismatch')
    manifest=_json(raw)
    version=manifest.get('schema')
    vintage=version=='ATLAS_VINTAGE_REPLAY_EXPORT_V1'
    fields='schema archive_header archive_chunks archive_sha256 references decisions case_artifacts report dashboard source_authenticated startup_authorized recovery_authorized trading_authorized'
    _fields(manifest,fields+(' browser_export' if version=='ATLAS_DESCRIPTIVE_REPLAY_EXPORT_V2' or vintage else ''))
    if version not in ('ATLAS_DESCRIPTIVE_REPLAY_EXPORT_V1','ATLAS_DESCRIPTIVE_REPLAY_EXPORT_V2','ATLAS_VINTAGE_REPLAY_EXPORT_V1') or any(manifest[k] is not False for k in
            ('source_authenticated','startup_authorized','recovery_authorized','trading_authorized')):
        raise ResearchInputRefused('Replay export identity/authority mismatch')
    if type(manifest['archive_header']) is not dict or {'rows','records'} & set(manifest['archive_header']):
        raise ResearchInputRefused('Replay archive header mismatch')
    chunks=manifest['archive_chunks'];rows=[]
    if type(chunks) is not list or len(chunks)>10:raise ResearchInputRefused('Bounded source chunks required')
    for spec in chunks:
        _fields(spec,'artifact start_index record_n')
        if type(spec['start_index']) is not int or spec['start_index']!=len(rows) or type(spec['record_n']) is not int or not 1<=spec['record_n']<=1000:
            raise ResearchInputRefused('Missing/reordered source chunk')
        chunk=_json(_read_artifact(reader,spec['artifact']))
        key='records' if vintage else 'rows'
        _fields(chunk,'schema start_index '+key)
        if (chunk['schema']!=('ATLAS_RECEIPT_SOURCE_CHUNK_V1' if vintage else 'ATLAS_REPLAY_SOURCE_CHUNK_V1') or type(chunk['start_index']) is not int
                or chunk['start_index']!=len(rows) or type(chunk[key]) is not list or len(chunk[key])!=spec['record_n']):
            raise ResearchInputRefused('Replay source chunk contradiction')
        rows.extend(chunk[key])
    archive={**manifest['archive_header'],('records' if vintage else 'rows'):rows}
    if fingerprint(archive)!=manifest['archive_sha256']:raise ResearchInputRefused('Reconstructed archive commitment mismatch')
    references=_json(_read_artifact(reader,manifest['references']))
    report=(replay_vintages if vintage else replay_research)(archive,references,manifest['decisions'])
    if encoded(_json(_read_artifact(reader,manifest['report'])))!=encoded(report):
        raise ResearchInputRefused('Replay report does not reproduce from preserved inputs')
    if _read_artifact(reader,manifest['dashboard'],'.html')!=(render_vintages if vintage else render_replay)(report).encode():
        raise ResearchInputRefused('Replay dashboard contradiction')
    if (version=='ATLAS_DESCRIPTIVE_REPLAY_EXPORT_V2' or vintage) and _read_artifact(reader,manifest['browser_export'])!=(browser_vintages if vintage else browser_replay)(report).encode():
        raise ResearchInputRefused('Replay browser payload contradiction')
    specs=manifest['case_artifacts']
    if type(specs) is not list or len(specs)!=len(report['cases']):raise ResearchInputRefused('Exact decision artifact coverage required')
    for case,spec in zip(report['cases'],specs,strict=True):
        _fields(spec,'index decision_sha256 artifact')
        if type(spec['index']) is not int or spec['index']!=case['index'] or spec['decision_sha256']!=case['decision_sha256']:
            raise ResearchInputRefused('Decision mapping contradiction')
        expected={'schema':'ATLAS_VINTAGE_DECISION_V1' if vintage else 'ATLAS_DESCRIPTIVE_DECISION_V1','case':{k:v for k,v in case.items() if k!='index'}}
        if encoded(_json(_read_artifact(reader,spec['artifact'])))!=encoded(expected):
            raise ResearchInputRefused('Decision artifact does not reproduce')
    return {'status':'OFFLINE_REPLAY_VERIFIED','planned_decision_n':report['planned_decision_n'],
            'status_counts':report['status_counts'],'source_authenticated':False,
            'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}


def export_replay(*, bundle_root, request_name, output_root):
    reader=BundleReader(bundle_root);request=_json(reader.read(request_name))
    _fields(request,'schema archive expected_archive_sha256 references expected_references_sha256 decisions')
    if request['schema'] not in ('ATLAS_DESCRIPTIVE_REPLAY_REQUEST_V1','ATLAS_VINTAGE_REPLAY_REQUEST_V1'):
        raise ResearchInputRefused('Unsupported replay request')
    vintage=request['schema']=='ATLAS_VINTAGE_REPLAY_REQUEST_V1'
    inputs={}
    for key in ('archive','references'):
        raw=reader.read(request[key]);expected=request['expected_'+key+'_sha256']
        if type(expected) is not str or hashlib.sha256(raw).hexdigest()!=expected:
            raise ResearchInputRefused('Replay input commitment mismatch')
        inputs[key]=_json(raw)
    return _publish_replay(_plan_replay(inputs['archive'],inputs['references'],request['decisions'],vintage=vintage),output_root)


def _plan_replay(archive,references,decisions, *, vintage):
    """Pure full validation/byte planning reused by source-backed exports."""
    report=(replay_vintages if vintage else replay_research)(archive,references,decisions)
    planned={}
    def plan(value,extension='.json'):
        text=(render_vintages if vintage else render_replay)(value) if extension=='.html' else encoded(value).decode()
        raw=text.encode();name=hashlib.sha256(raw).hexdigest()+extension
        if len(raw)>2_000_000:raise ResearchInputRefused('Replay artifact exceeds existing publisher limit')
        planned[name]=(text,extension)
        return name
    chunks=[]
    key='records' if vintage else 'rows'
    for start in range(0,len(archive[key]),1000):
        rows=archive[key][start:start+1000]
        name=plan({'schema':'ATLAS_RECEIPT_SOURCE_CHUNK_V1' if vintage else 'ATLAS_REPLAY_SOURCE_CHUNK_V1','start_index':start,key:rows})
        chunks.append({'artifact':name,'start_index':start,'record_n':len(rows)})
    refs_name=plan(references);case_artifacts=[]
    for case in report['cases']:
        name=plan({'schema':'ATLAS_VINTAGE_DECISION_V1' if vintage else 'ATLAS_DESCRIPTIVE_DECISION_V1','case':{k:v for k,v in case.items() if k!='index'}})
        case_artifacts.append({'index':case['index'],'decision_sha256':case['decision_sha256'],'artifact':name})
    report_name=plan(report);dashboard=plan(report,'.html')
    browser_text=(browser_vintages if vintage else browser_replay)(report);browser_payload=_json(browser_text.encode())
    browser_name=plan(browser_payload)
    manifest={'schema':'ATLAS_VINTAGE_REPLAY_EXPORT_V1' if vintage else 'ATLAS_DESCRIPTIVE_REPLAY_EXPORT_V2',
              'archive_header':{k:v for k,v in archive.items() if k!=key},
              'archive_chunks':chunks,'archive_sha256':fingerprint(archive),'references':refs_name,
              'decisions':[case['decision_at'] for case in report['cases']],'case_artifacts':case_artifacts,
              'report':report_name,'dashboard':dashboard,'browser_export':browser_name,'source_authenticated':False,
              'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}
    manifest_name=plan(manifest)
    if sum(len(text.encode()) for text,_ in planned.values())>20_000_000:
        raise ResearchInputRefused('Replay output byte budget exceeded before publication')
    return planned,manifest_name,report_name,dashboard,browser_name


def _publish_replay(plan,output_root):
    planned,manifest_name,report_name,dashboard,browser_name=plan
    for name,(text,extension) in planned.items():
        path=publish_research_text(output_root,text,extension=extension)
        if path.name!=name or path.read_text(encoding='utf-8')!=text:
            raise ResearchInputRefused('Replay publication/readback uncertain; preserve partial evidence')
    checked=verify_replay(bundle_root=output_root,manifest_name=manifest_name,expected_manifest_sha256=manifest_name[:-5])
    return {**checked,'status':'OFFLINE_REPLAY_EXPORTED','manifest':manifest_name,'report':report_name,
            'dashboard':dashboard,'browser_export':browser_name,'artifact_n':len(planned)}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicit offline descriptive replay; no collection, recovery or trading')
    parser.add_argument('--bundle-root',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--request');mode.add_argument('--verify')
    parser.add_argument('--output-root');parser.add_argument('--expected-manifest-sha256')
    args=parser.parse_args(argv)
    if (args.request is not None and (args.output_root is None or args.expected_manifest_sha256 is not None)
            or args.verify is not None and (args.expected_manifest_sha256 is None or args.output_root is not None)):
        parser.error('Export needs output root; verification needs exact manifest hash and cannot write output')
    try:
        result=(export_replay(bundle_root=args.bundle_root,request_name=args.request,output_root=args.output_root)
                if args.request is not None else verify_replay(bundle_root=args.bundle_root,manifest_name=args.verify,
                    expected_manifest_sha256=args.expected_manifest_sha256))
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as error:
        print(json.dumps({'status':'REFUSED','error_type':type(error).__name__,'message':'Replay evidence/publication refused; preserve partial outputs.',
                          'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}))
        return 2
    print(json.dumps(result,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
