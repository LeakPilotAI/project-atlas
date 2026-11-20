/* Confined test host only: exercise original iframe navigation in real Chrome. */
if(new URLSearchParams(location.search).get('hubAcceptance')==='1'){
 const failures=[],tabs=[];window.addEventListener('error',event=>failures.push(event.message));
 window.addEventListener('load',async()=>{
  for(const name of ['perps','quality','invest','archive','command','prediction']){
   try{
    document.querySelector('.tab[data-pane="'+name+'"]').click();
    const frame=document.querySelector('#pane-'+name+' iframe');
    for(let i=0;i<100;i++){if(frame.contentDocument?.body?.textContent.length>200&&frame.contentDocument.readyState==='complete')break;await new Promise(resolve=>setTimeout(resolve,20));}
    await new Promise(resolve=>setTimeout(resolve,60));
    const doc=frame.contentDocument;
    const value={name,url:frame.getAttribute('src'),title:doc.title,characters:doc.body.textContent.length,tables:doc.querySelectorAll('table').length,panels:doc.querySelectorAll('.panel,.card,.metric,.stat').length};
    if(!value.title||value.characters<200)throw Error('Workspace did not mount: '+name);tabs.push(value);
   }catch(error){failures.push(String(error))}
  }
  const result=document.createElement('pre');result.id='hub-browser-result';result.style.cssText='position:fixed;top:0;left:0;z-index:99999;background:#020a0d;color:#65d9e7;white-space:pre-wrap';result.textContent=JSON.stringify({passed:tabs.length===6&&failures.length===0,tabs,failures});document.body.append(result);
 });
}
