import json
from pathlib import Path

import pytest
from app.backtest import forecast_artifacts, forecast_report
from app.backtest.forecast_baselines import PROBABILITY_METHOD
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import (
    ForecastBatchIncomplete,
    main,
    run_forecast_batch,
)
from test_afi_baselines import history
from test_afi_dataset_integrity import ASOF, encode, fixture, review


def inputs(tmp_path):
    output=tmp_path/'output';output.mkdir();specs=[]
    for asset,kind in [('US_EQUITY:AAPL','US_EQUITY'),('ETF:SPY','ETF'),('CRYPTO:BTC-USD','CRYPTO')]:
        if kind=='CRYPTO':dataset=history();lookback=5
        else:
            m,p=fixture();m['assets'][0].update(asset_id=asset,asset_class=kind);p['universe'][0]['asset_id']=asset
            dates=['2026-10-14T20:00:00+00:00','2026-10-15T20:00:00+00:00','2026-10-16T20:00:00+00:00','2026-10-19T20:00:00+00:00']
            p['records']=[dict(p['records'][0],record_id=f'r{i}',asset_id=asset,observed_at=t,available_at=t,value=100+i,raw_price=100+i) for i,t in enumerate(dates)]
            m.update(period_start=dates[0],period_end=dates[-1]);dataset=review(m,p);lookback=2
        name=kind.lower();(tmp_path/(name+'-manifest.json')).write_bytes(dataset.manifest_bytes);(tmp_path/(name+'-records.json')).write_bytes(dataset.payload_bytes)
        specs.append({'dataset_manifest':name+'-manifest.json','dataset_records':name+'-records.json','source_archive':None,
                      'asset_id':asset,'issued_at':'2026-10-16T20:01:00+00:00','method':'NO_CHANGE','lookback':lookback,'horizon':'1D',
                      'interval':None,'probability_method':PROBABILITY_METHOD})
    plan={'schema':'AFI_FORECAST_BATCH_V1','asof':ASOF.isoformat(),'forecasts':specs}
    (tmp_path/'batch.json').write_bytes(encode(plan))
    return {'bundle_root':tmp_path,'batch_name':'batch.json','output_root':output},plan


def test_actual_equity_etf_crypto_batch_preserves_calendars_and_retries(tmp_path):
    args,plan=inputs(tmp_path);result=run_forecast_batch(**args);root=args['output_root']
    index=json.loads((root/result['index']).read_text(encoding='utf-8'))
    assert result['forecast_n']==result['unique_asset_n']==3 and index['ranking'] is index['pooled_price_error'] is None
    assert all(item['status']=='PUBLISHED_VERIFIED' for item in index['items'])
    for item in index['items']:
        artifact=json.loads((root/item['artifact']).read_text(encoding='utf-8'));target=artifact['forecast']['target_at']
        assert target==('2026-10-17T00:00:00+00:00' if item['asset_class']=='CRYPTO' else '2026-10-19T20:00:00+00:00')
    before={p:p.read_bytes() for p in root.iterdir()};assert run_forecast_batch(**args)==result
    assert all(p.read_bytes()==raw for p,raw in before.items())
    html=(root/result['dashboard']).read_text(encoding='utf-8');assert all(s['asset_id'] in html for s in plan['forecasts'])


@pytest.mark.parametrize('failure',['duplicate','traversal','unknown_asset','probability','oversized','unknown_field'])
def test_complete_preflight_refuses_bad_plan_before_any_output(tmp_path,failure):
    args,plan=inputs(tmp_path)
    if failure=='duplicate':plan['forecasts'].append(dict(plan['forecasts'][0]))
    elif failure=='traversal':plan['forecasts'][1]['dataset_manifest']='../outside.json'
    elif failure=='unknown_asset':plan['forecasts'][2]['asset_id']='CRYPTO:UNKNOWN'
    elif failure=='probability':plan['forecasts'][1]['probability_method']='MAGIC'
    elif failure=='oversized':plan['forecasts']*=22
    else:plan['forecasts'][1]['live_capital_allowed']=True
    (tmp_path/'batch.json').write_bytes(encode(plan))
    with pytest.raises(ForecastEvidenceRefused):run_forecast_batch(**args)
    assert not list(args['output_root'].iterdir())


