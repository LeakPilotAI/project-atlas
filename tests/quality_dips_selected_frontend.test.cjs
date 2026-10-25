// Actual shipped scripts in a deterministic DOM/fetch harness. No browser or HTTP listener.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ui = require('../backend/app/static/quality_dips_selected_paper.js');
const html = fs.readFileSync('backend/app/static/quality_dips.html', 'utf8');
const external = fs.readFileSync('backend/app/static/quality_dips_selected_paper.js', 'utf8');
const inline = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const STAMP = 1792843200;
function unifiedView(){return {schema:'ATLAS_UNIFIED_PAPER_VIEW_V1',state:'RUNNING',financial_state:'READ_SEPARATE_ACCOUNTS',
  startup_authorized:false,total_cash:null,total_equity:null,lanes:Object.fromEntries(['QUALITY_DIPS','HYPERLIQUID'].map(lane=>
    [lane,{lane,at:STAMP,connection:'CONNECTED',session:lane==='QUALITY_DIPS'?'CLOSED':'OPEN',signal:null}]))};}

test('both markets show session and no-signal monitoring without fabricated consolidated balances',async()=>{
  const d=payload();d.multi_market=unifiedView();const h=harness(d);await h.controller.load();
  const s=h.elements.paperMultiMarket.innerHTML;
  for(const v of ['QUALITY_DIPS','HYPERLIQUID','CLOSED','OPEN','No validated signal','Combined cash/equity: UNAVAILABLE'])assert.ok(s.includes(v));
  assert.equal(h.requests.length,1);assert.equal(h.requests[0].options.method,'GET');
});
test('multi-market stale and network failures clear apparent health',async()=>{
  const d=payload();d.multi_market=unifiedView();const h=harness(d);await h.controller.load();
  h.setNow((STAMP+6)*1000);h.controller.refreshAge();assert.match(h.elements.paperMultiMarket.innerHTML,/STALE/);
  h.setData(new Error('offline'));await h.controller.load();assert.match(h.elements.paperMultiMarket.innerHTML,/UNAVAILABLE/);
});
test('unified view rejects invented totals and escapes signal labels',()=>{
  const d=unifiedView();d.lanes.HYPERLIQUID.signal='<script>bad()</script>';
  assert.match(ui.renderUnified(d,STAMP*1000),/&lt;script&gt;/);
  d.total_equity='1000';assert.match(ui.renderUnified(d,STAMP*1000),/UNAVAILABLE/);
});
function iexView(){return {schema:'ATLAS_ALPACA_IEX_VIEW_V1',feed:'IEX',scope:'SINGLE_EXCHANGE_NOT_NBBO',
  size_units:'ROUND_LOTS',connection:'CONNECTED',authenticated:true,subscribed:true,paper_startup_authorized:false,
  observed_at:STAMP,quotes:[{symbol:'MSFT',bid:'100',ask:'100.1',bid_lots:1,ask_lots:2,
    timestamp:new Date(STAMP*1000).toISOString(),state:'FRESH'}]};}

test('IEX displays quote evidence without financial enrollment or extra requests',async()=>{
  const h=harness({schema:'QD_SELECTED_FINANCIAL_VIEW_V1',status:'UNAVAILABLE',market_data:iexView()});
  await h.controller.load();assert.match(h.elements.paperMarket.innerHTML,/NOT consolidated NBBO/);
  assert.match(h.elements.paperMarket.innerHTML,/\$100\.1/);assert.match(h.elements.paperStatus.textContent,/UNAVAILABLE/);
  assert.equal(h.requests.length,1);assert.equal(h.requests[0].url,ui.ENDPOINT);
});
test('IEX stale and disconnected quotes cannot remain FRESH',()=>{
  const v=iexView();assert.doesNotMatch(ui.renderMarket(v,(STAMP+6)*1000),/>FRESH</);
  v.connection='DISCONNECTED';assert.match(ui.renderMarket(v,STAMP*1000),/>STALE</);
});
test('IEX missing data never becomes a zero valuation',()=>{
  const v=iexView();v.quotes=[{symbol:'MSFT',bid:null,ask:null,timestamp:null,state:'UNAVAILABLE'}];
  const s=ui.renderMarket(v,STAMP*1000);assert.match(s,/UNAVAILABLE/);assert.doesNotMatch(s,/\$0/);
});
test('IEX labels are escaped and unsupported feed is refused',()=>{
  const v=iexView();v.quotes[0].symbol='<img src=x>';assert.match(ui.renderMarket(v,STAMP*1000),/&lt;img/);
  v.scope='NBBO';assert.match(ui.renderMarket(v,STAMP*1000),/refused/);
});
test('IEX network failure clears its quote display without legacy fallback',async()=>{
  const d=payload();d.market_data=iexView();const h=harness(d);await h.controller.load();
  h.setData(new Error('offline'));await h.controller.load();assert.match(h.elements.paperMarket.innerHTML,/UNAVAILABLE/);
  assert.ok(h.requests.every(r=>r.url===ui.ENDPOINT && r.options.method==='GET'));
});
const clone = value => JSON.parse(JSON.stringify(value));
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };

