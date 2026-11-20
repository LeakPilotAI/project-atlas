import fs from 'node:fs';
import vm from 'node:vm';
const html=fs.readFileSync(new URL('../backend/app/static/command_center_health.html',import.meta.url),'utf8');
const script=[...html.matchAll(/<script(?:[^>]*)>([\s\S]*?)<\/script>/g)].map(x=>x[1]).filter(x=>x.trim()).join('\n');
export function payloads(){return {
  '/health':Object.fromEntries(['scanner_running','opportunity_tracker_running','paper_trade_tracker_running','quality_dip_running','command_center_running','perp_manual_running','perp_alert_delivery_running','daily_paper_recap_running','micro_heartbeat_running','discord_ready'].map(k=>[k,true])),
  '/api/command-center/summary':{perps:{running:true}},
  '/api/live':{investment:{enabled:false},quality_dips:{running:true,data_freshness:{}}},
  '/api/perps/manual/board?limit=8':{auto_paper:{pending_count:2,open_count:3,closed_total:4},data_freshness:{}},
  '/api/perps/paper-risk':{kill_switch:false,reliable:true},
  '/diagnostics/paper-reconciliation':{current:{reconciliation_ok:true},runtime:{paper_review:{state:'COMPLETE'},reconciliation_review:{state:'COMPLETE'}}},
  '/api/archive/export/summary':{totals:{available_sources:1,bytes:128},sources:[{label:'Synthetic store',bytes:128,rows:3}]},
};}
export function page(){
  const nodes=new Map();let responses=payloads(),intercept=null;
  const node=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',innerHTML:'',className:'',addEventListener(){}});return nodes.get(id);};
  const context=vm.createContext({document:{getElementById:node,querySelectorAll:()=>[]},window:{addEventListener(){}},
    performance:{now:()=>0},atlasPoll(){},atlasDataFreshness:()=> 'ready',
    atlasFetch:async url=>{if(intercept)return intercept(url);if(responses[url]===false)throw Error('synthetic unavailable');return {json:async()=>responses[url]};}});
  vm.runInContext(script,context);
  vm.runInContext('renderAll=()=>{renderMetrics();renderServices();renderPaper();renderFeeds();renderFindings();renderStores();}',context);
  return {node,set:data=>{responses=data;},fetch:fn=>{intercept=fn;},load:()=>context.load()};
}

