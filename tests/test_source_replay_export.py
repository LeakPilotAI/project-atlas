import hashlib
import json
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from test_source_vintages import NOW, setup, source

import scripts.observation_runtime.source_replay_export as exporter
from scripts.observation_runtime.research_replay import encoded
from scripts.observation_runtime.research_replay_export import (
    export_replay,
    verify_replay,
)


def prepare(tmp_path):
    bundle,source_request=setup(tmp_path,[source(tmp_path,'first'),source(tmp_path,'second',20,120),source(tmp_path,'third',30,120)])
    raw=b'[]\n';(bundle/'references.json').write_bytes(raw)
    request={'schema':'ATLAS_SOURCE_REPLAY_REQUEST_V1','source_request':source_request,'references':'references.json',
        'expected_references_sha256':hashlib.sha256(raw).hexdigest(),'decisions':[(NOW+timedelta(seconds=s)).isoformat() for s in (0,20,30)]}
    (bundle/'source-replay.json').write_text(json.dumps(request));return bundle,request


def export(bundle):return exporter.export_source_replay(bundle_root=bundle,request_name='source-replay.json',output_root=bundle)


def verify(bundle,result):return exporter.verify_source_replay(bundle_root=bundle,binding_name=result['binding'],expected_binding_sha256=result['binding'][:-5])


def test_single_export_reproduces_all_sources_cases_and_existing_browser(tmp_path):
    bundle,_=prepare(tmp_path);before={p.name:p.read_bytes() for p in bundle.iterdir()};result=export(bundle)
    assert result['status']=='SYNTHETIC_SOURCE_REPLAY_EXPORTED' and result['planned_decision_n']==3
    assert result['status_counts']['INSUFFICIENT_REFERENCE']==3 and result['network_authorized'] is False
    assert verify(bundle,result)['status']=='SYNTHETIC_SOURCE_REPLAY_REPRODUCED'
    assert all((bundle/name).read_bytes()==raw for name,raw in before.items())
    root=Path(__file__).resolve().parents[1]
    code="const fs=require('node:fs'),api=require(process.argv[1]);api.verifyVintageReplay(fs.readFileSync(process.argv[2],'utf8')).then(r=>{if(r.cases[0].correction_n!==0||r.cases[2].confirmation_n!==1||r.planned_decision_n!==3)throw Error('contract');process.stdout.write('PASS')}).catch(()=>process.exitCode=1)"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(root/'frontend/offline/market-replay/view.cjs'),str(bundle/result['browser_export'])],capture_output=True,text=True,timeout=10,check=False)
    assert checked.returncode==0 and checked.stdout=='PASS',checked.stderr


def test_legacy_export_bytes_and_exact_retries_preserved(tmp_path):
    bundle,request=prepare(tmp_path);reader=exporter.BundleReader(bundle);plan,_,binding=exporter._prepare(reader,request)
    companion=json.loads(plan[0][binding['source_companion']][0]);archive_raw=encoded(companion['archive'])
    (bundle/'normalized.json').write_bytes(archive_raw)
    legacy={'schema':'ATLAS_VINTAGE_REPLAY_REQUEST_V1','archive':'normalized.json','expected_archive_sha256':hashlib.sha256(archive_raw).hexdigest(),
      'references':request['references'],'expected_references_sha256':request['expected_references_sha256'],'decisions':request['decisions']}
    (bundle/'legacy.json').write_text(json.dumps(legacy));old_output=tmp_path/'legacy';old_output.mkdir()
    old=export_replay(bundle_root=bundle,request_name='legacy.json',output_root=old_output);result=export(bundle)
    for path in old_output.iterdir():assert path.read_bytes()==(bundle/path.name).read_bytes()
    assert old['manifest']==result['manifest']
    before={p.name:p.read_bytes() for p in bundle.iterdir()};assert export(bundle)==result
    assert before=={p.name:p.read_bytes() for p in bundle.iterdir()}


@pytest.mark.parametrize('fault',['reference-pin','reference-shape','decision-future','decision-duplicate','source-duplicate','source-tie','extra'])
def test_invalid_complete_request_refuses_before_any_publication(tmp_path,fault):
    bundle,request=prepare(tmp_path)
    if fault=='reference-pin':request['expected_references_sha256']='0'*64
    if fault=='reference-shape':
        raw=b'{}';(bundle/'references.json').write_bytes(raw);request['expected_references_sha256']=hashlib.sha256(raw).hexdigest()
    if fault=='decision-future':request['decisions'][-1]=(NOW+timedelta(days=1)).isoformat()
    if fault=='decision-duplicate':request['decisions'][-1]=request['decisions'][0]
    if fault=='source-duplicate':request['source_request']['archives'][1]=request['source_request']['archives'][0]
    if fault=='source-tie':request['source_request']['archives'].reverse()
    if fault=='extra':request['unexpected']='SYNTHETIC_PRIVATE_VALUE'
    (bundle/'source-replay.json').write_text(json.dumps(request));before={p.name:p.read_bytes() for p in bundle.iterdir()}
    with pytest.raises(ValueError):export(bundle)
    assert before=={p.name:p.read_bytes() for p in bundle.iterdir()}


