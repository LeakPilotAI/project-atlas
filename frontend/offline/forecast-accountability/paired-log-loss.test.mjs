import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import api from './view.cjs';
const asof='2026-10-20T00:00:00+00:00';
function row(lookback,day=1,changes={}){return {asset_class:'CRYPTO',asset_id:'CRYPTO:BTC-USD',model:'ENDPOINT_DRIFT',model_version:'v1',lookback,model_configuration_sha256:(lookback===5?'a':'b').repeat(64),horizon:'1D',forecast_point:lookback===5?101:102,reference:100,actual:104,status:'RESOLVED',interval:null,
 forecast_sha256:(lookback*100+day).toString(16).padStart(64,'0'),forecast_dataset_sha256:'c'.repeat(64),forecast_dataset_manifest_sha256:'d'.repeat(64),forecast_dataset_id:'fixture',forecast_dataset_version:'v1',forecast_code_sha256:'f'.repeat(64),release_source_sha256:null,
 issued_at:`2026-10-${String(day).padStart(2,'0')}T00:01:00Z`,target_at:`2026-10-${String(day+1).padStart(2,'0')}T00:00:00Z`,source_revision:'v1',source_available_at:`2026-10-${String(day+1).padStart(2,'0')}T00:00:00Z`,last_reconciled_asof:asof,outcome_dataset_sha256:'e'.repeat(64),probability_up:.8,...changes};}
