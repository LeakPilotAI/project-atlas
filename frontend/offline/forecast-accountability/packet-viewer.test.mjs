import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {createHash,webcrypto} from 'node:crypto';
import {File} from 'node:buffer';
import {spawnSync} from 'node:child_process';
import api from './view.cjs';
import packetView from './packet-mount.cjs';
import {buildPacketViewer} from './packet-build.mjs';
import {createComparisonPacket} from './vintage-export.mjs';
const hash=value=>createHash('sha256').update(value).digest('hex');
const reports=JSON.parse(fs.readFileSync(new URL('../../../tests/fixtures/afi-report-vintages-v1/reports.json',import.meta.url),'utf8'));
const browser=report=>{const text=JSON.stringify(report);return JSON.stringify({schema:'AFI_BROWSER_REPORT_V1',report_json:text,payload_sha256:hash(text)});};
const left=browser(reports[1]),right=browser(reports[2]);
const pins={comparator_source_sha256:hash(fs.readFileSync(new URL('./view.cjs',import.meta.url))),exporter_source_sha256:hash(fs.readFileSync(new URL('./vintage-export.mjs',import.meta.url))),artifact_io_source_sha256:hash(fs.readFileSync(new URL('../market-replay/artifact-io.mjs',import.meta.url)))};
const packet=await createComparisonPacket(left,right);
const file=text=>new File([text],'comparison.json',{type:'application/json'});
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.attributes={};this.listeners=new Map();this._text='';this.value='';}set textContent(value){this._text=String(value);this.children=[];}get textContent(){return this._text+this.children.map(item=>item.textContent).join(' ');}set innerHTML(_value){throw Error('HTML insertion forbidden');}append(...items){this.children.push(...items);}replaceChildren(...items){this._text='';this.children=items;}setAttribute(key,value){this.attributes[key]=value;}addEventListener(key,value){this.listeners.set(key,value);}removeEventListener(key,value){if(this.listeners.get(key)===value)this.listeners.delete(key);}}
function document(){const elements=new Map(['packet-file','clear-packet','packet-status','packet-results'].map(id=>[id,new Element()]));return {elements,getElementById:id=>elements.get(id),createElement:tag=>new Element(tag)};}
function setup(custom=api,sourcePins=pins){const doc=document(),app=packetView.mount(doc,custom,sourcePins);return {doc,app,results:doc.getElementById('packet-results'),status:doc.getElementById('packet-status')};}
const temp=()=>fs.mkdtempSync(path.join(os.tmpdir(),'atlas-packet-view-'));
test('shared pure constructor reproduces exact CLI packet bytes',async()=>{assert.equal(await api.createComparisonPacket(left,right,pins,hash),packet);});
test('native File bytes and trusted pins display complete comparison',async()=>{const {app,results}=setup();assert.equal((await app.loadFile(file(packet))).status,'LOADED');assert.match(results.textContent,/Every forecast/);assert.match(results.textContent,/OUTCOME_VALUE_CHANGED/);assert.match(results.textContent,/Original probability impact/);assert.equal(app.current().comparison.union_forecast_n,1);assert.equal(app.current().source_authenticated,false);});
for(const malformed of [undefined,{}, {...pins,unexpected:'0'.repeat(64)},{...pins,comparator_source_sha256:'bad'}])test(`trusted source pins are required: ${String(malformed)}`,()=>{assert.throws(()=>packetView.mount(document(),api,malformed));});
for(const fault of ['source','result','duplicate','malformed','authority'])test(`invalid packet ${fault} clears previous comparison`,async()=>{const {app,results}=setup();await app.loadFile(file(packet));let raw='{';const p=JSON.parse(packet);if(fault==='source'){for(const key of Object.keys(pins))p[key]='0'.repeat(64);raw=JSON.stringify(p)+'\n';}if(fault==='result'){const r=JSON.parse(p.comparison_json);r.rows[0].right_actual=999;p.comparison_json=JSON.stringify(r);p.comparison_sha256=hash(p.comparison_json);raw=JSON.stringify(p)+'\n';}if(fault==='duplicate')raw=packet.replace('{','{"production_approved":true,');if(fault==='authority'){p.production_approved=true;raw=JSON.stringify(p)+'\n';}assert.equal((await app.loadFile(file(raw))).status,'REFUSED');assert.equal(results.textContent,'');assert.equal(app.current(),null);});
for(const bytes of [Buffer.from([0xff]),Buffer.concat([Buffer.from([0xef,0xbb,0xbf]),Buffer.from(packet)])])test(`malformed/BOM native bytes refuse length ${bytes.length}`,async()=>{const {app}=setup();assert.equal((await app.loadFile(new File([bytes],'bytes.json'))).status,'REFUSED');});
test('declared oversized file is refused before reading',async()=>{const {app}=setup();let read=false;assert.equal((await app.loadFile({size:2000001,arrayBuffer:async()=>{read=true;return new ArrayBuffer(1);}})).status,'REFUSED');assert.equal(read,false);});
test('actual oversized ArrayBuffer cannot use a false size claim',async()=>{const {app}=setup();assert.equal((await app.loadFile({size:1,arrayBuffer:async()=>new ArrayBuffer(2000001)})).status,'REFUSED');});
test('non-ArrayBuffer reader output refuses without coerced strings',async()=>{const {app}=setup();assert.equal((await app.loadFile({size:1,arrayBuffer:async()=>packet})).status,'REFUSED');});
test('late native-byte read cannot restore after Clear',async()=>{const {app,results}=setup();let release;const pending=app.loadFile({size:1,arrayBuffer:()=>new Promise(resolve=>{release=resolve;})});app.clear();release(new TextEncoder().encode(packet).buffer);assert.equal((await pending).status,'SUPERSEDED');assert.equal(results.textContent,'');});
test('late crypto verification cannot overwrite a newer refusal',async()=>{let release,started;const ready=new Promise(resolve=>{started=resolve;}),gate=new Promise(resolve=>{release=resolve;});let calls=0;const custom={...api,verifyComparisonPacket:async(...args)=>{if(++calls===1){started();await gate;}return api.verifyComparisonPacket(...args);}};const {app,results}=setup(custom);const old=app.loadFile(file(packet));await ready;await app.loadFile(file('{'));release();assert.equal((await old).status,'SUPERSEDED');assert.equal(results.textContent,'');});
test('trusted pins are copied before asynchronous input arrives',async()=>{const supplied={...pins},{app}=setup(api,supplied);supplied.comparator_source_sha256='0'.repeat(64);assert.equal((await app.loadFile(file(packet))).status,'LOADED');});
test('render commit failure clears model',async()=>{const {app,results}=setup();const original=results.replaceChildren.bind(results);let n=0;results.replaceChildren=(...items)=>{if(++n===2)throw Error('synthetic render');return original(...items);};assert.equal((await app.loadFile(file(packet))).status,'REFUSED');assert.equal(app.current(),null);assert.equal(results.textContent,'');});
test('persistent cleanup failure never acknowledges successful loading',async()=>{const {app,results}=setup();results.replaceChildren=()=>{throw Error('synthetic DOM failure');};await assert.rejects(()=>app.loadFile(file(packet)),AggregateError);assert.equal(app.current(),null);});
test('current model is copied and disposed listeners cannot import',async()=>{const {app,doc}=setup();await app.loadFile(file(packet));app.current().comparison.rows.length=0;assert.equal(app.current().comparison.rows.length,1);app.dispose();assert.equal(doc.getElementById('packet-file').listeners.size,0);assert.equal((await app.loadFile(file(packet))).status,'DISPOSED');});
async function builtVM(crypto=webcrypto){const output=path.join(temp(),'packet.html'),receipt=buildPacketViewer(output),html=fs.readFileSync(output,'utf8'),script=html.match(/<script>([\s\S]*)<\/script>/)[1],style=html.match(/<style>([\s\S]*?)<\/style>/)[1];for(const text of [script,style])assert.ok(html.includes("'sha256-"+createHash('sha256').update(text).digest('base64')+"'"));assert.deepEqual(receipt.source_pins,pins);assert.match(html,/connect-src 'none'/);assert.doesNotMatch(html.replaceAll("createElementNS('http://www.w3.org/2000/svg',",'createElementNS(SVG_NAMESPACE,'),/<script[^>]+src=|https?:\/\//);const doc=document(),context={document:doc,crypto,TextEncoder,TextDecoder,structuredClone,fetch:()=>{throw Error('Network forbidden');}};Object.defineProperty(context,'localStorage',{get(){throw Error('Storage forbidden');}});vm.runInNewContext(script,context,{timeout:2000});return {doc,html,receipt};}
test('built page uses native crypto and embedded build pins, not packet pins',async()=>{const {doc,receipt}=await builtVM();doc.getElementById('packet-file').files=[file(packet)];await doc.getElementById('packet-file').listeners.get('change')();assert.match(doc.getElementById('packet-results').textContent,/OUTCOME_VALUE_CHANGED/);const forged=JSON.parse(packet);for(const key of Object.keys(pins))forged[key]='0'.repeat(64);doc.getElementById('packet-file').files=[file(JSON.stringify(forged)+'\n')];await doc.getElementById('packet-file').listeners.get('change')();assert.equal(doc.getElementById('packet-results').textContent,'');assert.match(doc.getElementById('packet-status').textContent,/refused/);assert.equal(receipt.native_browser_acceptance,'NOT_ESTABLISHED');});
test('old packet refuses in changed code while archived CLI still verifies unchanged bytes',async()=>{const old=new URL('../../../logs/diagnostics/vintage-export-20261021/demo/comparison.json',import.meta.url),source=new URL('../../../logs/diagnostics/vintage-export-20261021/reproduction-source/forecast-accountability/vintage-export.mjs',import.meta.url);const bytes=fs.readFileSync(old);await assert.rejects(()=>api.verifyComparisonPacket(bytes.toString(),pins,hash),/archived/);const run=spawnSync(process.execPath,[fileURLToPath(source),'--verify',fileURLToPath(old)],{encoding:'utf8'});assert.equal(run.status,0,run.stderr);assert.equal(JSON.parse(run.stdout).status,'VERIFIED_SUPPLIED_BYTES');assert.equal(hash(fs.readFileSync(old)),hash(bytes));});
test('existing page output is never overwritten',()=>{const output=path.join(temp(),'packet.html');fs.writeFileSync(output,'original');assert.throws(()=>buildPacketViewer(output));assert.equal(fs.readFileSync(output,'utf8'),'original');});

test('missing native cryptography refuses instead of trusting the packet digest',async()=>{const {doc}=await builtVM(null);doc.getElementById('packet-file').files=[file(packet)];await doc.getElementById('packet-file').listeners.get('change')();assert.equal(doc.getElementById('packet-results').textContent,'');assert.match(doc.getElementById('packet-status').textContent,/refused/);});
test('native reader error clears comparison without exposing its message',async()=>{const {app,status,results}=setup();await app.loadFile(file(packet));assert.equal((await app.loadFile({size:1,arrayBuffer:async()=>{throw Error('PRIVATE_SYNTHETIC_PATH');}})).status,'REFUSED');assert.equal(results.textContent,'');assert.doesNotMatch(status.textContent,/PRIVATE_SYNTHETIC_PATH/);});
test('packet page preserves missing-side union and pending states',async()=>{const after=structuredClone(reports[2]);after.rows[0].forecast_sha256='f'.repeat(64);const missing=await createComparisonPacket(left,browser(after));const {app,results}=setup();assert.equal((await app.loadFile(file(missing))).status,'LOADED');assert.equal(app.current().comparison.union_forecast_n,2);assert.match(results.textContent,/LEFT_ONLY/);assert.match(results.textContent,/RIGHT_ONLY/);const pending=await createComparisonPacket(browser(reports[0]),browser(reports[1]));await app.loadFile(file(pending));assert.match(results.textContent,/RESOLUTION_REPORTED/);assert.match(results.textContent,/NOT_BOTH_RESOLVED/);});
test('named properties on an array do not supply a valid trusted pin object',()=>{const invalid=Object.assign([],pins);assert.throws(()=>packetView.mount(document(),api,invalid));});
test('pure verification snapshots trusted pins before asynchronous digest work',async()=>{const expected={...pins};let release,started;const ready=new Promise(resolve=>{started=resolve;}),gate=new Promise(resolve=>{release=resolve;});let first=true;const delayed=async text=>{if(first){first=false;started();await gate;}return hash(text);};const check=api.verifyComparisonPacket(packet,expected,delayed);await ready;for(const key of Object.keys(expected))expected[key]='0'.repeat(64);release();assert.equal((await check).comparison.union_forecast_n,1);});


for(const key of Object.keys(pins))test(`source mismatch ${key} explains archived viewer requirement without accepting evidence`,async()=>{
  const {app,status,results}=setup();await app.loadFile(file(packet));
  const changed=JSON.parse(packet);changed[key]='0'.repeat(64);
  assert.equal((await app.loadFile(file(JSON.stringify(changed)+'\n'))).status,'REFUSED');
  assert.equal(app.current(),null);assert.equal(results.textContent,'');
  assert.match(status.textContent,/Source\/build mismatch/);
  assert.match(status.textContent,/matching archived sources/);
  assert.match(status.textContent,/Do not edit pins or manifests/);
  assert.match(status.textContent,/validity is not established/);
  assert.doesNotMatch(status.textContent,/PRIVATE_SYNTHETIC_PATH|<script>/);
});

test('authority and malformed packets do not receive a compatibility-only diagnosis',async()=>{
  const {app,status}=setup();const changed=JSON.parse(packet);changed.production_approved=true;
  for(const text of ['{',JSON.stringify(changed)+'\n']){
    assert.equal((await app.loadFile(file(text))).status,'REFUSED');
    assert.doesNotMatch(status.textContent,/Source\/build mismatch/);
    assert.match(status.textContent,/complete, supported comparison packet/);
    assert.equal(app.current(),null);
  }
});
