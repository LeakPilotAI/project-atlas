import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import api from './view.cjs';
function row(n=1,changes={}){return {asset_class:'CRYPTO',asset_id:'CRYPTO:BTC-USD',model:'NO_CHANGE',horizon:'1D',
  reference:100,forecast_point:101,actual:104,status:'RESOLVED',interval:null,forecast_sha256:n.toString(16).padStart(64,'0'),
  issued_at:`2026-10-${String(n).padStart(2,'0')}T00:01:00Z`,target_at:`2026-10-${String(n+1).padStart(2,'0')}T00:00:00Z`,probability_up:.8,...changes};}
const metric=values=>api.logLossDiagnostics(values).cohorts[0];
for(const [p,actual,state,loss] of [[0,100,'FINITE',0],[1,104,'FINITE',0],[0,104,'INFINITE',null],[1,100,'INFINITE',null],[.5,104,'FINITE',Math.log(2)]])
  test(`log loss boundary ${p}/${actual}`,()=>{const c=metric([row(1,{probability_up:p,actual})]);assert.equal(c.loss_state,state);assert.equal(c.mean_log_loss,loss);assert.equal(c.flat_outcome_n,Number(actual===100));});
test('impossible event retains full denominator and no finite subset mean',()=>{
  const c=metric([row(1,{probability_up:1,actual:90}),row(2)]);assert.equal(c.probability_n,2);assert.equal(c.infinite_loss_n,1);assert.equal(c.finite_loss_n,1);assert.equal(c.mean_log_loss,null);
});
test('tiny probabilities use stable logs without clipping or false zero mean',()=>{
  assert.equal(metric([row(1,{probability_up:Number.MIN_VALUE})]).mean_log_loss,-Math.log(Number.MIN_VALUE));
  const c=metric([row(1,{probability_up:Number.MIN_VALUE,actual:90}),row(2,{probability_up:0,actual:90})]);
  assert.equal(c.loss_state,'UNAVAILABLE_NUMERIC_RANGE');assert.equal(c.mean_log_loss,null);assert.equal(c.zero_loss_n,1);
});
test('pending none and unrecorded remain separate from losses',()=>{
  const absent=row(3);delete absent.probability_up;const values=[row(),row(2,{probability_up:null}),absent,row(4,{status:'FORECAST_ONLY',actual:null})];
  const before=JSON.stringify(values),c=metric(values);assert.equal(c.probability_n,1);assert.equal(c.pending_n,1);assert.equal(c.no_probability_n,1);assert.equal(c.unrecorded_probability_n,1);assert.equal(JSON.stringify(values),before);
});
test('sample and overlapping-target policy survives additional proper score',()=>{
  const values=Array.from({length:20},(_,i)=>row(i+1,{issued_at:`2026-10-01T00:${String(i+1).padStart(2,'0')}:00Z`,target_at:'2026-10-02T00:00:00Z'}));
  const result=api.logLossDiagnostics(values);assert.equal(result.cohorts[0].status,'OVERLAPPING_TARGET_EVIDENCE');
  assert.equal(result.cohorts[0].distinct_target_n,1);assert.equal(result.calibration_established,false);assert.equal(result.winner_established,false);
});
for(const value of [true,NaN,Infinity,-.1,1.1,'0.5'])test(`malformed log-loss probability ${value}`,()=>assert.throws(()=>api.logLossDiagnostics([row(1,{probability_up:value})])));
test('empty probability scope remains unknown',()=>{
  const c=metric([row(1,{probability_up:null})]);assert.equal(c.loss_state,'UNAVAILABLE');assert.equal(c.half_probability_mean_log_loss,null);assert.deepEqual(api.logLossDiagnostics([]).cohorts,[]);
});
test('dataset and interval contexts do not pool error units',()=>{
  const c=api.logLossDiagnostics([row(),row(2,{interval:{lower:99,upper:104,level:.8}}),row(3,{asset_class:'ETF',asset_id:'ETF:SPY'})]);assert.equal(c.cohorts.length,3);
});

const actual=fs.readFileSync(new URL('../../../tests/fixtures/afi-log-loss-v1/corrected-browser.json',import.meta.url),'utf8');
const hash=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),n=>n.toString(16).padStart(2,'0')).join('');
async function changed(change){const e=JSON.parse(actual),d=JSON.parse(e.diagnostics_json);change(d);e.diagnostics_json=JSON.stringify(d);e.diagnostics_sha256=await hash(e.diagnostics_json);return JSON.stringify(e);}
test('actual Python forecast/outcome correction companion verifies native source and scores',async()=>{
  const result=await api.verifyLogLossEnvelope(actual);assert.equal(result.source_report.correction_n,1);assert.equal(result.source_report.forecast_n,1);
  assert.equal(result.diagnostics.cohorts[0].probability_n,1);assert.equal(result.diagnostics.cohorts[0].status,'INSUFFICIENT_EVIDENCE');
  assert.equal(result.diagnostics.original_forecast_history_verified,false);
});
for(const [name,change] of [
  ['fake-zero',d=>{d.cohorts[0].mean_log_loss=0;}],['negative-loss',d=>{d.cohorts[0].cases[0].log_loss=-1e-15;}],
  ['impossible-count',d=>{d.cohorts[0].infinite_loss_n=1;}],['missing-probability',d=>{d.cohorts[0].probability_n=0;}],
  ['case-outcome',d=>{d.cohorts[0].cases[0].actual_up=true;}],['epsilon-clipping',d=>{d.epsilon_clipping_applied=true;}],
  ['history-authority',d=>{d.original_forecast_history_verified=true;}],['winner',d=>{d.winner_established=true;}],
  ['array-substitution',d=>{d.cohorts={0:d.cohorts[0]};}],['extra-field',d=>{d.unrequested='SYNTHETIC_PRIVATE_VALUE';}],
])test(`rehashed ${name} cannot change log-loss evidence`,async()=>assert.rejects(api.verifyLogLossEnvelope(await changed(change))));
test('source and diagnostic byte changes require exact matching digests',async()=>{
  for(const key of ['source_report_json','diagnostics_json']){const e=JSON.parse(actual);e[key]+=' ';await assert.rejects(api.verifyLogLossEnvelope(JSON.stringify(e)));}
});
test('original caller report authority cannot hide behind a corrected outer digest',async()=>{
  const e=JSON.parse(actual),r=JSON.parse(e.source_report_json);r.trading_authority=true;e.source_report_json=JSON.stringify(r);e.source_report_sha256=await hash(e.source_report_json);
  await assert.rejects(api.verifyLogLossEnvelope(JSON.stringify(e)));
});

