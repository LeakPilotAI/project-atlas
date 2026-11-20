import hashlib
import json
import os
import shutil
from datetime import UTC, datetime, timedelta

import pytest
from test_market_replay_integration import fixture

import scripts.observation_runtime.chart_archive as archive

NOW=datetime(2026,10,20,14,1,10,tzinfo=UTC)


def prepare(tmp_path,payload=None):
    inputs=tmp_path/'inputs';outputs=tmp_path/'outputs';inputs.mkdir();outputs.mkdir()
    raw=json.dumps(payload or fixture(NOW-timedelta(seconds=70))).encode()+b' \r\n'
    (inputs/'source.json').write_bytes(raw)
    request={'schema':'ATLAS_CHART_ARCHIVE_REQUEST_V1','source':'source.json',
        'expected_source_sha256':hashlib.sha256(raw).hexdigest(),'observed_at':NOW.isoformat(),'asset_class':'US_ETF'}
    (inputs/'request.json').write_text(json.dumps(request))
    return inputs,outputs,raw,request


def run(inputs,outputs):
    return archive.archive_chart_fixture(bundle_root=inputs,request_name='request.json',output_root=outputs)


def verify(root,result):
    return archive.verify_chart_archive(bundle_root=root,receipt_name=result['receipt'],expected_receipt_sha256=result['receipt_sha256'])


def test_archive_preserves_original_bytes_and_can_replay_after_portable_copy(tmp_path):
    inputs,outputs,raw,_=prepare(tmp_path);before={p.name:p.read_bytes() for p in inputs.iterdir()}
    result=run(inputs,outputs)
    assert result['status']=='SYNTHETIC_CHART_ARCHIVED' and result['bar_n']==1
    assert (outputs/(hashlib.sha256(raw).hexdigest()+'.json')).read_bytes()==raw
    assert verify(outputs,result)['status']=='SYNTHETIC_ARCHIVE_REPRODUCED'
    moved=tmp_path/'copied';shutil.copytree(outputs,moved)
    assert verify(moved,result)==verify(outputs,result)
    assert before=={p.name:p.read_bytes() for p in inputs.iterdir()}
    assert result['source_authenticated'] is False and result['startup_authorized'] is False


def test_exact_retry_preserves_all_five_artifacts(tmp_path):
    inputs,outputs,_,_=prepare(tmp_path);result=run(inputs,outputs)
    before={p.name:p.read_bytes() for p in outputs.iterdir()};assert len(before)==5
    assert run(inputs,outputs)==result and before=={p.name:p.read_bytes() for p in outputs.iterdir()}


@pytest.mark.parametrize('path',['../source.json','/source.json','x/../source.json','C:/source.json','x\\source.json'])
def test_unreviewed_relative_source_path_refuses_without_publication(tmp_path,path):
    inputs,outputs,_,request=prepare(tmp_path);request['source']=path;(inputs/'request.json').write_text(json.dumps(request))
    with pytest.raises(ValueError):run(inputs,outputs)
    assert list(outputs.iterdir())==[]


@pytest.mark.parametrize('where',['root','result','meta','indicators','quote'])
def test_unrequested_fields_cannot_be_copied_into_archive(tmp_path,where):
    payload=fixture(NOW-timedelta(seconds=70));result=payload['chart']['result'][0]
    target={'root':payload,'result':result,'meta':result['meta'],'indicators':result['indicators'],'quote':result['indicators']['quote'][0]}[where]
    target['unexpected_private_field']='SYNTHETIC_NOT_A_SECRET'
    inputs,outputs,_,_=prepare(tmp_path,payload)
    with pytest.raises(ValueError):run(inputs,outputs)
    assert list(outputs.iterdir())==[]


def test_changed_source_cannot_reuse_original_request_pin(tmp_path):
    inputs,outputs,raw,_=prepare(tmp_path);(inputs/'source.json').write_bytes(raw+b' ')
    with pytest.raises(ValueError):run(inputs,outputs)
    assert list(outputs.iterdir())==[]


@pytest.mark.parametrize('which',['source','report','dashboard','provenance'])
def test_missing_or_replaced_companion_never_verifies(tmp_path,which):
    inputs,outputs,_,_=prepare(tmp_path);result=run(inputs,outputs)
    receipt=json.loads((outputs/result['receipt']).read_bytes())
    target=outputs/receipt[which]['name'];target.write_bytes(b'{}')
    with pytest.raises(ValueError):verify(outputs,result)


