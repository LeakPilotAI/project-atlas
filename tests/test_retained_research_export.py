import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest
from test_retained_research import populate

from scripts.observation_runtime import quality_report
from scripts.observation_runtime.market_replay import ReplayStore


def setup(tmp_path):
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);now,reference=populate(store)
        history=store.history('SPY',now=now)
    inputs={'history':history,'reference':reference}
    request={'schema':'ATLAS_RETAINED_RESEARCH_REQUEST_V1','now':now.isoformat()}
    for key,value in inputs.items():
        raw=json.dumps(value,sort_keys=True).encode();name=key+'.json';(tmp_path/name).write_bytes(raw)
        request[key]=name;request['expected_'+key+'_sha256']=hashlib.sha256(raw).hexdigest()
    (tmp_path/'request.json').write_text(json.dumps(request));output=tmp_path/'output';output.mkdir()
    return request,inputs,output


def run(root,output):return quality_report.export_retained_research(bundle_root=root,request_name='request.json',output_root=output)


def test_actual_research_export_cli_and_frontend_preserve_evidence(tmp_path,capsys):
    _,_,output=setup(tmp_path);result=run(tmp_path,output)
    before={p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert quality_report.main(['--bundle-root',str(tmp_path),'--request','request.json','--output-root',str(output),'--retained-research'])==0
    assert json.loads(capsys.readouterr().out)==result
    assert all(p.read_bytes()==raw for p,raw in before.items())
    report=json.loads((output/result['report']).read_bytes())
    assert report['analysis']['relative_volume']==2 and report['trading_authorized'] is False
    consumer=Path(__file__).resolve().parents[1]/'frontend/offline/market-replay/view.cjs'
    script="const c=require(process.argv[1]),f=require('node:fs');const r=c.parseRetainedResearch(f.readFileSync(process.argv[2],'utf8'));if(r.analysis.relative_volume!==2||r.trading_authorized!==false)process.exit(2);console.log('RETAINED_RESEARCH_CONSUMER_PASS');"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(consumer),str(output/result['report'])],capture_output=True,text=True,timeout=10,check=True)
    assert 'RETAINED_RESEARCH_CONSUMER_PASS' in checked.stdout


@pytest.mark.parametrize('fault',['history_pin','reference_pin','escape','future_reference','undated_reference','authority'])
def test_invalid_inputs_refuse_before_any_export(tmp_path,fault):
    request,inputs,output=setup(tmp_path)
    if fault in ('history_pin','reference_pin'):request['expected_'+fault.replace('_pin','')+'_sha256']='a'*64
    elif fault=='escape':request['history']='../history.json'
    elif fault=='authority':request['trading_authorized']=True
    else:
        reference=inputs['reference']
        if fault=='future_reference':reference['available_at']='2026-10-21T20:00:00+00:00'
        else:reference['source']='UNKNOWN'
        raw=json.dumps(reference).encode();(tmp_path/'reference.json').write_bytes(raw)
        request['expected_reference_sha256']=hashlib.sha256(raw).hexdigest()
    (tmp_path/'request.json').write_text(json.dumps(request))
    with pytest.raises(ValueError):run(tmp_path,output)
    assert list(output.iterdir())==[]


@pytest.mark.parametrize('stage',[2,3])
def test_late_export_failure_is_not_success_and_retains_outputs(tmp_path,monkeypatch,stage):
    _,_,output=setup(tmp_path);real=quality_report.publish_research_text;calls=0
    def fail(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==stage:raise OSError('synthetic research publication failure')
        return real(*args,**kwargs)
    monkeypatch.setattr(quality_report,'publish_research_text',fail)
    with pytest.raises(OSError):run(tmp_path,output)
    assert len(list(output.iterdir()))==stage-1


def test_research_mode_is_explicit_and_mutually_exclusive(tmp_path,capsys):
    _,_,output=setup(tmp_path)
    args=['--bundle-root',str(tmp_path),'--request','request.json','--output-root',str(output)]
    assert quality_report.main(args)==2
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'
    with pytest.raises(SystemExit) as raised:quality_report.main(args+['--quote-quality','--retained-research'])
    assert raised.value.code==2 and list(output.iterdir())==[]
