const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('observation status polls only visible panes and resumes without extra timers',async()=>{
 let calls=0,tick,timers=0,paneVisible=true;
 const element=()=>({style:{},append(){},textContent:'',open:false});
 const document={hidden:false,createElement:element,body:{append(){}}};
 const window={frameElement:{closest:()=>({classList:{contains:()=>paneVisible}})}};
 const context=vm.createContext({document,window,fetch:async()=>{calls++;return {ok:true,json:async()=>({status:'DISCONNECTED'})}},setInterval:fn=>{timers++;tick=fn}});
 vm.runInContext(fs.readFileSync('scripts/observation_runtime/observation_status.js','utf8'),context);
 await new Promise(setImmediate);assert.equal(calls,1);assert.equal(timers,1);
 paneVisible=false;await tick();assert.equal(calls,1);
 paneVisible=true;document.hidden=true;await tick();assert.equal(calls,1);
 document.hidden=false;await tick();assert.equal(calls,2);assert.equal(timers,1);
 window.frameElement=null;await tick();assert.equal(calls,3);
});
test('initially hidden observation iframe makes no read requests',()=>{
 let calls=0;const element=()=>({style:{},append(){},textContent:''});
 const context=vm.createContext({document:{hidden:false,createElement:element,body:{append(){}}},window:{frameElement:{closest:()=>({classList:{contains:()=>false}})}},fetch:()=>{calls++;throw Error('must not run')},setInterval(){}});
 vm.runInContext(fs.readFileSync('scripts/observation_runtime/observation_status.js','utf8'),context);assert.equal(calls,0);
});

test('slow status response cannot accumulate overlapping polling requests',async()=>{
 let calls=0,tick,release;
 const element=()=>({style:{},append(){},textContent:'',open:false});
 const context=vm.createContext({document:{hidden:false,createElement:element,body:{append(){}}},window:{frameElement:null},fetch:()=>{calls++;return new Promise(resolve=>{release=resolve})},setInterval:fn=>{tick=fn}});
 vm.runInContext(fs.readFileSync('scripts/observation_runtime/observation_status.js','utf8'),context);
 await tick();await tick();assert.equal(calls,1);
 release({ok:true,json:async()=>({status:'DISCONNECTED'})});await new Promise(setImmediate);
 const pending=tick();assert.equal(calls,2);release({ok:true,json:async()=>({status:'DISCONNECTED'})});await pending;
});
