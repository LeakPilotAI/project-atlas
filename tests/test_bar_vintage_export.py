import hashlib
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from test_bar_vintages import corrected, seeded

from scripts.observation_runtime import research_replay_export as export
from scripts.observation_runtime.research_comparison import compare_exports
from scripts.observation_runtime.research_replay import encoded, fingerprint


def setup(tmp_path, *, large=False,correction=True):
    with sqlite3.connect(':memory:') as db:
        store,now,ref=seeded(db)
        if correction:corrected(store,now)
        archive=store.archive('SPY',now=now+timedelta(minutes=1))
    if large:
        row=archive['records'][-1]['row']
        while len(archive['records'])<1001:
            row={**row,'observed_at':(now+timedelta(seconds=len(archive['records'])+30)).isoformat()}
            record={'sequence':len(archive['records'])+1,'previous':archive['head'],'row':row}
            record['digest']=fingerprint(record);archive['records'].append(record);archive['head']=record['digest']
        archive['record_n']=len(archive['records']);archive['asof']=row['observed_at']
    decisions=[now.isoformat(),(now+timedelta(seconds=20)).isoformat()]
    request={'schema':'ATLAS_VINTAGE_REPLAY_REQUEST_V1','decisions':decisions}
    for key,value in [('archive',archive),('references',[ref])]:
        raw=encoded(value);(tmp_path/(key+'.json')).write_bytes(raw)
        request[key]=key+'.json';request['expected_'+key+'_sha256']=hashlib.sha256(raw).hexdigest()
    (tmp_path/'request.json').write_bytes(encoded(request));output=tmp_path/'output';output.mkdir()
    return output,archive


def run(root,output):return export.export_replay(bundle_root=root,request_name='request.json',output_root=output)


def verify(root,result):
    return export.verify_replay(bundle_root=root,manifest_name=result['manifest'],expected_manifest_sha256=result['manifest'][:-5])


def test_actual_vintage_source_chunks_case_audits_dashboard_and_browser_reproduce(tmp_path):
    output,archive=setup(tmp_path);result=run(tmp_path,output)
    manifest=json.loads((output/result['manifest']).read_bytes());report=json.loads((output/result['report']).read_bytes())
    assert manifest['schema']=='ATLAS_VINTAGE_REPLAY_EXPORT_V1'
    assert manifest['archive_header']['head']==archive['head']
    assert [row['report']['analysis']['bar_close'] for row in report['cases']]==[103,120]
    assert report['cases'][0]['correction_n']==0 and report['cases'][1]['correction_n']==1
    assert 'Receipt-vintage evidence' in (output/result['dashboard']).read_text()
    assert json.loads((output/result['browser_export']).read_bytes())['schema']=='ATLAS_VINTAGE_REPLAY_BROWSER_V1'
    fixture=Path(__file__).parent/'fixtures/market-replay-v1/bar-vintages.json'
    assert (output/result['browser_export']).read_bytes()==fixture.read_bytes()
    before={p:p.read_bytes() for p in output.iterdir()}
    assert verify(output,result)['planned_decision_n']==2
    assert run(tmp_path,output)==result and before=={p:p.read_bytes() for p in output.iterdir()}


def test_large_receipt_archive_is_chunked_and_not_reduced_to_latest_value(tmp_path):
    output,archive=setup(tmp_path,large=True);result=run(tmp_path,output)
    manifest=json.loads((output/result['manifest']).read_bytes())
    assert [chunk['record_n'] for chunk in manifest['archive_chunks']]==[1000,1]
    assert manifest['archive_header']['record_n']==1001
    assert verify(output,result)['planned_decision_n']==2
    assert archive['record_n']==1001


@pytest.mark.parametrize('fault',['tail','pin','authority','request_schema'])
def test_bad_vintage_inputs_refuse_before_publication(tmp_path,fault):
    output,archive=setup(tmp_path)
    request=json.loads((tmp_path/'request.json').read_bytes())
    if fault=='tail':archive['records'].pop();archive['record_n']-=1
    if fault=='authority':archive['trading_enabled']=True
    if fault in ('tail','authority'):
        raw=encoded(archive);(tmp_path/'archive.json').write_bytes(raw)
        request['expected_archive_sha256']=hashlib.sha256(raw).hexdigest()
    if fault=='pin':request['expected_archive_sha256']='0'*64
    if fault=='request_schema':request['schema']='ATLAS_DESCRIPTIVE_REPLAY_REQUEST_V1'
    (tmp_path/'request.json').write_bytes(encoded(request))
    with pytest.raises(ValueError):run(tmp_path,output)
    assert list(output.iterdir())==[]


@pytest.mark.parametrize('fault',['case_audit','browser','chunk_count','report'])
def test_rehashed_derived_tampering_is_detected_by_source_reproduction(tmp_path,fault):
    output,_=setup(tmp_path);result=run(tmp_path,output);manifest=json.loads((output/result['manifest']).read_bytes())
    def put(value):
        raw=encoded(value);name=hashlib.sha256(raw).hexdigest()+'.json';(output/name).write_bytes(raw);return name
    if fault=='case_audit':
        spec=manifest['case_artifacts'][1];body=json.loads((output/spec['artifact']).read_bytes())
        body['case']['vintage_decision_sha256']='0'*64;spec['artifact']=put(body)
    if fault=='browser':
        body=json.loads((output/manifest['browser_export']).read_bytes());body['payload_sha256']='0'*64
        manifest['browser_export']=put(body)
    if fault=='chunk_count':manifest['archive_chunks'][0]['record_n']-=1
    if fault=='report':
        body=json.loads((output/manifest['report']).read_bytes());body['cases'][1]['correction_n']=0
        manifest['report']=put(body)
    name=put(manifest)
    with pytest.raises(ValueError):
        export.verify_replay(bundle_root=output,manifest_name=name,expected_manifest_sha256=name[:-5])


def test_pair_comparison_uses_vintage_audit_identity_and_preserves_denominators(tmp_path):
    sources=[]
    for correction in (False,True):
        root=tmp_path/str(correction);root.mkdir();output,_=setup(root,correction=correction);result=run(root,output)
        sources.append((output,result))
    args={side+'_'+field:value for side,(root,result) in zip(('left','right'),sources,strict=True)
          for field,value in [('root',root),('manifest',result['manifest']),('pin',result['manifest'][:-5])]}
    report=compare_exports(**args)
    assert report['planned_pair_n']==2 and report['both_descriptive_n']==2
    assert report['same_evidence_n']==1 and report['changed_evidence_n']==1
    assert report['pairs'][1]['metrics']['observed_change_percent']['right_minus_left']==17


def test_partial_vintage_publication_is_preserved_without_success(tmp_path,monkeypatch):
    output,_=setup(tmp_path);original=export.publish_research_text;calls=0
    def fail(root,text,extension):
        nonlocal calls
        calls+=1
        if calls==3:raise OSError('synthetic disk full')
        return original(root,text,extension=extension)
    monkeypatch.setattr(export,'publish_research_text',fail)
    with pytest.raises(OSError):run(tmp_path,output)
    assert len(list(output.iterdir()))==2