def test_full_source_verifier_refuses_when_only_legacy_replay_dependencies_remain(tmp_path):
    bundle,_=prepare(tmp_path);result=export(bundle);partial=tmp_path/'partial';partial.mkdir()
    # Preserve everything except one declared original; old normalized replay
    # is still reproducible but cannot imply original source retention.
    binding=json.loads((bundle/result['binding']).read_bytes())
    receipt=json.loads((bundle/binding['request']['source_request']['archives'][0]['receipt']).read_bytes())
    missing=receipt['source']['name']
    for path in bundle.iterdir():
        if path.name!=missing:shutil.copy2(path,partial/path.name)
    assert verify_replay(bundle_root=partial,manifest_name=result['manifest'],expected_manifest_sha256=result['manifest'][:-5])['status']=='OFFLINE_REPLAY_VERIFIED'
    with pytest.raises(ValueError):verify(partial,result)


def test_mutable_input_change_is_safe_but_changed_retained_reference_refuses(tmp_path):
    bundle,_=prepare(tmp_path);result=export(bundle)
    (bundle/'references.json').write_bytes(b' []\n')
    assert verify(bundle,result)['status']=='SYNTHETIC_SOURCE_REPLAY_REPRODUCED'
    binding=json.loads((bundle/result['binding']).read_bytes())
    (bundle/binding['request']['references']).write_bytes(b' []\n')
    with pytest.raises(ValueError):verify(bundle,result)


def test_rehashed_omitted_mapping_and_sidecar_refuses(tmp_path):
    bundle,_=prepare(tmp_path);result=export(bundle);binding=json.loads((bundle/result['binding']).read_bytes())
    name=binding['source_companion'];companion=json.loads((bundle/name).read_bytes());companion['source_entries'].pop()
    raw=encoded(companion);new=hashlib.sha256(raw).hexdigest();(bundle/(new+'.json')).write_bytes(raw)
    binding['source_companion']=new+'.json';binding['expected_source_companion_sha256']=new
    raw=encoded(binding);pin=hashlib.sha256(raw).hexdigest();(bundle/(pin+'.json')).write_bytes(raw)
    with pytest.raises(ValueError):exporter.verify_source_replay(bundle_root=bundle,binding_name=pin+'.json',expected_binding_sha256=pin)


def test_failed_publication_or_final_reproduction_never_acknowledges(tmp_path,monkeypatch):
    bundle,_=prepare(tmp_path);before={p.name:p.read_bytes() for p in bundle.iterdir()}
    def fail(*args,**kwargs):raise OSError('synthetic publication failure')
    monkeypatch.setattr(exporter,'_publish_replay',fail)
    with pytest.raises(OSError):export(bundle)
    assert before=={p.name:p.read_bytes() for p in bundle.iterdir()}


def test_final_recheck_failure_preserves_new_outputs_without_success(tmp_path,monkeypatch):
    bundle,_=prepare(tmp_path);before={p.name:p.read_bytes() for p in bundle.iterdir()}
    def fail(**kwargs):raise OSError('synthetic verification disconnect')
    monkeypatch.setattr(exporter,'verify_source_replay',fail)
    with pytest.raises(OSError):export(bundle)
    assert len(list(bundle.iterdir()))>len(before) and all((bundle/n).read_bytes()==b for n,b in before.items())


def test_detached_output_and_wrong_verification_pin_refuse(tmp_path):
    bundle,_=prepare(tmp_path);other=tmp_path/'other';other.mkdir()
    with pytest.raises(ValueError):exporter.export_source_replay(bundle_root=bundle,request_name='source-replay.json',output_root=other)
    assert list(other.iterdir())==[]
    result=export(bundle)
    with pytest.raises(ValueError):exporter.verify_source_replay(bundle_root=bundle,binding_name=result['binding'],expected_binding_sha256='0'*64)


def test_cli_export_and_reproduction_with_explicit_receipt_pin(tmp_path,capsys):
    bundle,_=prepare(tmp_path)
    assert exporter.main(['--bundle-root',str(bundle),'--request','source-replay.json','--output-root',str(bundle)])==0
    result=json.loads(capsys.readouterr().out)
    assert exporter.main(['--bundle-root',str(bundle),'--verify-binding',result['binding'],'--expected-binding-sha256',result['binding'][:-5]])==0
    assert json.loads(capsys.readouterr().out)['status']=='SYNTHETIC_SOURCE_REPLAY_REPRODUCED'