const pair=(a=.8,b=.6,changes={})=>[row(5,1,{probability_up:a,...changes}),row(10,1,{probability_up:b,...changes})];
const metric=rows=>api.pairedLogLossDiagnostics(rows,asof).comparisons[0];
test('paired log loss uses exact shared denominator not individual-model means',()=>{
 const p=metric([...pair(),row(5,2,{probability_up:.99})]);assert.equal(p.probability_paired_n,1);assert.equal(p.b_only_n,1);assert.equal(p.a_mean_log_loss,-Math.log(.6));assert.equal(p.b_mean_log_loss,-Math.log(.8));
});
for(const [a,b,expected] of [[0,.5,'POSITIVE_INFINITY'],[.5,0,'NEGATIVE_INFINITY'],[0,0,'UNDEFINED_BOTH_INFINITE']])test(`explicit infinite difference ${expected}`,()=>{
 const rows=pair(a,b),base=metric(rows),ids=Object.fromEntries([base.a,base.b].map(id=>[JSON.parse(id).lookback,id]));
 const p=api.pairedLogLossDiagnostics(rows,asof,[[ids[5],ids[10]]]).comparisons[0];assert.equal(p.difference_state,expected);assert.equal(p.a_minus_b_mean_log_loss,null);assert.equal(p.cases[0].a_minus_b_log_loss,null);
});
test('both aggregate infinities stay undefined when impossible cases differ',()=>{
 const p=metric([...pair(0,.5),row(5,2,{probability_up:.5}),row(10,2,{probability_up:0})]);
 assert.equal(p.a_infinite_loss_n,1);assert.equal(p.b_infinite_loss_n,1);assert.equal(p.undefined_difference_n,0);assert.equal(p.difference_state,'UNDEFINED_BOTH_INFINITE');
});
test('equal exact probabilities permit finite ties without a model winner',()=>{
 const p=metric(pair(.8,.8));assert.equal(p.difference_state,'FINITE');assert.equal(p.a_minus_b_mean_log_loss,0);assert.equal(api.pairedLogLossDiagnostics(pair(),asof).winner_established,false);
});
test('cancelling opposite finite differences remain numerically unavailable',()=>{
 const p=metric([...pair(.8,.2),row(5,2,{probability_up:.2}),row(10,2,{probability_up:.8})]);assert.equal(p.difference_state,'UNAVAILABLE_NUMERIC_RANGE');assert.equal(p.finite_difference_n,2);assert.equal(p.a_minus_b_mean_log_loss,null);
});
for(const fault of ['pending','missing','outcome','reference','dataset'])test(`paired refusal retains ${fault} count`,()=>{
 const rows=pair();
 if(fault==='pending')Object.assign(rows[1],{status:'FORECAST_ONLY',actual:null,source_revision:null,source_available_at:null,last_reconciled_asof:null,outcome_dataset_sha256:null});
 if(fault==='missing')delete rows[1].probability_up;if(fault==='outcome')rows[1].source_revision='v2';if(fault==='reference')rows[1].reference=99;if(fault==='dataset')rows[1].forecast_dataset_manifest_sha256='9'.repeat(64);
 const p=metric(rows);assert.equal(p.shared_n,1);assert.equal(p.probability_paired_n,0);assert.equal(p.a_mean_log_loss,null);
 const field={pending:'pending_shared_n',missing:'missing_probability_n',outcome:'outcome_conflict_n',reference:'reference_conflict_n',dataset:'unassessed_shared_n'}[fault];assert.equal(p[field],1);
});
const actual=fs.readFileSync(new URL('../../../tests/fixtures/afi-log-loss-v2/corrected-browser.json',import.meta.url),'utf8');
const hash=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),n=>n.toString(16).padStart(2,'0')).join('');
async function changed(change){const e=JSON.parse(actual),d=JSON.parse(e.diagnostics_json);change(d);e.diagnostics_json=JSON.stringify(d);e.diagnostics_sha256=await hash(e.diagnostics_json);return JSON.stringify(e);}
test('actual two-model corrected V2 fixture verifies source and paired scores',async()=>{
 const r=await api.verifyLogLossEnvelope(actual),p=r.diagnostics.paired_log_loss_diagnostics.comparisons[0];assert.equal(r.source_report.forecast_n,2);assert.equal(r.source_report.correction_n,2);assert.equal(p.probability_paired_n,1);assert.equal(p.status,'INSUFFICIENT_EVIDENCE');
});
for(const [name,change] of [
 ['zero-difference',d=>{d.paired_log_loss_diagnostics.comparisons[0].a_minus_b_mean_log_loss=0;}],
 ['mean',d=>{d.paired_log_loss_diagnostics.comparisons[0].a_mean_log_loss=0;}],
 ['count',d=>{d.paired_log_loss_diagnostics.comparisons[0].probability_paired_n=2;}],
 ['missing-pair',d=>{d.paired_log_loss_diagnostics.comparisons=[];}],
 ['winner',d=>{d.paired_log_loss_diagnostics.winner_established=true;}],
 ['difference-state',d=>{d.paired_log_loss_diagnostics.comparisons[0].difference_state='UNDEFINED_BOTH_INFINITE';}],
])test(`rehashed ${name} cannot replace paired evidence`,async()=>assert.rejects(api.verifyLogLossEnvelope(await changed(change))));
test('changed pair role declaration cannot reuse automatic comparison output',async()=>{
 const e=JSON.parse(actual),p=JSON.parse(e.diagnostics_json).paired_log_loss_diagnostics.comparisons[0];e.model_pairs=[[p.b,p.a]];
 await assert.rejects(api.verifyLogLossEnvelope(JSON.stringify(e)));
});
function documentFixture(){
 class Element{constructor(){this.children=[];this.listeners={};this.value='';this.textContent='';}replaceChildren(...v){this.children=v;}appendChild(v){this.children.push(v);}addEventListener(name,fn){this.listeners[name]=fn;}setAttribute(){}}
 const names=['report-file','forecast-rows','interval-rows','directional-rows','error-rows','reliability-rows','log-loss-rows','log-loss-status','paired-log-loss-rows','paired-log-loss-status','error-status','pair-rows','paired-interval-rows','paired-probability-rows','pair-status','compare-a','compare-b','auto-pairs','asset-filter','state-filter','sort-order','visible-count','load-status','forecast-count','resolved-count','correction-count','report-asof','clear-report'];
 const ids=Object.fromEntries(names.map(k=>[k,new Element()]));ids['state-filter'].value='ALL';ids['sort-order'].value='target-asc';return {ids,getElementById:id=>ids[id],createElement:()=>new Element()};
}
const load=(doc,text)=>doc.ids['report-file'].listeners.change({target:{files:[{size:new TextEncoder().encode(text).length,text:async()=>text}]}});
test('mounted fixed pair plan retains denominators under state filter and asset search',async()=>{
 const doc=documentFixture();api.mount(doc);await load(doc,actual);assert.equal(doc.ids['paired-log-loss-rows'].children.length,1);
 assert.equal(doc.ids['paired-log-loss-rows'].children[0].children[5].textContent,'1');
 doc.ids['state-filter'].value='PENDING_TARGET';doc.ids['state-filter'].listeners.input();assert.equal(doc.ids['log-loss-rows'].children.length,0);assert.equal(doc.ids['paired-log-loss-rows'].children.length,1);
 assert.match(doc.ids['paired-log-loss-status'].textContent,/do not rescore this fixed paired plan/);
 doc.ids['asset-filter'].value='UNOBSERVED';doc.ids['asset-filter'].listeners.input();assert.equal(doc.ids['paired-log-loss-rows'].children.length,0);assert.match(doc.ids['paired-log-loss-status'].textContent,/0 of 1/);
});
test('failed V2 replacement clears both original and paired metrics',async()=>{
 const doc=documentFixture();api.mount(doc);await load(doc,actual);await load(doc,'SYNTHETIC_PRIVATE_INPUT');assert.equal(doc.ids['paired-log-loss-rows'].children.length,0);assert.equal(doc.ids['forecast-rows'].children.length,0);assert.ok(!doc.ids['load-status'].textContent.includes('SYNTHETIC_PRIVATE_INPUT'));
});
test('V1 companion remains unchanged and cannot masquerade as a paired plan',async()=>{
 const v1=fs.readFileSync(new URL('../../../tests/fixtures/afi-log-loss-v1/corrected-browser.json',import.meta.url),'utf8');const result=await api.verifyLogLossEnvelope(v1);assert.equal(result.diagnostics.schema,'AFI_LOG_LOSS_DIAGNOSTICS_V1');
 const doc=documentFixture();api.mount(doc);await load(doc,actual);await load(doc,v1);assert.equal(doc.ids['paired-log-loss-rows'].children.length,0);assert.equal(doc.ids['log-loss-rows'].children.length,1);
});
