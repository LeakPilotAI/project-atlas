/* One active refresh per surface; hidden workspaces do not poll. */
function atlasVisible(){
  return !document.hidden && (!window.frameElement || window.frameElement.closest('.pane')?.classList.contains('on') !== false);
}
async function atlasFetch(url, timeout=6500){
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),timeout);
  try {const response=await fetch(url,{cache:'no-store',signal:controller.signal});
    if(!response.ok)throw Error('HTTP '+response.status);
    // Consume the body inside the deadline, not just the response headers.
    const data=await response.json(); return {ok:true,json:async()=>data};
  } finally {clearTimeout(timer);}
}
function atlasPoll(refresh, interval){
  let busy=false;
  const run=async()=>{if(busy || !atlasVisible())return;busy=true;try{await refresh();}finally{busy=false;}};
  run();setInterval(run,interval);return run;
}