def test_dated_reference_and_future_corrections_preserve_original_decision(tmp_path):
    from test_retained_research import reference
    bundle,request=prepare(tmp_path);first_ref=reference(NOW)
    raw=json.dumps([first_ref]).encode();(bundle/'references.json').write_bytes(raw);request['expected_references_sha256']=hashlib.sha256(raw).hexdigest()
    (bundle/'source-replay.json').write_text(json.dumps(request));initial=export(bundle)
    old_report=json.loads((bundle/initial['report']).read_bytes());assert old_report['cases'][0]['report']['analysis']['observed_change_percent']==1
    assert old_report['cases'][0]['report']['analysis']['relative_volume'] is None
    future_ref={**first_ref,'previous_close':99,'available_at':(NOW+timedelta(seconds=25)).isoformat()}
    raw=json.dumps([first_ref,future_ref]).encode();(bundle/'references.json').write_bytes(raw);request['expected_references_sha256']=hashlib.sha256(raw).hexdigest()
    (bundle/'source-replay.json').write_text(json.dumps(request));updated=export(bundle);new_report=json.loads((bundle/updated['report']).read_bytes())
    assert encoded(old_report['cases'][0])==encoded(new_report['cases'][0])
    assert new_report['cases'][2]['report']['analysis']['observed_change_percent']==21.212
    assert initial['binding']!=updated['binding'] and (bundle/initial['binding']).exists()
    assert verify(bundle,initial)['status']=='SYNTHETIC_SOURCE_REPLAY_REPRODUCED'


def test_partial_publisher_failure_preserves_all_committed_evidence(tmp_path,monkeypatch):
    import scripts.observation_runtime.research_replay_export as legacy
    bundle,_=prepare(tmp_path);before={p.name:p.read_bytes() for p in bundle.iterdir()};publish=legacy.publish_research_text;count=0
    def partial(*args,**kwargs):
        nonlocal count
        count+=1
        if count==3:raise OSError('synthetic disk full after two writes')
        return publish(*args,**kwargs)
    monkeypatch.setattr(legacy,'publish_research_text',partial)
    with pytest.raises(OSError):export(bundle)
    assert count==3 and len(list(bundle.iterdir()))==len(before)+2
    assert all((bundle/n).read_bytes()==raw for n,raw in before.items())


def test_source_changed_between_preflight_and_publication_cannot_acknowledge(tmp_path,monkeypatch):
    bundle,request=prepare(tmp_path);publish=exporter._publish_replay
    receipt=json.loads((bundle/request['source_request']['archives'][0]['receipt']).read_bytes());source_path=bundle/receipt['source']['name']
    def changed(plan,output_root):
        source_path.write_bytes(source_path.read_bytes()+b' ')
        return publish(plan,output_root)
    monkeypatch.setattr(exporter,'_publish_replay',changed)
    with pytest.raises(ValueError):export(bundle)


def test_oversized_combined_plan_is_refused_before_writes(tmp_path,monkeypatch):
    bundle,_=prepare(tmp_path);plan_fn=exporter._plan_replay
    def oversized(*args,**kwargs):
        result=plan_fn(*args,**kwargs);result[0]['0'*64+'.json']=('x'*2_000_001,'.json');return result
    monkeypatch.setattr(exporter,'_plan_replay',oversized);before={p.name:p.read_bytes() for p in bundle.iterdir()}
    with pytest.raises(ValueError):export(bundle)
    assert before=={p.name:p.read_bytes() for p in bundle.iterdir()}


def test_complete_source_bundle_is_portable_without_original_root(tmp_path):
    bundle,_=prepare(tmp_path);result=export(bundle);copy=tmp_path/'copy';shutil.copytree(bundle,copy)
    assert verify(copy,result)==verify(bundle,result)


def test_cli_refusal_does_not_expose_supplied_paths_or_payload(tmp_path,capsys):
    bundle,request=prepare(tmp_path);request['references']='SYNTHETIC_PRIVATE_PATH.json';(bundle/'source-replay.json').write_text(json.dumps(request))
    with pytest.raises(SystemExit) as failure:exporter.main(['--bundle-root',str(bundle),'--request','source-replay.json','--output-root',str(bundle)])
    captured=capsys.readouterr();assert failure.value.code==2 and 'SYNTHETIC_PRIVATE_PATH' not in captured.err and not captured.out


def test_adding_future_source_archives_cannot_rewrite_original_exported_case(tmp_path):
    from test_retained_research import reference
    bundle,request=prepare(tmp_path);all_sources=request['source_request']['archives'][:]
    raw=json.dumps([reference(NOW)]).encode();(bundle/'references.json').write_bytes(raw);request['expected_references_sha256']=hashlib.sha256(raw).hexdigest()
    request['source_request']['archives']=all_sources[:1];request['decisions']=[NOW.isoformat()]
    (bundle/'source-replay.json').write_text(json.dumps(request));initial=export(bundle)
    original_case=json.loads((bundle/initial['report']).read_bytes())['cases'][0]
    request['source_request']['archives']=all_sources;request['decisions']=[(NOW+timedelta(seconds=s)).isoformat() for s in (0,20,30)]
    (bundle/'source-replay.json').write_text(json.dumps(request));updated=export(bundle)
    assert encoded(json.loads((bundle/updated['report']).read_bytes())['cases'][0])==encoded(original_case)
    assert verify(bundle,initial)['status']=='SYNTHETIC_SOURCE_REPLAY_REPRODUCED'
