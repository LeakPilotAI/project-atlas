import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import api from './chart-archive.cjs';

const folder=new URL('../../../tests/fixtures/chart-archive-v1/',import.meta.url);
const selection=JSON.parse(fs.readFileSync(new URL('selection.json',folder),'utf8'));
const files=()=>selection.files.map(name=>({name,bytes:new Uint8Array(fs.readFileSync(new URL(name,folder)))}));
const text=b=>new TextDecoder().decode(b),bytes=s=>new TextEncoder().encode(s);
const digest=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(v=>v.toString(16).padStart(2,'0')).join('');
const ordered=v=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
const canonical=v=>JSON.stringify(ordered(v),null,2)+'\n';
async function variant(change,rawChange=null){
  const original=files(),receipt=JSON.parse(text(original.find(f=>f.name===selection.receipt).bytes));
  const report=JSON.parse(text(original.find(f=>f.name===receipt.report.name).bytes));change(report);
  let reportBytes=bytes(JSON.stringify(report,null,2)+'\n');if(rawChange)reportBytes=bytes(rawChange(text(reportBytes)));
  const reportHash=await digest(reportBytes);receipt.report={name:reportHash+'.json',sha256:reportHash};
  const provenance=JSON.parse(text(original.find(f=>f.name===receipt.provenance.name).bytes));provenance.report_sha256=reportHash;
  const provenanceBytes=bytes(canonical(provenance)),provenanceHash=await digest(provenanceBytes);receipt.provenance={name:provenanceHash+'.json',sha256:provenanceHash};
  const receiptBytes=bytes(canonical(receipt)),pin=await digest(receiptBytes);
  return {pin,files:[original.find(f=>f.name===receipt.source.name),original.find(f=>f.name===receipt.dashboard.name),
    {name:receipt.report.name,bytes:reportBytes},{name:receipt.provenance.name,bytes:provenanceBytes},{name:pin+'.json',bytes:receiptBytes}]};
}

test('actual Python archive verifies native SHA with explicit byte-only scope',async()=>{
  const result=await api.verifyArchive(files(),selection.expectedReceiptSha256);
  assert.equal(result.status,'BYTE_INTEGRITY_ONLY');assert.equal(result.python_reproduction_verified,false);
  assert.equal(result.report.rows[0].bar_close,101);assert.equal(result.report.rows[0].reported_adjusted_close,50.5);
  assert.equal(result.report.provider_reported_delay,15);assert.equal(result.report.provider_delay_unit,'UNVERIFIED');
  assert.equal(result.report.live_status,'NOT_ESTABLISHED');assert.equal(result.report.startup_authorized,false);
  assert.throws(()=>{result.report.rows[0].bar_close=999;},TypeError);
});
for(const mode of ['missing','extra','duplicate','tampered','traversal','oversize','wrong-pin'])test(`reject archive ${mode}`,async()=>{
  const f=files();let pin=selection.expectedReceiptSha256;
  if(mode==='missing')f.pop();if(mode==='extra')f.push({name:'a'.repeat(64)+'.json',bytes:bytes('{}')});
  if(mode==='duplicate')f[1]={...f[0]};if(mode==='tampered')f[0].bytes[0]^=1;
  if(mode==='traversal')f[0].name='../'+f[0].name;if(mode==='oversize')f[0].bytes=new Uint8Array(2000001);
  if(mode==='wrong-pin')pin='0'.repeat(64);
  await assert.rejects(api.verifyArchive(f,pin));
});
for(const [name,change] of [
  ['authority',r=>{r.startup_authorized=true;}],['live',r=>{r.live_status='LIVE';}],['basis',r=>{r.adjustment_basis='VERIFIED';}],
  ['delay-units',r=>{r.provider_delay_unit='MINUTES';}],['missing-delay',r=>{delete r.provider_reported_delay;}],
  ['count',r=>{r.bar_n=2;}],['future',r=>{r.rows[0].timestamp='2026-10-20T15:00:00+00:00';}],
  ['adjustment-null',r=>{r.rows[0].reported_adjusted_close=null;}],['price',r=>{r.rows[0].bar_close=-1;}],
  ['unexpected',r=>{r.private_value='SYNTHETIC_PRIVATE_VALUE';}],
])test(`rehashed ${name} contradiction refuses`,async()=>{
  const v=await variant(change);await assert.rejects(api.verifyArchive(v.files,v.pin));
});