function payload(symbol='MSFT') {
  return {schema:'QD_SELECTED_FINANCIAL_VIEW_V1',status:'ACKNOWLEDGED',account_id:'fixture-account',epoch:'fixture-epoch',
    policy_digest:'a'.repeat(64),source_revision:2,projection_revision:2,source_identity:{fixture:'source'},observed_at:STAMP,
    inception:{schema:'QD_SELECTED_INCEPTION_VIEW_V1',account_id:'fixture-account',epoch:'fixture-epoch',policy_digest:'a'.repeat(64),
      currency:'USD',opening_cash:'1000',policy_schema:'QD_SELECTED_ACCOUNT_POLICY_V2'},cash:'943.968',
    realized:{gross:'4',net:'3.968',costs:'0.032',fees:null,slippage:null},
    positions:{'fixture-epoch:position':{symbol,quantity:'2.5',remaining:'1.500000000000000000000000001'}},
    valuation:null,report_status:'INCOMPLETE',lifecycle_status:'NOT_EVALUATED',
    selection:{schema:'QD_SELECTION_PRESENTATION_V1',candidates:[
      {symbol:'MSFT',asset_class:'STOCK',rank:1,status:'SELECTED',reasons:['Manual approval and evidence bound']},
      {symbol:'SPY',asset_class:'ETF',rank:2,status:'REJECTED',reasons:['ONE_POSITION_NO_SCALE_IN']},
      {symbol:'AAPL',asset_class:'STOCK',rank:3,status:'RESEARCH_ONLY',reasons:['Not manually approved']},
      {symbol:'QQQ',asset_class:'ETF',rank:4,status:'REJECTED',reasons:['EXECUTION_EVIDENCE_INVALID']} ]}};
}
function dom() {
  const elements={};
  const document={getElementById(id){return elements[id]??={innerHTML:'',textContent:'',hidden:false,value:id==='stateFilter'?'all':'',
    attrs:{},listeners:{},style:{},classList:{toggle(){},remove(){}},setAttribute(k,v){this.attrs[k]=v;},
    addEventListener(k,v){this.listeners[k]=v;},scrollIntoView(){}};},addEventListener(){},querySelectorAll(){return [];},
    querySelector(){return {scrollIntoView(){}};},body:{classList:{toggle(){}}}};
  return {document,elements};
}
function harness(data=payload()) {
  const d=dom(), requests=[], timers=new Map(); let tick=0, now=STAMP*1000, current=data;
  const controller=ui.createController({document:d.document,clock:()=>now,Abort:AbortController,
    schedule(fn){timers.set(++tick,fn);return tick;},cancel(id){timers.delete(id);},
    fetch:async(url, options)=>{requests.push({url,options});if(current instanceof Error)throw current;
      return {ok:true,json:async()=>clone(current)};}});
  controller.setActive(true);
  return {...d,controller,requests,timers,setData(value){current=value;},setNow(value){now=value;}};
}

