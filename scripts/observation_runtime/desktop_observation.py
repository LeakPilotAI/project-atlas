"""Actual original UI, observation only. No Atlas lifespan/financial stores/dispatch.

Default has no providers. Explicit bounded data-only authorization is required
for the separate collector; this is never financial enrollment or E1 acceptance.
"""
import argparse
import hashlib
import json
import os
import socket
import sys
import threading
import time
import uuid
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'backend'))
sys.path.insert(0,str(REPO))
STATIC=REPO/'backend/app/static'
PAGES={'/dashboard/future':'future_overview.html','/api/investments/prospective/view':'prospective_research.html','/':'dashboard_hub.html','/dashboard':'dashboard_hub.html','/dashboard/perps':'dashboard_shell.html',
 '/dashboard/legacy':'dashboard.html','/api/investments/quality-dips/view':'quality_dips.html',
 '/quality_dips.html':'quality_dips.html','/dashboard/investment':'investment.html','/dashboard/archive':'archive.html',
 '/dashboard/command-center':'command_center.html','/dashboard/command-center/health':'command_center_health.html',
 '/dashboard/command-center/risk':'command_center_risk.html','/dashboard/prediction-paper':'prediction_paper.html',
 '/dashboard/archive/paper-trades':'archive_paper_trades.html','/dashboard/archive/research':'archive_research.html',
 '/dashboard/archive/snapshots':'archive_snapshots.html','/dashboard/archive/export':'archive_export.html'}
ASSETS={'/static/'+name:name for name in ('runtime_poll.js','quality_dips_selected_paper.js','atlas_ui.css','atlas-perp-backdrop.png')}
SELECTED='/api/investments/quality-dips/selected-paper'


def initial():
 return {'schema':'ATLAS_DESKTOP_OBSERVATION_V1','mode':'OBSERVATION_ONLY','status':'DISCONNECTED',
  'paper_startup_authorized':False,'financial_writers':False,'providers':{'ALPACA_IEX':'NOT_ACTIVATED','HYPERLIQUID':'NOT_ACTIVATED'},
  'quality_dips':{'scope':['MSFT','SPY'],'scope_kind':'BOUNDED_QUOTE_SCOPE_NOT_COMPLETE_RANKED_UNIVERSE',
   'scanner':'WAITING_FOR_VERIFIED_RESEARCH_INPUTS','candidates':None,'reason':'QUOTES_ALONE_DO_NOT_ESTABLISH_QUALITY_OR_FUNDAMENTALS'},
  'perpetuals':{'scope':['BTC','ETH','SOL'],'scanner':'WAITING_FOR_DATA','signals':None,'financial_execution_authorized':False},
  'accounts':{'QUALITY_DIPS':{'currency':'USD','proposed_hypothetical_opening':'1000','status':'NOT_INITIALIZED_OR_READ',
   'cash':None,'positions':None,'capacity_remaining':None},'HYPERLIQUID':{'currency':'USDC','proposed_hypothetical_opening':'1000',
   'status':'NOT_INITIALIZED_OR_READ','cash':None,'positions':None,'capacity_remaining':None}},'financial_gates':'PERSONAL_ACTIVATION_PENDING','release_profile':'PERSONAL_PAPER_ONLY_V1',
  'release_authority':'SOLE_LOCAL_OPERATOR','historical_strict_gates':'B1_C1_D1_E1_BLOCKED_NOT_PERSONAL_REVIEW_PREREQUISITES'}


