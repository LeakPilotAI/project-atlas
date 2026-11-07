'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const api=require('./view.cjs');
const {build}=require('./build.cjs');
const hash=text=>crypto.createHash('sha256').update(text).digest('hex');
function report(asset='CRYPTO:BTC-USD',id='a'.repeat(64)){
 return {schema:'AFI_ACCOUNTABILITY_REPORT_V1',evidence_class:'SYNTHETIC',asof:'2026-10-19T00:00:00+00:00',
 rows:[{asset_id:asset,asset_class:'CRYPTO',model:'NO_CHANGE',horizon:'1D',issued_at:'2026-10-17T00:01:00+00:00',target_at:'2026-10-18T00:00:00+00:00',
 forecast_point:100,reference:100,actual:101,status:'RESOLVED',forecast_sha256:id,source_available_at:'2026-10-18T00:00:00+00:00',last_reconciled_asof:'2026-10-18T12:00:00+00:00',correction_n:0,history_n:1,expected_head:'b'.repeat(64)}],
 score:{issued_n:1,scored_n:1,pending_n:0,cohorts:[{n:1}]},forecast_n:1,correction_n:0,production_approved:false,trading_authority:false,recovery_authorized:false,
 calibration_established:false,live_feed_freshness_verified:false,history_completeness_verified:false};
}
function envelope(r){const text=typeof r==='string'?r:JSON.stringify(r);return JSON.stringify({schema:'AFI_BROWSER_REPORT_V1',report_json:text,payload_sha256:hash(text)});}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('valid byte-bound synthetic report imports without authority',async()=>{const r=report();assert.deepEqual(await api.verifyEnvelope(envelope(r),hash),r);});
test('input receipt provenance is validated and rendered for new reports',async()=>{
 const r=report(),row=r.rows[0];
 Object.assign(row,{input_observed_at:'2026-10-17T00:00:00+00:00',input_available_at:'2026-10-17T00:00:01+00:00',
  input_source_id:'daily-chart-fixture',input_source_revision:'a'.repeat(64),input_source_sha256:'b'.repeat(64)});
 assert.deepEqual(await api.verifyEnvelope(envelope(r),hash),r);
 const doc=fixtureDocument();api.mount(doc);const text=envelope(r);
 await doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 const cells=doc.ids['forecast-rows'].children[0].children;
 assert.equal(cells[5].textContent,row.input_observed_at);assert.equal(cells[6].textContent,row.input_available_at);
 assert.equal(cells[7].textContent,row.input_source_id);assert.equal(cells[8].textContent,row.input_source_revision);
 assert.equal(cells[9].textContent,row.input_source_sha256);
 for(const [key,value] of [['input_available_at','2026-10-16T23:59:00+00:00'],['input_source_sha256','invalid']]){
  const bad={...r,rows:[{...row,[key]:value}]};await assert.rejects(api.verifyEnvelope(envelope(bad),hash));
 }
});
test('modified bytes and missing cryptographic proof refuse',async()=>{const e=JSON.parse(envelope(report()));e.report_json+=' ';await assert.rejects(api.verifyEnvelope(JSON.stringify(e),hash),/digest/);e.payload_sha256='bad';await assert.rejects(api.verifyEnvelope(JSON.stringify(e),hash));});
for(const mutation of ['authority','class','count','duplicate','outcome','history','future','nonfinite','depth','scenario']){
 test(`malformed or misleading ${mutation} refuses`,async()=>{
  const r=report();
  if(mutation==='authority')r.production_approved=true;
  if(mutation==='class')r.rows[0].asset_class='ETF';
  if(mutation==='count')r.score.scored_n=100;
  if(mutation==='duplicate')r.rows.push({...r.rows[0]});
  if(mutation==='outcome')r.rows[0].actual=null;
  if(mutation==='history')r.rows[0].expected_head=null;
  if(mutation==='future'){r.rows[0].last_reconciled_asof=r.asof;r.rows[0].source_available_at='2026-10-19T00:00:00.000001+00:00';}
  if(mutation==='nonfinite')r.rows[0].forecast_point='not a number';
  if(mutation==='depth'){let v={};r.extra=v;for(let i=0;i<25;i++){v.next={};v=v.next;}}
  if(mutation==='scenario')r.rows[0].horizon='SCENARIO_2050';
  await assert.rejects(api.verifyEnvelope(envelope(r),hash));
 });
}
test('prototype keys are refused without mutating object prototypes',async()=>{const text=JSON.stringify(report()).replace('"schema":','"__proto__":{"polluted":true},"schema":');await assert.rejects(api.verifyEnvelope(envelope(text),hash));assert.equal({}.polluted,undefined);});
test('timestamp parsing preserves UTC identity and microsecond ordering',()=>{assert.equal(api.instant('2026-10-18T01:00:00+01:00'),api.instant('2026-10-18T00:00:00Z'));assert(api.instant('2026-10-18T00:00:00.000001Z')>api.instant('2026-10-18T00:00:00Z'));for(const t of ['2026-02-30T00:00:00Z','2026-01-01T00:00:00','bad'])assert.throws(()=>api.instant(t));});
test('asset/state filters and stable sort never mutate evidence',()=>{const r=report();r.rows.push({...r.rows[0],asset_id:'CRYPTO:ETH-USD',forecast_sha256:'c'.repeat(64)});const before=JSON.stringify(r);assert.equal(api.selectRows(r,'eth').length,1);assert.equal(api.selectRows(r,'','PENDING_TARGET').length,0);assert.equal(api.selectRows(r,'','ALL','asset')[0].asset_id,'CRYPTO:BTC-USD');assert.equal(JSON.stringify(r),before);assert.throws(()=>api.selectRows(r,'','TRADE'));});
test('old asynchronous verification cannot replace a newer selected report',async()=>{const states=[],waiters=new Map();const loader=api.createLoader(x=>states.push(x),text=>new Promise(resolve=>waiters.set(text,()=>resolve(hash(text)))));const a=report(),b=report('CRYPTO:ETH-USD','c'.repeat(64));const first=loader.load(envelope(a));const second=loader.load(envelope(b));await tick();waiters.get(JSON.stringify(b))();await second;waiters.get(JSON.stringify(a))();await first;assert.equal(states.at(-1).report.rows[0].asset_id,'CRYPTO:ETH-USD');});
test('clearing an in-flight load retains empty state and no cached evidence',async()=>{const states=[];let resolve;const loader=api.createLoader(x=>states.push(x),text=>new Promise(r=>resolve=()=>r(hash(text))));const pending=loader.load(envelope(report()));await tick();loader.clear();resolve();await pending;assert.equal(states.at(-1).status,'EMPTY');assert.equal(states.at(-1).report,null);});
test('file-read race cannot resurrect an older file',async()=>{const states=[];const loader=api.createLoader(x=>states.push(x),hash);let resolve;const old=loader.loadFile({size:50,text:()=>new Promise(r=>resolve=r)});await loader.load(envelope(report('CRYPTO:ETH-USD','c'.repeat(64))));resolve(envelope(report()));await old;assert.equal(states.at(-1).report.rows[0].asset_id,'CRYPTO:ETH-USD');});
test('a failed new load clears prior evidence and redacts parse/file errors',async()=>{const states=[];const loader=api.createLoader(x=>states.push(x),hash);await loader.load(envelope(report()));await loader.load('secret malformed raw value');assert.equal(states.at(-1).status,'REFUSED');assert.equal(states.at(-1).report,null);assert(!states.at(-1).message.includes('secret'));await loader.loadFile({size:1000001,text:async()=>envelope(report())});assert.equal(states.at(-1).status,'REFUSED');});
test('single-file build pins inline CSP hashes and is idempotent',()=>{const base=process.env.ATLAS_VIEWER_TEST_ROOT||os.tmpdir();const dir=fs.mkdtempSync(path.join(base,'viewer-'));const out=path.join(dir,'viewer.html');build(out);const raw=fs.readFileSync(out,'utf8');assert(raw.includes("connect-src 'none'"));assert(!raw.includes('unsafe-inline'));assert(raw.includes('scope="col"'));assert(raw.includes('aria-live="polite"'));assert(raw.includes('type="file"'));const script=raw.match(/<script>([\s\S]*?)<\/script>/)[1];assert(raw.includes(`sha256-${crypto.createHash('sha256').update(script).digest('base64')}`));build(out);assert.equal(fs.readFileSync(out,'utf8'),raw);fs.writeFileSync(out,'partial preserved');assert.throws(()=>build(out),/refusing overwrite/);assert.equal(fs.readFileSync(out,'utf8'),'partial preserved');});
test('client source uses no execution/network/storage or unsafe HTML sinks',()=>{const source=fs.readFileSync(path.join(__dirname,'view.cjs'),'utf8');for(const token of ['innerHTML','eval(','fetch(','WebSocket(','localStorage','sessionStorage'])assert(!source.includes(token));});

