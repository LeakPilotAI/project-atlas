"""Bounded actual data-only collection; no app.main, financial stores or orders."""
import asyncio
import copy
import time
from dataclasses import asdict

import httpx


async def collect(session,seconds,*,operator_data_only_approved=False):
 if operator_data_only_approved is not True or type(seconds) is not int or not 1<=seconds<=30:
  raise ValueError('EXPLICIT_BOUNDED_DATA_ONLY_APPROVAL_REQUIRED')
 from app.adapters import hyperliquid_gate_registry
 from app.adapters.hyperliquid import HyperliquidAdapter
 from app.adapters.hyperliquid_request_gate import HyperliquidRequestGate
 from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused, decode
 from app.services.perp_source_planner import discovery_plans
 from desktop_observation import REPO
 gate=HyperliquidRequestGate(getattr(session,'budget_path',session.root/'provider-budget.sqlite'),rights_approved=True,budget_approved=True,max_attempts=18)
 hyperliquid_gate_registry.install_gate(gate)
 feed=IEXFeed(['MSFT','SPY']);adapter=HyperliquidAdapter()
 original_receive=feed.receive;frames=[0]
 def retain(raw):
  if frames[0]>=96:
   session.stop.set();raise IEXRefused('IEX_OBSERVATION_CAPACITY_REACHED')
  original_receive(raw);frames[0]+=1
  events=[{k:v for k,v in row.items() if k in ('T','S','bx','bp','bs','ax','ap','as','c','t','z')}
   for row in decode(raw) if row.get('T')=='q' and row.get('S') in feed.symbols]
  session.append('ALPACA_IEX_STATE_CHANGE',{'snapshot':feed.snapshot(),'quote_events':events})
 feed.receive=retain
 session.append('DATA_ONLY_AUTHORIZATION',{'scope':'OPERATOR_BOUNDED_OBSERVATION_NOT_E1_OR_FINANCIAL_AUTHORITY','seconds':seconds,
  'hyperliquid_max_logical_attempts':18,'symbols':['BTC','ETH','SOL'],'iex_symbols':['MSFT','SPY']})
 async def stock():
  try:
   result=await feed.run(Credentials.load(REPO/'config/alpaca.env'),seconds=seconds,max_reconnects=0,stop=session.stop)
   session.update('iex_session_result',result);session.append('ALPACA_IEX_SESSION_RESULT',result)
  except (OSError,ValueError,TimeoutError):session.update('iex_error','DATA_UNAVAILABLE_OR_REFUSED')
 async def perp():
  original=adapter._post;metadata=[None]
  async def observed_post(request):
   if request.get('type') not in ('meta','metaAndAssetCtxs','l2Book','candleSnapshot','fundingHistory'):
    raise ValueError('READ_ONLY_PUBLIC_MARKET_REQUEST_REQUIRED')
   result=await original(request)
   session.append('HYPERLIQUID_PUBLIC_RESPONSE',{'request':request,'received_at':int(time.time()),'response':result})
   if request['type']=='metaAndAssetCtxs':metadata[0]=result
   return result
  adapter._post=observed_post
  try:
   async with asyncio.timeout(seconds):
    await adapter.connect();tickers=await adapter.get_all_tickers();markets=[asdict(t) for t in tickers if t.symbol in ('BTC','ETH','SOL')]
    candles={};books={};funding={}
    now=int(time.time());end=(now//3600)*3600
    for symbol in ('BTC','ETH','SOL'):
     if session.stop.is_set():return
     started=int(time.time()*1000)
     raw=await adapter._post({'type':'l2Book','coin':symbol})
     books[symbol]={'raw':raw,'received_at_ms':int(time.time()*1000),'financial_execution_authorized':False}
     try:
      from app.adapters.hyperliquid import _paper_execution_observation
      books[symbol]['validated_public_book']=_paper_execution_observation(symbol,metadata[0],raw,started,int(time.time()*1000))
     except ValueError:
      books[symbol]['executable_evidence_status']='REFUSED_NOT_RELAXED_FOR_RESEARCH'
     candles[symbol]=await adapter.get_candles(symbol,'5m',lookback=96)
     funding[symbol]=await adapter._post({'type':'fundingHistory','coin':symbol,'startTime':(end-3600)*1000,'endTime':(end+3600)*1000-1})
    plans=discovery_plans(markets,candles,('BTC','ETH','SOL'))
    for row in plans:row['financial_execution_authorized']=False
    value={'scope':['BTC','ETH','SOL'],'scanner':'RESEARCH_COMPLETED','markets':markets,'books':books,'candles':candles,
     'funding':funding,'signals':plans,'observed_at':int(time.time()),'financial_execution_authorized':False,
     'limitations':['PUBLIC_RESEARCH_NOT_FILL_OR_QUEUE_AUTHORITY','SETTLEMENT_ORACLE_NOT_ACCEPTED']}
    session.update('perpetuals',value);session.append('HYPERLIQUID_RESEARCH',value)
  except (OSError,ValueError,RuntimeError,TimeoutError,httpx.HTTPError) as error:
   session.update('perp_error',type(error).__name__);session.append('HYPERLIQUID_REFUSED',{'reason':type(error).__name__})
  finally:await adapter.close()
 jobs=[asyncio.create_task(stock()),asyncio.create_task(perp())]
 try:
  session.update('status','BOUNDED_DATA_COLLECTION')
  session.update('providers',{'ALPACA_IEX':'BOUNDED_CONNECTING','HYPERLIQUID':'BOUNDED_PUBLIC_RESEARCH'})
  for _ in range(seconds):
   if session.stop.is_set():break
   snapshot=feed.snapshot();session.update('iex',snapshot)
   await asyncio.sleep(1)
 finally:
  for job in jobs:
   if not job.done():job.cancel()
  await asyncio.gather(*jobs,return_exceptions=True)
  snapshot=feed.snapshot();session.update('iex',snapshot)
  session.update('providers',{'ALPACA_IEX':'BOUNDED_SESSION_CLOSED','HYPERLIQUID':'BOUNDED_SESSION_CLOSED'})
  session.update('status','OBSERVATION_SESSION_COMPLETE_NO_FINANCIAL_DISPATCH')
  session.update('provider_budget_remaining',gate.remaining())
  session.append('DATA_COLLECTION_STOP',{'iex':copy.deepcopy(snapshot),'remaining_logical_attempts':gate.remaining(),'financial_writers':False})
