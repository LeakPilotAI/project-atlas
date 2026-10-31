"""Actual extracted market-research source, without a server or provider connection."""
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from test_offline_candidate_packaging import candidate, fixture_root


@pytest.mark.parametrize('asset_class,symbol', [('US_EQUITY', 'AAPL'), ('US_ETF', 'SPY')])
@pytest.mark.parametrize('stamp,session', [
    ('2026-10-20T12:00:00+00:00', 'PRE_MARKET'),
    ('2026-10-20T14:00:00+00:00', 'REGULAR'),
    ('2026-10-20T21:00:00+00:00', 'AFTER_HOURS'),
    ('2026-11-27T18:00:00+00:00', 'AFTER_HOURS'),
    ('2026-11-02T14:30:00+00:00', 'REGULAR'),
])
def test_extracted_market_pipeline(tmp_path, monkeypatch, asset_class, symbol, stamp, session):
    root, _ = fixture_root(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[1]
    selected = ['backend/app/__init__.py', 'frontend/offline/market-replay/view.cjs']
    for directory in ['backend/app/investment', 'scripts/observation_runtime']:
        selected.extend(str(p.relative_to(repo)).replace('\\', '/') for p in sorted((repo / directory).glob('*.py')))
    for name in selected:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repo / name).read_bytes())
    previous = candidate.git
    monkeypatch.setattr(candidate, 'git', lambda *args: previous(*args) + selected if '--others' in args else previous(*args))
    destination = tmp_path / 'candidate'
    candidate.build(destination)
    extracted = tmp_path / 'clean'
    with zipfile.ZipFile(destination / 'atlas-source.zip') as bundle:
        bundle.extractall(extracted)
    code = '''
import sys,os,json,pathlib,sqlite3,asyncio
from datetime import datetime,timedelta
root=pathlib.Path.cwd()
def guard(event,args):
    if event=='socket.connect' and sys._getframe(1).f_code.co_name!='_fallback_socketpair':raise PermissionError('external transport prohibited')
    if event=='open' and isinstance(args[0],(str,bytes)) and pathlib.Path(os.fsdecode(args[0])).name=='.env':raise PermissionError('credentials prohibited')
sys.addaudithook(guard)
from scripts.observation_runtime.market_replay import ReplayStore,create_replay_app
import app.investment.offline_research as research
import scripts.observation_runtime.market_replay as replay
import httpx
assert pathlib.Path(research.__file__).resolve().is_relative_to(root)
assert pathlib.Path(replay.__file__).resolve().is_relative_to(root)
asset,symbol,stamp,session=sys.argv[1:]
ts=datetime.fromisoformat(stamp);now=ts+timedelta(seconds=70)
payload={'chart':{'error':None,'result':[{'meta':{'symbol':symbol,'currency':'USD','dataGranularity':'1m','instrumentType':'ETF' if asset=='US_ETF' else 'EQUITY','exchangeTimezoneName':'America/New_York'},'timestamp':[int(ts.timestamp())],'indicators':{'quote':[{'open':[100],'high':[102],'low':[99],'close':[101],'volume':[120]}]}}]}}
prefix={'PRE_MARKET':'preMarket','REGULAR':'regularMarket','AFTER_HOURS':'postMarket'}[session]
quote={'quoteResponse':{'error':None,'result':[{'symbol':symbol,'currency':'USD','quoteType':'ETF' if asset=='US_ETF' else 'EQUITY','exchangeTimezoneName':'America/New_York','exchangeDataDelayedBy':0,prefix+'Time':int((now-timedelta(seconds=5)).timestamp()),prefix+'Price':101.25}]}}
path=root/'fixture.sqlite'
with sqlite3.connect(path) as db:
    store=ReplayStore(db)
    assert store.ingest(payload,observed_at=now,asset_class=asset)==1
    assert store.ingest(payload,observed_at=now+timedelta(seconds=1),asset_class=asset)==0
    assert store.ingest_quote(quote,observed_at=now,asset_class=asset)==1
    assert store.ingest_quote(quote,observed_at=now+timedelta(seconds=1),asset_class=asset)==0
with sqlite3.connect(path) as db:
    store=ReplayStore(db);app=create_replay_app(store,symbols=[symbol,'MISSING'],clock=lambda:now)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://in-process.invalid') as client:
            response=await client.get('/api/market-data');assert response.status_code==200
            value=response.json();row=next(r for r in value['rows'] if r['symbol']==symbol)
            assert (row['session'],row['status'],row['price'])==(session,'FRESH',101)
            assert next(r for r in value['rows'] if r['symbol']=='MISSING')['status']=='UNAVAILABLE'
            quote_row=next(r for r in value['quote_rows'] if r['symbol']==symbol)
            assert (quote_row['session'],quote_row['status'],quote_row['price'])==(session,'FRESH',101.25)
            assert quote_row['price_kind']=='REFERENCE_QUOTE_NOT_EXECUTABLE'
            assert quote_row['provider_delay_unit']=='UNVERIFIED_FIXTURE_METADATA'
            assert next(r for r in value['quote_rows'] if r['symbol']=='MISSING')['status']=='UNAVAILABLE'
            assert value['network_authorized'] is False
            (root/'response.json').write_text(json.dumps(value),encoding='utf-8')
            page=await client.get('/');assert '<td>'+session+'</td>' in page.text
            assert 'Synthetic fixtures only' in page.text and '<td>UNAVAILABLE</td>' in page.text
            assert page.headers['cache-control']=='no-store'
            assert 'default-src' in page.headers['content-security-policy']
            assert (await client.post('/api/market-data')).status_code==405
    asyncio.run(exercise())
assert not any(getattr(m,'__file__',None) and str(getattr(m,'__file__')).startswith(str(pathlib.Path(os.environ['ATLAS_CHECKOUT'])/'backend/app')) for m in list(sys.modules.values()))
print('EXTRACTED_MARKET_API_PASS')
'''
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(extracted / 'backend') + os.pathsep + str(extracted)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['ATLAS_CHECKOUT'] = str(repo)
    result = subprocess.run([sys.executable, '-c', code, asset_class, symbol, stamp, session], cwd=extracted, env=environment, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'EXTRACTED_MARKET_API_PASS' in result.stdout
    node_code = "const fs=require('node:fs');const api=require('./frontend/offline/market-replay/view.cjs'); const value=api.parseExport(fs.readFileSync('response.json','utf8')); if(value.rows.length!==2||value.quote_rows.length!==2)throw Error('lost rows'); if(!value.quote_rows.some(r=>r.price===101.25))throw Error('lost quote'); console.log('EXTRACTED_MARKET_BROWSER_PARSE_PASS');"
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', '-e', node_code], cwd=extracted, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'EXTRACTED_MARKET_BROWSER_PARSE_PASS' in result.stdout
