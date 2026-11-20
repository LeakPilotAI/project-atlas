/* Read-only contract panes. No commands, provider calls or browser ACK. */
(function(root){
  'use strict';
  const esc=x=>String(x??'UNAVAILABLE').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const obj=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
  const dec=x=>typeof x==='string'&&x.length<=160&&/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(x)&&Number.isFinite(Number(x));
  const stamp=x=>Number.isSafeInteger(x)&&x>=0;
  function render(data,now,pane){
    if(!obj(data)||data.schema!=='ATLAS_DASHBOARD_READ_MODEL_V1'||!['DISPOSABLE','OPERATIONAL','UNAVAILABLE'].includes(data.execution_domain)||data.startup_authorized!==false||data.total_cash!==null||data.total_equity!==null||!stamp(data.observed_at)||!obj(data.lanes)||!obj(data.accounts)||!(/^[0-9a-f]{64}$/.test(data.snapshot_id)))return '<p>UNKNOWN — invalid read snapshot. Financial values UNAVAILABLE.</p>';
    const current=Number.isFinite(now)&&now-data.observed_at*1000>=0&&now-data.observed_at*1000<=5000;
    let html=`<p>${esc(data.execution_domain)} · SIMULATED / RESEARCH ONLY · snapshot ${esc(data.snapshot_id)}</p>`;
    if(['invest','archive','prediction'].includes(pane))return html+'<p>UNAVAILABLE — no accepted read capability for this surface. Research candidates are not financial positions.</p>';
    if(pane==='command')return html+'<p>Runtime connection UNAVAILABLE. Stop UNAVAILABLE: no separately accepted owned-session control. Continuation UNAVAILABLE: no enrolled current map. PAPER startup BLOCKED. No command is available from this read-only page.</p>';
    const lane=pane==='perps'?'HYPERLIQUID':'QUALITY_DIPS',currency=lane==='QUALITY_DIPS'?'USD':'USDC',row=data.lanes[lane],research=row?.research;
    if(!obj(row)||row.currency!==currency||!obj(research))return html+'<p>UNKNOWN — account isolation conflict.</p>';
    const source=research.source,age=obj(source)&&stamp(source.observed_at)?now-source.observed_at*1000:NaN;
    const fresh=current&&research.status==='FRESH'&&Number.isFinite(age)&&age>=0&&age<=source.max_age_seconds*1000;
    html+=`<h2>${lane} / ${currency}</h2><p>Research ${fresh?'FRESH':research.status==='UNAVAILABLE'?'UNAVAILABLE':research.status==='UNKNOWN'?'UNKNOWN':'STALE'} · provider connection UNAVAILABLE</p>`;
    if(obj(source))html+=`<p>Source ${esc(source.source_id)} · revision ${esc(source.revision)} · observed ${esc(source.observed_at)} UTC epoch · digest ${esc(source.digest)}</p>`;
    html+=fresh?`<pre>${esc(JSON.stringify(research.data,null,2))}</pre>`:'<p>Current research values UNAVAILABLE. No candidate or signal is promoted from old evidence.</p>';
    const a=data.accounts.state==='ACKNOWLEDGED'?data.accounts.accounts?.[lane]:null;
    const financial=current&&obj(a)&&a.currency===currency&&stamp(a.source_revision)&&stamp(a.observed_at)&&now-a.observed_at*1000>=0&&now-a.observed_at*1000<=5000&&['cash','gross','realized_costs','net'].every(k=>dec(a[k]));
    if(!financial)return html+'<p>Financial state '+(data.accounts.state==='UNKNOWN'?'UNKNOWN':'UNAVAILABLE')+' — cash, positions, P&amp;L and valuation UNAVAILABLE.</p>';
    html+=`<h3>Separate simulated account</h3><p>Epoch ${esc(a.epoch)} · revision ${esc(a.source_revision)} · head ${esc(a.source_head)}</p><dl><dt>Cash</dt><dd>${esc(a.cash)} ${currency}</dd><dt>Realized net</dt><dd>${esc(a.net)} ${currency}</dd><dt>Positions (accepted account state only)</dt><dd>${esc(JSON.stringify(a.positions))}</dd><dt>Valuation / equity</dt><dd>UNAVAILABLE</dd></dl>`;
    return html;
  }
  if(typeof module!=='undefined')module.exports={render};
  if(typeof document==='undefined')return;
  const target=document.getElementById('atlas-read-model'),pane=document.body.dataset.atlasPane;
  let last=null;
  async function load(){
    try{const response=await atlasFetch('/api/dashboard/read-model');if(!response.ok)throw Error();last=await response.json();target.innerHTML=render(last,Date.now(),pane);}
    catch{last=null;target.textContent='UNAVAILABLE — read failed; prior financial and research values cleared.';}
  }
  atlasPoll(load,5000);
  setInterval(()=>{if(atlasVisible()&&last)target.innerHTML=render(last,Date.now(),pane);},1000);
})(typeof window==='undefined'?globalThis:window);
