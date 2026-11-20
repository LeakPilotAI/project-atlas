import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {createHash,webcrypto} from 'node:crypto';
import {File} from 'node:buffer';
import api from './view.cjs';
import viewer from './mount.cjs';
import {build} from './build.mjs';
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.attributes={};this.listeners=new Map();this.value='';this._text='';}
  set textContent(text){this._text=String(text);this.children=[];}
  get textContent(){return this._text+this.children.map(node=>node.textContent).join(' ');}
  set innerHTML(_value){throw Error('HTML injection attempted');}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=nodes;}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(key,listener){this.listeners.set(key,listener);}
  removeEventListener(key,listener){if(this.listeners.get(key)===listener)this.listeners.delete(key);}
}
function document(){const elements=new Map(['market-file','clear-market','market-status','market-clock','market-results','market-symbol','market-import-identity'].map(id=>[id,new Element()]));return {getElementById:id=>elements.get(id),createElement:tag=>new Element(tag),elements};}
const fixture=name=>fs.readFileSync(new URL('../../../tests/fixtures/market-replay-v1/'+name,import.meta.url),'utf8');
const file=text=>new File([text],'fixture.json',{type:'application/json'});
function setup(custom=api){const doc=document();return {doc,app:viewer.mount(doc,custom),results:doc.getElementById('market-results'),status:doc.getElementById('market-status')};}
function temp(){return fs.mkdtempSync(path.join(os.tmpdir(),'atlas-market-viewer-'));}
for(const [name,title] of [['api.json','Completed bar closes'],['quote-quality.json','Quote-reference quality'],['research.json','Recorded analysis'],['research-replay.json','Every planned decision'],['research-comparison.json','Every planned pair'],['market-refusal.json','Source refused the request']])test(`native local File and validators render ${name}`,async()=>{const {app,results}=setup();assert.equal((await app.loadFile(file(fixture(name)))).status,'LOADED');assert.ok(results.textContent.includes(title));assert.ok(app.current());});
test('all missing/unknown/refused decisions remain visible',async()=>{const {app,results}=setup();await app.loadFile(file(fixture('api.json')));assert.match(results.textContent,/MISSING/);assert.match(results.textContent,/Unavailable/);assert.match(results.textContent,/Unavailable/);await app.loadFile(file(fixture('research-replay.json')));assert.match(results.textContent,/Refused/);assert.match(results.textContent,/Planned decisions/);});
test('valid source refusal never claims usable prices',async()=>{const {app,status}=setup();await app.loadFile(file(fixture('market-refusal.json')));assert.match(status.textContent,/No usable prices/);assert.equal(app.current().status,'REFUSED');});
for(const fault of ['malformed','unsupported','authority','unsafe-key'])test(`bad replacement ${fault} clears previous evidence`,async()=>{const {app,results}=setup();await app.loadFile(file(fixture('api.json')));let raw='broken';if(fault==='unsupported')raw='{"schema":"UNKNOWN"}';if(fault==='authority'){const v=JSON.parse(fixture('api.json'));v.network_authorized=true;raw=JSON.stringify(v);}if(fault==='unsafe-key')raw=fixture('api.json').replace('{','{"__proto__":{},');assert.equal((await app.loadFile(file(raw))).status,'REFUSED');assert.equal(results.textContent,'');assert.equal(app.current(),null);});
test('oversized declared file is refused before read',async()=>{const {app}=setup();let read=false;const result=await app.loadFile({size:1000001,text:()=>{read=true;return fixture('api.json');}});assert.equal(result.status,'REFUSED');assert.equal(read,false);});
test('actual UTF8 read bound rejects false file-size claims',async()=>{const {app}=setup();assert.equal((await app.loadFile({size:1,text:async()=>'€'.repeat(400000)})).status,'REFUSED');});
test('file read failure clears old content without leaking details',async()=>{const {app,status,results}=setup();await app.loadFile(file(fixture('api.json')));assert.equal((await app.loadFile({size:1,text:async()=>{throw Error('private-path');}})).status,'REFUSED');assert.equal(results.textContent,'');assert.doesNotMatch(status.textContent,/private-path/);});
test('source text is displayed as text without HTML execution',async()=>{const {app,results}=setup();const v=JSON.parse(fixture('research.json'));v.analysis.reference_source='<img src=x onerror=alert(1)>';assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'LOADED');assert.ok(results.textContent.includes(v.analysis.reference_source));});
test('late file read cannot restore older data across types',async()=>{const {app}=setup();let finish;const old=app.loadFile({size:1,text:()=>new Promise(resolve=>{finish=resolve;})});await app.loadFile(file(fixture('quote-quality.json')));finish('broken old file');assert.equal((await old).status,'SUPERSEDED');assert.equal(app.current().schema,'ATLAS_QUOTE_QUALITY_V1');});
test('late native crypto verification cannot restore an older report',async()=>{let release,started;const gate=new Promise(resolve=>{release=resolve;}),ready=new Promise(resolve=>{started=resolve;});const custom={...api,verifyResearchReplay:async raw=>{started();await gate;return api.verifyResearchReplay(raw);}};const {app}=setup(custom);const old=app.loadFile(file(fixture('research-replay.json')));await ready;await app.loadFile(file(fixture('api.json')));release();assert.equal((await old).status,'SUPERSEDED');assert.equal(app.current().schema,'ATLAS_MARKET_REPLAY_V1');});
test('clear and disposal cancel pending data and remove event handlers',async()=>{const {app,doc,results}=setup();let release;const pending=app.loadFile({size:1,text:()=>new Promise(resolve=>{release=resolve;})});app.clear();release(fixture('api.json'));assert.equal((await pending).status,'SUPERSEDED');assert.equal(results.textContent,'');app.dispose();assert.equal(doc.getElementById('market-file').listeners.size,0);assert.equal(doc.getElementById('clear-market').listeners.size,0);assert.equal((await app.loadFile(file(fixture('api.json')))).status,'DISPOSED');});
test('render commit failure refuses and clears',async()=>{const {app,results}=setup();const original=results.replaceChildren.bind(results);let count=0;results.replaceChildren=(...nodes)=>{if(++count===2)throw Error('synthetic rendering');original(...nodes);};assert.equal((await app.loadFile(file(fixture('api.json')))).status,'REFUSED');assert.equal(results.textContent,'');assert.equal(app.current(),null);});
test('persistent cleanup failure is explicit, never success',async()=>{const {app,results}=setup();results.replaceChildren=()=>{throw Error('synthetic DOM unavailable');};await assert.rejects(()=>app.loadFile(file(fixture('api.json'))),AggregateError);assert.equal(app.current(),null);});
test('current accessor cannot mutate the displayed model',async()=>{const {app}=setup();await app.loadFile(file(fixture('api.json')));app.current().rows.length=0;assert.equal(app.current().rows.length,2);});
test('built HTML is self-contained with exact CSP hashes and native crypto',async()=>{const output=path.join(temp(),'viewer.html');const result=build(output),html=fs.readFileSync(output,'utf8');assert.equal(createHash('sha256').update(html).digest('hex'),result.sha256);assert.equal(result.production_approved,false);const script=html.match(/<script>([\s\S]*)<\/script>/)[1],style=html.match(/<style>([\s\S]*?)<\/style>/)[1];for(const text of [script,style])assert.ok(html.includes("'sha256-"+createHash('sha256').update(text).digest('base64')+"'"));assert.match(html,/connect-src 'none'/);assert.doesNotMatch(html,/<script[^>]+src=|https?:\/\//);const doc=document();const sandbox={document:doc,crypto:webcrypto,TextEncoder,structuredClone,fetch:()=>{throw Error('Network forbidden');}};Object.defineProperty(sandbox,'localStorage',{get(){throw Error('Storage forbidden');}});vm.runInNewContext(script,sandbox,{timeout:2000});doc.getElementById('market-file').files=[file(fixture('research-replay.json'))];await doc.getElementById('market-file').listeners.get('change')();assert.match(doc.getElementById('market-results').textContent,/Every planned decision/);assert.match(html,/Production NO-GO/);});
test('existing output is never overwritten',()=>{const output=path.join(temp(),'viewer.html');fs.writeFileSync(output,'original');assert.throws(()=>build(output));assert.equal(fs.readFileSync(output,'utf8'),'original');});
test('native junction/symlink output parent is refused',()=>{const root=temp(),target=path.join(root,'target'),alias=path.join(root,'alias');fs.mkdirSync(target);fs.symlinkSync(target,alias,process.platform==='win32'?'junction':'dir');assert.throws(()=>build(path.join(alias,'viewer.html')),/Unsafe output/);assert.equal(fs.existsSync(path.join(target,'viewer.html')),false);});
test('failed fsync preserves evidence and never acknowledges build',()=>{const output=path.join(temp(),'viewer.html'),original=fs.fsyncSync;try{fs.fsyncSync=()=>{throw Error('synthetic fsync');};assert.throws(()=>build(output),/synthetic fsync/);}finally{fs.fsyncSync=original;}assert.equal(fs.existsSync(output),true);assert.throws(()=>build(output));});
test('short write refuses and retains partial evidence',()=>{const output=path.join(temp(),'viewer.html'),original=fs.writeSync;try{fs.writeSync=()=>0;assert.throws(()=>build(output),/Short HTML/);}finally{fs.writeSync=original;}assert.equal(fs.existsSync(output),true);});
test('read-back mismatch is not successful publication',()=>{const output=path.join(temp(),'viewer.html'),original=fs.fsyncSync;try{fs.fsyncSync=fd=>{fs.writeSync(fd,Buffer.from('x'),0,1,0);original(fd);};assert.throws(()=>build(output),/read-back/);}finally{fs.fsyncSync=original;}assert.equal(fs.existsSync(output),true);});
test('publication and descriptor-close failures both remain visible',()=>{const output=path.join(temp(),'viewer.html'),sync=fs.fsyncSync,close=fs.closeSync;let failedDescriptor;try{fs.fsyncSync=fd=>{failedDescriptor=fd;throw Error('synthetic sync');};fs.closeSync=fd=>{close(fd);if(fd===failedDescriptor)throw Error('synthetic close');};assert.throws(()=>build(output),error=>error instanceof AggregateError&&error.errors.length===2);}finally{fs.fsyncSync=sync;fs.closeSync=close;}});
test('stale retained values are separate from unavailable usable prices',async()=>{const {app,results}=setup();const v=JSON.parse(fixture('api.json'));v.asof='2026-10-20T12:05:10+00:00';for(const kind of ['rows','quote_rows'])for(const row of v[kind])if(row.symbol==='SPY'){row.status='STALE';row.age_seconds+=240;row.price=null;}assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'LOADED');assert.match(results.textContent,/Stale at report clock/);assert.match(results.textContent,/Usable at report clock/);assert.match(results.textContent,/Last recorded close/);assert.match(results.textContent,/Last recorded reference/);assert.equal(app.current().rows.find(r=>r.symbol==='SPY').price,null);});
test('friendly state labels never relabel a symbol named FRESH',async()=>{const {app,results}=setup();const v=JSON.parse(fixture('api.json'));for(const kind of ['rows','quote_rows'])for(const row of v[kind])if(row.symbol==='SPY')row.symbol='FRESH';await app.loadFile(file(JSON.stringify(v)));function cells(node){return [node,...node.children.flatMap(cells)];}assert.ok(cells(results).some(node=>node.tagName==='td'&&node.textContent==='FRESH'));assert.equal(app.current().rows.find(r=>r.symbol==='FRESH').symbol,'FRESH');});

test('quality view preserves interior gaps and recorded lifecycle refusal',async()=>{const {app,results}=setup();const value=JSON.parse(fixture('quality.json'));value.lifecycle={status:'RECOVERY_REQUIRED',authenticated:false,live_process_state_verified:false,record_n:2,expected_head:'a'.repeat(64)};assert.equal((await app.loadFile(file(JSON.stringify(value)))).status,'LOADED');assert.match(results.textContent,/Missing interior minutes/);assert.match(results.textContent,/Recovery remains prohibited/);assert.match(results.textContent,/never full-session completeness/);assert.equal(app.current().recovery_authorized,false);});
test('invalid quality import clears prior view',async()=>{const {app,results}=setup();await app.loadFile(file(fixture('api.json')));const value=JSON.parse(fixture('quality.json'));value.lifecycle.authenticated=true;assert.equal((await app.loadFile(file(JSON.stringify(value)))).status,'REFUSED');assert.equal(results.textContent,'');});

test('empty quality cannot masquerade as zero gaps or complete coverage',async()=>{const {app,results}=setup();const v=JSON.parse(fixture('quality.json'));v.windows=[];v.observed_bar_n=0;v.status='NO_OBSERVATIONS';assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'LOADED');assert.match(results.textContent,/No retained observations/);assert.match(results.textContent,/No session coverage, freshness or missed-event conclusion/);assert.equal(app.current().windows.length,0);});
test('truncated quality keeps explicit retained-window warning',async()=>{const {app,results}=setup();const v=JSON.parse(fixture('quality.json'));v.history_window_truncated=true;assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'LOADED');assert.match(results.textContent,/History is truncated/);assert.equal(app.current().windows[0].missing_minutes_between_observed_bars,1);});
test('past-session quality does not claim current freshness',async()=>{const {app,results}=setup();const v=JSON.parse(fixture('quality.json'));v.asof='2026-11-03T01:02:10+00:00';v.current_market_session='CLOSED';v.windows[0].latest_completed_bar_age_seconds=3610;v.windows[0].status='PAST_SESSION';assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'LOADED');assert.match(results.textContent,/PAST_SESSION/);assert.equal(app.current().provider_freshness_verified,false);});
test('empty quality count contradiction clears earlier evidence',async()=>{const {app,results}=setup();await app.loadFile(file(fixture('quality.json')));const v=JSON.parse(fixture('quality.json'));v.windows=[];v.status='NO_OBSERVATIONS';assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'REFUSED');assert.equal(results.textContent,'');});