test('required build fsync failure propagates once, closes handle and preserves bytes',()=>{const base=process.env.ATLAS_VIEWER_TEST_ROOT||os.tmpdir();const dir=fs.mkdtempSync(path.join(base,'sync-failure-'));const out=path.join(dir,'viewer.html');const original=fs.fsyncSync;let calls=0;fs.fsyncSync=()=>{calls++;const error=new Error('synthetic fsync failure');error.code='EEXIST';throw error;};try{assert.throws(()=>build(out),/fsync failure/);}finally{fs.fsyncSync=original;}assert.equal(calls,1);const before=fs.readFileSync(out,'utf8');build(out);assert.equal(fs.readFileSync(out,'utf8'),before);});
test('short build writes preserve incomplete evidence and conflicting retry refuses',()=>{const base=process.env.ATLAS_VIEWER_TEST_ROOT||os.tmpdir();const dir=fs.mkdtempSync(path.join(base,'short-write-'));const out=path.join(dir,'viewer.html');const original=fs.writeSync;fs.writeSync=()=>0;try{assert.throws(()=>build(out),/Short/);}finally{fs.writeSync=original;}assert(fs.existsSync(out));assert.throws(()=>build(out),/refusing overwrite/);assert.equal(fs.readFileSync(out).length,0);});

for(const mutation of ['early-cutoff','early-source','missing-cutoff','head-without-history','late-pending-target','early-pending-publication']){
 test(`contradictory historical evidence ${mutation} refuses`,async()=>{
  const r=report(),row=r.rows[0];
  if(mutation==='early-cutoff')row.last_reconciled_asof='2026-10-17T12:00:00Z';
  if(mutation==='early-source')row.source_available_at='2026-10-17T12:00:00Z';
  if(mutation==='missing-cutoff'){row.status='MISSING_OUTCOME';row.actual=null;row.last_reconciled_asof=null;r.score={issued_n:1,scored_n:0,pending_n:1,cohorts:[]};}
  if(mutation==='head-without-history'){row.status='FORECAST_ONLY';row.actual=null;row.history_n=0;row.last_reconciled_asof=null;r.score={issued_n:1,scored_n:0,pending_n:1,cohorts:[]};}
  if(mutation==='late-pending-target'){row.status='PENDING_TARGET';row.actual=null;r.score={issued_n:1,scored_n:0,pending_n:1,cohorts:[]};}
  if(mutation==='early-pending-publication'){row.status='PENDING_PUBLICATION';row.actual=null;row.last_reconciled_asof='2026-10-17T12:00:00Z';r.score={issued_n:1,scored_n:0,pending_n:1,cohorts:[]};}
  await assert.rejects(api.verifyEnvelope(envelope(r),hash));
 });
}

function intervalReport(){const r=report();r.rows[0].interval={lower:99,upper:110,level:.8};r.interval_diagnostics=api.intervalDiagnostics(r.rows);return r;}
test('original intervals and inclusive coverage stay diagnostic only',async()=>{const r=intervalReport();const c=r.interval_diagnostics.cohorts[0];assert.equal(c.coverage,1);assert.equal(c.mean_interval_score,11);assert.equal(c.status,'INSUFFICIENT_EVIDENCE');assert.equal((await api.verifyEnvelope(envelope(r),hash)).forecast_n,1);});
for(const mutation of ['incomplete','boolean','level','point','missing-diagnostic','coverage','sample','duplicate','nonfinite-score']){
 test(`interval ${mutation} evidence refuses`,async()=>{const r=intervalReport();
 if(mutation==='incomplete')delete r.rows[0].interval.upper;
 if(mutation==='boolean')r.rows[0].interval.lower=true;
 if(mutation==='level')r.rows[0].interval.level=1;
 if(mutation==='point')r.rows[0].interval.upper=99;
 if(mutation==='missing-diagnostic')delete r.interval_diagnostics;
 if(mutation==='coverage')r.interval_diagnostics.cohorts[0].coverage=0;
 if(mutation==='sample')r.interval_diagnostics.cohorts[0].status='DIAGNOSTIC_ONLY';
 if(mutation==='duplicate')r.interval_diagnostics.cohorts.push(r.interval_diagnostics.cohorts[0]);
 if(mutation==='nonfinite-score'){r.rows[0].actual=1e308;r.rows[0].interval.level=.999999999999;}
 await assert.rejects(api.verifyEnvelope(envelope(r),hash));});
}
test('pending intervals have no coverage and levels stay separate',()=>{const r=intervalReport(),pending={...r.rows[0],status:'FORECAST_ONLY',actual:null};let d=api.intervalDiagnostics([pending]);assert.equal(d.cohorts[0].coverage,null);assert.equal(d.cohorts[0].pending_n,1);d=api.intervalDiagnostics([r.rows[0],{...r.rows[0],interval:{...r.rows[0].interval,level:.9}}]);assert.equal(d.cohorts.length,2);});

test('aggregate overflow refuses even when every individual score is finite',()=>{const r=intervalReport();r.rows[0].interval={lower:0,upper:1.6e308,level:.8};assert.throws(()=>api.intervalDiagnostics([r.rows[0],r.rows[0]]),/finite/);});

