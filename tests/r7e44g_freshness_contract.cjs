const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('backend/app/static/runtime_poll.js','utf8');
let clock=Date.parse('2026-10-16T14:00:00Z'),payload={},fail=false;
class Clock extends Date{static now(){return clock}}
const states=[];
const c=vm.createContext({Date:Clock,AbortController,setTimeout,clearTimeout,console,
  fetch:async()=>{if(fail)throw Error('fixture unavailable');return{ok:true,json:async()=>payload}}});
vm.runInContext(source,c);
c.capture=(state,message)=>states.push({state,message});
vm.runInContext('atlasSetSurfaceState=capture',c);
const proof=()=>({status:'HEALTHY',observed_at:new Date(clock).toISOString(),max_age_seconds:30,market_count:1,fresh_markets:1});
const classify=data=>{c.fixture=data;return vm.runInContext('atlasDataFreshness(fixture)',c)};
async function run(){
  assert.equal(classify({}),'connected');
  assert.equal(classify({data_status:'STALE'}),'stale');
  for(const observed_at of [null,'invalid','2026-10-16T14:00:00',new Date(clock+1).toISOString()]){
    assert.equal(classify({data_freshness:{...proof(),observed_at}}),'unavailable');
  }
  assert.equal(classify({data_freshness:{...proof(),observed_at:new Date(clock-30001).toISOString()}}),'stale');
  assert.equal(classify({data_freshness:{...proof(),fresh_markets:0}}),'unavailable');
  assert.equal(classify({data_freshness:proof()}),'ready');
  await c.atlasFetch('/board');assert.equal(states.at(-1).state,'connected');
  assert.match(states.at(-1).message,/freshness unverified/);
  payload={data_freshness:proof()};await c.atlasFetch('/board');
  assert.equal(states.at(-1).state,'ready');
  clock+=30001;vm.runInContext('atlasRenderResponseState()',c);
  assert.equal(states.at(-1).state,'stale');
  payload={};await c.atlasFetch('/health');assert.equal(states.at(-1).state,'stale');
  payload={data_freshness:proof()};await c.atlasFetch('/board');
  assert.equal(states.at(-1).state,'connected'); // HTTP health is not quote evidence
  fail=true;await assert.rejects(()=>c.atlasFetch('/failed'));
  fail=false;await c.atlasFetch('/board');assert.equal(states.at(-1).state,'error');
  const html=fs.readFileSync('backend/app/static/command_center_health.html','utf8');
  const a=html.indexOf('function providerFeedStatus('),b=html.indexOf('\n',a);
  vm.runInContext(html.slice(a,b),c);
  assert.equal(c.providerFeedStatus(true,null,true),'UNAVAILABLE');
  assert.equal(c.providerFeedStatus(true,proof(),false),'UNAVAILABLE');
  assert.equal(c.providerFeedStatus(false,proof(),true),'STOPPED');
  assert.equal(c.providerFeedStatus(true,proof(),true),'HEALTHY');
  assert.equal(c.providerFeedStatus(true,{...proof(),status:'STALE'},true),'STALE');
  assert.ok(!html.includes('age_seconds>21600'));
  assert.ok(html.includes('Investment Scanner (cycle)'));
  assert.ok(html.includes('Quality Dips Quotes'));
  console.log('freshness/HTTP/future/expiry/partial-error/dashboard contracts passed');
}
run().catch(error=>{console.error(error);process.exitCode=1});
