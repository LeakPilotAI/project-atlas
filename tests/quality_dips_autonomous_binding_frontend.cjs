// Actual shipped page/controller, synthetic fetch/DOM. Not HTTP or a real browser.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const frames=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const html=fs.readFileSync('backend/app/static/quality_dips.html','utf8');
const script=fs.readFileSync('backend/app/static/quality_dips_selected_paper.js','utf8');
const inline=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements={},requests=[];let current,now,loops=0;
const document={getElementById(id){return elements[id]??={textContent:'',innerHTML:'',hidden:false,value:'',style:{},
  classList:{toggle(){},remove(){}},setAttribute(){},addEventListener(){},scrollIntoView(){}};},
  addEventListener(){},querySelectorAll(){return [];},querySelector(){return {scrollIntoView(){}};},body:{classList:{toggle(){}}}};
class Clock extends Date{static now(){return now*1000;}}
const context=vm.createContext({document,Date:Clock,AbortController,URLSearchParams,location:{search:'?mode=selected-paper'},
  setTimeout:()=>1,clearTimeout(){},atlasPoll(){loops++;},atlasFetch(){throw Error('LEGACY_RESEARCH_GET_FORBIDDEN');},
  fetch:async(url,options)=>{requests.push({url,method:options.method});return {ok:true,json:async()=>current};}});
vm.runInContext(script,context);vm.runInContext(inline,context);
(async()=>{
  for(const frame of frames){
    current=frame.payload;now=current.observed_at;await context.load();
    assert.match(elements.paperStatus.textContent,/ACKNOWLEDGED/);
    assert.ok(elements.paperContent.innerHTML.includes('$'+frame.cash));
    if(frame.quantity)assert.ok(elements.paperContent.innerHTML.includes(frame.quantity));
    else assert.match(elements.paperContent.innerHTML,/No open positions in this acknowledged projection/);
    assert.match(elements.paperContent.innerHTML,/UNAVAILABLE/);
    assert.equal(elements.researchWorkspace.hidden,true);
  }
  assert.equal(loops,1);assert.equal(requests.length,frames.length);
  assert.ok(requests.every(r=>r.url==='/api/investments/quality-dips/selected-paper'&&r.method==='GET'));
  process.stdout.write('V5 actual page: three native-backed snapshots rendered; GET-only; no legacy fallback\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