function fixtureDocument(){
 class Element{constructor(){this.children=[];this.listeners={};this.value='';this.textContent='';}replaceChildren(...items){this.children=items;}appendChild(item){this.children.push(item);}addEventListener(name,fn){this.listeners[name]=fn;}setAttribute(){} }
 const ids={};for(const name of ['report-file','forecast-rows','interval-rows','signed-error-rows','directional-rows','error-rows','reliability-rows','error-status','pair-rows','paired-interval-rows','paired-probability-rows','pair-status','compare-a','compare-b','auto-pairs','asset-filter','state-filter','sort-order','visible-count','load-status','forecast-count','resolved-count','correction-count','report-asof','clear-report'])ids[name]=new Element();
 ids['state-filter'].value='ALL';ids['sort-order'].value='target-asc';
 return {ids,getElementById:id=>ids[id],createElement:()=>new Element()};
}
test('mounted viewer renders intervals, respects filters and clears evidence',async()=>{
 const doc=fixtureDocument();api.mount(doc);const text=envelope(intervalReport());
 await doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 assert.equal(doc.ids['forecast-rows'].children.length,1);assert.equal(doc.ids['interval-rows'].children.length,1);
 assert.equal(doc.ids['interval-rows'].children[0].children.at(-5).textContent,'INSUFFICIENT_EVIDENCE');assert.equal(doc.ids['interval-rows'].children[0].children.at(-1).textContent,'RECORDED_TARGETS_ONLY');
 doc.ids['state-filter'].value='PENDING_TARGET';doc.ids['state-filter'].listeners.input();assert.equal(doc.ids['interval-rows'].children.length,0);
 doc.ids['clear-report'].listeners.click();assert.equal(doc.ids['forecast-rows'].children.length,0);assert.equal(doc.ids['interval-rows'].children.length,0);
});
test('mounted invalid replacement cannot retain earlier interval evidence',async()=>{
 const doc=fixtureDocument();api.mount(doc);let text=envelope(intervalReport());
 const load=()=>doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 await load();text='invalid secret payload';await load();
 assert.equal(doc.ids['interval-rows'].children.length,0);assert.equal(doc.ids['forecast-rows'].children.length,0);assert(!doc.ids['load-status'].textContent.includes('secret'));
});

test('interval model versions and lookbacks remain separate cohorts',()=>{const r=intervalReport(),a={...r.rows[0],model_version:'v1',lookback:5},b={...a,model_version:'v2'},c={...a,lookback:20};assert.equal(api.intervalDiagnostics([a,b,c]).cohorts.length,3);assert.throws(()=>api.intervalDiagnostics([{...r.rows[0],model_version:'v1'}]),/binding/);});
test('fractional sample counts cannot hide within rounding tolerance',async()=>{const r=intervalReport();r.interval_diagnostics.cohorts[0].resolved_n=1.0000000000000002;await assert.rejects(api.verifyEnvelope(envelope(r),hash));});

for(const field of ['forecast_dataset_sha256','release_source_sha256'])test(`interval cohorts separate ${field}`,()=>{
 const a={...intervalReport().rows[0],forecast_dataset_sha256:'a'.repeat(64),release_source_sha256:'b'.repeat(64)},b={...a,[field]:'c'.repeat(64)};
 assert.equal(api.intervalDiagnostics([a,b]).cohorts.length,2);
});
for(const changes of [{forecast_dataset_sha256:'bad'},{forecast_dataset_sha256:true},{forecast_dataset_sha256:'a'.repeat(64),release_source_sha256:false}])test(`malformed cohort binding ${JSON.stringify(changes)} refuses`,()=>{
 assert.throws(()=>api.intervalDiagnostics([{...intervalReport().rows[0],...changes}]));
});


test('frozen pre-partition interval export remains accepted and display derives bound cohort',async()=>{
 const raw=fs.readFileSync(path.join(__dirname,'../../../tests/fixtures/afi-legacy-v1/accountability-interval-unpartitioned.json'),'utf8');
 assert.equal(hash(raw),'0fa3fdab1837b3dea8ea8efaab44c22007f658d9aa2635e2886ce54db1f80672');
 const r=await api.verifyEnvelope(envelope(raw),hash);assert.equal(r.diagnostic_partition,undefined);
 assert.equal(api.intervalDiagnostics(r.rows).cohorts[0].cohort.forecast_dataset_sha256,r.rows[0].forecast_dataset_sha256);
});
test('new bound interval export requires exact provenance partitions',async()=>{
 const r=intervalReport();r.diagnostic_partition='DATASET_RELEASE_V1';r.rows[0].forecast_dataset_sha256='a'.repeat(64);r.rows[0].release_source_sha256=null;
 r.interval_diagnostics=api.intervalDiagnostics(r.rows);r.directional_diagnostics=api.directionalDiagnostics(r.rows);await api.verifyEnvelope(envelope(r),hash);
 delete r.interval_diagnostics.cohorts[0].cohort.forecast_dataset_sha256;await assert.rejects(api.verifyEnvelope(envelope(r),hash));
});
test('mounted legacy evidence displays safe dataset commitments',async()=>{
 const r=JSON.parse(fs.readFileSync(path.join(__dirname,'../../../tests/fixtures/afi-legacy-v1/accountability-interval-unpartitioned.json'),'utf8'));
 const doc=fixtureDocument();api.mount(doc);const text=envelope(r);await doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 assert(doc.ids['interval-rows'].children[0].children.some(c=>c.textContent===r.rows[0].forecast_dataset_sha256));
});


test('directional matrix includes flat outcomes and explicit false positives',()=>{
 const a=report().rows[0],rows=[{...a,forecast_point:110,actual:120},{...a,forecast_point:110,actual:90},{...a,forecast_point:110,actual:100},{...a,forecast_point:90,actual:120},{...a,forecast_point:100,actual:100}];
 const c=api.directionalDiagnostics(rows).cohorts[0];assert.deepEqual(c.matrix.UP,{DOWN:1,FLAT:1,UP:1});assert.equal(c.up.precision,1/3);assert.equal(c.up.recall,.5);assert.equal(c.directional_accuracy,.4);
 const pending=api.directionalDiagnostics([{...a,actual:null,status:'FORECAST_ONLY'}]).cohorts[0];assert.equal(pending.directional_accuracy,null);assert.equal(pending.up.precision,null);
});
for(const field of ['forecast_dataset_sha256','release_source_sha256'])test(`directional cohorts separate ${field}`,()=>{
 const a={...report().rows[0],forecast_dataset_sha256:'a'.repeat(64),release_source_sha256:'b'.repeat(64)};assert.equal(api.directionalDiagnostics([a,{...a,[field]:'c'.repeat(64)}]).cohorts.length,2);
});
for(const mutation of ['matrix','fractional-matrix','precision','missing','duplicate'])test(`directional ${mutation} substitution refuses`,async()=>{
 const r=intervalReport();r.diagnostic_partition='DATASET_RELEASE_V1';r.directional_diagnostics=api.directionalDiagnostics(r.rows);
 if(mutation==='matrix')r.directional_diagnostics.cohorts[0].matrix.UP.UP=99;
 if(mutation==='fractional-matrix')r.directional_diagnostics.cohorts[0].matrix.UP.UP=Number.EPSILON;
 if(mutation==='precision')r.directional_diagnostics.cohorts[0].up.precision=1;
 if(mutation==='missing')delete r.directional_diagnostics;
 if(mutation==='duplicate')r.directional_diagnostics.cohorts.push(r.directional_diagnostics.cohorts[0]);
 await assert.rejects(api.verifyEnvelope(envelope(r),hash));
});
test('malformed provenance without an interval is still refused',async()=>{
 const r=report();r.rows[0].forecast_dataset_sha256='bad';await assert.rejects(api.verifyEnvelope(envelope(r),hash));
});
test('mounted directional evidence follows filters and clears on replacement failure',async()=>{
 const doc=fixtureDocument();api.mount(doc);let text=envelope(report());const load=()=>doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 await load();assert.equal(doc.ids['directional-rows'].children.length,1);doc.ids['state-filter'].value='PENDING_TARGET';doc.ids['state-filter'].listeners.input();assert.equal(doc.ids['directional-rows'].children.length,0);
 doc.ids['state-filter'].value='ALL';await load();assert.equal(doc.ids['directional-rows'].children.length,1);text='invalid';await load();assert.equal(doc.ids['directional-rows'].children.length,0);
});