test('acknowledged exact cash, position, inception and unavailable valuation',async()=>{
  const h=harness();await h.controller.load();const content=h.elements.paperContent.innerHTML;
  assert.match(content,/\$1000/);assert.match(content,/\$943\.968/);
  assert.match(content,/1\.500000000000000000000000001/);assert.match(content,/\$3\.968/);
  assert.match(content,/Total equity \/ unrealized valuation<\/dt><dd>UNAVAILABLE/);
  assert.match(h.elements.paperStatus.textContent,/ACKNOWLEDGED.*INCOMPLETE/);
  assert.equal(h.requests[0].url,ui.ENDPOINT);assert.equal(h.requests[0].options.method,'GET');
});
test('stock and ETF reasons retain supplied order, status and no automatic action',async()=>{
  const h=harness();await h.controller.load();const s=h.elements.paperContent.innerHTML;
  for(const symbol of ['MSFT','SPY','AAPL','QQQ'])assert.match(s,new RegExp(symbol));
  assert.match(s,/STOCK/);assert.match(s,/ETF/);assert.match(s,/ONE_POSITION_NO_SCALE_IN/);assert.match(s,/RESEARCH_ONLY/);
  assert.equal(h.requests.length,1);assert.doesNotMatch(s,/<button|<form/);
});
test('missing inception does not invent hypothetical capital',async()=>{
  const data=payload();delete data.inception;const h=harness(data);await h.controller.load();
  assert.match(h.elements.paperContent.innerHTML,/Hypothetical starting cash<\/dt><dd>UNAVAILABLE/);
  assert.doesNotMatch(h.elements.paperContent.innerHTML,/\$1000/);
});
test('verified zero amounts display zero, never fabricate missing costs',async()=>{
  const data=payload();data.realized={gross:'0',costs:'0',net:'0',fees:null,slippage:null};
  const h=harness(data);await h.controller.load();const s=h.elements.paperContent.innerHTML;
  assert.match(s,/Realized gross P&amp;L<\/dt><dd>\$0/);assert.match(s,/Aggregate fees<\/dt><dd>UNAVAILABLE/);
});
test('verified scoped daily report shows cutoff and costs separately',async()=>{
  const data=payload();data.report={schema:'FS3_DAILY_REPORT_V1',account_id:data.account_id,epoch:data.epoch,status:'INCOMPLETE',
    date:'2026-10-24',timezone:'America/New_York',period:{end_exclusive:STAMP+3600,effective_end_exclusive:STAMP},realized:{fees:'0.016',slippage:'0.016'}};
  const h=harness(data);await h.controller.load();const s=h.elements.paperContent.innerHTML;
  assert.match(s,/Reporting cutoff \(exclusive\)/);assert.match(s,/America\/New_York/);assert.match(s,/Report realized fees<\/dt><dd>\$0\.016/);
  assert.match(h.elements.paperStatus.textContent,/INCOMPLETE/);assert.match(s,/NOT_EVALUATED/);
});
for(const state of ['UNKNOWN','INCOMPLETE','UNAVAILABLE'])test(`${state} clears prior financial amounts`,async()=>{
  const h=harness();await h.controller.load();h.setData({schema:'QD_SELECTED_FINANCIAL_VIEW_V1',status:state,reasons:['EVIDENCE_MISSING']});await h.controller.load();
  assert.equal(h.elements.paperStatus.textContent,state);assert.doesNotMatch(h.elements.paperContent.innerHTML,/943\.968|MSFT/);
});
test('stale and future source snapshots never display current balances',async()=>{
  for(const delta of [-31,1]){const data=payload();data.observed_at+=delta;const h=harness(data);await h.controller.load();
    assert.equal(h.elements.paperStatus.textContent,'STALE');assert.doesNotMatch(h.elements.paperContent.innerHTML,/943\.968/);}
});
test('network failure retains only explicitly stale last acknowledged evidence',async()=>{
  const h=harness();await h.controller.load();h.setData(Error('offline'));await h.controller.load();
  assert.match(h.elements.paperStatus.textContent,/STALE/);assert.match(h.elements.paperFreshness.textContent,/not current/);
  assert.match(h.elements.paperContent.innerHTML,/943\.968/);h.controller.setActive(false);h.controller.setActive(true);
  assert.match(h.elements.paperStatus.textContent,/STALE/);
});
test('refused initial HTTP read has no fallback',async()=>{
  const d=dom(), urls=[];const c=ui.createController({document:d.document,Abort:AbortController,clock:()=>STAMP*1000,
    fetch:async url=>{urls.push(url);return {ok:false};},schedule:()=>1,cancel(){}});c.setActive(true);await c.load();
  assert.equal(d.elements.paperStatus.textContent,'UNAVAILABLE');assert.deepEqual(urls,[ui.ENDPOINT]);
});
test('untrusted HTML remains escaped throughout the selected view',async()=>{
  const data=payload('<img onerror="bad">');data.selection.candidates[0].reasons=['<script>alert(1)</script>'];
  const h=harness(data);await h.controller.load();const s=h.elements.paperContent.innerHTML;
  assert.doesNotMatch(s,/<img|<script/);assert.match(s,/&lt;img/);assert.match(s,/&lt;script/);
});
for(const kind of ['scope','rollback','same-revision-conflict','malformed'])test(`${kind} cannot replace acknowledged state`,async()=>{
  const h=harness();await h.controller.load();const next=payload();
  if(kind==='scope'){next.account_id='other-account';next.inception.account_id='other-account';}
  if(kind==='rollback')next.source_revision=next.projection_revision=1;
  if(kind==='same-revision-conflict')next.cash='999';if(kind==='malformed')next.positions=null;
  h.setData(next);await h.controller.load();assert.equal(h.elements.paperStatus.textContent,'UNKNOWN');
  assert.doesNotMatch(h.elements.paperContent.innerHTML,/943\.968|\$999/);
  if(kind==='scope')assert.match(h.elements.paperFreshness.textContent,/ACCOUNT_OR_POLICY_REPLACED/);
  if(kind==='rollback')assert.match(h.elements.paperFreshness.textContent,/SOURCE_REVISION_ROLLBACK_OR_CONFLICT/);
});
test('partial and overnight positions remain positions until committed full close',async()=>{
  const h=harness();await h.controller.load();h.setNow((STAMP+86400)*1000);h.controller.refreshAge();
  assert.equal(h.elements.paperStatus.textContent,'STALE');assert.match(h.elements.paperContent.innerHTML,/1\.500000000000000000000000001/);
  const next=payload();next.observed_at+=86400;next.source_revision=next.projection_revision=3;next.positions={};h.setData(next);await h.controller.load();
  assert.match(h.elements.paperContent.innerHTML,/No open positions in this acknowledged projection/);
});
test('duplicate loads and repeated activation use one in-flight request',async()=>{
  const d=dom(), wait=deferred();let calls=0;
  const c=ui.createController({document:d.document,Abort:AbortController,clock:()=>STAMP*1000,schedule:()=>1,cancel(){},
    fetch:async()=>{calls++;return wait.promise;}});c.setActive(true);const first=c.load();c.setActive(true);await c.load();assert.equal(calls,1);
  wait.resolve({ok:true,json:async()=>payload()});await first;assert.match(d.elements.paperStatus.textContent,/ACKNOWLEDGED/);
});
test('mode replacement aborts and ignores an old response',async()=>{
  const d=dom(), wait=deferred();let signal;
  const c=ui.createController({document:d.document,Abort:AbortController,clock:()=>STAMP*1000,schedule:()=>1,cancel(){},
    fetch:async(url,options)=>{signal=options.signal;return wait.promise;}});c.setActive(true);const pending=c.load();c.setActive(false);c.setActive(true);
  assert.equal(signal.aborted,true);wait.resolve({ok:true,json:async()=>payload()});await pending;
  assert.doesNotMatch(d.elements.paperContent.innerHTML,/943\.968/);
});
test('timed-out response cannot become acknowledged even if a test transport ignores abort',async()=>{
  const d=dom(), wait=deferred();let timeout;
  const c=ui.createController({document:d.document,Abort:AbortController,clock:()=>STAMP*1000,schedule:fn=>{timeout=fn;return 1;},cancel(){},
    fetch:async()=>wait.promise});c.setActive(true);const pending=c.load();timeout();wait.resolve({ok:true,json:async()=>payload()});await pending;
  assert.equal(d.elements.paperStatus.textContent,'UNAVAILABLE');
});

