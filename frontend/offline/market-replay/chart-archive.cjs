/* Local supplied-byte verification only. No fetch, storage, provider or execution. */
'use strict';
const fail=()=>{throw Error('Chart archive byte verification refused');};
const flags=['source_authenticated','network_authorized','startup_authorized','recovery_authorized','trading_authorized'];
const digestPattern=/^[a-f0-9]{64}$/;
const exact=(v,keys)=>{if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).sort().join('|')!==[...keys].sort().join('|'))fail();};
const denied=v=>{if(flags.some(k=>v[k]!==false))fail();};
const pin=v=>{if(typeof v!=='string'||!digestPattern.test(v))fail();return v;};
function decode(bytes){
  const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);let offset=0,work=0;
  const space=()=>{while(/\s/.test(text[offset]??'')&&offset<text.length)offset++;};
  const string=()=>{
    const match=/"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"/y;
    match.lastIndex=offset;const token=match.exec(text);if(!token)fail();offset=match.lastIndex;return JSON.parse(token[0]);
  };
  const scan=depth=>{
    if(depth>32||++work>200000)fail();space();
    if(text[offset]==='{'){
      offset++;space();const keys=new Set();if(text[offset]==='}'){offset++;return;}
      for(;;){
        space();const key=string();if(keys.has(key))fail();keys.add(key);space();if(text[offset++]!==':')fail();
        scan(depth+1);space();const end=text[offset++];if(end==='}')return;if(end!==',')fail();
      }
    }
    if(text[offset]==='['){
      offset++;space();if(text[offset]===']'){offset++;return;}
      for(;;){scan(depth+1);space();const end=text[offset++];if(end===']')return;if(end!==',')fail();}
    }
    if(text[offset]==='"'){string();return;}
    const match=/(?:-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null)/y;
    match.lastIndex=offset;if(!match.exec(text))fail();offset=match.lastIndex;
  };
  scan(0);space();if(offset!==text.length)fail();
  return JSON.parse(text,(key,value)=>{if(['__proto__','constructor','prototype'].includes(key))fail();return value;});
}
function time(v){
  if(typeof v!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00$/.test(v))fail();
  const n=Date.parse(v);if(!Number.isFinite(n)||new Date(n).toISOString().slice(0,19)!==v.slice(0,19))fail();return n;
}
async function sha256(bytes){
  if(!globalThis.crypto?.subtle)fail();
  return [...new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
}
function ordered(v){
  if(v&&typeof v==='object'&&!Array.isArray(v))return Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])]));
  return v;
}
async function verifyArchive(files,expectedPin,hash=sha256){
  pin(expectedPin);if(!Array.isArray(files)||files.length!==5||typeof hash!=='function')fail();
  const retained=new Map();let total=0;
  for(const item of files){
    exact(item,['name','bytes']);
    if(typeof item.name!=='string'||! /^[a-f0-9]{64}\.(json|html)$/.test(item.name)||retained.has(item.name)||
       !(item.bytes instanceof Uint8Array)||item.bytes.length<1||item.bytes.length>2000000)fail();
    total+=item.bytes.length;if(total>8000000)fail();
    retained.set(item.name,new Uint8Array(item.bytes));
  }
  const checked=async(name,expected)=>{
    pin(expected);const bytes=retained.get(name);
    if(!bytes||await hash(bytes)!==expected)fail();return bytes;
  };
  const receiptName=expectedPin+'.json',receiptBytes=await checked(receiptName,expectedPin),receipt=decode(receiptBytes);
  exact(receipt,['schema','scope','observed_at','asset_class','source','report','dashboard','provenance',...flags]);denied(receipt);
  if(receipt.schema!=='ATLAS_CHART_ARCHIVE_V1'||receipt.scope!=='SYNTHETIC_REVIEWED_SUBSET_V1'||!['US_EQUITY','US_ETF'].includes(receipt.asset_class))fail();
  // Receipt is ASCII strings/booleans only: canonical roundtrip also rejects duplicate keys.
  if(new TextDecoder().decode(receiptBytes)!==JSON.stringify(ordered(receipt),null,2)+'\n')fail();
  const observed=time(receipt.observed_at),parts={};const names=new Set([receiptName]);
  for(const key of ['source','report','dashboard','provenance']){
    const r=receipt[key];exact(r,['name','sha256']);pin(r.sha256);
    if(r.name!==r.sha256+(key==='dashboard'?'.html':'.json')||names.has(r.name))fail();names.add(r.name);
    parts[key]=await checked(r.name,r.sha256);
  }
  if(parts.source.length>1000000)fail();
  const report=decode(parts.report),provenance=decode(parts.provenance);
  exact(provenance,['schema','source_sha256','report_sha256','html_sha256',...flags]);denied(provenance);
  if(provenance.schema!=='ATLAS_CHART_PROVENANCE_EXPORT_V1'||provenance.source_sha256!==receipt.source.sha256||
     provenance.report_sha256!==receipt.report.sha256||provenance.html_sha256!==receipt.dashboard.sha256)fail();
  exact(report,['schema','mode','source_sha256','observed_at','symbol','asset_class','bar_n','price_basis','adjustment_basis',
    'adjusted_series','provider_reported_delay','provider_delay_unit','live_status','rows',...flags]);denied(report);
  if(report.schema!=='ATLAS_CHART_PROVENANCE_V1'||report.mode!=='SYNTHETIC_REPLAY'||report.source_sha256!==receipt.source.sha256||
     report.observed_at!==receipt.observed_at||report.asset_class!==receipt.asset_class||
     typeof report.symbol!=='string'||!/^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(report.symbol)||
     report.price_basis!=='CHART_QUOTE_CLOSE_NOT_VERIFIED_UNADJUSTED'||report.adjustment_basis!=='UNVERIFIED'||
     !['ABSENT','PRESENT_NOT_AUTHENTICATED'].includes(report.adjusted_series)||report.provider_delay_unit!=='UNVERIFIED'||
     report.live_status!=='NOT_ESTABLISHED'||(report.provider_reported_delay!==null&&(!Number.isSafeInteger(report.provider_reported_delay)||
     report.provider_reported_delay<0||report.provider_reported_delay>86400))||!Array.isArray(report.rows)||
     !Number.isSafeInteger(report.bar_n)||report.bar_n<1||report.bar_n>10000||report.rows.length!==report.bar_n)fail();
  let prior=-Infinity;
  for(const row of report.rows){
    exact(row,['timestamp','session','bar_close','reported_adjusted_close']);const event=time(row.timestamp);
    if(event<=prior||event%60000!==0||event+60000>observed||!['PRE_MARKET','REGULAR','AFTER_HOURS'].includes(row.session)||
       typeof row.bar_close!=='number'||!Number.isFinite(row.bar_close)||row.bar_close<=0)fail();prior=event;
    const adjusted=row.reported_adjusted_close;
    if(report.adjusted_series==='ABSENT'?adjusted!==null:typeof adjusted!=='number'||!Number.isFinite(adjusted)||adjusted<=0)fail();
    Object.freeze(row);
  }
  Object.freeze(report.rows);Object.freeze(report);
  return Object.freeze({status:'BYTE_INTEGRITY_ONLY',python_reproduction_verified:false,receipt_sha256:expectedPin,report,
    ...Object.fromEntries(flags.map(key=>[key,false]))});
}
function createController(display,hash=sha256){
  if(typeof display!=='function')fail();let current=null,revision=0;
  const empty=state=>({state,rows:[],notice:'No verified archive displayed. No live data or authority.'});
  return {
    async load(files,expectedPin){
      const own=++revision;current=null;display(empty('EMPTY'));
      try{
        const value=await verifyArchive(files,expectedPin,hash);if(own!==revision)return {status:'SUPERSEDED'};
        current=value;display({state:'BYTE_INTEGRITY_ONLY',...value.report,notice:'Byte integrity only. Run the Python verifier for source reproduction; no live freshness or provider authenticity.'});return value;
      }catch(error){
        if(own!==revision)return {status:'SUPERSEDED'};current=null;
        try{display(empty('REFUSED'));}catch(renderError){throw new AggregateError([error,renderError],'Archive and refusal display failed');}throw error;
      }
    },
    clear(){revision++;current=null;display(empty('EMPTY'));},
    refuse(){revision++;current=null;display(empty('REFUSED'));},
    current(){return current;}
  };
}
function mount(document){
  const ids=['archive-files','receipt-pin','verify','clear','status','summary','rows'];
  const nodes=Object.fromEntries(ids.map(id=>[id,document.getElementById(id)]));if(ids.some(id=>!nodes[id]))fail();
  const display=value=>{
    nodes.rows.replaceChildren();nodes.summary.textContent='';nodes.status.textContent=value.notice;
    if(value.state!=='BYTE_INTEGRITY_ONLY')return;
    nodes.summary.textContent=`${value.symbol} / ${value.bar_n} bars / adjustment basis unverified / reported delay ${value.provider_reported_delay??'unknown'} (unit unverified). Showing first ${Math.min(value.bar_n,100)} rows.`;
    for(const row of value.rows.slice(0,100)){
      const tr=document.createElement('tr');
      for(const key of ['timestamp','session','bar_close','reported_adjusted_close']){
        const td=document.createElement('td');td.textContent=row[key]===null?'Unavailable':String(row[key]);tr.appendChild(td);
      }nodes.rows.appendChild(tr);
    }
  };
  const controller=createController(display);let generation=0;
  const invalidate=()=>{generation++;controller.clear();};
  nodes['receipt-pin'].addEventListener('input',invalidate);nodes['archive-files'].addEventListener('change',invalidate);nodes.clear.addEventListener('click',invalidate);
  nodes.verify.addEventListener('click',async()=>{
    const own=++generation;controller.clear();const expected=nodes['receipt-pin'].value;
    try{
      pin(expected);const selected=Array.from(nodes['archive-files'].files??[]);
      if(selected.length!==5||selected.some(f=>!Number.isSafeInteger(f.size)||f.size<1||f.size>2000000)||selected.reduce((n,f)=>n+f.size,0)>8000000)fail();
      const files=await Promise.all(selected.map(async f=>{const bytes=new Uint8Array(await f.arrayBuffer());if(bytes.length!==f.size)fail();return {name:f.name,bytes};}));
      if(own!==generation)return;await controller.load(files,expected);
    }catch{if(own===generation)controller.refuse();}
  });
  controller.clear();return controller;
}
const api={verifyArchive,createController,mount};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
else globalThis.AtlasChartArchive=Object.freeze(api);
