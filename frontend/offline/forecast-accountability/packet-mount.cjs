/* Inert packet-only local-file presentation; trusted pins come from the build. */
'use strict';
function mount(document,api,pins){
  const file=document.getElementById('packet-file'),clearButton=document.getElementById('clear-packet'),status=document.getElementById('packet-status'),results=document.getElementById('packet-results');
  if(!file||!clearButton||!status||!results||typeof api?.verifyComparisonPacket!=='function'||typeof api?.comparisonSourcePins!=='function'||api.PACKET_LIMIT!==2000000)throw Error('Complete isolated packet view required');
  const trusted=api.comparisonSourcePins(pins);
  let revision=0n,current=null,disposed=false;
  const node=(tag,text)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=String(text);return element;};
  const show=value=>value===null||value===undefined?'Unavailable':typeof value==='boolean'?value?'Yes':'No':String(value);
  function empty(message){current=null;results.replaceChildren();status.textContent=message;}
  function table(root,title,caption,headings,rows){
    const section=node('section');section.className='panel';section.append(node('h2',title));
    const scroll=node('div');scroll.className='scroll';scroll.tabIndex=0;scroll.setAttribute('aria-label',title);
    const body=node('table');body.append(node('caption',caption));const head=node('thead'),line=node('tr');
    for(const label of headings){const cell=node('th',label);cell.setAttribute('scope','col');line.append(cell);}head.append(line);body.append(head);
    const entries=node('tbody');for(const values of rows){const line=node('tr');for(const value of values)line.append(node('td',show(value)));entries.append(line);}body.append(entries);scroll.append(body);section.append(scroll);root.append(section);
  }
  function render(value){
    const report=value.comparison,root=node('div');
    table(root,'Supplied report comparison','Full forecast union. Updates do not add forecasts. No independent chain ancestry, source truth or runtime attestation.',
      ['Measure','Recorded value'],[['Prior report UTC',report.left_asof],['Current report UTC',report.right_asof],['Prior forecasts',report.left_forecast_n],['Current forecasts',report.right_forecast_n],['Shared forecasts',report.matched_forecast_n],['Full union',report.union_forecast_n],...Object.entries(report.status_counts)]);
    table(root,'Every forecast','Left-only, right-only, pending and conflicted records remain visible. Price-error differences are per forecast, never trading P&L or a cross-asset mean.',
      ['Asset','Model','Horizon','Forecast commitment','State','Prior actual','Current actual','Prior source revision','Current source revision','Provenance changed','Error state','Prior absolute error','Current absolute error','Right minus left error'],
      report.rows.map(row=>[row.asset_id,row.model,row.horizon,row.forecast_sha256,row.status,row.left_actual,row.right_actual,row.left_source_revision,row.right_source_revision,row.outcome_provenance_changed,row.metric_state,row.left_absolute_error,row.right_absolute_error,row.right_minus_left_absolute_error]));
    table(root,'Original interval impact','Inclusive boundaries. Missing uncertainty is unavailable, not a miss. Original inputs stay fixed; reported coverage is not calibrated confidence.',
      ['Asset','Forecast commitment','State','Nominal level','Prior covered','Current covered','Prior score','Current score','Right minus left score'],
      report.rows.map(row=>{const i=row.score_impact.interval;return [row.asset_id,row.forecast_sha256,i.state,i.level,i.left_covered,i.right_covered,i.left_score,i.right_score,i.right_minus_left_score];}));
    table(root,'Original probability impact','Natural logs, no clipping. Infinite/undefined/numeric-range states are explicit; absent values never become zero loss. Flat outcomes are not UP.',
      ['Asset','Forecast commitment','State','Recorded probability UP','Prior actual UP','Current actual UP','Prior Brier','Current Brier','Right minus left Brier','Prior log state','Current log state','Prior log loss','Current log loss','Change state','Right minus left log loss'],
      report.rows.map(row=>{const p=row.score_impact.probability;return [row.asset_id,row.forecast_sha256,p.state,p.probability_up,p.left_actual_up,p.right_actual_up,p.left_brier,p.right_brier,p.right_minus_left_brier,p.left_log_loss_state,p.right_log_loss_state,p.left_log_loss,p.right_log_loss,p.log_loss_difference_state,p.right_minus_left_log_loss];}));
    return root;
  }
  async function loadFile(input){
    if(disposed)return {status:'DISPOSED'};const own=++revision;
    try{
      empty('Checking local comparison packet…');
      if(!input||!Number.isSafeInteger(input.size)||input.size<1||input.size>api.PACKET_LIMIT||typeof input.arrayBuffer!=='function')throw Error('Bounded local packet required');
      const buffer=await input.arrayBuffer();if(own!==revision||disposed)return {status:'SUPERSEDED'};
      const length=Object.getOwnPropertyDescriptor(ArrayBuffer.prototype,'byteLength').get.call(buffer);
      if(!Number.isSafeInteger(length)||length<1||length>api.PACKET_LIMIT)throw Error('Bounded packet bytes required');
      const raw=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(new Uint8Array(buffer));
      const verified=await api.verifyComparisonPacket(raw,trusted);if(own!==revision||disposed)return {status:'SUPERSEDED'};
      const content=render(verified);results.replaceChildren(content);current=verified;
      status.textContent='Packet reproduced with the trusted build pins. Source authenticity, ancestry, runtime and production readiness are not established.';
      return {status:'LOADED'};
    }catch(error){
      if(own!==revision||disposed)return {status:'SUPERSEDED'};current=null;
      const sourceMismatch=error?.name==='AtlasEvidenceRefusal'&&error.message==='Matching archived comparator source required.';
      const refusal=sourceMismatch
        ?'Source/build mismatch: packet refused. Previous comparison cleared. Open the viewer built from matching archived sources. Do not edit pins or manifests. Packet validity is not established.'
        :'Packet refused or could not be verified. Previous comparison cleared. Check that the file is a complete, supported comparison packet. No authority granted.';
      try{empty(refusal);}
      catch(cleanup){throw new AggregateError([error,cleanup],'Packet import and refusal display failed');}
      return {status:'REFUSED'};
    }
  }
  function clear(){revision++;file.value='';empty('Comparison cleared. Select a local packet; nothing is uploaded.');}
  const change=()=>loadFile(file.files?.[0]);file.addEventListener('change',change);clearButton.addEventListener('click',clear);
  empty('Select a comparison packet, maximum 2 MB. No connection or storage is used.');
  return {loadFile,clear,current:()=>current===null?null:structuredClone(current),dispose(){disposed=true;file.removeEventListener('change',change);clearButton.removeEventListener('click',clear);clear();}};
}
module.exports={mount};