def test_rehashed_report_and_receipt_cannot_override_source_reproduction(tmp_path):
    inputs,outputs,_,_=prepare(tmp_path);result=run(inputs,outputs)
    receipt=json.loads((outputs/result['receipt']).read_bytes())
    report=json.loads((outputs/receipt['report']['name']).read_bytes());report['rows'][0]['bar_close']=999
    raw=archive._text(report).encode();name=hashlib.sha256(raw).hexdigest()+'.json';(outputs/name).write_bytes(raw)
    receipt['report']={'name':name,'sha256':name[:-5]}
    raw=archive._text(receipt).encode();pin=hashlib.sha256(raw).hexdigest();(outputs/(pin+'.json')).write_bytes(raw)
    with pytest.raises(ValueError):archive.verify_chart_archive(bundle_root=outputs,receipt_name=pin+'.json',expected_receipt_sha256=pin)


def test_publication_failure_keeps_committed_source_and_does_not_acknowledge(tmp_path,monkeypatch):
    inputs,outputs,raw,_=prepare(tmp_path)
    def fail(*args,**kwargs):raise OSError('synthetic storage full')
    original=archive.export_chart_provenance;monkeypatch.setattr(archive,'export_chart_provenance',fail)
    with pytest.raises(OSError):run(inputs,outputs)
    assert [p.name for p in outputs.iterdir()]==[hashlib.sha256(raw).hexdigest()+'.json']
    monkeypatch.setattr(archive,'export_chart_provenance',original)
    assert run(inputs,outputs)['status']=='SYNTHETIC_CHART_ARCHIVED'


def test_receipt_publication_failure_preserves_prior_artifacts(tmp_path,monkeypatch):
    inputs,outputs,_,_=prepare(tmp_path);publish=archive.publish_research_text
    def fail_receipt(root,text,*,extension):
        if 'ATLAS_CHART_ARCHIVE_V1' in text:raise OSError('synthetic receipt failure')
        return publish(root,text,extension=extension)
    monkeypatch.setattr(archive,'publish_research_text',fail_receipt)
    with pytest.raises(OSError):run(inputs,outputs)
    assert len(list(outputs.iterdir()))==4


def test_hardlinked_input_refuses_even_with_matching_bytes(tmp_path):
    inputs,outputs,_,_=prepare(tmp_path);os.link(inputs/'source.json',inputs/'linked.json')
    with pytest.raises(ValueError):run(inputs,outputs)
    assert list(outputs.iterdir())==[]


def test_cli_archive_verify_and_wrong_pin_refusal(tmp_path,capsys):
    inputs,outputs,_,_=prepare(tmp_path)
    assert archive.main(['--bundle-root',str(inputs),'--request','request.json','--output-root',str(outputs)])==0
    result=json.loads(capsys.readouterr().out)
    args=['--bundle-root',str(outputs),'--verify-receipt',result['receipt'],'--expected-receipt-sha256',result['receipt_sha256']]
    assert archive.main(args)==0 and json.loads(capsys.readouterr().out)['status']=='SYNTHETIC_ARCHIVE_REPRODUCED'
    with pytest.raises(SystemExit) as error:archive.main(args[:-1]+['0'*64])
    assert error.value.code==2 and 'refused' in capsys.readouterr().err


def test_final_receipt_verification_failure_never_reports_success(tmp_path,monkeypatch):
    inputs,outputs,_,_=prepare(tmp_path)
    def fail(**kwargs):raise OSError('synthetic verification interruption')
    monkeypatch.setattr(archive,'verify_chart_archive',fail)
    with pytest.raises(OSError):run(inputs,outputs)
    assert len(list(outputs.iterdir()))==5


def test_partial_receipt_collision_is_preserved_and_retry_refuses(tmp_path,monkeypatch):
    inputs,outputs,_,_=prepare(tmp_path);publish=archive.publish_research_text
    def interrupt(root,text,*,extension):
        if 'ATLAS_CHART_ARCHIVE_V1' in text:
            raw=text.encode();target=outputs/(hashlib.sha256(raw).hexdigest()+'.json');target.write_bytes(raw[:20])
            raise OSError('synthetic interrupted write')
        return publish(root,text,extension=extension)
    monkeypatch.setattr(archive,'publish_research_text',interrupt)
    with pytest.raises(OSError):run(inputs,outputs)
    before={p.name:p.read_bytes() for p in outputs.iterdir()}
    monkeypatch.setattr(archive,'publish_research_text',publish)
    with pytest.raises(ValueError):run(inputs,outputs)
    assert before=={p.name:p.read_bytes() for p in outputs.iterdir()}


