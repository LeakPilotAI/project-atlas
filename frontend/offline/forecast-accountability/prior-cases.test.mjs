import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import api from './view.cjs';
const reports=JSON.parse(fs.readFileSync(new URL('../../../tests/fixtures/afi-vintage-score-impact-v1/reports.json',import.meta.url),'utf8')).interval;
const prior=()=>structuredClone(reports[1].rows[0]);
const query=()=>({...prior(),forecast_sha256:'f'.repeat(64),issued_at:'2026-10-19T00:01:00+00:00',target_at:'2026-10-20T00:00:00+00:00',status:'PENDING_TARGET',actual:null,source_available_at:null,last_reconciled_asof:null});
test('earlier same-cohort context exposes only outcomes recorded by query cutoff',()=>{
 const rows=[query(),prior()],before=JSON.stringify(rows),m=api.priorCaseContext(rows,rows[0].forecast_sha256);
 assert.equal(m.prior_n,1);assert.equal(m.known_outcome_n,1);assert.equal(m.cases[0].actual,prior().actual);
 assert.equal(m.historical_availability_authenticated,false);assert.equal(m.similarity_ranking_established,false);assert.equal(JSON.stringify(rows),before);
});
test('later correction never backfills its value or an invented earlier label into context',()=>{
 const q=query(),late=structuredClone(reports[2].rows[0]),m=api.priorCaseContext([q,late],q.forecast_sha256);
 assert.equal(m.prior_n,1);assert.equal(m.unavailable_outcome_n,1);
 for(const key of ['actual','source_available_at','last_reconciled_asof','outcome_dataset_sha256','source_revision'])assert.equal(m.cases[0][key],null);
 assert.equal(m.cases[0].outcome_state,'UNAVAILABLE_AT_QUERY_CUTOFF');
});
for(const key of ['asset_id','horizon','model_version','forecast_dataset_version','input_source_id'])test(`context separates ${key}`,()=>{
 const p=prior(),q=query();p[key]=({asset_id:'CRYPTO:ETH-USD',horizon:'5D',model_version:'other',forecast_dataset_version:'other',input_source_id:'other'})[key];
 const m=api.priorCaseContext([q,p],q.forecast_sha256);assert.equal(m.prior_n,0);assert.equal(m.other_cohort_n,1);
});
test('same-time cases are not prior and unresolved values remain missing',()=>{
 const q=query(),p={...prior(),actual:null,status:'MISSING_OUTCOME'},equal={...query(),forecast_sha256:'e'.repeat(64)};
 const m=api.priorCaseContext([q,p,equal],q.forecast_sha256);assert.equal(m.not_prior_n,1);assert.equal(m.prior_n,1);assert.equal(m.cases[0].actual,null);
 assert.equal(m.cases[0].outcome_state,'NOT_RESOLVED_IN_SUPPLIED_VINTAGE');
});
test('cutoff uses exact timezone-aware microseconds and accepts only inclusive known times',()=>{
 const q=query(),p=prior();q.issued_at=p.last_reconciled_asof;
 assert.equal(api.priorCaseContext([q,p],q.forecast_sha256).known_outcome_n,1);
 q.issued_at='2026-10-18T11:59:59.999999+00:00';
 assert.equal(api.priorCaseContext([q,p],q.forecast_sha256).known_outcome_n,0);
});
test('empty, missing query and unbound provenance cannot supply prior context',()=>{
 assert.equal(api.priorCaseContext([]).status,'NO_VISIBLE_CASES');
 assert.equal(api.priorCaseContext([query()],'missing').status,'QUERY_NOT_VISIBLE');
 const q=query();delete q.model_version;delete q.lookback;
 assert.equal(api.priorCaseContext([q],q.forecast_sha256).status,'QUERY_PROVENANCE_UNAVAILABLE');
});
test('malformed issue and contradictory outcome clocks refuse rather than exposing values',()=>{
 const q=query();assert.throws(()=>api.priorCaseContext([{...q,issued_at:'bad'}],q.forecast_sha256));
 assert.throws(()=>api.priorCaseContext([q,{...prior(),last_reconciled_asof:'2026-10-10T00:00:00Z'}],q.forecast_sha256));
 assert.throws(()=>api.priorCaseContext([q,q],q.forecast_sha256));
});
test('prior context table uses exact values and clears on empty or replaced query',()=>{
 class E{constructor(){this.children=[];this.value='';this.textContent='';}replaceChildren(...v){this.children=v;}appendChild(v){this.children.push(v);}}
 const ids=Object.fromEntries(['memory-query','memory-rows','memory-status'].map(k=>[k,new E()]));
 const document={getElementById:k=>ids[k],createElement:()=>new E()},q=query();ids['memory-query'].value=q.forecast_sha256;
 api.renderPriorCases(document,[q,prior()]);assert.equal(ids['memory-rows'].children.length,1);
 assert.equal(ids['memory-rows'].children[0].children[5].textContent,String(prior().actual));
 api.renderPriorCases(document,[prior()]);assert.equal(ids['memory-rows'].children.length,0);assert.equal(ids['memory-query'].value,'');
 api.renderPriorCases(document,[]);assert.equal(ids['memory-rows'].children.length,0);
});
test('mounted prior-case selection resets on refused replacement, clear and superseded reads',async()=>{
 class E{constructor(){this.children=[];this.listeners={};this.value='';this.textContent='';}replaceChildren(...v){this.children=v;}appendChild(v){this.children.push(v);}setAttribute(){}addEventListener(k,v){this.listeners[k]=v;}}
 const ids=Object.fromEntries(['memory-query','memory-rows','memory-status','report-file','forecast-rows','asset-filter','state-filter','horizon-filter','sort-order','visible-count','load-status','forecast-count','resolved-count','correction-count','report-asof','clear-report'].map(k=>[k,new E()]));
 ids['state-filter'].value=ids['horizon-filter'].value='ALL';ids['sort-order'].value='target-asc';
 const document={getElementById:k=>ids[k],createElement:()=>new E()};api.mount(document);
 const report_json=JSON.stringify(reports[1]),raw=JSON.stringify({schema:'AFI_BROWSER_REPORT_V1',report_json,payload_sha256:createHash('sha256').update(report_json).digest('hex')});
 const load=text=>ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 await load(raw);ids['memory-query'].value=reports[1].rows[0].forecast_sha256;ids['memory-query'].listeners.input();
 assert.match(ids['memory-status'].textContent,/NO_PRIOR_CASES/);
 await load('{');assert.equal(ids['memory-query'].value,'');assert.equal(ids['memory-rows'].children.length,0);
 await load(raw);let finish;
 const pending=ids['report-file'].listeners.change({target:{files:[{size:1,text:()=>new Promise(resolve=>{finish=resolve;})}]}});
 ids['clear-report'].listeners.click();finish(raw);await pending;
 assert.equal(ids['memory-query'].value,'');assert.equal(ids['memory-rows'].children.length,0);assert.match(ids['memory-status'].textContent,/NO_VISIBLE_CASES/);
});
