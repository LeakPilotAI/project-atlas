const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const poll=fs.readFileSync('backend/app/static/runtime_poll.js','utf8');
const dashboard=fs.readFileSync('backend/app/static/dashboard.html','utf8').split('<script>')[1].split('</script>')[0];
async function states(){
  const elements={};let mode='optional', payload={};
  const document={querySelectorAll:()=>[],getElementById:id=>elements[id]??=({dataset:{},classList:{add(){},remove(){},toggle(){}},innerHTML:'',textContent:''})};
  const c=vm.createContext({document,console:{warn(){}},AbortController,
    setTimeout:f=>{queueMicrotask(f);return 1},clearTimeout(){},
    atlasPoll(){},atlasFetch:async url=>{if(mode==='transport'||url!='/health')throw Error('unavailable');return {ok:true,json:async()=>({})}},
    fetch:async()=>{if(mode==='transport'||mode==='stale')throw Error('unavailable');return {ok:true,json:async()=>payload}}});
  vm.runInContext(dashboard,c);
  await c.load();assert.equal(elements.api.textContent,'API connected');
  mode='stale';await c.load();assert.equal(elements.api.textContent,'API connected · dashboard stale');
  mode='transport';await c.load();await c.load();assert.equal(elements.api.textContent,'API reconnecting');
  mode='optional';payload={quality_dips:{candidates:{invalid:true}}};
  await c.load();assert.equal(elements.api.textContent,'API connected · dashboard degraded');
}
// Poll's second job must be resolved explicitly rather than awaiting a blocked tick.
async function overlap(){
  let tick, finish, calls=0;const document={hidden:false};
  const c=vm.createContext({document,window:{frameElement:null},setInterval:f=>tick=f});
  vm.runInContext(poll,c);c.refresh=()=>{calls++;return new Promise(r=>finish=r)};
  vm.runInContext('atlasPoll(refresh,8000)',c);await tick();await tick();assert.equal(calls,1);
  finish();await Promise.resolve();document.hidden=true;await tick();assert.equal(calls,1);
  document.hidden=false;const pending=tick();assert.equal(calls,2);finish();await pending;
}
Promise.all([overlap(),states()]).then(()=>console.log('poll/transport/optional/render contracts passed')).catch(e=>{console.error(e);process.exitCode=1});