function documentFixture(){
  class Element{constructor(){this.children=[];this.listeners={};this.value='';this.textContent='';}replaceChildren(...v){this.children=v;}appendChild(v){this.children.push(v);}addEventListener(name,fn){this.listeners[name]=fn;}setAttribute(){}}
  const names=['report-file','forecast-rows','interval-rows','directional-rows','error-rows','reliability-rows','log-loss-rows','log-loss-status','error-status','pair-rows','paired-interval-rows','paired-probability-rows','pair-status','compare-a','compare-b','auto-pairs','asset-filter','state-filter','sort-order','visible-count','load-status','forecast-count','resolved-count','correction-count','report-asof','clear-report'];
  const ids=Object.fromEntries(names.map(k=>[k,new Element()]));ids['state-filter'].value='ALL';ids['sort-order'].value='target-asc';
  return {ids,getElementById:id=>ids[id],createElement:()=>new Element()};
}
const load=(doc,text)=>doc.ids['report-file'].listeners.change({target:{files:[{size:new TextEncoder().encode(text).length,text:async()=>text}]}});
test('mounted opt-in log loss follows filters and clears every view',async()=>{
  const doc=documentFixture();api.mount(doc);await load(doc,actual);
  assert.equal(doc.ids['forecast-count'].textContent,'1');assert.equal(doc.ids['log-loss-rows'].children.length,1);
  const cells=doc.ids['log-loss-rows'].children[0].children;assert.equal(cells[5].textContent,'1');assert.equal(cells[10].textContent,'FINITE');assert.equal(cells[13].textContent,'INSUFFICIENT_EVIDENCE');
  doc.ids['state-filter'].value='FORECAST_ONLY';doc.ids['state-filter'].listeners.input();assert.equal(doc.ids['log-loss-rows'].children.length,0);assert.match(doc.ids['log-loss-status'].textContent,/No visible forecasts/);
  doc.ids['clear-report'].listeners.click();assert.equal(doc.ids['forecast-rows'].children.length,0);assert.equal(doc.ids['log-loss-rows'].children.length,0);
});
test('mounted log-loss refusal clears earlier metrics and redacts bad input',async()=>{
  const doc=documentFixture();api.mount(doc);await load(doc,actual);await load(doc,'SYNTHETIC_PRIVATE_INPUT');
  assert.equal(doc.ids['log-loss-rows'].children.length,0);assert.equal(doc.ids['forecast-rows'].children.length,0);assert.ok(!doc.ids['load-status'].textContent.includes('SYNTHETIC_PRIVATE_INPUT'));
});
test('one loader serializes old report versus late companion file reads',async()=>{
  const doc=documentFixture();api.mount(doc);let release;const gate=new Promise(resolve=>{release=resolve;});
  const pending=doc.ids['report-file'].listeners.change({target:{files:[{size:actual.length,text:async()=>{await gate;return actual;}}]}});
  const envelope=JSON.parse(actual),legacy=JSON.stringify({schema:'AFI_BROWSER_REPORT_V1',report_json:envelope.source_report_json,payload_sha256:envelope.source_report_sha256});
  await load(doc,legacy);release();await pending;assert.equal(doc.ids['forecast-count'].textContent,'1');assert.equal(doc.ids['log-loss-rows'].children.length,0);
});
test('JSON fields cannot forge the private import marker',async()=>{
  const e=JSON.parse(actual),report=JSON.parse(e.source_report_json);report.source_report={forecast_n:999,rows:[],score:{scored_n:999}};report.diagnostics={minimum_samples:1};
  const text=JSON.stringify(report),legacy=JSON.stringify({schema:'AFI_BROWSER_REPORT_V1',report_json:text,payload_sha256:await hash(text)});
  const doc=documentFixture();api.mount(doc);await load(doc,legacy);assert.equal(doc.ids['forecast-count'].textContent,'1');assert.equal(doc.ids['log-loss-rows'].children.length,0);
});
test('built offline file includes opt-in pane and canonical inline hashes',async()=>{
  const {default:os}=await import('node:os'),{default:path}=await import('node:path'),{default:crypto}=await import('node:crypto'),{build}=await import('./build.cjs');
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'atlas-log-loss-')),output=path.join(root,'viewer.html');build(output);const html=fs.readFileSync(output,'utf8');
  assert.match(html,/id="log-loss-rows"/);assert.match(html,/no epsilon clipping|No epsilon clipping/);assert.match(html,/connect-src 'none'/);
  const script=html.match(/<script>([\s\S]*)<\/script>/)[1],style=html.match(/<style>([\s\S]*?)<\/style>/)[1];
  assert.ok(!script.includes('\r')&&!style.includes('\r'));
  for(const content of [script,style])assert.ok(html.includes("'sha256-"+crypto.createHash('sha256').update(content).digest('base64')+"'"));
  assert.equal(build(output),output);
});