test('vintage viewer verifies receipts and preserves every planned case',async()=>{const {app,results}=setup();const raw=fixture('bar-vintages.json');const expected=await api.verifyVintageReplay(raw);assert.equal((await app.loadFile(file(raw))).status,'LOADED');assert.match(results.textContent,/Every vintage decision/);assert.match(results.textContent,/Unchanged confirmations/);assert.match(results.textContent,/not authenticated arrival history/);assert.equal(app.current().cases.length,expected.planned_decision_n);assert.deepEqual(app.current().status_counts,expected.status_counts);});
test('tampered vintage evidence clears loaded quality',async()=>{const {app,results}=setup();await app.loadFile(file(fixture('quality.json')));const v=JSON.parse(fixture('bar-vintages.json'));v.payload_sha256='0'.repeat(64);assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'REFUSED');assert.equal(results.textContent,'');});
test('late vintage verification cannot replace newer quality',async()=>{let release,started;const wait=new Promise(resolve=>{release=resolve;}),ready=new Promise(resolve=>{started=resolve;});const {app}=setup({...api,verifyVintageReplay:async raw=>{started();await wait;return api.verifyVintageReplay(raw);}});const old=app.loadFile(file(fixture('bar-vintages.json')));await ready;await app.loadFile(file(fixture('quality.json')));release();assert.equal((await old).status,'SUPERSEDED');assert.equal(app.current().schema,'ATLAS_SESSION_QUALITY_V1');});

