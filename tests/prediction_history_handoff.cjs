// Synthetic evaluator/journal snapshot consumer; never starts a browser or service.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const input=JSON.parse(fs.readFileSync(0,'utf8')),html=fs.readFileSync(process.argv[2],'utf8');
const els={},handlers={};const row={dataset:{i:'0'},classList:{add(){},remove(){}},addEventListener(name,fn){handlers[name]=fn}};
const el=id=>els[id]??={textContent:'',innerHTML:'',children:[row],querySelectorAll:()=>[row]};
const status={automation:{automatic_paper_position_opening:false,live_capital_allowed:false},summary:{}};
const context=vm.createContext({document:{getElementById:el},atlasPoll:()=>{},atlasFetch:async url=>({ok:true,json:async()=>url.includes('candidates')?input.snapshot:status})});
vm.runInContext(html.match(/<script>\s*([\s\S]*?)<\/script>/)[1],context);
(async()=>{await vm.runInContext('guardedRefresh()',context);assert.match(el('historyEvidence').textContent,/Select/);assert.equal(typeof handlers.click,'function');handlers.click();for(const expected of input.expected)assert.ok(el('historyEvidence').textContent.includes(expected),expected+' missing: '+el('historyEvidence').textContent);assert.deepEqual(JSON.parse(el('detail').textContent),input.snapshot.candidates.at(-1));assert.match(el('historyEvidence').textContent,/availability not established/);assert.equal(el('lock').textContent,'AUTO-OPEN LOCKED · LIVE OFF');process.stdout.write(JSON.stringify({synthetic_only:true,history:el('historyEvidence').textContent}));})().catch(error=>{console.error(error);process.exitCode=1});
