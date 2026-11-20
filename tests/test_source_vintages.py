import hashlib
import json
from datetime import timedelta

import pytest
from test_chart_archive import NOW, prepare, run

import scripts.observation_runtime.source_vintages as bridge
from scripts.observation_runtime.bar_vintages import project_history
from scripts.observation_runtime.research_replay import encoded


def source(tmp_path,name,seconds=0,price=101,symbol='SPY',asset='US_ETF'):
    parent=tmp_path/name;parent.mkdir();inputs,outputs,_,request=prepare(parent)
    payload=json.loads((inputs/'source.json').read_bytes());result=payload['chart']['result'][0]
    result['meta']['symbol']=symbol;quote=result['indicators']['quote'][0];quote['close']=[price];quote['high']=[max(price,102)]
    raw=json.dumps(payload).encode();(inputs/'source.json').write_bytes(raw)
    request.update(expected_source_sha256=hashlib.sha256(raw).hexdigest(),observed_at=(NOW+timedelta(seconds=seconds)).isoformat(),asset_class=asset)
    (inputs/'request.json').write_text(json.dumps(request));result=run(inputs,outputs)
    return outputs,{'receipt':result['receipt'],'expected_sha256':result['receipt_sha256']}


def setup(tmp_path,specs):
    bundle=tmp_path/'bundle';bundle.mkdir();entries=[]
    for folder,spec in specs:
        entries.append(spec)
        for path in folder.iterdir():
            target=bundle/path.name
            if target.exists():assert target.read_bytes()==path.read_bytes()
            else:target.write_bytes(path.read_bytes())
    request={'schema':'ATLAS_SOURCE_VINTAGES_REQUEST_V1','symbol':'SPY','asof':(NOW+timedelta(minutes=1)).isoformat(),'archives':entries}
    (bundle/'request.json').write_text(json.dumps(request));return bundle,request


def build(bundle):return bridge.build_source_vintages(bundle_root=bundle,request_name='request.json')


def test_actual_original_correction_confirmation_maps_to_exact_source_and_earlier_view(tmp_path):
    original=source(tmp_path,'original');corrected=source(tmp_path,'corrected',20,120);confirmed=source(tmp_path,'confirmed',30,120)
    bundle,request=setup(tmp_path,[original,corrected,confirmed]);result=build(bundle)
    archive=result['archive'];assert result['source_n']==3 and archive['record_n']==3
    assert [entry['first_sequence'] for entry in result['source_entries']]==[1,2,3]
    assert [entry['source_receipt_sha256'] for entry in result['source_entries']]==[e['expected_sha256'] for e in request['archives']]
    assert project_history(archive,now=NOW)['history']['rows'][0]['close']==101
    corrected_view=project_history(archive,now=NOW+timedelta(seconds=20))
    assert corrected_view['history']['rows'][0]['close']==120 and corrected_view['correction_n']==1
    confirmed_view=project_history(archive,now=NOW+timedelta(seconds=30))
    assert confirmed_view['confirmation_n']==1 and confirmed_view['history']['rows'][0]['observed_at']==(NOW+timedelta(seconds=20)).isoformat()
    request['archives']=request['archives'][:1];(bundle/'request.json').write_text(json.dumps(request))
    early=build(bundle)
    assert project_history(early['archive'],now=NOW)==project_history(archive,now=NOW)
    assert result['source_authenticated'] is False and result['monitoring_completeness_verified'] is False


@pytest.mark.parametrize('fault',['duplicate','reorder','tie','symbol','asset','future'])
def test_invalid_source_scope_refuses_before_companion_output(tmp_path,fault):
    first=source(tmp_path,'first');second=source(tmp_path,'second',0 if fault=='tie' else 20,120,
         symbol='QQQ' if fault=='symbol' else 'SPY',asset='US_EQUITY' if fault=='asset' else 'US_ETF')
    bundle,request=setup(tmp_path,[first,second])
    if fault=='duplicate':request['archives'][1]=request['archives'][0]
    if fault=='reorder':request['archives'].reverse()
    if fault=='future':request['asof']=NOW.isoformat()
    (bundle/'request.json').write_text(json.dumps(request));before={p.name:p.read_bytes() for p in bundle.iterdir()}
    with pytest.raises(ValueError):build(bundle)
    assert before=={p.name:p.read_bytes() for p in bundle.iterdir()}


def test_companion_reproduces_sources_and_rehashed_mapping_tamper_refuses(tmp_path):
    bundle,_=setup(tmp_path,[source(tmp_path,'first'),source(tmp_path,'second',20,120)])
    result=bridge.export_source_vintages(bundle_root=bundle,request_name='request.json',output_root=bundle)
    raw=(bundle/result['companion']).read_bytes();pin=hashlib.sha256(raw).hexdigest()
    kwargs={'bundle_root':bundle,'companion_name':result['companion'],'expected_sha256':pin}
    assert bridge.verify_source_vintages(**kwargs)['record_n']==2
    value=json.loads(raw);value['source_entries'].pop();tampered=encoded(value);identity=hashlib.sha256(tampered).hexdigest();(bundle/(identity+'.json')).write_bytes(tampered)
    with pytest.raises(ValueError):bridge.verify_source_vintages(bundle_root=bundle,companion_name=identity+'.json',expected_sha256=identity)
    before={p.name:p.read_bytes() for p in bundle.iterdir()}
    assert bridge.export_source_vintages(bundle_root=bundle,request_name='request.json',output_root=bundle)==result
    assert before=={p.name:p.read_bytes() for p in bundle.iterdir()}