def test_missing_source_companion_is_not_an_empty_success(tmp_path):
    inputs,outputs,_,_=prepare(tmp_path);result=run(inputs,outputs)
    receipt=json.loads((outputs/result['receipt']).read_bytes());moved=tmp_path/'incomplete';moved.mkdir()
    for path in outputs.iterdir():
        if path.name!=receipt['source']['name']:shutil.copy2(path,moved/path.name)
    with pytest.raises(ValueError):verify(moved,result)


def test_archive_original_reproduces_existing_api_and_dashboard_consumer(tmp_path):
    import asyncio
    import sqlite3
    import subprocess
    from pathlib import Path

    import httpx

    from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app

    inputs,outputs,_,_=prepare(tmp_path);result=run(inputs,outputs)
    assert verify(outputs,result)['bar_n']==1
    receipt=json.loads((outputs/result['receipt']).read_bytes())
    retained=(outputs/receipt['source']['name']).read_bytes()
    async def scenario():
        with sqlite3.connect(':memory:') as db:
            store=ReplayStore(db);store.ingest(json.loads(retained),observed_at=receipt['observed_at'],asset_class=receipt['asset_class'])
            app=create_replay_app(store,symbols=['SPY','MISSING'],clock=lambda:NOW)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data');assert response.status_code==200
                page=await client.get('/');assert 'Synthetic fixtures only' in page.text
            return response.content
    output=tmp_path/'actual-api.json';output.write_bytes(asyncio.run(scenario()))
    root=Path(__file__).resolve().parents[1]
    code="const fs=require('node:fs');const v=require(process.argv[1]);const r=v.parseExport(fs.readFileSync(process.argv[2],'utf8'));if(r.rows.find(x=>x.symbol==='SPY').price!==101||r.network_authorized!==false)throw Error('contract');process.stdout.write('PASS')"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(root/'frontend/offline/market-replay/view.cjs'),str(output)],capture_output=True,text=True,timeout=10,check=False)
    assert checked.returncode==0 and checked.stdout=='PASS',checked.stderr


def test_checked_in_archive_is_exact_actual_export(tmp_path):
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'tests/fixtures/chart-archive-v1'
    selected=json.loads((root/'selection.json').read_bytes())
    checked=archive.verify_chart_archive(bundle_root=root,receipt_name=selected['receipt'],expected_receipt_sha256=selected['expectedReceiptSha256'])
    receipt=json.loads((root/selected['receipt']).read_bytes());inputs=tmp_path/'input';outputs=tmp_path/'output';inputs.mkdir();outputs.mkdir()
    source=root/receipt['source']['name'];shutil.copy2(source,inputs/'source.json')
    request={'schema':'ATLAS_CHART_ARCHIVE_REQUEST_V1','source':'source.json','expected_source_sha256':receipt['source']['sha256'],
             'observed_at':receipt['observed_at'],'asset_class':receipt['asset_class']}
    (inputs/'request.json').write_text(json.dumps(request));result=run(inputs,outputs)
    assert result['receipt_sha256']==selected['expectedReceiptSha256']==checked['receipt_sha256']
    assert sorted(p.name for p in outputs.iterdir())==selected['files']
    assert all((outputs/name).read_bytes()==(root/name).read_bytes() for name in selected['files'])


def test_actual_archive_export_is_consumed_by_new_browser_contract(tmp_path):
    import subprocess
    from pathlib import Path
    inputs,outputs,_,_=prepare(tmp_path);result=run(inputs,outputs)
    root=Path(__file__).resolve().parents[1]
    code="const fs=require('node:fs'),path=require('node:path'),api=require(process.argv[1]);const files=fs.readdirSync(process.argv[2]).map(name=>({name,bytes:new Uint8Array(fs.readFileSync(path.join(process.argv[2],name)))}));api.verifyArchive(files,process.argv[3]).then(r=>{if(r.status!=='BYTE_INTEGRITY_ONLY'||r.report.rows[0].bar_close!==101||r.python_reproduction_verified!==false)throw Error('contract');process.stdout.write('PASS')}).catch(()=>process.exitCode=1)"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(root/'frontend/offline/market-replay/chart-archive.cjs'),str(outputs),result['receipt_sha256']],capture_output=True,text=True,timeout=10,check=False)
    assert checked.returncode==0 and checked.stdout=='PASS',checked.stderr