def test_second_item_disk_full_keeps_verified_first_and_uncertain_second(tmp_path,monkeypatch):
    args,_=inputs(tmp_path);real=forecast_artifacts.publish_forecast;count=0
    def fail(*a,**kw):
        nonlocal count
        count+=1
        if count==2:raise OSError(28,'synthetic disk full')
        return real(*a,**kw)
    monkeypatch.setattr(forecast_artifacts,'publish_forecast',fail)
    with pytest.raises(ForecastBatchIncomplete) as caught:run_forecast_batch(**args)
    result=caught.value.result;assert caught.value.__cause__.errno==28
    assert [r['status'] for r in result['items']]==['PUBLISHED_VERIFIED','UNCERTAIN_PUBLICATION','NOT_ATTEMPTED']
    assert result['failure_report'] and (args['output_root']/result['failure_report']).is_file()
    assert (args['output_root']/result['items'][0]['artifact']).is_file()


@pytest.mark.parametrize('stage',['DASHBOARD_PUBLICATION','INDEX_PUBLICATION'])
def test_derived_output_failure_never_becomes_complete(tmp_path,monkeypatch,stage):
    args,_=inputs(tmp_path);real=forecast_report.publish_research_text
    def fail(*a,**kw):
        if kw['extension']==('.html' if stage=='DASHBOARD_PUBLICATION' else '.json'):raise OSError(5,'synthetic publication failure')
        return real(*a,**kw)
    monkeypatch.setattr(forecast_report,'publish_research_text',fail)
    with pytest.raises(ForecastBatchIncomplete) as caught:run_forecast_batch(**args)
    assert caught.value.result['status']=='INCOMPLETE' and caught.value.result['failed_stage']==stage
    assert all(r['status']=='PUBLISHED_VERIFIED' for r in caught.value.result['items'])


def test_failure_evidence_write_failure_preserves_original_context(tmp_path,monkeypatch):
    args,_=inputs(tmp_path)
    def fail_forecast(*a,**kw):raise OSError(28,'original synthetic failure')
    def fail_evidence(*a,**kw):raise PermissionError('synthetic evidence denial')
    monkeypatch.setattr(forecast_artifacts,'publish_forecast',fail_forecast);monkeypatch.setattr(forecast_report,'publish_research_text',fail_evidence)
    with pytest.raises(ForecastBatchIncomplete) as caught:run_forecast_batch(**args)
    assert caught.value.__cause__.errno==28 and caught.value.result['failure_report'] is None
    assert caught.value.result['failure_report_error_type']=='PermissionError'


def test_actual_cli_batch_dispatch(tmp_path,capsys):
    args,_=inputs(tmp_path)
    assert main(['--bundle-root',str(tmp_path),'--forecast-batch','batch.json','--output-root',str(args['output_root'])])==0
    assert json.loads(capsys.readouterr().out)['status']=='OFFLINE_FORECAST_BATCH_COMPLETE'


def test_distinct_source_archives_remain_bound_per_item(tmp_path):
    import app
    from app.backtest.forecast_source import package_source
    args,plan=inputs(tmp_path)
    for i in range(2):
        package=package_source(Path(app.__file__).resolve().parent.parent,tmp_path,release_id=f'batch-source-{i}',include=['app/backtest/forecast_report.py'])
        plan['forecasts'][i]['source_archive']=package['archive']
    (tmp_path/'batch.json').write_bytes(encode(plan));result=run_forecast_batch(**args)
    index=json.loads((args['output_root']/result['index']).read_text(encoding='utf-8'))
    assert index['items'][0]['release_source_sha256']!=index['items'][1]['release_source_sha256']
    assert index['items'][2]['release_source_sha256'] is None
