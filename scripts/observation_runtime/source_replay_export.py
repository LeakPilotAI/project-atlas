"""One explicit source-backed descriptive replay export; no runtime or transport."""
from __future__ import annotations

import argparse
import hashlib
import json

from app.backtest.forecast_dataset import _fields, _json
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused

from scripts.observation_runtime.chart_archive import FLAGS, _pin, _read
from scripts.observation_runtime.research_replay import encoded, fingerprint
from scripts.observation_runtime.research_replay_export import (
    _plan_replay,
    _publish_replay,
)
from scripts.observation_runtime.source_vintages import _build


def _prepare(reader,request):
    budget_before=reader.budget
    _fields(request,'schema source_request references expected_references_sha256 decisions')
    if request['schema']!='ATLAS_SOURCE_REPLAY_REQUEST_V1':raise ResearchInputRefused('Explicit source replay request required')
    companion=_build(reader,request['source_request'])
    references_raw=_read(reader,request['references'])
    if hashlib.sha256(references_raw).hexdigest()!=_pin(request['expected_references_sha256']):
        raise ResearchInputRefused('Reference source commitment mismatch')
    plan=_plan_replay(companion['archive'],_json(references_raw),request['decisions'],vintage=True)
    planned,manifest,*_=plan
    companion_raw=encoded(companion);companion_id=hashlib.sha256(companion_raw).hexdigest()
    # Never make an old result depend on the caller's mutable input filename.
    # Retain exact reference bytes, including original whitespace, separately
    # from the legacy export's canonical normalized reference artifact.
    reference_name=hashlib.sha256(references_raw).hexdigest()+'.json'
    retained_request=json.loads(encoded(request));retained_request['references']=reference_name
    binding={'schema':'ATLAS_SOURCE_BACKED_REPLAY_EXPORT_V1','mode':'SYNTHETIC_REPLAY','request':retained_request,
        'request_sha256':fingerprint(retained_request),'source_companion':companion_id+'.json',
        'expected_source_companion_sha256':companion_id,'replay_manifest':manifest,
        'expected_replay_manifest_sha256':manifest[:-5],'sources_reproduced':True,
        'monitoring_completeness_verified':False,**FLAGS}
    binding_raw=encoded(binding);binding_name=hashlib.sha256(binding_raw).hexdigest()+'.json'
    # Existing artifacts remain byte-identical; the additional companion/sidecar
    # is not a new version of the legacy replay manifest or browser payload.
    planned[companion_id+'.json']=(companion_raw.decode(),'.json')
    planned[reference_name]=(references_raw.decode('utf-8'),'.json')
    planned[binding_name]=(binding_raw.decode(),'.json')
    if any(len(text.encode())>2_000_000 for text,_ in planned.values()) or sum(len(t.encode()) for t,_ in planned.values())>20_000_000:
        raise ResearchInputRefused('Combined source replay output budget exceeded before publication')
    if budget_before-reader.budget+len(binding_raw)+sum(len(t.encode()) for t,_ in planned.values())>50_000_000:
        raise ResearchInputRefused('Complete verification read budget exceeded before publication')
    return plan,binding_name,binding


def verify_source_replay(*,bundle_root,binding_name,expected_binding_sha256):
    expected=_pin(expected_binding_sha256);reader=BundleReader(bundle_root)
    if binding_name!=expected+'.json':raise ResearchInputRefused('Exact source replay binding name/pin required')
    raw=_read(reader,binding_name)
    if hashlib.sha256(raw).hexdigest()!=expected:raise ResearchInputRefused('Source replay binding commitment mismatch')
    value=_json(raw)
    _fields(value,'schema mode request request_sha256 source_companion expected_source_companion_sha256 replay_manifest expected_replay_manifest_sha256 sources_reproduced monitoring_completeness_verified '+' '.join(FLAGS))
    plan,rebuilt_name,rebuilt=_prepare(reader,value['request'])
    if rebuilt_name!=binding_name or encoded(rebuilt)!=raw:
        raise ResearchInputRefused('Source binding does not reproduce')
    for name,(text,_) in plan[0].items():
        if _read(reader,name)!=text.encode():raise ResearchInputRefused('Source replay artifact does not reproduce')
    report=_json(plan[0][plan[2]][0].encode())
    return {'status':'SYNTHETIC_SOURCE_REPLAY_REPRODUCED','binding':binding_name,
        'planned_decision_n':report['planned_decision_n'],'status_counts':report['status_counts'],**FLAGS}


def export_source_replay(*,bundle_root,request_name,output_root):
    reader=BundleReader(bundle_root)
    if BundleReader(output_root).root!=reader.root:
        raise ResearchInputRefused('Full source replay must remain with retained source dependencies')
    request=_json(_read(reader,request_name));plan,binding_name,_=_prepare(reader,request)
    result=_publish_replay(plan,output_root)
    checked=verify_source_replay(bundle_root=bundle_root,binding_name=binding_name,expected_binding_sha256=binding_name[:-5])
    return {**result,**checked,'status':'SYNTHETIC_SOURCE_REPLAY_EXPORTED'}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicit offline source-backed replay; no provider or startup')
    parser.add_argument('--bundle-root',required=True);mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--request');mode.add_argument('--verify-binding')
    parser.add_argument('--output-root');parser.add_argument('--expected-binding-sha256');args=parser.parse_args(argv)
    if ((args.request is not None and (args.output_root is None or args.expected_binding_sha256 is not None)) or
        (args.verify_binding is not None and (args.output_root is not None or args.expected_binding_sha256 is None))):
        parser.error('Export needs explicit output root; verification needs only an exact binding pin')
    try:
        result=(export_source_replay(bundle_root=args.bundle_root,request_name=args.request,output_root=args.output_root)
            if args.request is not None else verify_source_replay(bundle_root=args.bundle_root,binding_name=args.verify_binding,expected_binding_sha256=args.expected_binding_sha256))
    except (ValueError,OSError,TypeError,KeyError,OverflowError):
        parser.exit(2,'Source replay refused; preserve all inputs and partial outputs.\n')
    print(json.dumps(result,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