test('rehashed duplicate report keys are refused before display',async()=>{
  const v=await variant(()=>{},s=>s.replace('"bar_n": 1','"bar_n": 1, "bar_n": 1'));
  await assert.rejects(api.verifyArchive(v.files,v.pin));
});
test('unknown delay and absent adjusted series remain null and unverified',async()=>{
  const v=await variant(r=>{r.provider_reported_delay=null;r.adjusted_series='ABSENT';r.rows[0].reported_adjusted_close=null;});
  const result=await api.verifyArchive(v.files,v.pin);assert.equal(result.report.provider_reported_delay,null);
  assert.equal(result.python_reproduction_verified,false); // Deliberately no source reproduction claim for a rehashed report.
});
test('failed replacement clears prior evidence without exposing raw private values',async()=>{
  const views=[],controller=api.createController(v=>views.push(v));await controller.load(files(),selection.expectedReceiptSha256);
  const changed=files();changed[0].bytes=bytes('SYNTHETIC_PRIVATE_VALUE');
  await assert.rejects(controller.load(changed,selection.expectedReceiptSha256));
  assert.equal(controller.current(),null);assert.equal(views.at(-1).state,'REFUSED');assert.deepEqual(views.at(-1).rows,[]);
  assert.ok(!JSON.stringify(views).includes('SYNTHETIC_PRIVATE_VALUE'));
});
test('superseded cryptographic load cannot restore cleared evidence',async()=>{
  let release;const gate=new Promise(resolve=>{release=resolve;});let calls=0;
  const controller=api.createController(()=>{},async b=>{if(calls++===0)await gate;return digest(b);});
  const pending=controller.load(files(),selection.expectedReceiptSha256);controller.clear();release();
  assert.equal((await pending).status,'SUPERSEDED');assert.equal(controller.current(),null);
});
test('input bytes are copied before awaiting crypto',async()=>{
  let release;const gate=new Promise(resolve=>{release=resolve;});let calls=0;const f=files();
  const pending=api.verifyArchive(f,selection.expectedReceiptSha256,async b=>{if(calls++===0)await gate;return digest(b);});
  f[0].bytes.fill(0);release();assert.equal((await pending).status,'BYTE_INTEGRITY_ONLY');
});
test('renderer failure clears model and preserves original error',async()=>{
  const original=Error('fixture display failed');const controller=api.createController(v=>{if(v.state==='BYTE_INTEGRITY_ONLY')throw original;});
  await assert.rejects(controller.load(files(),selection.expectedReceiptSha256),e=>e===original);assert.equal(controller.current(),null);
});