def test_shared_reader_budget_is_not_reset_per_source(tmp_path,monkeypatch):
    bundle,_=setup(tmp_path,[source(tmp_path,'first'),source(tmp_path,'second',20,120)]);original=bridge._review_chart_archive;seen=[]
    def review(reader,name,pin):
        seen.append((id(reader),reader.budget));return original(reader,name,pin)
    monkeypatch.setattr(bridge,'_review_chart_archive',review);build(bundle)
    assert len(seen)==2 and seen[0][0]==seen[1][0] and seen[1][1]<seen[0][1]
    reader=bridge.BundleReader(bundle);reader.budget=1
    with pytest.raises(ValueError):bridge._build(reader,json.loads((bundle/'request.json').read_bytes()))


def test_missing_source_or_publication_failure_never_acknowledges(tmp_path,monkeypatch):
    bundle,_=setup(tmp_path,[source(tmp_path,'first')]);before={p.name:p.read_bytes() for p in bundle.iterdir()}
    def fail(*args,**kwargs):raise OSError('synthetic full disk')
    monkeypatch.setattr(bridge,'publish_research_text',fail)
    with pytest.raises(OSError):bridge.export_source_vintages(bundle_root=bundle,request_name='request.json',output_root=bundle)
    assert before=={p.name:p.read_bytes() for p in bundle.iterdir()}
    elsewhere=tmp_path/'elsewhere';elsewhere.mkdir()
    with pytest.raises(ValueError):bridge.export_source_vintages(bundle_root=bundle,request_name='request.json',output_root=elsewhere)
    assert list(elsewhere.iterdir())==[]


def test_missing_declared_source_is_not_treated_as_empty_history(tmp_path):
    bundle,request=setup(tmp_path,[source(tmp_path,'first')]);spec=request['archives'][0]
    receipt=json.loads((bundle/spec['receipt']).read_bytes());missing=receipt['source']['name']
    partial=tmp_path/'partial';partial.mkdir()
    for path in bundle.iterdir():
        if path.name!=missing:(partial/path.name).write_bytes(path.read_bytes())
    with pytest.raises(ValueError):build(partial)
    assert not (partial/missing).exists()


def test_final_reproduction_failure_leaves_companion_without_success(tmp_path,monkeypatch):
    bundle,_=setup(tmp_path,[source(tmp_path,'first')]);before={p.name:p.read_bytes() for p in bundle.iterdir()}
    def fail(**kwargs):raise OSError('synthetic readback disconnected')
    monkeypatch.setattr(bridge,'verify_source_vintages',fail)
    with pytest.raises(OSError):bridge.export_source_vintages(bundle_root=bundle,request_name='request.json',output_root=bundle)
    assert all((bundle/name).read_bytes()==raw for name,raw in before.items())
    assert len(list(bundle.iterdir()))==len(before)+1


def test_archived_sources_to_temporal_replay_to_existing_frontend(tmp_path):
    import subprocess
    from pathlib import Path

    from scripts.observation_runtime.bar_vintages import (
        browser_vintages,
        replay_vintages,
    )

    bundle,_=setup(tmp_path,[source(tmp_path,'first'),source(tmp_path,'second',20,120),source(tmp_path,'third',30,120)])
    companion=build(bundle);report=replay_vintages(companion['archive'],[],[NOW,NOW+timedelta(seconds=20),NOW+timedelta(seconds=30)])
    assert [c['correction_n'] for c in report['cases']]==[0,1,1]
    assert [c['confirmation_n'] for c in report['cases']]==[0,0,1]
    assert report['planned_decision_n']==3 and report['status_counts']['INSUFFICIENT_REFERENCE']==3
    output=tmp_path/'actual-source-vintage-browser.json';output.write_text(browser_vintages(report))
    root=Path(__file__).resolve().parents[1]
    code="const fs=require('node:fs'),api=require(process.argv[1]);api.verifyVintageReplay(fs.readFileSync(process.argv[2],'utf8')).then(r=>{if(r.planned_decision_n!==3||r.cases[0].correction_n!==0||r.cases[2].confirmation_n!==1)throw Error('contract');process.stdout.write('PASS')}).catch(()=>process.exitCode=1)"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(root/'frontend/offline/market-replay/view.cjs'),str(output)],capture_output=True,text=True,timeout=10,check=False)
    assert checked.returncode==0 and checked.stdout=='PASS',checked.stderr