function page(search='?mode=selected-paper',withModule=true) {
  const d=dom(), calls=[], loops=[];let data=payload();
  class Clock extends Date {static now(){return STAMP*1000;}}
  const context=vm.createContext({document:d.document,Date:Clock,AbortController,URLSearchParams,location:{search},
    setTimeout:()=>1,clearTimeout(){},fetch:async(url,options)=>{calls.push([url,options.method]);return {ok:true,json:async()=>clone(data)};},
    atlasPoll(fn,ms){loops.push({fn,ms});},atlasFetch:async url=>{calls.push([url,'GET']);return {ok:true,json:async()=>({board:[],runtime_refresh:{state:'FRESH'}})};}});
  if(withModule)vm.runInContext(external,context);vm.runInContext(inline,context);
  return {...d,calls,loops,context,setData(value){data=value;}};
}
test('actual HTML selected bootstrap and repeated polls never call legacy research GET',async()=>{
  const h=page();await h.context.load();await h.loops[0].fn();assert.equal(h.loops.length,1);assert.equal(h.loops[0].ms,10000);
  assert.equal(h.elements.researchWorkspace.hidden,true);assert.equal(h.elements.selectedPaper.hidden,false);
  assert.ok(h.calls.length>0);assert.ok(h.calls.every(([url,method])=>url===ui.ENDPOINT&&method==='GET'));
});
test('selected mode remains fail-closed if its external script fails to load',async()=>{
  const h=page('?mode=selected-paper',false);await h.context.load();assert.equal(h.calls.length,0);assert.equal(h.elements.paperStatus.textContent,'UNAVAILABLE');
});
test('research stays accessible only after explicit mode change',async()=>{
  const h=page();await h.context.load();vm.runInContext("setView('overview')",h.context);await h.context.load();
  assert.equal(h.elements.researchWorkspace.hidden,false);assert.ok(h.calls.some(([url])=>url==='/api/investments/quality-dips?limit=50'));
  vm.runInContext('setFinancialMode(true)',h.context);const old=h.calls.length;await h.context.load();assert.ok(h.calls.slice(old).every(([url])=>url===ui.ENDPOINT));
});
test('late research response cannot overwrite selected mode or initiate another legacy read',async()=>{
  const h=page(''),wait=deferred();let requestedInSelectedMode;
  h.context.atlasFetch=async url=>{requestedInSelectedMode=vm.runInContext('selectedFinancialMode',h.context);h.calls.push([url,'GET']);return wait.promise;};
  const old=h.context.load();vm.runInContext('setFinancialMode(true)',h.context);await h.context.load();
  wait.resolve({ok:true,json:async()=>({board:[],runtime_refresh:{state:'FRESH'}})});await old;
  assert.equal(requestedInSelectedMode,false);assert.equal(vm.runInContext('snapshot',h.context),null);
  assert.match(h.elements.paperContent.innerHTML,/943\.968/);
  assert.equal(h.calls.filter(([url])=>url==='/api/investments/quality-dips?limit=50').length,1);
});
test('responsive and accessible structural contract, without claiming layout/browser execution',()=>{
  for(const value of ['aria-live="polite"','aria-atomic="true"','aria-controls="selectedPaper"','scope="col"','@media(max-width:550px)','grid-template-columns:1fr'])assert.ok((html+external).includes(value),value);
  assert.match(html,/#selectedPaper\[hidden\],#researchWorkspace\[hidden\]/);
  assert.match(html,/overflow-wrap:anywhere/);assert.match(html,/\.paperTable\{overflow:auto/);
  assert.doesNotMatch(external,/method:\s*['"]POST['"]|\/commands/);
});
function automatic() {
  const d=payload();
  d.available_cash=d.cash;
  d.autonomous={schema:'QD_AUTO_ACTIVITY_V1',execution:'SIMULATED',session_state:'PAUSED',observed_at:STAMP,
    controls:'DISABLED_NOT_OPERATIONALLY_ACCEPTED',candidate:{symbol:'SPY'},l1_state:'FRESH',
    l1:{schema:'QD_AUTO_L1_V1',bid:'109.9',ask:'110',source_timestamp:STAMP,provider_id:'SYNTHETIC',feed_id:'FIXTURE',entitlement_id:'NOT_REAL'},
    decision:{id:'partial-fixture',kind:'EXIT',quantity:'0.4',reason:'EXIT_REVIEW_PARTIAL'},
    pending_exits:null,latest_refusal:{reason:'L1_STALE'}};
  return d;
}

test('explicit graceful shutdown outcome preserves incomplete position evidence',async()=>{
  const d=automatic();d.autonomous.shutdown_outcome={schema:'QD_AUTO_SHUTDOWN_V1',mode:'SHUTDOWN_FLATTEN',status:'SHUTDOWN_INCOMPLETE',position_state:'POSITION_OPEN'};
  const h=harness(d);await h.controller.load();
  assert.match(h.elements.paperContent.innerHTML,/Latest shutdown outcome<\/dt><dd>SHUTDOWN_INCOMPLETE/);
  assert.match(h.elements.paperContent.innerHTML,/Shutdown position state<\/dt><dd>POSITION_OPEN/);
  d.autonomous.shutdown_outcome.status='FAKE_CLEAN';h.setData(d);await h.controller.load();
  assert.equal(h.elements.paperStatus.textContent,'UNKNOWN');
});
test('autonomous evidence displays session L1 simulated decision and disabled-control explanation',async()=>{
  const h=harness(automatic());await h.controller.load();const s=h.elements.paperContent.innerHTML;
  for(const value of ['SIMULATED','PAUSED','109.9','110','SYNTHETIC','NOT_REAL','partial-fixture','EXIT_REVIEW_PARTIAL','L1_STALE'])assert.ok(s.includes(value));
  assert.match(s,/Financial Start\/Stop controls are disabled/);assert.doesNotMatch(s,/<button|<form/);
  assert.equal(h.requests.length,1);assert.equal(h.requests[0].options.method,'GET');
});
test('autonomous missing quote and pending exit evidence are unavailable',async()=>{
  const d=automatic();d.autonomous.l1=null;d.autonomous.l1_state='UNAVAILABLE';d.autonomous.candidate=null;
  const h=harness(d);await h.controller.load();const s=h.elements.paperContent.innerHTML;
  assert.match(s,/Observed bid<\/dt><dd>UNAVAILABLE/);assert.match(s,/Pending exit evidence<\/dt><dd>UNAVAILABLE/);
  assert.match(s,/Last verified ranked candidate<\/dt><dd>UNAVAILABLE/);
});
test('autonomous stale quote is explicit and never presented as connected live feed',async()=>{
  const d=automatic();d.autonomous.l1_state='STALE';const h=harness(d);await h.controller.load();
  assert.match(h.elements.paperContent.innerHTML,/L1 evidence state<\/dt><dd>STALE/);
  assert.match(h.elements.paperContent.innerHTML,/not a connected live feed/);
});
test('autonomous malformed activity clears prior balances',async()=>{
  const d=automatic();d.autonomous.execution='REAL';const h=harness();await h.controller.load();h.setData(d);await h.controller.load();
  assert.equal(h.elements.paperStatus.textContent,'UNKNOWN');assert.doesNotMatch(h.elements.paperContent.innerHTML,/943\.968/);
});
test('autonomous quote provenance and refusal explanations escape untrusted text',async()=>{
  const d=automatic();d.autonomous.l1.provider_id='<img src=x onerror=alert(1)>';d.autonomous.latest_refusal.reason='<script>bad()</script>';
  const h=harness(d);await h.controller.load();const s=h.elements.paperContent.innerHTML;
  assert.ok(s.includes('&lt;img'));assert.ok(s.includes('&lt;script&gt;'));assert.doesNotMatch(s,/<img|<script/);
});
test('autonomous cash-debited costs remain separate from realized allocations',async()=>{
  const d=automatic();d.cash_cost_evidence={schema:'QD_AUTO_CASH_COSTS_V1',fees:'0.02',slippage:'0.02',unallocated_entry_costs:'0.04'};
  const h=harness(d);await h.controller.load();const s=h.elements.paperContent.innerHTML;
  assert.match(s,/Modeled fees debited from cash<\/dt><dd>\$0\.02/);assert.match(s,/Unallocated entry costs<\/dt><dd>\$0\.04/);
  assert.match(s,/Realized fees/);assert.doesNotMatch(s,/Aggregate fees/);
  d.cash_cost_evidence.fees='-1';h.setData(d);await h.controller.load();assert.equal(h.elements.paperStatus.textContent,'UNKNOWN');
});
