"""Real HTTP boundaries over original assets; no provider or financial source."""
import hashlib
import importlib.util
import json
import threading
import uuid
from contextlib import closing
from http.client import HTTPConnection
from pathlib import Path

import pytest

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('desktop_obs',REPO/'scripts/observation_runtime/desktop_observation.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.fixture
def host():
 s=m.Session(REPO/'logs/observation-only'/('session-test-'+uuid.uuid4().hex),test=True);server,identity=m.make_host(s)
 t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
 try:yield s,server,identity
 finally:server.shutdown();server.server_close();t.join(3)


def request(h,path,method='GET',headers=None):
 _s,server,_identity=h
 with closing(HTTPConnection('127.0.0.1',server.server_port,timeout=3)) as c:
  c.request(method,path,headers=headers or {});r=c.getresponse();return r.status,r.read()

@pytest.mark.parametrize('path',['/','/dashboard/perps','/quality_dips.html','/api/investments/quality-dips/view','/dashboard/command-center','/static/atlas-perp-backdrop.png'])
def test_original_ui_assets_and_mode_notice(host,path):
 code,raw=request(host,path);assert code==200
 if not path.endswith('.png'):assert b'observation_status.js' in raw

@pytest.mark.parametrize('path',['/.env','/config/alpaca.env','/../config/alpaca.env','/.git/config','/api/investments/quality-dips','/api/perps/manual/positions'])
def test_no_secret_or_mutating_legacy_get(host,path):
 assert request(host,path)[0] in (404,503)

@pytest.mark.parametrize('method',['POST','PUT','PATCH','DELETE'])
def test_all_financial_commands_refuse(host,method):
 assert request(host,'/api/investments/quality-dips/selected-paper/commands',method)[0]==403


def test_host_and_origin_refusal(host):
 assert request(host,'/health',headers={'Host':'foreign'})[0]==403
 assert request(host,'/health',headers={'Origin':'https://foreign.example'})[0]==403


def test_get_has_no_observation_or_financial_mutations(host):
 s,_server,_identity=host;p=s.root/'observations.jsonl';before=hashlib.sha256(p.read_bytes()).hexdigest()
 for path in ['/health','/api/observation/state','/api/observation/history',m.SELECTED]:assert request(host,path)[0]==200
 assert hashlib.sha256(p.read_bytes()).hexdigest()==before
 d=json.loads(request(host,m.SELECTED)[1]);assert d['status']=='UNAVAILABLE' and d['cash'] is None and d['startup_authorized'] is False
 view=json.loads(request(host,'/api/observation/state')[1]);assert view['accounts']['QUALITY_DIPS']['currency']=='USD' and view['accounts']['HYPERLIQUID']['currency']=='USDC'
 assert all(x['cash'] is None and x['capacity_remaining'] is None for x in view['accounts'].values())


def test_current_history_reopens_without_reset_and_corruption_refuses(host):
 s,_server,_identity=host;s.append('TEST_OBSERVATION',{'source':'EXPLICIT_TEST_NOT_LIVE'})
 result=s.history();current=next(x for x in result['sessions'] if x['session']==s.root.name)
 assert len(current['records'])==2
 p=s.root/'observations.jsonl';old=p.read_bytes();p.write_bytes(old.replace(b'EXPLICIT_TEST_NOT_LIVE',b'ALTERED'))
 assert request(host,'/api/observation/history')[0]==503
 p.write_bytes(old)  # Explicit test-owned fixture repair only; not application recovery.


def test_no_backend_or_financial_modules_imported():
 import ast
 tree=ast.parse((REPO/'scripts/observation_runtime/desktop_observation.py').read_text())
 names=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
 assert not any(n.startswith(('app.main','app.services.investment','app.investment.storage')) for n in names)

@pytest.mark.asyncio
@pytest.mark.parametrize('seconds,approved',[(30,False),(31,True),(0,True)])
async def test_source_default_refuses_before_network_or_budget(seconds,approved):
 import sys
 sys.path.insert(0,str(REPO/'scripts/observation_runtime'))
 from desktop_observation_sources import collect
 with pytest.raises(ValueError,match='APPROVAL'):
  await collect(None,seconds,operator_data_only_approved=approved)


def test_retained_research_is_read_only_and_never_executable(host):
 s,_server,_identity=host
 from app.adapters.hyperliquid import candle_window
 bars=[{'t':i*300000,'o':'100','h':'101','l':'99','c':'100','v':'2','n':1} for i in range(97)]
 meta=[{'universe':[{'name':x} for x in ('BTC','ETH','SOL')]},[{'markPx':'100','dayNtlVlm':'10000000','openInterest':'100000','funding':'0'} for _ in range(3)]]
 s.append('HYPERLIQUID_PUBLIC_RESPONSE',{'request':{'type':'metaAndAssetCtxs'},'received_at':1,'response':meta})
 for symbol in ('BTC','ETH','SOL'):
  s.append('HYPERLIQUID_PUBLIC_RESPONSE',{'request':{'type':'candleSnapshot','req':{'coin':symbol}},'received_at':1,'response':bars})
 p=s.root/'observations.jsonl';before=p.read_bytes()
 status,raw=request(host,'/api/observation/research');assert status==200
 result=json.loads(raw)
 assert result['freshness']=='STALE_NOT_EXECUTABLE' and result['financial_execution_authorized'] is False
 assert set(result['raw_candle_counts'].values())=={97} and set(result['selected_candle_counts'].values())=={96}
 assert p.read_bytes()==before and len(candle_window(bars,96))==96
