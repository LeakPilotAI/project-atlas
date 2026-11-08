"""Actual Python microsecond receipts/asof survive SQLite, ASGI and Node parsing."""
import asyncio
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from test_market_replay_integration import fixture

from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app


@pytest.mark.parametrize('microseconds',[0,1,99,100,999,123456,999999])
def test_backend_receipt_precision_matches_actual_offline_browser(tmp_path,microseconds):
    stamp=datetime(2026,10,20,14,tzinfo=UTC)
    now=stamp+timedelta(seconds=70,microseconds=microseconds)
    path=tmp_path/'fixture.sqlite'
    with sqlite3.connect(path) as connection:
        store=ReplayStore(connection)
        store.ingest(fixture(stamp),observed_at=now,asset_class='US_ETF')
        store.ingest_quote({'quoteResponse':{'error':None,'result':[{'symbol':'SPY','currency':'USD','regularMarketTime':int((stamp+timedelta(seconds=68)).timestamp()),'regularMarketPrice':101,'exchangeDataDelayedBy':0}]}},observed_at=now,asset_class='US_ETF')
    with sqlite3.connect(path) as connection:
        store=ReplayStore(connection)
        app=create_replay_app(store,symbols=['SPY'],clock=lambda:now)
        async def response():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://in-process.invalid') as client:
                value=await client.get('/api/market-data')
                assert value.status_code==200
                return value.json()
        value=asyncio.run(response())
        assert value['asof']==now.isoformat()
        assert value['rows'][0]['observed_at']==now.isoformat()
        assert value['quote_rows'][0]['observed_at']==now.isoformat()
        assert value['rows'][0]['age_seconds']==(10000000+microseconds)/1000000
        assert value['quote_rows'][0]['age_seconds']==(2000000+microseconds)/1000000
    output=tmp_path/'response.json'
    output.write_text(json.dumps(value),encoding='utf-8')
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/market-replay/view.cjs'
    code="const fs=require('node:fs');const api=require(process.argv[1]);const v=api.parseExport(fs.readFileSync(process.argv[2],'utf8'));if(v.network_authorized!==false)throw Error('authority');"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(viewer),str(output)],capture_output=True,text=True,timeout=20,check=False)
    assert result.returncode==0,result.stdout+result.stderr