for(const field of ['forecast_dataset_manifest_sha256','forecast_code_sha256'])test(`both diagnostics separate ${field} under identical payload`,()=>{
 const a={...intervalReport().rows[0],forecast_dataset_sha256:'a'.repeat(64),release_source_sha256:null,forecast_dataset_manifest_sha256:'b'.repeat(64),forecast_dataset_id:'fixture',forecast_dataset_version:'v1',forecast_code_sha256:'c'.repeat(64)},b={...a,[field]:'d'.repeat(64)};
 assert.equal(api.intervalDiagnostics([a,b]).cohorts.length,2);assert.equal(api.directionalDiagnostics([a,b]).cohorts.length,2);
});


test('partial or invalid manifest/version bindings refuse in both diagnostics',()=>{
 for(const changes of [{forecast_dataset_manifest_sha256:'e'.repeat(64)},{forecast_dataset_id:'fixture'},{forecast_dataset_manifest_sha256:'e'.repeat(64),forecast_dataset_id:'fixture',forecast_dataset_version:true}]){
  const row={...intervalReport().rows[0],forecast_dataset_sha256:'a'.repeat(64),...changes};assert.throws(()=>api.intervalDiagnostics([row]));assert.throws(()=>api.directionalDiagnostics([row]));
 }
});


function rowBoundReport(){
 const r=JSON.parse(fs.readFileSync(path.join(__dirname,'../../../tests/fixtures/afi-legacy-v1/accountability-interval-unpartitioned.json'),'utf8'));
 r.score_rows_contract='ROW_BOUND_SCORE_V1';r.rows[0].score_cohort=JSON.parse(JSON.stringify(r.score.cohorts[0].cohort));r.rows[0].probability_up=null;return r;
}
for(const mutation of ['mae','rmse','direction','sample-status','probability','binding','missing-input','unknown-contract'])test(`row-bound score ${mutation} refuses`,async()=>{
 const r=rowBoundReport(),c=r.score.cohorts[0];
 if(mutation==='mae')c.mae=0;
 if(mutation==='rmse')c.rmse=0;
 if(mutation==='direction')c.directional_accuracy=1;
 if(mutation==='sample-status')c.status='DIAGNOSTIC_ONLY';
 if(mutation==='probability')c.brier=0;
 if(mutation==='binding')r.rows[0].score_cohort.asset_id='CRYPTO:ETH-USD';
 if(mutation==='missing-input')delete r.rows[0].probability_up;
 if(mutation==='unknown-contract')r.score_rows_contract='UNKNOWN';
 await assert.rejects(api.verifyEnvelope(envelope(r),hash));
});


test('valid complete row-bound score remains accepted without authority',async()=>{const r=rowBoundReport();assert.deepEqual(await api.verifyEnvelope(envelope(r),hash),r);});
for(const offset of [false,true])test(`duplicate forecast case under another hash refuses, offset=${offset}`,async()=>{
 const r=rowBoundReport(),row={...r.rows[0],forecast_sha256:'d'.repeat(64)};if(offset)row.issued_at='2026-10-17T01:01:00+01:00';r.rows.push(row);r.forecast_n=2;r.score.issued_n=2;r.score.scored_n=2;r.score.cohorts[0].n=2;r.score.cohorts[0].interval_n=2;
 r.directional_diagnostics=api.directionalDiagnostics(r.rows,false);r.interval_diagnostics=api.intervalDiagnostics(r.rows,false);
 await assert.rejects(api.verifyEnvelope(envelope(r),hash));
});


test('removing score contract cannot downgrade original score inputs',async()=>{const r=rowBoundReport();delete r.score_rows_contract;await assert.rejects(api.verifyEnvelope(envelope(r),hash));});
test('duplicate legacy case cannot inflate the sample count',async()=>{
 const r=rowBoundReport();delete r.score_rows_contract;delete r.rows[0].score_cohort;delete r.rows[0].probability_up;
 r.rows.push({...r.rows[0],forecast_sha256:'d'.repeat(64)});r.forecast_n=2;r.score.issued_n=2;r.score.scored_n=2;r.score.cohorts[0].n=2;r.score.cohorts[0].interval_n=2;
 r.directional_diagnostics=api.directionalDiagnostics(r.rows,false);r.interval_diagnostics=api.intervalDiagnostics(r.rows,false);await assert.rejects(api.verifyEnvelope(envelope(r),hash));
});


function configurationReport(){
 const r=rowBoundReport(),row=r.rows[0];r.score_rows_contract='ROW_BOUND_SCORE_V2';row.model_configuration_sha256='e'.repeat(64);row.score_cohort.model_configuration_sha256=row.model_configuration_sha256;r.score.cohorts[0].cohort.model_configuration_sha256=row.model_configuration_sha256;
 r.directional_diagnostics=api.directionalDiagnostics(r.rows,false);r.interval_diagnostics=api.intervalDiagnostics(r.rows,false);return r;
}
test('configuration-aware V2 score is accepted alongside legacy V1',async()=>{const r=configurationReport();assert.deepEqual(await api.verifyEnvelope(envelope(r),hash),r);await api.verifyEnvelope(envelope(rowBoundReport()),hash);});
for(const mutation of ['mismatch','missing-metadata','null','malformed','downgrade'])test(`configuration score ${mutation} refuses`,async()=>{
 const r=configurationReport(),row=r.rows[0];
 if(mutation==='mismatch')row.score_cohort.model_configuration_sha256='f'.repeat(64);
 if(mutation==='missing-metadata')delete row.score_cohort.model_configuration_sha256;
 if(mutation==='null')row.model_configuration_sha256=null;
 if(mutation==='malformed')row.model_configuration_sha256='bad';
 if(mutation==='downgrade')r.score_rows_contract='ROW_BOUND_SCORE_V1';
 await assert.rejects(api.verifyEnvelope(envelope(r),hash));
});


test('visible errors reuse original rows and never mutate the verified report',()=>{
 const r=rowBoundReport(),before=JSON.stringify(r),e=api.visibleErrors(r);
 assert.equal(e.status,'DIAGNOSTIC_ONLY');assert.equal(e.cohorts.length,1);
 const c=e.cohorts[0];assert.equal(c.mae,2);assert.equal(c.no_change_mae,2);assert.equal(c.mae_ratio_to_no_change,1);assert.equal(c.rmse,2);assert.equal(c.probability_n,0);assert.equal(c.brier,null);assert.equal(c.issued_n,1);assert.equal(c.pending_n,0);assert.equal(c.status,'INSUFFICIENT_EVIDENCE');assert.equal(JSON.stringify(r),before);
});
test('legacy prices remain useful while missing probability inputs stay unknown',()=>{const e=api.visibleErrors(report());assert.equal(e.status,'PARTIAL_LEGACY_INPUTS');assert.equal(e.cohorts[0].mae,1);assert.equal(e.cohorts[0].probability_n,null);assert.equal(e.cohorts[0].missing_probability_n,1);assert.equal(e.cohorts[0].brier,null);});
test('no visible forecasts never becomes zero error',()=>{const e=api.visibleErrors(rowBoundReport(),'ETH');assert.equal(e.status,'NO_VISIBLE_CASES');assert.deepEqual(e.cohorts,[]);});