class Session:
 def __init__(self,root,*,test=False):
  root=Path(root).absolute();parent=REPO/'logs/observation-only'
  if root.parent!=parent or not root.name.startswith('session-') or any(p.is_symlink() or p.is_junction() for p in (root,*root.parents)):
   raise ValueError('EXACT_NEW_OBSERVATION_ROOT_REQUIRED')
  root.mkdir(parents=True,exist_ok=False)
  self.test=test
  self.root,self.lock,self.state,self.stop=root,threading.RLock(),initial(),threading.Event()
  self.head='0'*64;self.count=0
  self.append('SESSION_START',{'mode':'OBSERVATION_ONLY','scope':'DISPOSABLE_TEST' if test else 'OPERATOR_OBSERVATION','financial_sources_accessed':False})
 def append(self,kind,value):
  with self.lock:
   if self.count>=128:raise ValueError('OBSERVATION_SESSION_CAPACITY')
   row={'revision':self.count+1,'at':int(time.time()),'kind':kind,'value':value,'parent':self.head}
   raw=json.dumps(row,sort_keys=True,separators=(',',':'),default=str,allow_nan=False)
   record={**row,'digest':hashlib.sha256(raw.encode()).hexdigest()}
   with (self.root/'observations.jsonl').open('ab') as stream:
    stream.write((json.dumps(record,default=str,allow_nan=False)+'\n').encode());stream.flush();os.fsync(stream.fileno())
   self.head=record['digest'];self.count+=1
 def update(self,key,value):
  with self.lock:self.state[key]=value
 def snapshot(self):
  with self.lock:
   result=json.loads(json.dumps({**self.state,'observed_at':int(time.time()),'journal_records':self.count},default=str))
   perp=result['perpetuals'];stamp=perp.get('observed_at')
   perp['freshness']='FRESH' if type(stamp) is int and 0<=time.time()-stamp<=5 else 'UNAVAILABLE' if stamp is None else 'STALE'
   return result
 def research(self):
  """Pure historical replay of retained public observations; never a refresh."""
  from app.adapters.hyperliquid import candle_window
  from app.services.perp_source_planner import discovery_plans
  choices=[]
  for session in self.history()['sessions']:
   records=[r for r in session['records'] if r['kind']=='HYPERLIQUID_PUBLIC_RESPONSE']
   meta=[r for r in records if r['value']['request']['type']=='metaAndAssetCtxs']
   bars={r['value']['request']['req']['coin']:r['value']['response'] for r in records if r['value']['request']['type']=='candleSnapshot'}
   if meta and set(bars)=={'BTC','ETH','SOL'}:choices.append((meta[-1]['at'],session,meta[-1]['value'],bars))
  if not choices:return {'status':'UNAVAILABLE','reason':'NO_COMPLETE_RETAINED_MARKET_WINDOW','financial_execution_authorized':False}
  stamp,session,record,bars=max(choices,key=lambda x:x[0]);metadata=record['response'];markets=[]
  for instrument,context in zip(metadata[0]['universe'],metadata[1],strict=True):
   if instrument['name'] not in ('BTC','ETH','SOL'):continue
   markets.append({'symbol':instrument['name'],'price':context.get('markPx') or context.get('midPx'),
    'volume_24h':context.get('dayNtlVlm') or '0','open_interest':context.get('openInterest') or '0',
    'funding_rate':context.get('funding'),'observed_at':record['received_at']})
  windows={symbol:candle_window(rows,96) for symbol,rows in bars.items()}
  plans=discovery_plans(markets,windows,('BTC','ETH','SOL'))
  return {'schema':'ATLAS_RETAINED_MARKET_RESEARCH_V1','status':'HISTORICAL_RESEARCH_REPLAY','source_session':session['session'],
   'source_observed_at':stamp,'processed_at':int(time.time()),'freshness':'STALE_NOT_EXECUTABLE',
   'markets':markets,'signals':plans,'raw_candle_counts':{k:len(v) for k,v in bars.items()},
   'selected_candle_counts':{k:len(v) for k,v in windows.items()},'financial_execution_authorized':False,
   'note':'Original raw responses preserved; existing strategy filters unchanged; no orders or financial admission'}
 def history(self):
  output=[]
  directories=[self.root] if self.test else [p for p in self.root.parent.glob('session-*') if not p.name.startswith('session-test-')]
  if len(directories)>256 or any(p.is_symlink() or p.is_junction() for p in directories):
   raise ValueError('OBSERVATION_ARCHIVE_ROSTER_UNVERIFIED_OR_UNBOUNDED')
  archive_count=len(directories)
  # UUID lexical order is unrelated to session time. Never hide window truncation.
  directories=sorted(directories,key=lambda p:(p.stat().st_ctime_ns,p.name))[-20:]
  for directory in directories:
   file=directory/'observations.jsonl'
   if directory.is_symlink() or directory.is_junction() or not file.is_file() or file.is_symlink() or file.stat().st_nlink!=1 or file.stat().st_size>8388608:
    raise ValueError('OBSERVATION_ARCHIVE_IDENTITY_OR_BOUND_REFUSED')
   parent='0'*64;rows=[]
   # A concurrent append is read only through the last complete line.
   raw=file.read_bytes();lines=raw.splitlines(keepends=True)
   for line in lines:
    if not line.endswith(b'\n'):raise ValueError('OBSERVATION_INTERRUPTED_APPEND')
    row=json.loads(line);checksum=row.pop('digest')
    encoded=json.dumps(row,sort_keys=True,separators=(',',':'),default=str,allow_nan=False)
    if row['revision']!=len(rows)+1 or row['parent']!=parent or hashlib.sha256(encoded.encode()).hexdigest()!=checksum:
     raise ValueError('OBSERVATION_ARCHIVE_CORRUPT')
    parent=checksum;rows.append({**row,'digest':checksum})
   output.append({'session':directory.name,'records':rows,'status':'CLOSED' if rows and rows[-1]['kind']=='SESSION_STOP' else 'ACTIVE_OR_INTERRUPTED'})
  return {'schema':'ATLAS_LOCAL_OBSERVATION_HISTORY_V1','authority':'LOCAL_RETAINED_RESEARCH_NOT_FINANCIAL_CUSTODY','sessions':output,
   'archive_count':archive_count,'omitted_sessions':max(0,archive_count-20),
   'status':'PARTIAL_ARCHIVE_WINDOW' if archive_count>20 else 'COMPLETE_LOCAL_WINDOW'}
 def diagnostics(self):
  history=self.history();now=int(time.time());counts={};books=[];iex=None;budget=None;refusals=[]
  for session in history['sessions']:
   for row in session['records']:
    value=row['value'];kind=row['kind']
    if kind=='HYPERLIQUID_PUBLIC_RESPONSE':
     request=value['request'];name=request['type'];counts[name]=counts.get(name,0)+1
     if name=='l2Book':
      source=value['response'].get('time');received=value['received_at']
      books.append({'symbol':request['coin'],'source_time_ms':source,'received_at':received,
       'received_age_seconds':now-received,'source_age_seconds':(now*1000-source)/1000 if type(source) is int else None,
       'freshness':'STALE_NOT_EXECUTABLE','financial_execution_authorized':False})
    elif kind=='ALPACA_IEX_SESSION_RESULT':iex=value
    elif kind=='DATA_COLLECTION_STOP':budget=value.get('remaining_logical_attempts')
    elif kind.endswith('REFUSED'):refusals.append({'session':session['session'],'at':row['at'],'kind':kind,'reason':value.get('reason')})
  current=next((s for s in history['sessions'] if s['session']==self.root.name),None)
  records=current['records'] if current else []
  ended=records[-1]['at'] if current and current['status']=='CLOSED' else now
  return {'schema':'ATLAS_OBSERVATION_DIAGNOSTICS_V1','served_at':now,'source':'VERIFIED_LOCAL_RESEARCH_WINDOW_NOT_FINANCIAL_AUTHORITY',
   'archive_count':history['archive_count'],'omitted_sessions':history['omitted_sessions'],'archive_status':history['status'],
   'public_response_counts':counts,'books':books,'iex_last_completed_session':iex,'historical_budget_remaining':budget,
   'budget_status':'LAST_RETAINED_RECEIPT_NOT_CURRENT_CUSTODY','refusals':refusals,
   'current_session':{'state':current['status'] if current else 'UNAVAILABLE','records':len(records),
    'records_remaining':128-len(records),'started_at':records[0]['at'] if records else None,
    'last_record_at':records[-1]['at'] if records else None,'duration_seconds':ended-records[0]['at'] if records else None},
   'quality_dips_research':'WAITING_FOR_VERIFIED_FUNDAMENTALS_HISTORY_VALUATION_AND_RANKING',
   'financial_reconciliation':'UNAVAILABLE_NO_ACCEPTED_FINANCIAL_RUNTIME','financial_capacity_remaining':None,
   'financial_startup_authorized':False}


