/* Shared frontend runtime contract.
   One active refresh per visible surface; hidden workspaces do not poll.
   The status chip is presentation-only and never changes domain semantics. */
let atlasRuntimeInstalled=false;
let atlasRuntimeReady=false;
let atlasRuntimeFailures=0;

function atlasVisible(){
  return !document.hidden && (!window.frameElement || window.frameElement.closest('.pane')?.classList.contains('on') !== false);
}

function atlasInstallRuntimeState(){
  if(atlasRuntimeInstalled)return;
  atlasRuntimeInstalled=true;
  if(typeof document==='undefined' || !document.createElement || !document.head || !document.body)return;

  const style=document.createElement('style');
  style.textContent=`
    #atlas-runtime-state{position:fixed;right:12px;bottom:10px;z-index:2147483000;display:flex;align-items:center;gap:6px;
      max-width:min(420px,calc(100vw - 24px));padding:5px 8px;border:1px solid #23515a;border-radius:9px 3px 9px 3px;
      background:rgba(2,10,13,.92);box-shadow:0 7px 24px rgba(0,0,0,.34);backdrop-filter:blur(8px);
      color:#8fb0bd;font:9px/1.2 Consolas,monospace;letter-spacing:.04em;text-transform:uppercase;pointer-events:none;
      opacity:.82;transition:opacity .15s ease,border-color .15s ease,color .15s ease}
    #atlas-runtime-state i{width:7px;height:7px;border-radius:50%;background:#35e5ee;box-shadow:0 0 7px currentColor;flex:none}
    #atlas-runtime-state[data-state="ready"]{color:#00ddb0;border-color:#1c6558}
    #atlas-runtime-state[data-state="loading"]{color:#35e5ee}
    #atlas-runtime-state[data-state="degraded"]{color:#efb35a;border-color:#73552a;opacity:1}
    #atlas-runtime-state[data-state="error"]{color:#ff5268;border-color:#7f2d3d;opacity:1}
    #atlas-runtime-state[data-state="stale"]{color:#efb35a;border-color:#73552a;opacity:1}
    #atlas-runtime-state[data-state="ready"]{opacity:.48}
    :focus-visible{outline:2px solid rgba(53,229,238,.8)!important;outline-offset:2px!important}
    @media(max-width:900px){
      #atlas-runtime-state{right:7px;bottom:6px;font-size:8px;max-width:calc(100vw - 14px)}
      body{overflow-x:hidden}
      .tableWrap,.gallery,.chartWrap,.activity,.previewChart{max-width:100%}
    }
    @media(prefers-reduced-motion:reduce){*,*:before,*:after{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
  `;
  document.head.appendChild(style);

  const chip=document.createElement('div');
  chip.id='atlas-runtime-state';
  chip.dataset.state='loading';
  chip.innerHTML='<i></i><span>Loading workspace…</span>';
  document.body.appendChild(chip);
}

function atlasSetSurfaceState(state, message){
  atlasInstallRuntimeState();
  if(typeof document==='undefined' || !document.getElementById)return;
  const chip=document.getElementById('atlas-runtime-state');
  if(!chip)return;
  chip.dataset.state=state;
  const label=chip.querySelector ? chip.querySelector('span') : null;
  if(label)label.textContent=message || state;
}

async function atlasFetch(url, timeout=6500){
  atlasInstallRuntimeState();
  if(!atlasRuntimeReady)atlasSetSurfaceState('loading','Loading workspace…');
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),timeout);
  try {
    const response=await fetch(url,{cache:'no-store',signal:controller.signal});
    if(!response.ok)throw Error('HTTP '+response.status);
    // Consume the body inside the deadline, not just the response headers.
    const data=await response.json();
    atlasRuntimeReady=true;
    atlasRuntimeFailures=0;
    atlasSetSurfaceState('ready','Live data ready');
    return {ok:true,json:async()=>data};
  } catch(error) {
    atlasRuntimeFailures+=1;
    const aborted=error && (error.name==='AbortError' || String(error).includes('AbortError'));
    atlasSetSurfaceState(
      atlasRuntimeReady?'degraded':'error',
      aborted?'Request timeout · retrying':'Data read failed · retrying'
    );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function atlasPoll(refresh, interval){
  atlasInstallRuntimeState();
  let busy=false;
  const run=async()=>{
    if(busy || !atlasVisible())return;
    busy=true;
    try{
      await refresh();
      if(atlasRuntimeReady && atlasRuntimeFailures===0)atlasSetSurfaceState('ready','Live data ready');
    }catch(error){
      atlasSetSurfaceState(atlasRuntimeReady?'degraded':'error','Refresh failed · retrying');
    }finally{
      busy=false;
    }
  };
  run();
  setInterval(run,interval);
  return run;
}