function twoAssetErrors(){
 const r=rowBoundReport(),other=JSON.parse(JSON.stringify(r.rows[0]));other.asset_id='CRYPTO:ETH-USD';other.forecast_sha256='f'.repeat(64);other.score_cohort.asset_id=other.asset_id;
 r.rows.push(other);r.forecast_n=2;r.score.issued_n=2;r.score.scored_n=2;const c=JSON.parse(JSON.stringify(r.score.cohorts[0]));c.cohort.asset_id=other.asset_id;r.score.cohorts.push(c);
 r.directional_diagnostics=api.directionalDiagnostics(r.rows,false);r.interval_diagnostics=api.intervalDiagnostics(r.rows,false);return r;
}
test('error filters preserve asset cohorts and exact denominators',()=>{
 const r=twoAssetErrors();assert.equal(api.visibleErrors(r).cohorts.length,2);
 const one=api.visibleErrors(r,'eth');assert.equal(one.visible_n,1);assert.equal(one.cohorts[0].cohort.asset_id,'CRYPTO:ETH-USD');assert.equal(one.cohorts[0].n,1);
 assert.equal(api.visibleErrors(r,'','PENDING_TARGET').cohorts.length,0);
});
test('zero baseline produces unavailable ratio rather than fabricated zero or infinity',()=>{
 const r=rowBoundReport();r.rows[0].actual=138;Object.assign(r.score.cohorts[0],{mae:0,rmse:0,no_change_mae:0,no_change_rmse:0,mape_percent:0,smape_percent:0,mae_ratio_to_no_change:null,directional_accuracy:1,flat_outcome_n:1});r.directional_diagnostics=api.directionalDiagnostics(r.rows,false);r.interval_diagnostics=api.intervalDiagnostics(r.rows,false);
 const c=api.visibleErrors(r).cohorts[0];assert.equal(c.mae,0);assert.equal(c.no_change_mae,0);assert.equal(c.mae_ratio_to_no_change,null);
});
test('legacy numeric overflow is unavailable while original evidence remains intact',()=>{
 const r=report();r.rows[0].forecast_point=1e200;r.rows[0].reference=1;r.rows[0].actual=1;const raw=JSON.stringify(r),e=api.visibleErrors(r);
 assert.equal(e.status,'PARTIAL_NUMERIC_EVIDENCE');assert.equal(e.cohorts[0].status,'UNAVAILABLE_NUMERIC_RANGE');assert.equal(e.cohorts[0].mae,null);assert.equal(e.cohorts[0].n,1);assert.equal(JSON.stringify(r),raw);
});
test('mounted error comparisons follow filters and clear every stale result',async()=>{
 const doc=fixtureDocument();api.mount(doc);let text=envelope(twoAssetErrors());const load=()=>doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 await load();assert.equal(doc.ids['error-rows'].children.length,2);assert.equal(doc.ids['error-rows'].children[0].children[7].textContent,'2');
 doc.ids['asset-filter'].value='eth';doc.ids['asset-filter'].listeners.input();assert.equal(doc.ids['error-rows'].children.length,1);assert.equal(doc.ids['error-rows'].children[0].children[0].textContent,'CRYPTO:ETH-USD');
 text='invalid replacement';await load();for(const id of ['error-rows','forecast-rows','directional-rows','interval-rows'])assert.equal(doc.ids[id].children.length,0);
});
test('unsupported filter cannot leave earlier error evidence visible',async()=>{
 const doc=fixtureDocument();api.mount(doc);const text=envelope(rowBoundReport());await doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 assert.equal(doc.ids['error-rows'].children.length,1);doc.ids['state-filter'].value='INVALID';assert.doesNotThrow(()=>doc.ids['state-filter'].listeners.input());
 for(const id of ['error-rows','forecast-rows','directional-rows','interval-rows'])assert.equal(doc.ids[id].children.length,0);assert.equal(doc.ids['forecast-count'].textContent,'—');assert(doc.ids['load-status'].textContent.includes('Reload'));
});
test('legacy table shows recorded price error and unavailable missing probability',async()=>{
 const doc=fixtureDocument();api.mount(doc);const text=envelope(report());await doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 const cells=doc.ids['error-rows'].children[0].children;assert.equal(cells[7].textContent,'1');assert.equal(cells[12].textContent,'1');assert.equal(cells[13].textContent,'Unavailable');assert(doc.ids['error-status'].textContent.includes('Legacy'));
});


function pairRow(window,day=1,changes={}){
 return {asset_class:'CRYPTO',asset_id:'CRYPTO:BTC-USD',model:'ENDPOINT_DRIFT',model_version:'v1',lookback:window,model_configuration_sha256:(window===5?'a':'b').repeat(64),horizon:'1D',forecast_point:window===5?101:102,reference:100,actual:104,status:'RESOLVED',interval:null,forecast_sha256:(window*100+day).toString(16).padStart(64,'0'),forecast_dataset_sha256:'c'.repeat(64),forecast_dataset_manifest_sha256:'d'.repeat(64),forecast_dataset_id:'fixture',forecast_dataset_version:'v1',forecast_code_sha256:'f'.repeat(64),release_source_sha256:null,issued_at:`2026-10-${String(day).padStart(2,'0')}T00:01:00Z`,target_at:`2026-10-${String(day+1).padStart(2,'0')}T00:00:00Z`,source_revision:'v1',source_available_at:`2026-10-${String(day+1).padStart(2,'0')}T00:00:00Z`,last_reconciled_asof:'2026-10-20T00:00:00Z',outcome_dataset_sha256:'e'.repeat(64),...changes};
}
function paired(rows){const result=api.pairedDiagnostics(rows,'2026-10-20T00:00:00Z'),ids=new Map(result.models.map(m=>[m.cohort.lookback,m.id]));return api.pairedDiagnostics(rows,'2026-10-20T00:00:00Z',[[ids.get(5),ids.get(10)]]).comparisons[0];}
test('paired errors use only compatible shared cases and UTC identities',()=>{
 const p=paired([pairRow(5),pairRow(10,1,{issued_at:'2026-10-01T01:01:00+01:00'}),pairRow(5,2)]);assert.equal(p.paired_n,1);assert.equal(p.a_only_n,1);assert.equal(p.a_mae,3);assert.equal(p.b_mae,2);assert.equal(p.a_minus_b_mae,1);assert.equal(p.distinct_target_n,1);
});
for(const changes of [{actual:105},{source_revision:'v2'},{outcome_dataset_sha256:'9'.repeat(64)}])test(`incompatible paired outcome ${JSON.stringify(changes)} stays unscored`,()=>{const p=paired([pairRow(5),pairRow(10,1,changes)]);assert.equal(p.outcome_conflict_n,1);assert.equal(p.paired_n,0);assert.equal(p.a_mae,null);});
test('pending outcomes are not borrowed from the other model',()=>{const p=paired([pairRow(5),pairRow(10,1,{actual:null,status:'FORECAST_ONLY',source_revision:null,source_available_at:null,last_reconciled_asof:null,outcome_dataset_sha256:null})]);assert.equal(p.pending_shared_n,1);assert.equal(p.b_mae,null);});
test('paired comparison cap requires explicit model selection',()=>{
 const rows=Array.from({length:13},(_,i)=>pairRow(i+2,1,{model_configuration_sha256:(i+1000).toString(16).padStart(64,'0'),forecast_sha256:(i+2000).toString(16).padStart(64,'0')}));
 const auto=api.pairedDiagnostics(rows,'2026-10-20T00:00:00Z');assert.equal(auto.possible_pair_n,78);assert.equal(auto.status,'EXPLICIT_PAIR_SELECTION_REQUIRED');assert.equal(auto.comparisons.length,0);
 assert.equal(api.pairedDiagnostics(rows,'2026-10-20T00:00:00Z',[[auto.models[0].id,auto.models[1].id]]).comparisons.length,1);
});
test('repeated targets are reported rather than treated as independent evidence',()=>{
 const rows=[];for(let i=0;i<20;i++)for(const w of [5,10])rows.push(pairRow(w,1,{forecast_sha256:(w*1000+i).toString(16).padStart(64,'0'),issued_at:`2026-10-01T00:${String(i+1).padStart(2,'0')}:00Z`}));
 const p=paired(rows);assert.equal(p.paired_n,20);assert.equal(p.distinct_target_n,1);assert.equal(p.status,'OVERLAPPING_TARGET_EVIDENCE');
});
test('duplicate or stale explicit pair requests refuse',()=>{
 const rows=[pairRow(5),pairRow(10)],models=api.pairedDiagnostics(rows,'2026-10-20T00:00:00Z').models,ids=models.map(m=>m.id);
 assert.throws(()=>api.pairedDiagnostics(rows,'2026-10-20T00:00:00Z',[ids,ids.slice().reverse()]));assert.throws(()=>api.pairedDiagnostics(rows,'2026-10-20T00:00:00Z',[[ids[0],'stale-id']]));
});
test('rehashed paired diagnostics cannot invent model counts or winners',async()=>{
 for(const key of ['model_n','winner_established']){
  const r=rowBoundReport();r.paired_model_contract='MATCHED_CASE_V1';r.paired_model_diagnostics=api.pairedDiagnostics(r.rows,r.asof);r.paired_model_diagnostics[key]=true;await assert.rejects(api.verifyEnvelope(envelope(r),hash));
 }
});


