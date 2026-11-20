const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('backend/app/static/prediction_paper.html','utf8');const code=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];const els={};const el=id=>els[id]??={textContent:'',innerHTML:'',querySelectorAll:()=>[]};
let fail=false;const status={summary:{closed_accounting_status:'RECONCILED',net_pnl_dollars:'0.44'},automation:{automatic_paper_position_opening:false,live_capital_allowed:false},events:[]};
const context=vm.createContext({document:{getElementById:el},atlasPoll:()=>{},atlasFetch:async url=>({ok:!fail,json:async()=>url.includes('candidates')?{candidates:[]}:status})});vm.runInContext(code,context);
let count=0;function check(expr,expected){assert.equal(vm.runInContext(expr,context),expected);count++}
(async()=>{for(const value of ['true','false','null','undefined','"NaN"','"Infinity"','"0x10"','"<img>"','" "'])check(`money(${value})`,'—');check('money(0)','$0.00');check('money(".44")','$0.44');check('eventRow({event:"close",net_pnl_dollars:"99"}).includes("$99")',false);check('eventRow({}).includes("NO</td>")',false);
await vm.runInContext('guardedRefresh()',context);assert.equal(el('pnl').textContent,'$0.44');count++;
status.summary.closed_accounting_status='INSUFFICIENT_EVIDENCE';await vm.runInContext('guardedRefresh()',context);assert.equal(el('pnl').textContent,'—');count++;
fail=true;await vm.runInContext('guardedRefresh()',context);assert.equal(el('pnl').textContent,'—');assert.equal(el('events').innerHTML,'');assert.equal(el('lock').textContent,'SAFETY STATE UNKNOWN');count+=3;
console.log(`${count} dashboard assertions passed; synthetic VM only`);})().catch(e=>{console.error(e);process.exitCode=1});
