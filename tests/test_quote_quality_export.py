import hashlib
import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_quote_quality import populate

from scripts.observation_runtime import quality_report
from scripts.observation_runtime.market_replay import ReplayStore


def setup(tmp_path):
    now=datetime(2026,10,20,14,0,10,tzinfo=UTC)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);symbols=populate(store,now)
        snapshot={**store.snapshot(symbols,now=now),'quote_rows':store.quote_snapshot(symbols,now=now)}
    raw=json.dumps(snapshot,sort_keys=True).encode();(tmp_path/'snapshot.json').write_bytes(raw)
    request={'schema':'ATLAS_QUOTE_QUALITY_REQUEST_V1','now':now.isoformat(),'snapshot':'snapshot.json',
             'expected_snapshot_sha256':hashlib.sha256(raw).hexdigest()}
    (tmp_path/'request.json').write_text(json.dumps(request));output=tmp_path/'output';output.mkdir()
    return request,snapshot,output


def run(root,output):return quality_report.export_quote_quality(bundle_root=root,request_name='request.json',output_root=output)


def test_actual_export_cli_and_frontend_are_reusable_without_authority(tmp_path,capsys):
    _,_,output=setup(tmp_path);result=run(tmp_path,output)
    before={p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert quality_report.main(['--bundle-root',str(tmp_path),'--request','request.json','--output-root',str(output),'--quote-quality'])==0
    assert json.loads(capsys.readouterr().out)==result
    assert all(p.read_bytes()==raw for p,raw in before.items())
    report=json.loads((output/result['report']).read_bytes())
    assert report['status_counts']['DELAYED']==2 and all('price' not in row for row in report['rows'])
    provenance=json.loads((output/result['provenance']).read_bytes())
    assert provenance['scope']=='QUOTE_ROWS_ONLY_BAR_EVIDENCE_NOT_AUDITED'
    assert provenance['source_authenticated'] is False
    consumer=Path(__file__).resolve().parents[1]/'frontend/offline/market-replay/view.cjs'
    script="const c=require(process.argv[1]),f=require('node:fs');const r=c.parseQuoteQuality(f.readFileSync(process.argv[2],'utf8'));if(r.status_counts.DELAYED!==2||r.trading_authorized!==false)process.exit(2);console.log('QUOTE_EXPORT_CONSUMER_PASS');"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(consumer),str(output/result['report'])],capture_output=True,text=True,timeout=10,check=True)
    assert 'QUOTE_EXPORT_CONSUMER_PASS' in checked.stdout


@pytest.mark.parametrize('fault',['pin','escape','clock','authority','missing_quote'])
def test_invalid_quote_export_refuses_before_publication(tmp_path,fault):
    request,snapshot,output=setup(tmp_path)
    if fault=='pin':request['expected_snapshot_sha256']='a'*64
    elif fault=='escape':request['snapshot']='../snapshot.json'
    elif fault=='clock':request['now']='2026-10-20T14:01:10+00:00'
    else:
        if fault=='authority':snapshot['network_authorized']=True
        else:del snapshot['quote_rows']
        raw=json.dumps(snapshot).encode();(tmp_path/'snapshot.json').write_bytes(raw)
        request['expected_snapshot_sha256']=hashlib.sha256(raw).hexdigest()
    (tmp_path/'request.json').write_text(json.dumps(request))
    with pytest.raises(ValueError):run(tmp_path,output)
    assert list(output.iterdir())==[]


@pytest.mark.parametrize('stage',[2,3])
def test_quote_export_failure_preserves_partial_evidence(tmp_path,monkeypatch,stage):
    _,_,output=setup(tmp_path);real=quality_report.publish_research_text;calls=0
    def fail(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==stage:raise OSError('synthetic quote publication failure')
        return real(*args,**kwargs)
    monkeypatch.setattr(quality_report,'publish_research_text',fail)
    with pytest.raises(OSError):run(tmp_path,output)
    assert len(list(output.iterdir()))==stage-1


def test_bar_default_never_silently_accepts_quote_request(tmp_path,capsys):
    _,_,output=setup(tmp_path)
    assert quality_report.main(['--bundle-root',str(tmp_path),'--request','request.json','--output-root',str(output)])==2
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'
    assert list(output.iterdir())==[]