test('mounted actual paired export supports explicit roles, filters and failure clearing',async()=>{
 const dir=path.join(__dirname,'../../../tests/fixtures/afi-paired-v1'),raw=fs.readFileSync(path.join(dir,'corrected-browser.json'),'utf8'),provenance=JSON.parse(fs.readFileSync(path.join(dir,'provenance.json'),'utf8'));
 assert.equal(hash(raw),provenance.sha256);const r=await api.verifyEnvelope(raw,hash),ids=new Map(r.paired_model_diagnostics.models.map(m=>[m.cohort.lookback,m.id]));
 const doc=fixtureDocument();api.mount(doc);let text=raw;const load=()=>doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});await load();
 assert.equal(doc.ids['pair-rows'].children.length,1);assert.equal(doc.ids['pair-rows'].children[0].children[5].textContent,'1');
 doc.ids['compare-a'].value=ids.get(5);doc.ids['compare-a'].listeners.input();assert.equal(doc.ids['pair-rows'].children.length,0);
 doc.ids['compare-b'].value=ids.get(10);doc.ids['compare-b'].listeners.input();let cells=doc.ids['pair-rows'].children[0].children;assert(cells[2].textContent.includes('window 5'));assert.equal(cells[13].textContent,'15.75');assert.equal(cells[14].textContent,'16');
 doc.ids['state-filter'].value='PENDING_TARGET';doc.ids['state-filter'].listeners.input();assert.equal(doc.ids['pair-rows'].children.length,0);
 doc.ids['state-filter'].value='ALL';doc.ids['auto-pairs'].listeners.click();assert.equal(doc.ids['pair-rows'].children.length,1);
 text='invalid replacement';await load();assert.equal(doc.ids['pair-rows'].children.length,0);assert.equal(doc.ids['compare-a'].value,'');assert.equal(doc.ids['compare-a'].children.length,1);
});
test('exact binary interval identities stay distinct without inventing a second point model',()=>{
 const a=pairRow(5,1,{interval:{lower:100,upper:104,level:.8}}),b=pairRow(5,1,{forecast_sha256:'9'.repeat(64),interval:{lower:100,upper:104,level:.9}});
 const result=api.pairedDiagnostics([a,b],'2026-10-20T00:00:00Z');assert.equal(result.model_n,2);assert.equal(result.possible_pair_n,0);assert(result.models[0].id.includes('FLOAT64:'));
});

function intervalPairRows(){return [pairRow(5,1,{interval:{lower:100,upper:104,level:.8}}),pairRow(10,1,{interval:{lower:100,upper:103,level:.8}})];}
function intervalPaired(rows){const models=api.pairedDiagnostics(rows,'2026-10-20T00:00:00Z').models,ids=new Map(models.map(m=>[m.cohort.lookback,m.id]));return api.pairedIntervalDiagnostics(rows,'2026-10-20T00:00:00Z',[[ids.get(5),ids.get(10)]]).comparisons[0];}
test('paired intervals retain their own denominator and inclusive coverage',()=>{
 const rows=intervalPairRows(),before=JSON.stringify(rows),p=intervalPaired(rows);assert.equal(p.interval_paired_n,1);assert.equal(p.a_coverage,1);assert.equal(p.b_coverage,0);assert.equal(p.a_mean_interval_score,4);assert(Math.abs(p.b_mean_interval_score-13)<1e-12);assert(Math.abs(p.a_minus_b_interval_score+9)<1e-12);assert.equal(JSON.stringify(rows),before);
});
for(const interval of [null,{lower:100,upper:103,level:.9}])test(`missing or mismatched interval stays unknown ${JSON.stringify(interval)}`,()=>{
 const rows=intervalPairRows();rows[1].interval=interval;const p=intervalPaired(rows);assert.equal(p.point_paired_n,1);assert.equal(p.interval_paired_n,0);assert.equal(p.a_coverage,null);assert.equal(p.missing_interval_n+p.level_mismatch_n,1);
});
test('interval correction mismatch remains unscored until both outcome vintages agree',()=>{
 const rows=intervalPairRows();rows[1].source_revision='v2';let p=intervalPaired(rows);assert.equal(p.outcome_conflict_n,1);assert.equal(p.interval_paired_n,0);rows[0].source_revision='v2';p=intervalPaired(rows);assert.equal(p.interval_paired_n,1);
});
test('rehashed interval claims and missing companion contracts refuse',async()=>{
 for(const field of ['model_n','calibration_established']){const r=rowBoundReport();r.paired_interval_contract='MATCHED_INTERVAL_V1';r.paired_interval_diagnostics=api.pairedIntervalDiagnostics(r.rows,r.asof);r.paired_interval_diagnostics[field]=true;await assert.rejects(api.verifyEnvelope(envelope(r),hash));}
 const r=rowBoundReport();r.paired_interval_diagnostics=api.pairedIntervalDiagnostics(r.rows,r.asof);await assert.rejects(api.verifyEnvelope(envelope(r),hash));
});
test('mounted interval comparisons follow explicit roles and clear on failed replacement',async()=>{
 const raw=fs.readFileSync(path.join(__dirname,'../../../tests/fixtures/afi-paired-v1/corrected-browser.json'),'utf8'),r=await api.verifyEnvelope(raw,hash),ids=new Map(r.paired_model_diagnostics.models.map(m=>[m.cohort.lookback,m.id]));
 const doc=fixtureDocument();api.mount(doc);let text=raw;const load=()=>doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});await load();
 assert.equal(doc.ids['paired-interval-rows'].children.length,1);assert.equal(doc.ids['paired-interval-rows'].children[0].children[5].textContent,'0');
 doc.ids['compare-a'].value=ids.get(5);doc.ids['compare-a'].listeners.input();assert.equal(doc.ids['paired-interval-rows'].children.length,0);
 doc.ids['compare-b'].value=ids.get(10);doc.ids['compare-b'].listeners.input();assert.equal(doc.ids['paired-interval-rows'].children.length,1);
 text='broken';await load();assert.equal(doc.ids['paired-interval-rows'].children.length,0);
});

