// Consume actual disposable Python router responses through the shipped page.
// This is a VM DOM/fetch test, not a browser, server or live network test.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const frames=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const html=fs.readFileSync('backend/app/static/quality_dips.html','utf8');
const script=fs.readFileSync('backend/app/static/quality_dips_selected_paper.js','utf8');
const inline=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements={},requests=[];let current,now,loops=0;
const doc={getElementById(id){return elements[id]??={textContent:'',innerHTML:'',hidden:false,value:'',style:{},
  listeners:{},classList:{toggle(){},remove(){}},setAttribute(){},addEventListener(k,v){this.listeners[k]=v;},scrollIntoView(){}};},
  addEventListener(){},querySelectorAll(){return [];},querySelector(){return {scrollIntoView(){}};},body:{classList:{toggle(){}}}};
class Clock extends Date{static now(){return now*1000;}}
const context=vm.createContext({document:doc,Date:Clock,AbortController,URLSearchParams,location:{search:'?mode=selected-paper'},
  setTimeout:()=>1,clearTimeout(){},atlasPoll(){loops++;},atlasFetch(){throw Error('LEGACY_RESEARCH_GET_FORBIDDEN');},
  fetch:async(url,options)=>{requests.push({url,method:options.method});return {ok:true,json:async()=>current};}});
vm.runInContext(script,context);vm.runInContext(inline,context);
async function run(){
  for(const frame of frames){current=frame.payload;now=frame.now;await context.load();
    if(frame.expectedCash!==null){assert.match(elements.paperStatus.textContent,/ACKNOWLEDGED/);assert.ok(elements.paperContent.innerHTML.includes('$'+frame.expectedCash));
      if(frame.remaining)assert.ok(elements.paperContent.innerHTML.includes(frame.remaining));
      else assert.match(elements.paperContent.innerHTML,/No open positions in this acknowledged projection/);
      assert.match(elements.paperContent.innerHTML,/Report realized fees/);assert.match(elements.paperStatus.textContent,/INCOMPLETE/);
      assert.match(elements.paperContent.innerHTML,/Acknowledged entry decision; not current eligibility/);
    }else{assert.equal(elements.paperStatus.textContent,'UNAVAILABLE');assert.doesNotMatch(elements.paperContent.innerHTML,/\$1000|\$900|\$1009/);}
    assert.equal(elements.researchWorkspace.hidden,true);
  }
  assert.equal(loops,1);assert.equal(requests.length,frames.length);
  assert.ok(requests.every(row=>row.url==='/api/investments/quality-dips/selected-paper'&&row.method==='GET'));
  console.log(`${frames.length} disposable application frames passed; zero legacy/provider/writer calls`);
}
run().catch(error=>{console.error(error);process.exitCode=1;});
