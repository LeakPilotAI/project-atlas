/* Test host only. Runs original application functions in a real browser DOM. */
if(new URLSearchParams(location.search).get('acceptance')==='1'){
 const failures=[],steps=[];window.addEventListener('error',event=>failures.push({message:event.message,file:event.filename,line:event.lineno}));
 window.addEventListener('unhandledrejection',event=>failures.push({message:String(event.reason)}));
 window.addEventListener('load',async()=>{
  const wait=async()=>{for(let i=0;i<100&&researchBusy;i++)await new Promise(r=>setTimeout(r,20));if(researchBusy)throw Error('Research request never drained')};
  const check=(condition,message)=>{if(!condition)throw Error(message)};
  const capture=phase=>steps.push({phase,status:document.getElementById('status').textContent,board:document.getElementById('board').textContent,selected:document.getElementById('selectedTitle').textContent,candidates:document.getElementById('candidateCount').textContent});
  try{
   await wait();await load();await wait();check(document.getElementById('board').textContent.includes('MSFT'),'Initial MSFT absent');capture('VALID');
   await fetch('/__test__/phase/unavailable');await load();await wait();
   check(document.getElementById('candidateCount').textContent==='UNAVAILABLE','503 retained candidate metrics');check(!document.getElementById('selectedTitle').textContent.includes('MSFT'),'503 retained selected symbol');capture('HTTP_503');
   setView('watch');check(document.getElementById('board').textContent.includes('No accepted research evidence'),'Navigation lost refusal');capture('NAVIGATION');
   await fetch('/__test__/phase/recovered');await load();await wait();check(document.getElementById('board').textContent.includes('SPY'),'Recovery SPY absent');check(!document.getElementById('board').textContent.includes('MSFT'),'Recovery retained old symbol');capture('RECOVERED');
   // Complete the financial-state check before spending time on screenshots or navigation.
   setFinancialMode(true);await load();
   check(document.getElementById('paperStatus').textContent==='UNAVAILABLE','Financial refusal absent');
   check(document.getElementById('paperContent').textContent.includes('UNAVAILABLE'),'Missing financial amounts invented');
   const response=await fetch('/api/investments/quality-dips/selected-paper',{cache:'no-store'});
   const financial=await response.json();
   check(response.ok&&financial.status==='UNAVAILABLE'&&financial.cash===null&&financial.positions===null&&financial.startup_authorized===false,'Invalid financial refusal');
   const health=await (await fetch('/health',{cache:'no-store'})).json();
   check(health.financial_writers===false,'Unexpected financial capability');
   steps.push({phase:'FINANCIAL_UNAVAILABLE_WHILE_HOST_LIVE',status:document.getElementById('paperStatus').textContent,cash:financial.cash,positions:financial.positions});
   check(failures.length===0,'Browser runtime errors');
  }catch(error){failures.push({message:String(error)})}
  const result=document.createElement('pre');result.id='browser-acceptance-result';result.style.whiteSpace='pre-wrap';result.textContent=JSON.stringify({passed:failures.length===0&&steps.length===5,steps,failures,viewport:{width:innerWidth,height:innerHeight,bodyWidth:document.body.scrollWidth}},null,2);document.body.append(result);
 });
}