function probabilityRows(){return [pairRow(5,1,{probability_up:.8}),pairRow(10,1,{probability_up:.6})];}
function probabilityPaired(rows){const models=api.pairedDiagnostics(rows,'2026-10-20T00:00:00Z').models,ids=new Map(models.map(m=>[m.cohort.lookback,m.id]));return api.pairedProbabilityDiagnostics(rows,'2026-10-20T00:00:00Z',[[ids.get(5),ids.get(10)]]).comparisons[0];}
test('paired Brier errors use the same event and explicit uninformative baseline',()=>{
 const rows=probabilityRows(),raw=JSON.stringify(rows),p=probabilityPaired(rows);assert.equal(p.probability_paired_n,1);assert(Math.abs(p.a_brier-.04)<1e-12);assert(Math.abs(p.b_brier-.16)<1e-12);assert(Math.abs(p.a_minus_b_brier+.12)<1e-12);assert.equal(p.uninformative_baseline_brier,.25);assert.equal(JSON.stringify(rows),raw);
});
test('missing probability is unknown while recorded zero and flat outcomes are valid',()=>{
 const rows=probabilityRows();delete rows[0].probability_up;rows[1].probability_up=null;let p=probabilityPaired(rows);assert.equal(p.missing_probability_n,1);assert.equal(p.probability_paired_n,0);assert.equal(p.a_brier,null);assert.equal(p.cases[0].a_probability_state,'UNRECORDED');assert.equal(p.cases[0].b_probability_state,'NONE');
 for(const row of rows){row.probability_up=0;row.actual=100;}p=probabilityPaired(rows);assert.equal(p.flat_outcome_n,1);assert.equal(p.actual_up_n,0);assert.equal(p.a_brier,0);
});
for(const invalid of [true,-.1,1.1,'0.5',undefined])test(`malformed probability refuses ${String(invalid)}`,()=>{const rows=probabilityRows();rows[1].probability_up=invalid;assert.throws(()=>probabilityPaired(rows));});
test('probability outcome corrections cannot be mixed or create samples',()=>{
 const rows=probabilityRows();rows[1].source_revision='v2';let p=probabilityPaired(rows);assert.equal(p.outcome_conflict_n,1);assert.equal(p.probability_paired_n,0);rows[0].source_revision='v2';p=probabilityPaired(rows);assert.equal(p.probability_paired_n,1);
});
test('rehashed probability summaries cannot invent evidence or omit companion markers',async()=>{
 for(const field of ['model_n','calibration_established']){const r=rowBoundReport();r.paired_probability_contract='MATCHED_PROBABILITY_V1';r.paired_probability_diagnostics=api.pairedProbabilityDiagnostics(r.rows,r.asof);r.paired_probability_diagnostics[field]=true;await assert.rejects(api.verifyEnvelope(envelope(r),hash));}
 const r=rowBoundReport();r.paired_probability_diagnostics=api.pairedProbabilityDiagnostics(r.rows,r.asof);await assert.rejects(api.verifyEnvelope(envelope(r),hash));
});
test('mounted probability evidence follows roles and clears stale missing-input results',async()=>{
 const raw=fs.readFileSync(path.join(__dirname,'../../../tests/fixtures/afi-paired-v1/corrected-browser.json'),'utf8'),r=await api.verifyEnvelope(raw,hash),ids=new Map(r.paired_model_diagnostics.models.map(m=>[m.cohort.lookback,m.id]));
 const doc=fixtureDocument();api.mount(doc);let text=raw;const load=()=>doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});await load();
 assert.equal(doc.ids['paired-probability-rows'].children.length,1);let cells=doc.ids['paired-probability-rows'].children[0].children;assert.equal(cells[5].textContent,'0');assert.equal(cells[7].textContent,'1');assert.equal(cells[12].textContent,'Unavailable');
 doc.ids['compare-a'].value=ids.get(5);doc.ids['compare-a'].listeners.input();assert.equal(doc.ids['paired-probability-rows'].children.length,0);doc.ids['compare-b'].value=ids.get(10);doc.ids['compare-b'].listeners.input();assert.equal(doc.ids['paired-probability-rows'].children.length,1);
 text='broken';await load();assert.equal(doc.ids['paired-probability-rows'].children.length,0);
});

test('published empirical probability forecasts display paired scores after immutable corrections',async()=>{
 const dir=path.join(__dirname,'../../../tests/fixtures/afi-probability-baseline-v1'),raw=fs.readFileSync(path.join(dir,'corrected-browser.json'),'utf8'),provenance=JSON.parse(fs.readFileSync(path.join(dir,'provenance.json'),'utf8'));
 assert.equal(hash(raw),provenance.sha256);const r=await api.verifyEnvelope(raw,hash),ids=new Map(r.paired_model_diagnostics.models.map(m=>[m.cohort.lookback,m.id]));assert.equal(r.correction_n,2);
 const doc=fixtureDocument();api.mount(doc);await doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(raw),text:async()=>raw}]}});
 doc.ids['compare-a'].value=ids.get(5);doc.ids['compare-a'].listeners.input();doc.ids['compare-b'].value=ids.get(10);doc.ids['compare-b'].listeners.input();
 const cells=doc.ids['paired-probability-rows'].children[0].children;assert.equal(cells[5].textContent,'1');assert.equal(cells[7].textContent,'0');assert.equal(cells[12].textContent,'0.111111');assert.equal(cells[13].textContent,'0.132231');assert.equal(cells[15].textContent,'0.25');assert.equal(cells[18].textContent,'INSUFFICIENT_EVIDENCE');
 assert.equal(doc.ids['paired-interval-rows'].children[0].children[5].textContent,'0');
 doc.ids['state-filter'].value='PENDING_TARGET';doc.ids['state-filter'].listeners.input();assert.equal(doc.ids['paired-probability-rows'].children.length,0);
});

