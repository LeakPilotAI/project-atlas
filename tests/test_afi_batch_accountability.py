import hashlib
import json
from pathlib import Path

import pytest
from app.backtest import forecast_report
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import (
    main,
    prepare_batch_accountability,
    run_bundle,
    run_forecast_batch,
)
from test_afi_dataset_integrity import encode
from test_afi_forecast_batch import inputs


def setup(tmp_path):
    args,plan=inputs(tmp_path);batch=run_forecast_batch(**args);index=args['output_root']/batch['index'];data=json.loads(index.read_bytes())
    prepared=tmp_path/'prepared';prepared.mkdir();reports=tmp_path/'reports';reports.mkdir()
    request={'schema':'AFI_BATCH_ACCOUNTABILITY_REQUEST_V1','asof':plan['asof'],'batch_plan':'batch.json',
             'batch_index':'output/'+index.name,'expected_index_sha256':hashlib.sha256(index.read_bytes()).hexdigest(),
             'outcomes':[{'forecast_sha256':r['forecast_sha256'],'history':[],'expected_head':None,'append':None} for r in data['items']]}
    (tmp_path/'request.json').write_bytes(encode(request))
    return args,plan,batch,data,request,prepared,reports


def prepare(root,output,request):
    (root/'request.json').write_bytes(encode(request))
    return prepare_batch_accountability(bundle_root=root,request_name='request.json',output_root=output)


def test_actual_multi_market_pending_resolved_corrected_workflow(tmp_path):
    import subprocess
    args,plan,_batch,index,request,prepared,reports=setup(tmp_path);original={p:p.read_bytes() for p in args['output_root'].iterdir()}
    def execute():
        result=prepare(tmp_path,prepared,request)
        assert result['outcome_appends_performed']==0
        return run_bundle(bundle_root=tmp_path,bundle_name='prepared/'+result['bundle'],output_root=reports)
    first=execute();assert first['scored_n']==0 and first['updated_heads']==[None]*3
    for instruction,spec in zip(request['outcomes'],plan['forecasts'],strict=True):
        instruction['append']={**{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},'outcome_asof':'2026-10-16T20:02:00+00:00'}
    pending=execute();assert pending['scored_n']==0
    for i,(instruction,spec) in enumerate(zip(request['outcomes'],plan['forecasts'],strict=True)):
        reference={**{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},'artifact':'reports/'+pending['updated_heads'][i]+'.json'}
        instruction.update(history=[reference],expected_head=pending['updated_heads'][i]);instruction['append']['outcome_asof']='2026-10-19T20:30:00+00:00'
    resolved=execute();assert resolved['scored_n']==3
    for i,(instruction,spec) in enumerate(zip(request['outcomes'],plan['forecasts'],strict=True)):
        instruction['history'].append({**{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},'artifact':'reports/'+resolved['updated_heads'][i]+'.json'})
        instruction['expected_head']=resolved['updated_heads'][i]
        manifest=json.loads((tmp_path/spec['dataset_manifest']).read_bytes());payload=json.loads((tmp_path/spec['dataset_records']).read_bytes())
        forecast=json.loads((args['output_root']/index['items'][i]['artifact']).read_bytes())['forecast'];target=forecast['target_at']
        old=next(r for r in payload['records'] if r['observed_at']==target)
        payload['records'].append(dict(old,record_id='batch-correction',revision='v2',available_at='2026-10-19T21:00:00+00:00',value=old['value']+10,raw_price=old['raw_price']+10))
        raw=encode(payload);manifest.update(version='v2',record_count=len(payload['records']),content_sha256=hashlib.sha256(raw).hexdigest(),acquired_at='2026-10-19T21:00:00+00:00',generated_at='2026-10-19T21:00:00+00:00')
        m=f'corrected-{i}-manifest.json';p=f'corrected-{i}-records.json';(tmp_path/m).write_bytes(encode(manifest));(tmp_path/p).write_bytes(raw)
        instruction['append'].update(dataset_manifest=m,dataset_records=p,outcome_asof='2026-10-19T22:00:00+00:00')
    final=execute();report=json.loads((reports/final['report']).read_bytes());assert report['forecast_n']==report['correction_n']==report['score']['scored_n']==3
    assert {r['asset_class'] for r in report['rows']}=={'US_EQUITY','ETF','CRYPTO'}
    assert all(p.read_bytes()==raw for p,raw in original.items())
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const v=require(process.argv[1]),f=require('node:fs'),c=require('node:crypto');v.verifyEnvelope(f.readFileSync(process.argv[2],'utf8'),s=>c.createHash('sha256').update(s).digest('hex')).then(r=>{if(r.forecast_n!==3||r.correction_n!==3)process.exit(2);console.log('VERIFIED_SYNTHETIC');}).catch(e=>{console.error(e.message);process.exit(3)});"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),str(reports/final['browser_export'])],capture_output=True,text=True,timeout=10,check=True)
    assert 'VERIFIED_SYNTHETIC' in checked.stdout


@pytest.mark.parametrize('change',['pin','count','status'])
def test_index_pin_and_reconstructed_evidence_refuse_tampering(tmp_path,change):
    _,_,_,_,request,prepared,_=setup(tmp_path)
    if change=='pin':request['expected_index_sha256']='a'*64
    else:
        path=tmp_path/request['batch_index'];data=json.loads(path.read_bytes())
        if change=='count':data['forecast_n']=True
        else:data['items'][0]['status']='NOT_ATTEMPTED'
        raw=encode(data)+b'\n';digest=hashlib.sha256(raw).hexdigest();new=path.parent/(digest+'.json');new.write_bytes(raw)
        request.update(batch_index='output/'+new.name,expected_index_sha256=digest)
    with pytest.raises(ForecastEvidenceRefused):prepare(tmp_path,prepared,request)
    assert not list(prepared.iterdir())