def assets():
 result={}
 for route,name in {**PAGES,**ASSETS}.items():
  data=(STATIC/name).read_bytes()
  if name.endswith('.html'):
   data=data.replace(b'<head>',b'<head><meta name="atlas-observation" content="readonly">')
   ending=b'</body>' if b'</body>' in data else b'</html>'
   data=data.replace(ending,b'<script src="/static/observation_status.js"></script>'+ending)
  result[route]=(data,'text/html; charset=utf-8' if name.endswith('.html') else 'image/png' if name.endswith('.png') else 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8')
 result['/static/observation_status.js']=((Path(__file__).with_name('observation_status.js')).read_bytes(),'text/javascript; charset=utf-8')
 return result


def make_host(session,port=0,*,research_reader=None,request_limit=None,deadline_seconds=180):
 content=assets();identity=uuid.uuid4().hex
 class Handler(BaseHTTPRequestHandler):
  def response(self,status,value,mime='application/json'):
   data=value if isinstance(value,bytes) else json.dumps(value,allow_nan=False,default=str).encode()
   self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; connect-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'");self.end_headers();self.wfile.write(data)
  def do_GET(self):
   origin='http://127.0.0.1:'+str(self.server.server_port)
   if self.headers.get('Host')!=origin[7:] or self.headers.get('Origin') not in (None,origin):return self.response(403,{'status':'REFUSED'})
   route=urlsplit(self.path).path
   if route in content:return self.response(200,*content[route])
   if route=='/health':return self.response(200,{'status':'ok','host_id':identity,'mode':'OBSERVATION_ONLY','pid':os.getpid(),
    'scanner_running':False,'paper_trade_tracker_running':False,'production':'NO-GO','financial_writers':False})
   if route=='/api/observation/state':return self.response(200,session.snapshot())
   if route=='/api/observation/diagnostics':
    try:return self.response(200,session.diagnostics())
    except (OSError,ValueError,KeyError,TypeError):return self.response(503,{'status':'INCOMPLETE','reason':'OBSERVATION_DIAGNOSTICS_UNVERIFIED'})
   if route=='/api/observation/quality-dips':
    try:
     if research_reader is None:raise ValueError('NO_ACCEPTED_CURRENT_RESEARCH_PUBLICATION')
     return self.response(200,research_reader.read())
    except (OSError,ValueError,KeyError,TypeError):return self.response(503,{'status':'UNAVAILABLE','reason':'CURRENT_RESEARCH_PUBLICATION_UNVERIFIED','board':None})
   if route=='/api/observation/hyperliquid':
    try:
     from scripts.observation_runtime.research_reads import retained_hyperliquid
     return self.response(200,retained_hyperliquid(session.history()))
    except (OSError,ValueError,KeyError,TypeError):return self.response(503,{'status':'UNAVAILABLE','reason':'RETAINED_OBSERVATION_UNVERIFIED','markets':None})
   if route=='/api/observation/research':
    try:return self.response(200,session.research())
    except (OSError,ValueError,KeyError,TypeError):return self.response(503,{'status':'UNAVAILABLE','reason':'RETAINED_RESEARCH_UNVERIFIED'})
   if route=='/api/observation/history':
    try:return self.response(200,session.history())
    except (OSError,ValueError,KeyError):return self.response(503,{'status':'INCOMPLETE','reason':'LOCAL_OBSERVATION_HISTORY_UNVERIFIED'})
   if route==SELECTED:
    state=session.snapshot()
    value={'schema':'QD_SELECTED_FINANCIAL_VIEW_V1','account_id':None,'epoch':None,'status':'UNAVAILABLE',
     'cash':None,'realized':None,'positions':None,'valuation':None,'report_status':'UNAVAILABLE',
     'reasons':['NO_ACCEPTED_FINANCIAL_ENROLLMENT_OR_INCEPTION'],'startup_authorized':False}
    value['multi_market']={'schema':'ATLAS_UNIFIED_PAPER_VIEW_V1','state':'STOPPED','financial_state':'UNAVAILABLE_NO_FINANCIAL_RUNTIME',
     'startup_authorized':False,'total_cash':None,'total_equity':None,'lanes':{'QUALITY_DIPS':None,'HYPERLIQUID':None},
     'trade_history':{'schema':'ATLAS_EXIT_HISTORY_V1','status':'UNAVAILABLE','rows':[], 'accounts':None,
      'total_cash':None,'total_net':None,'startup_authorized':False}}
    if state.get('iex'):value['market_data']=state['iex']
    return self.response(200,value)
   return self.response(503 if route.startswith('/api/') else 404,{'status':'UNAVAILABLE','reason':'NO_OBSERVATION_CAPABILITY_FOR_THIS_PATH','financial_writers':False})
  def send_response(self,code,message=None):
   if request_limit is not None:self.server.record_status(code)
   return super().send_response(code,message)
  def do_POST(self):return self.response(403,{'status':'REFUSED','reason':'OBSERVATION_ONLY_NO_COMMANDS'})
  do_PUT=do_DELETE=do_PATCH=do_POST
  def log_message(self,*args):pass
 class Server(ThreadingHTTPServer):
  allow_reuse_address=False;daemon_threads=True
  def server_bind(self):
   if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
   super().server_bind()
 if request_limit is not None:
  from scripts.observation_runtime.bounded_http import BoundedHTTPServer
  return BoundedHTTPServer(('127.0.0.1',port),Handler,limit=request_limit,seconds=deadline_seconds),identity
 return Server(('127.0.0.1',port),Handler),identity


def main():
 p=argparse.ArgumentParser();p.add_argument('--data-only-seconds',type=int,default=0);p.add_argument('--operator-data-only-approved',action='store_true');p.add_argument('--existing-data-budget',type=Path);p.add_argument('--disposable-test',action='store_true');a=p.parse_args()
 if a.disposable_test and a.data_only_seconds:raise ValueError('DISPOSABLE_HOST_NETWORK_COLLECTION_FORBIDDEN')
 if a.data_only_seconds and (not a.operator_data_only_approved or not 1<=a.data_only_seconds<=30):raise ValueError('EXPLICIT_BOUNDED_DATA_ONLY_APPROVAL_REQUIRED')
 session=Session(REPO/'logs/observation-only'/(('session-test-' if a.disposable_test else 'session-')+uuid.uuid4().hex),test=a.disposable_test)
 if a.existing_data_budget:
  path=a.existing_data_budget.absolute()
  if (not a.data_only_seconds or path.name!='provider-budget.sqlite' or path.parent.parent!=REPO/'logs/observation-only'
      or path.parent.name.startswith('session-test-') or not path.is_file() or path.stat().st_nlink!=1
      or any(x.is_symlink() or x.is_junction() for x in (path,*path.parents))):
   raise ValueError('EXISTING_OBSERVATION_BUDGET_REQUIRED_NO_RESET')
  session.budget_path=path
 host,identity=make_host(session)
 worker=threading.Thread(target=host.serve_forever,daemon=True);worker.start();collector=None
 if a.data_only_seconds:
  import asyncio

  from desktop_observation_sources import collect
  collector=threading.Thread(target=lambda:asyncio.run(collect(session,a.data_only_seconds,operator_data_only_approved=a.operator_data_only_approved)),daemon=False)
 from http.client import HTTPConnection
 with closing(HTTPConnection('127.0.0.1',host.server_port,timeout=3)) as probe:
  probe.request('GET','/health');reply=probe.getresponse();evidence=json.loads(reply.read())
  if reply.status!=200 or evidence['host_id']!=identity:raise ValueError('OWNED_OBSERVATION_READINESS_REFUSED')
 from disposable_host_owner import observe_pid
 process=observe_pid(os.getpid())
 ready={'url':f'http://127.0.0.1:{host.server_port}/','host_id':identity,'pid':os.getpid(),'mode':'OBSERVATION_ONLY',
  'creation_filetime':process['created'],'image':process['image'],'data_only_seconds':a.data_only_seconds}
 (session.root/'host-ready.json').write_text(json.dumps(ready),encoding='utf-8')
 print(json.dumps(ready),flush=True)
 if collector:collector.start()
 try:sys.stdin.readline()
 finally:
  session.stop.set()
  if collector:
   collector.join(10)
   if collector.is_alive():raise RuntimeError('OBSERVATION_SOURCE_SHUTDOWN_UNCONFIRMED')
  host.shutdown();host.server_close();worker.join(5);session.append('SESSION_STOP',{'financial_writers':False})

if __name__=='__main__':main()