function documentFixture(){
  class Element{constructor(){this.children=[];this.listeners={};this.value='';this.textContent='';this.files=[];}replaceChildren(...v){this.children=v;}appendChild(v){this.children.push(v);}addEventListener(name,fn){this.listeners[name]=fn;}}
  const ids=Object.fromEntries(['archive-files','receipt-pin','verify','clear','status','summary','rows'].map(k=>[k,new Element()]));
  return {ids,getElementById:id=>ids[id],createElement:()=>new Element()};
}
function select(doc){doc.ids['receipt-pin'].value=selection.expectedReceiptSha256;doc.ids['archive-files'].files=files().map(f=>({name:f.name,size:f.bytes.length,arrayBuffer:async()=>f.bytes.buffer}));}
test('mounted local-file viewer displays separate prices and clears on pin change',async()=>{
  const doc=documentFixture(),controller=api.mount(doc);select(doc);await doc.ids.verify.listeners.click();
  assert.equal(controller.current().status,'BYTE_INTEGRITY_ONLY');assert.match(doc.ids.status.textContent,/Byte integrity only/);
  assert.match(doc.ids.summary.textContent,/unit unverified/);assert.equal(doc.ids.rows.children[0].children[2].textContent,'101');
  assert.equal(doc.ids.rows.children[0].children[3].textContent,'50.5');
  doc.ids['receipt-pin'].listeners.input();assert.equal(controller.current(),null);assert.deepEqual(doc.ids.rows.children,[]);
});
test('mounted file-read failure clears stale rows',async()=>{
  const doc=documentFixture(),controller=api.mount(doc);select(doc);await doc.ids.verify.listeners.click();
  doc.ids['archive-files'].files[0].arrayBuffer=async()=>{throw Error('PRIVATE_READ_ERROR');};await doc.ids.verify.listeners.click();
  assert.equal(controller.current(),null);assert.deepEqual(doc.ids.rows.children,[]);assert.ok(!doc.ids.status.textContent.includes('PRIVATE_READ_ERROR'));
});
test('static viewer denies connections and never inserts archive HTML',()=>{
  const page=fs.readFileSync(fileURLToPath(new URL('./chart-archive.html',import.meta.url)),'utf8');
  const script=fs.readFileSync(fileURLToPath(new URL('./chart-archive.cjs',import.meta.url)),'utf8');
  assert.match(page,/connect-src 'none'/);assert.doesNotMatch(script,/innerHTML|\bfetch\s*\(/);assert.match(page,/Byte integrity is not source reproduction/);
});

test('unavailable cryptography refuses and clears prior model',async()=>{
  const controller=api.createController(()=>{},async()=>{throw Error('synthetic unavailable crypto');});
  await assert.rejects(controller.load(files(),selection.expectedReceiptSha256));assert.equal(controller.current(),null);
});
test('import and refusal-render errors are both preserved',async()=>{
  const displayError=Error('fixture refusal renderer');const controller=api.createController(v=>{if(v.state==='REFUSED')throw displayError;});
  await assert.rejects(controller.load(files(),'0'.repeat(64)),e=>e instanceof AggregateError&&e.errors[1]===displayError);
  assert.equal(controller.current(),null);
});
test('late file read after pin edit cannot repopulate rows',async()=>{
  const doc=documentFixture(),controller=api.mount(doc);select(doc);let release;
  const gate=new Promise(resolve=>{release=resolve;}),original=doc.ids['archive-files'].files[0].arrayBuffer;
  doc.ids['archive-files'].files[0].arrayBuffer=async()=>{await gate;return original();};
  const pending=doc.ids.verify.listeners.click();doc.ids['receipt-pin'].listeners.input();release();await pending;
  assert.equal(controller.current(),null);assert.deepEqual(doc.ids.rows.children,[]);
});
test('only bounded byte arrays are accepted, not implicit strings',async()=>{
  const f=files();f[0].bytes=text(f[0].bytes);await assert.rejects(api.verifyArchive(f,selection.expectedReceiptSha256));
});
test('receipt BOM is not silently stripped into a canonical receipt',async()=>{
  const f=files(),receipt=f.find(v=>v.name===selection.receipt);receipt.bytes=new Uint8Array([239,187,191,...receipt.bytes]);
  const pin=await digest(receipt.bytes);receipt.name=pin+'.json';await assert.rejects(api.verifyArchive(f,pin));
});
test('browser-global entry mounts with no provider or filesystem globals',async()=>{
  const {runInNewContext}=await import('node:vm');const doc=documentFixture();
  const context={document:doc,TextEncoder,TextDecoder,Uint8Array,crypto};
  runInNewContext(fs.readFileSync(fileURLToPath(new URL('./chart-archive.cjs',import.meta.url)),'utf8'),context);
  runInNewContext(fs.readFileSync(fileURLToPath(new URL('./chart-archive-mount.js',import.meta.url)),'utf8'),context);
  assert.equal(typeof context.AtlasChartArchive.verifyArchive,'function');assert.deepEqual(doc.ids.rows.children,[]);
});
