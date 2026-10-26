/* Observation-only mode notice; original pages/styles remain unchanged on disk. */
(function(){'use strict';const box=document.createElement('details');box.style.cssText='position:fixed;bottom:32px;left:10px;z-index:2147483000;max-width:90vw;max-height:65vh;overflow:auto;background:#05090b;color:#65d9e7;border:1px solid #183c43;padding:8px;font:12px Consolas,monospace';
const summary=document.createElement('summary');summary.textContent='OBSERVATION ONLY · PAPER disabled · accounts not initialized';box.append(summary);
const label=document.createElement('p');label.textContent='Proposed Quality Dips: 1,000 USD · Proposed Hyperliquid: 1,000 USDC. Current cash, positions, P&L and financial capacity UNAVAILABLE. No financial enrollment or inception.';box.append(label);
const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';box.append(pre);document.body.append(box);
const history=document.createElement('button');history.textContent='Read retained observation history';history.onclick=async()=>{try{const r=await fetch('/api/observation/history');pre.textContent=JSON.stringify(await r.json(),null,2)}catch(e){pre.textContent='History UNAVAILABLE'}};box.append(history);
const research=document.createElement('button');research.textContent='Scan retained Hyperliquid observations (not live)';research.onclick=async()=>{try{const r=await fetch('/api/observation/research');pre.textContent=JSON.stringify(await r.json(),null,2)}catch(e){pre.textContent='Research UNAVAILABLE'}};box.append(research);
async function read(){try{const r=await fetch('/api/observation/state',{cache:'no-store'});if(!r.ok)throw Error();const data=await r.json();summary.textContent='OBSERVATION ONLY · '+data.status+' · PAPER disabled';if(!box.open)pre.textContent=JSON.stringify(data,null,2)}catch(e){summary.textContent='OBSERVATION ONLY · connection unavailable · PAPER disabled'}}
read();setInterval(read,5000);
})();