@pytest.mark.parametrize('change',['missing','duplicate','foreign'])
def test_exact_instruction_coverage_required(tmp_path,change):
    _,_,_,_,request,prepared,_=setup(tmp_path)
    if change=='missing':request['outcomes'].pop()
    elif change=='duplicate':request['outcomes'][1]=dict(request['outcomes'][0])
    else:request['outcomes'][1]['forecast_sha256']='a'*64
    with pytest.raises(ForecastEvidenceRefused):prepare(tmp_path,prepared,request)
    assert not list(prepared.iterdir())


def test_later_invalid_append_is_rejected_before_any_outcome_write(tmp_path):
    _,plan,_,index,request,prepared,reports=setup(tmp_path)
    for instruction,spec in zip(request['outcomes'],plan['forecasts'],strict=True):
        instruction['append']={**{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},'outcome_asof':'2026-10-19T20:30:00+00:00'}
    request['outcomes'][-1]['append']['outcome_asof']='2026-10-21T00:00:00+00:00'
    with pytest.raises(ForecastEvidenceRefused):prepare(tmp_path,prepared,request)
    assert not list(prepared.iterdir()) and not list(reports.iterdir())
    bundle={'schema':'AFI_ACCOUNTABILITY_BUNDLE_V2','asof':request['asof'],'forecasts':[
        {'artifact':'output/'+item['artifact'],**{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},
         **{k:instruction[k] for k in ('history','expected_head','append')}}
        for spec,item,instruction in zip(plan['forecasts'],index['items'],request['outcomes'],strict=True)]}
    (tmp_path/'invalid-bundle.json').write_bytes(encode(bundle))
    with pytest.raises(ForecastEvidenceRefused):run_bundle(bundle_root=tmp_path,bundle_name='invalid-bundle.json',output_root=reports)
    assert not list(reports.iterdir())


def test_preparation_is_idempotent_and_cli_does_not_append(tmp_path,capsys):
    args,_,_,_,request,prepared,_=setup(tmp_path);before={p:p.read_bytes() for p in args['output_root'].iterdir()}
    result=prepare(tmp_path,prepared,request);assert prepare(tmp_path,prepared,request)==result
    assert main(['--bundle-root',str(tmp_path),'--batch-accountability','request.json','--output-root',str(prepared)])==0
    assert json.loads(capsys.readouterr().out)['outcome_appends_performed']==0
    assert all(p.read_bytes()==raw for p,raw in before.items())


def test_provenance_publication_failure_never_reports_prepared(tmp_path,monkeypatch):
    _,_,_,_,request,prepared,_=setup(tmp_path);real=forecast_report.publish_research_text;count=0
    def fail(*a,**kw):
        nonlocal count
        count+=1
        if count==2:raise OSError(28,'synthetic full disk')
        return real(*a,**kw)
    monkeypatch.setattr(forecast_report,'publish_research_text',fail)
    with pytest.raises(OSError):prepare(tmp_path,prepared,request)
    assert len(list(prepared.iterdir()))==1


def test_missing_expected_head_cannot_hide_supplied_history(tmp_path):
    _,plan,_,_,request,prepared,reports=setup(tmp_path)
    for instruction,spec in zip(request['outcomes'],plan['forecasts'],strict=True):
        instruction['append']={**{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},'outcome_asof':'2026-10-16T20:02:00+00:00'}
    result=prepare(tmp_path,prepared,request);pending=run_bundle(bundle_root=tmp_path,bundle_name='prepared/'+result['bundle'],output_root=reports)
    request['outcomes'][0]['history']=[{**{k:plan['forecasts'][0][k] for k in ('dataset_manifest','dataset_records','source_archive')},'artifact':'reports/'+pending['updated_heads'][0]+'.json'}]
    request['outcomes'][0]['append']=None
    before={p:p.read_bytes() for p in prepared.iterdir()}
    with pytest.raises(ForecastEvidenceRefused):prepare(tmp_path,prepared,request)
    assert {p:p.read_bytes() for p in prepared.iterdir()}==before


def test_source_bound_batch_stays_bound_in_prepared_bundle(tmp_path):
    import app
    from app.backtest.forecast_source import package_source
    args,plan,_,_,request,prepared,_=setup(tmp_path)
    package=package_source(Path(app.__file__).resolve().parent.parent,tmp_path,release_id='batch-bridge-source',include=['app/backtest/forecast_report.py','app/backtest/forecast_outcomes.py'])
    for spec in plan['forecasts']:spec['source_archive']=package['archive']
    (tmp_path/'batch.json').write_bytes(encode(plan));batch=run_forecast_batch(**args);path=args['output_root']/batch['index'];index=json.loads(path.read_bytes())
    request.update(batch_index='output/'+path.name,expected_index_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   outcomes=[{'forecast_sha256':item['forecast_sha256'],'history':[],'expected_head':None,'append':None} for item in index['items']])
    result=prepare(tmp_path,prepared,request);bundle=json.loads((prepared/result['bundle']).read_bytes())
    assert all(item['source_archive']==package['archive'] for item in bundle['forecasts'])
