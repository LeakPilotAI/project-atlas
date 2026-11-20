import test from 'node:test';
import assert from 'node:assert/strict';
import {page,payloads} from './command_center_health_fixture.mjs';

test('failed reads cannot reuse cached healthy reconciliation, risk or PAPER counts',async()=>{
  const p=page();await p.load();assert.equal(p.node('hRecon').textContent,'OK');assert.equal(p.node('hKill').textContent,'OFF');
  const bad=payloads();for(const key of ['/diagnostics/paper-reconciliation','/api/perps/paper-risk','/api/perps/manual/board?limit=8'])bad[key]=false;
  p.set(bad);await p.load();
  assert.equal(p.node('hRecon').textContent,'UNAVAILABLE');assert.equal(p.node('hKill').textContent,'UNAVAILABLE');
  assert.equal(p.node('hOpen').textContent,'\u2014');assert.notEqual(p.node('hRecon').className,'good');
});

test('empty or unreliable kill-switch evidence never defaults to OFF',async()=>{
  const p=page(),data=payloads();data['/api/perps/paper-risk']={};data['/diagnostics/paper-reconciliation']={current:{}};
  p.set(data);await p.load();assert.equal(p.node('hKill').textContent,'UNAVAILABLE');assert.equal(p.node('hRecon').textContent,'UNKNOWN');
  assert.match(p.node('findings').innerHTML,/PAPER CONTROL EVIDENCE UNAVAILABLE/);
  data['/api/perps/paper-risk']={kill_switch:false,reliable:false};p.set(data);await p.load();
  assert.equal(p.node('hKill').textContent,'UNAVAILABLE');
});

test('fresh direct reconciliation remains separate from failed background reviews',async()=>{
  const p=page(),data=payloads();data['/diagnostics/paper-reconciliation'].runtime={paper_review:{state:'FAILED'},reconciliation_review:{state:'FAILED'}};
  p.set(data);await p.load();assert.equal(p.node('hRecon').textContent,'OK');
  assert.match(p.node('findings').innerHTML,/LAST PAPER REVIEW FAILED/);
  assert.match(p.node('findings').innerHTML,/LAST BACKGROUND RECONCILIATION FAILED/);
  assert.doesNotMatch(p.node('findings').innerHTML,/NO CURRENT HEALTH FINDINGS/);
});


for(const state of ['NOT_RUN','IN_PROGRESS','INTERRUPTED',undefined,'forged<script>'])test(`review ${state} never produces nominal-only findings`,async()=>{
  const p=page(),data=payloads();data['/diagnostics/paper-reconciliation'].runtime={paper_review:{state},reconciliation_review:{state}};
  p.set(data);await p.load();assert.equal(p.node('hRecon').textContent,'OK');
  assert.doesNotMatch(p.node('findings').innerHTML,/NO CURRENT HEALTH FINDINGS/);
  assert.doesNotMatch(p.node('findings').innerHTML,/forged|<script>/);
});

test('explicit unhealthy outcomes and successful refresh restoration remain distinct',async()=>{
  const p=page(),data=payloads();data['/api/perps/paper-risk'].kill_switch=true;data['/diagnostics/paper-reconciliation'].current.reconciliation_ok=false;
  p.set(data);await p.load();assert.equal(p.node('hKill').textContent,'ON');assert.equal(p.node('hRecon').textContent,'REVIEW');
  assert.match(p.node('findings').innerHTML,/PAPER KILL SWITCH ON/);
  p.set(payloads());await p.load();assert.equal(p.node('hKill').textContent,'OFF');assert.equal(p.node('hRecon').textContent,'OK');
  assert.match(p.node('findings').innerHTML,/NO CURRENT HEALTH FINDINGS/);
});