test('reliability bin edges retain zero, boundaries and probability one',()=>{
 const r=api.probabilityReliability([[0,0],[.1,1],[.999,1],[1,1]]);assert.deepEqual(r.calibration_bins.map(b=>[b.bin,b.n]),[[0,1],[1,1],[9,2]]);assert.equal(r.probability_n,4);
});
test('weighted reliability gap uses the recorded sample denominator',()=>{
 const r=api.probabilityReliability([[.1,0],[.1,0],[.1,0],[.9,0]]);assert(Math.abs(r.expected_calibration_error-.3)<1e-12);assert(Math.abs(r.brier-.21)<1e-12);
});
test('reliability displays empty bins as unknown rather than zero error',()=>{
 const c=api.reliabilityDiagnostics([pairRow(5,1,{probability_up:null})]).cohorts[0];assert.equal(c.probability_n,0);assert.equal(c.no_probability_n,1);assert.equal(c.expected_calibration_error,null);assert.equal(c.calibration_bins.length,10);assert(c.calibration_bins.every(b=>b.status==='EMPTY'&&b.mean_probability===null));assert.equal(c.calibration_bins[9].upper_inclusive,true);
});
test('partial legacy reliability has an explicit recorded-only denominator',()=>{
 const c=api.reliabilityDiagnostics([pairRow(5,1,{probability_up:.8}),pairRow(5,2,{probability_up:null}),pairRow(5,3)]).cohorts[0];assert.equal(c.probability_n,1);assert.equal(c.unrecorded_probability_n,1);assert.equal(c.no_probability_n,1);assert.equal(c.status,'PARTIAL_LEGACY_INPUTS');assert(Math.abs(c.brier-.04)<1e-12);
});
test('reliability repeated-target warning applies to the populated bin',()=>{
 const rows=Array.from({length:20},(_,i)=>pairRow(5,1,{probability_up:.5,forecast_sha256:(i+1000).toString(16).padStart(64,'0'),issued_at:`2026-10-01T00:${String(i+1).padStart(2,'0')}:00Z`}));const c=api.reliabilityDiagnostics(rows).cohorts[0];assert.equal(c.distinct_target_n,1);assert.equal(c.status,'OVERLAPPING_TARGET_EVIDENCE');assert.equal(c.calibration_bins[5].status,'OVERLAPPING_TARGET_EVIDENCE');
});
test('malformed reliability pairs refuse before metrics',()=>{
 for(const pair of [[true,1],[.2,true],[-.1,0],[1.1,1],[NaN,0],[.5,2]])assert.throws(()=>api.probabilityReliability([pair]));
});
test('reliability refuses duplicate forecasts and equivalent UTC case aliases',()=>{
 const a=pairRow(5,1,{probability_up:.8});assert.throws(()=>api.reliabilityDiagnostics([a,{...a}]));assert.throws(()=>api.reliabilityDiagnostics([a,{...a,forecast_sha256:'9'.repeat(64),issued_at:'2026-10-01T01:01:00+01:00'}]));
});
test('actual published probability bins follow filters and clear after invalid input',async()=>{
 const raw=fs.readFileSync(path.join(__dirname,'../../../tests/fixtures/afi-probability-baseline-v1/corrected-browser.json'),'utf8'),doc=fixtureDocument();api.mount(doc);let text=raw;const load=()=>doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});await load();
 assert.equal(doc.ids['reliability-rows'].children.length,20);const populated=doc.ids['reliability-rows'].children.find(row=>row.children[2].textContent==='5'&&row.children[10].textContent==='0.6');assert(populated);assert.equal(populated.children[13].textContent,'1');assert.equal(populated.children[15].textContent,'0.666667');assert.equal(populated.children[16].textContent,'1');assert.equal(populated.children[17].textContent,'0.333333');
 doc.ids['state-filter'].value='PENDING_TARGET';doc.ids['state-filter'].listeners.input();assert.equal(doc.ids['reliability-rows'].children.length,0);doc.ids['state-filter'].value='ALL';doc.ids['state-filter'].listeners.input();assert.equal(doc.ids['reliability-rows'].children.length,20);text='invalid';await load();assert.equal(doc.ids['reliability-rows'].children.length,0);
});

test('actual corrected equity ETF crypto batch exports stay separate under viewer filters',async()=>{
 const dir=path.join(__dirname,'../../../tests/fixtures/afi-batch-accountability-v1'),raw=fs.readFileSync(path.join(dir,'corrected-browser.json'),'utf8'),provenance=JSON.parse(fs.readFileSync(path.join(dir,'provenance.json'),'utf8'));assert.equal(hash(raw),provenance.sha256);
 const r=await api.verifyEnvelope(raw,hash);assert.equal(r.forecast_n,3);assert.equal(r.correction_n,3);assert.deepEqual(new Set(r.rows.map(row=>row.asset_class)),new Set(['US_EQUITY','ETF','CRYPTO']));
 const doc=fixtureDocument();api.mount(doc);let text=raw;const load=()=>doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});await load();assert.equal(doc.ids['forecast-rows'].children.length,3);assert.equal(doc.ids['reliability-rows'].children.length,30);
 for(const query of ['aapl','ETF:SPY','BTC-USD']){doc.ids['asset-filter'].value=query;doc.ids['asset-filter'].listeners.input();assert.equal(doc.ids['forecast-rows'].children.length,1);assert.equal(doc.ids['reliability-rows'].children.length,10);}
 doc.ids['asset-filter'].value='';doc.ids['asset-filter'].listeners.input();assert.equal(doc.ids['forecast-rows'].children.length,3);text='invalid';await load();assert.equal(doc.ids['forecast-rows'].children.length,0);assert.equal(doc.ids['reliability-rows'].children.length,0);
});


for(const schema of ['AFI_ASSUMPTION_SCENARIOS_V1','AFI_ASSUMPTION_SCENARIO_REQUEST_V1'])test(`scenario selection ${schema} refuses with useful guidance and clears scores`,async()=>{
 const states=[],loader=api.createLoader(s=>states.push(s),hash);
 await loader.load(envelope(report()));assert.equal(states.at(-1).status,'VERIFIED');
 await loader.load(JSON.stringify({schema,title:'SYNTHETIC_PRIVATE',trading_authority:false}));
 const refused=states.at(-1);assert.equal(refused.status,'REFUSED');assert.equal(refused.report,null);
 assert.match(refused.message,/separately generated scenario HTML/);assert.match(refused.message,/not established/);
 assert.ok(!refused.message.includes('SYNTHETIC_PRIVATE'));
});

test('scenario authority claim retains central refusal before kind guidance',async()=>{
 const states=[],loader=api.createLoader(s=>states.push(s),hash);
 await loader.load(JSON.stringify({schema:'AFI_ASSUMPTION_SCENARIOS_V1',trading_authority:true}));
 assert.equal(states.at(-1).status,'REFUSED');assert.equal(states.at(-1).report,null);
 assert.match(states.at(-1).message,/Authority or acceptance/);
});


test('mounted signed errors follow filters and clear with main evidence',async()=>{
 const doc=fixtureDocument();api.mount(doc);const text=envelope(report());
 await doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 const body=doc.ids['signed-error-rows'];assert.equal(body.children.length,1);
 const cells=body.children[0].children.map(c=>c.textContent);assert.equal(cells.at(-2),'-1');assert.equal(cells.at(-1),'DESCRIPTIVE_ONLY');
 doc.ids['state-filter'].value='PENDING_TARGET';doc.ids['state-filter'].listeners.input();assert.equal(body.children.length,0);
 doc.ids['clear-report'].listeners.click();assert.equal(body.children.length,0);
});


for(const action of ['clear','invalid'])test(`signed errors clear immediately on ${action} without prior filtering`,async()=>{
 const doc=fixtureDocument();api.mount(doc);const text=envelope(report());
 await doc.ids['report-file'].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});
 assert.equal(doc.ids['signed-error-rows'].children.length,1);
 if(action==='clear')doc.ids['clear-report'].listeners.click();
 else await doc.ids['report-file'].listeners.change({target:{files:[{size:1,text:async()=>'{'}]}});
 assert.equal(doc.ids['signed-error-rows'].children.length,0);
});