test('calendar-invalid market import visibly clears prior loaded research',async()=>{const {app,results,status}=setup();await app.loadFile(file(fixture('research.json')));const v=JSON.parse(fixture('api.json'));v.rows.find(r=>r.timestamp).session='REGULAR';assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'REFUSED');assert.equal(results.textContent,'');assert.equal(app.current(),null);assert.match(status.textContent,/Previous evidence cleared/);});
test('calendar-invalid quality window cannot replace loaded quote evidence',async()=>{const {app,results}=setup();await app.loadFile(file(fixture('quote-quality.json')));const v=JSON.parse(fixture('quality.json'));v.windows[0].session='REGULAR';assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'REFUSED');assert.equal(results.textContent,'');assert.equal(app.current(),null);});
test('built viewer supplies accessible export selection help without preloaded evidence',()=>{const output=path.join(temp(),'help.html');build(output);const html=fs.readFileSync(output,'utf8');assert.match(html,/<summary>Which export can I open\?<\/summary>/);for(const schema of ['ATLAS_SESSION_QUALITY_V1','ATLAS_VINTAGE_REPLAY_BROWSER_V1','ATLAS_DESCRIPTIVE_COMPARISON_BROWSER_V1'])assert.ok(html.includes(schema));assert.match(html,/whole envelope/);assert.match(html,/never silently repaired/);assert.doesNotMatch(html,/type="hidden"|<option/);});