test('late older successful refresh cannot overwrite newer unavailable evidence',async()=>{
  const p=page(),old=payloads();let release;const gate=new Promise(resolve=>{release=resolve;});
  p.fetch(async url=>{await gate;return {json:async()=>old[url]};});
  const earlier=p.load();p.fetch(async()=>{throw Error('synthetic newer failure');});
  await p.load();assert.equal(p.node('hRecon').textContent,'UNAVAILABLE');
  release();await earlier;
  assert.equal(p.node('hRecon').textContent,'UNAVAILABLE');assert.equal(p.node('hKill').textContent,'UNAVAILABLE');
});


test('failed health and storage reads do not present cached running or current footprints',async()=>{
  const p=page();await p.load();assert.match(p.node('coreServices').innerHTML,/RUNNING/);assert.equal(p.node('mStorage').textContent,'128 B');
  const bad=payloads();bad['/health']=false;bad['/api/archive/export/summary']=false;p.set(bad);await p.load();
  assert.doesNotMatch(p.node('coreServices').innerHTML,/RUNNING|STOPPED/);
  assert.match(p.node('coreServices').innerHTML,/UNAVAILABLE/);assert.equal(p.node('mServices').textContent,'UNAVAILABLE');
  assert.equal(p.node('mStorage').textContent,'UNAVAILABLE');assert.match(p.node('stores').innerHTML,/ARCHIVE STORAGE UNAVAILABLE/);
});

test('missing or nonboolean service states are unknown rather than stopped or running',async()=>{
  const p=page(),data=payloads();data['/health']={scanner_running:'false'};p.set(data);await p.load();
  assert.doesNotMatch(p.node('coreServices').innerHTML,/RUNNING|STOPPED/);
  assert.match(p.node('findings').innerHTML,/SERVICE STATE UNAVAILABLE/);
  data['/health']=payloads()['/health'];data['/health'].scanner_running=false;p.set(data);await p.load();
  assert.match(p.node('coreServices').innerHTML,/STOPPED/);
  assert.match(p.node('findings').innerHTML,/SERVICE STOPPED/);
});

test('missing investment status or failed live reads cannot assert disabled',async()=>{
  const p=page(),data=payloads();data['/api/live']={};p.set(data);await p.load();
  assert.equal(p.node('mFresh').textContent,'UNAVAILABLE');assert.match(p.node('findings').innerHTML,/INVESTMENT STATUS UNAVAILABLE/);
  data['/api/live']=false;p.set(data);await p.load();assert.equal(p.node('mFresh').textContent,'UNAVAILABLE');
  p.set(payloads());await p.load();assert.equal(p.node('mFresh').textContent,'DISABLED');
});

test('fresh board cannot borrow old collector state from a failed summary read',async()=>{
  const p=page();await p.load();const bad=payloads();bad['/api/command-center/summary']=false;p.set(bad);await p.load();
  assert.match(p.node('feeds').innerHTML,/<b>Hyperliquid Perp<\/b><span class="bad">UNAVAILABLE/);
});


test('unknown archive totals are unavailable while an explicit zero remains zero',async()=>{
  const p=page(),data=payloads();data['/api/archive/export/summary']={totals:{},sources:[]};p.set(data);await p.load();
  assert.equal(p.node('mStorage').textContent,'UNAVAILABLE');assert.match(p.node('findings').innerHTML,/ARCHIVE FOOTPRINT UNAVAILABLE/);
  data['/api/archive/export/summary']={totals:{bytes:0,available_sources:0},sources:[]};p.set(data);await p.load();
  assert.equal(p.node('mStorage').textContent,'0 B');
});


test('old runtime errors are not relabeled current after the live read fails',async()=>{
  const p=page(),data=payloads();data['/api/live'].health={last_error:'synthetic earlier runtime error'};
  p.set(data);await p.load();assert.match(p.node('findings').innerHTML,/synthetic earlier runtime error/);
  const bad=payloads();bad['/api/live']=false;p.set(bad);await p.load();
  assert.doesNotMatch(p.node('findings').innerHTML,/synthetic earlier runtime error/);
  assert.match(p.node('findings').innerHTML,/ENDPOINT FAILURE/);
});