test('checking status uses readable plain punctuation during local file read',async()=>{
  const {app,status}=setup();let finish;
  const pending=app.loadFile({size:2,text:()=>new Promise(resolve=>{finish=resolve;})});
  assert.equal(status.textContent,'Checking local evidence...');
  finish(fixture('research.json'));await pending;
});

function freshnessRows(results){
 const sections=results.children[0]?.children||[];
 const section=sections.find(n=>n.children[0]?.textContent==='Freshness across supplied symbols');
 if(!section)return [];
 const table=section.children[1].children[0],body=table.children.find(n=>n.tagName==='tbody');
 return body.children.map(row=>row.children.map(cell=>cell.textContent));
}
test('market freshness counts retain missing symbols separately for bars and quotes',async()=>{
 const {app,results}=setup();await app.loadFile(file(fixture('api.json')));
 assert.deepEqual(freshnessRows(results),[['Completed bars','2','1','0','0','1','0'],['Quote references','2','1','0','0','1','0']]);
 assert.match(results.textContent,/not current provider health or live coverage/);
});
test('market freshness counts separate stale bars from delayed quote references',async()=>{
 const {app,results}=setup(),v=JSON.parse(fixture('api.json'));
 v.asof=new Date(Date.parse(v.asof)+300000).toISOString().replace('.000Z','+00:00');
 for(const kind of ['rows','quote_rows'])for(const row of v[kind])if(row.symbol==='SPY'){
  row.age_seconds+=300;row.price=null;row.status=kind==='rows'?'STALE':'DELAYED';
  if(kind==='quote_rows')row.provider_reported_delay=15;
 }
 assert.equal((await app.loadFile(file(JSON.stringify(v)))).status,'LOADED');
 assert.deepEqual(freshnessRows(results),[['Completed bars','2','0','1','0','1','0'],['Quote references','2','0','0','1','1','0']]);
});
test('market freshness summary clears or replaces with the selected report',async()=>{
 const {app,results}=setup();await app.loadFile(file(fixture('api.json')));
 assert.equal(freshnessRows(results).length,2);
 await app.loadFile(file(fixture('quote-quality.json')));assert.deepEqual(freshnessRows(results),[]);
 await app.loadFile(file(fixture('api.json')));await app.loadFile(file('{'));assert.deepEqual(freshnessRows(results),[]);
 await app.loadFile(file(fixture('api.json')));app.clear();assert.deepEqual(freshnessRows(results),[]);
});
function evidenceRows(results,title){
 const section=results.children[0].children.find(n=>n.children[0]?.textContent===title);
 const body=section.children[1].children[0].children.find(n=>n.tagName==='tbody');
 return body.children.map(row=>row.children.map(cell=>cell.textContent));
}
test('explicit symbol selection narrows both tables without changing full-report counts or evidence',async()=>{
 const {app,doc,results}=setup(),filter=doc.getElementById('market-symbol');
 assert.equal(filter.disabled,true);await app.loadFile(file(fixture('api.json')));
 const original=app.current(),counts=freshnessRows(results);
 assert.deepEqual(filter.children.map(n=>n.value),['','MISSING','SPY']);
 filter.value='SPY';filter.listeners.get('change')();
 assert.deepEqual(evidenceRows(results,'Completed bar closes').map(r=>r[0]),['SPY']);
 assert.deepEqual(evidenceRows(results,'Separate quote references').map(r=>r[0]),['SPY']);
 assert.deepEqual(freshnessRows(results),counts);assert.deepEqual(app.current(),original);
 filter.value='MISSING';filter.listeners.get('change')();
 assert.equal(evidenceRows(results,'Completed bar closes')[0][2],'Unavailable');
 assert.equal(evidenceRows(results,'Separate quote references')[0][4],'Unavailable');
 assert.deepEqual(freshnessRows(results),counts);
 filter.value='';filter.listeners.get('change')();assert.equal(evidenceRows(results,'Completed bar closes').length,2);
});
test('symbol selector resets on replacement, refusal, clear and disposal',async()=>{
 const {app,doc,results}=setup(),filter=doc.getElementById('market-symbol');
 await app.loadFile(file(fixture('api.json')));filter.value='SPY';filter.listeners.get('change')();
 await app.loadFile(file(fixture('api.json')));assert.equal(filter.value,'');assert.equal(evidenceRows(results,'Completed bar closes').length,2);
 await app.loadFile(file(fixture('quote-quality.json')));assert.equal(filter.disabled,true);assert.equal(filter.children.length,0);
 await app.loadFile(file(fixture('api.json')));await app.loadFile(file('{'));assert.equal(filter.disabled,true);
 await app.loadFile(file(fixture('api.json')));app.clear();assert.equal(filter.value,'');assert.equal(filter.children.length,0);
 app.dispose();assert.equal(filter.listeners.size,0);
});
test('unsupplied symbol and selection render failure clear the model and counts',async()=>{
 const {app,doc,results,status}=setup(),filter=doc.getElementById('market-symbol');
 await app.loadFile(file(fixture('api.json')));filter.value='UNSUPPLIED';filter.listeners.get('change')();
 assert.equal(app.current(),null);assert.equal(results.textContent,'');assert.match(status.textContent,/Symbol view refused/);
 await app.loadFile(file(fixture('api.json')));filter.value='SPY';
 const replace=results.replaceChildren.bind(results);let fail=true;
 results.replaceChildren=(...nodes)=>{if(fail){fail=false;throw Error('synthetic render');}replace(...nodes);};
 filter.listeners.get('change')();assert.equal(app.current(),null);assert.equal(results.textContent,'');assert.equal(filter.disabled,true);
});
test('decoded export identity is exact text scope and changes for whitespace without source claims',async()=>{
 const {app,doc}=setup(),identity=doc.getElementById('market-import-identity'),raw=fixture('api.json');
 for(const text of [raw,raw+'\n']){
  assert.equal((await app.loadFile(file(text))).status,'LOADED');
  assert.ok(identity.textContent.includes(createHash('sha256').update(text).digest('hex')));
  assert.ok(identity.textContent.includes(Buffer.byteLength(text)+' UTF-8 bytes'));
  assert.match(identity.textContent,/not original file-byte attestation, provider authentication or live freshness/);
  assert.doesNotMatch(identity.textContent,/fixture\.json/);
 }
});
test('failed replacement and clear remove the prior decoded-text identity',async()=>{
 const {app,doc}=setup(),identity=doc.getElementById('market-import-identity');
 await app.loadFile(file(fixture('api.json')));assert.match(identity.textContent,/SHA-256/);
 await app.loadFile(file('{'));assert.equal(identity.textContent,'No decoded export identity');
 await app.loadFile(file(fixture('market-refusal.json')));assert.match(identity.textContent,/SHA-256/);
 app.clear();assert.equal(identity.textContent,'No decoded export identity');
});
test('superseded file read cannot restore an earlier decoded-text identity',async()=>{
 const {app,doc}=setup();let finish;
 const old=app.loadFile({size:1,text:()=>new Promise(resolve=>{finish=resolve;})});
 const latest=fixture('quote-quality.json');await app.loadFile(file(latest));
 finish(fixture('api.json'));assert.equal((await old).status,'SUPERSEDED');
 assert.ok(doc.getElementById('market-import-identity').textContent.includes(createHash('sha256').update(latest).digest('hex')));
});
