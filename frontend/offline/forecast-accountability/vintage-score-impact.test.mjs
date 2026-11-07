import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import api from './view.cjs';
const read=name=>JSON.parse(fs.readFileSync(new URL('../../../tests/fixtures/afi-vintage-score-impact-v1/'+name,import.meta.url),'utf8'));
const producer=read('reports.json'),declared=read('declared-boundaries.json');
const compare=reports=>api.compareReportVintages(reports[1],reports[2]);
const close=(a,b)=>assert.ok(Math.abs(a-b)<=1e-12*Math.max(1,Math.abs(b)));
for(const [name,reports] of Object.entries(producer))test(`actual immutable publisher score impact ${name}`,()=>{const before=JSON.stringify(reports),result=compare(reports),p=result.rows[0].score_impact.probability;assert.equal(result.union_forecast_n,1);assert.equal(result.history_ancestry_verified,false);if(name==='no_probability'){assert.equal(p.state,'NO_PROBABILITY');assert.equal(p.log_loss_difference_state,'NO_PROBABILITY');assert.equal(p.right_minus_left_brier,null);}else{close(p.left_brier,reports[1].score.cohorts[0].brier);close(p.right_brier,reports[2].score.cohorts[0].brier);close(p.right_minus_left_brier,p.right_brier-p.left_brier);assert.equal(p.log_loss_difference_state,'FINITE');}assert.equal(JSON.stringify(reports),before);});
test('actual original interval changes coverage inclusively and score with one sample',()=>{const i=compare(producer.interval).rows[0].score_impact.interval;assert.equal(i.state,'FINITE');assert.equal(i.left_covered,true);assert.equal(i.right_covered,false);close(i.left_score,4);close(i.right_score,464);close(i.right_minus_left_score,460);});
const expected={positive:'POSITIVE_INFINITY',negative:'NEGATIVE_INFINITY',both:'UNDEFINED_BOTH_INFINITE',positive_zero:'POSITIVE_INFINITY',negative_zero:'NEGATIVE_INFINITY',both_zero:'UNDEFINED_BOTH_INFINITE',half:'FINITE',near_half:'UNAVAILABLE_NUMERIC_RANGE',tiny:'FINITE'};
for(const [name,packet] of Object.entries(declared))test(`declared boundary import ${name}, not publisher-history evidence`,()=>{assert.equal(packet.scope,'DECLARED_SYNTHETIC_BOUNDARIES_NOT_PUBLISHER_HISTORIES');const result=api.compareReportVintages(...packet.reports),p=result.rows[0].score_impact.probability;assert.equal(p.log_loss_difference_state,expected[name]);if(expected[name]!=='FINITE')assert.equal(p.right_minus_left_log_loss,null);if(name==='half')assert.equal(p.right_minus_left_log_loss,0);if(name==='tiny'){assert.equal(p.state,'UNAVAILABLE_NUMERIC_RANGE');assert.equal(p.left_brier,null);assert.equal(p.right_minus_left_brier,null);assert.ok(p.right_minus_left_log_loss>700);}assert.equal(result.production_approved,false);});
test('missing fitted interval is unavailable, never a coverage miss',()=>{const i=compare(producer.up_to_down).rows[0].score_impact.interval;assert.equal(i.state,'NO_INTERVAL');assert.equal(i.left_covered,null);assert.equal(i.right_minus_left_score,null);});
test('pending outcomes never produce correction scores',()=>{const value=api.compareReportVintages(producer.interval[0],producer.interval[1]).rows[0].score_impact;assert.equal(value.interval.state,'NOT_BOTH_RESOLVED');assert.equal(value.probability.state,'NOT_BOTH_RESOLVED');assert.equal(value.probability.right_minus_left_log_loss,null);});
test('refused original identity cannot leak interval or probability impact',()=>{const a=producer.interval[1],b=structuredClone(producer.interval[2]);b.rows[0].forecast_artifact_sha256='f'.repeat(64);const value=api.compareReportVintages(a,b).rows[0].score_impact;assert.equal(value.interval.state,'REFUSED_IDENTITY');assert.equal(value.probability.state,'REFUSED_IDENTITY');assert.equal(value.probability.left_brier,null);});
test('unrecorded legacy inputs remain distinct from explicitly absent fits',()=>{const report=structuredClone(producer.up_to_down[1]);delete report.rows[0].score_cohort;delete report.rows[0].probability_up;delete report.rows[0].interval;for(const key of Object.keys(report))if(key.endsWith('_contract')||key.endsWith('_diagnostics')||key==='diagnostic_partition')delete report[key];report.score={issued_n:1,scored_n:1,pending_n:0,cohorts:[{n:1}]};const impact=api.compareReportVintages(report,report).rows[0].score_impact;assert.equal(impact.interval.state,'UNRECORDED_INTERVAL');assert.equal(impact.probability.state,'UNRECORDED_PROBABILITY');assert.equal(impact.probability.left_log_loss_state,'UNRECORDED_PROBABILITY');});

function document(){class Element{constructor(){this.children=[];this.listeners={};this.value='';this.textContent='';}replaceChildren(...items){this.children=items;}appendChild(item){this.children.push(item);}addEventListener(name,fn){this.listeners[name]=fn;}setAttribute(){}}const ids={};for(const id of ['prior-report-file','prior-load-status','vintage-rows','vintage-impact-rows','vintage-signed-rows','vintage-status','report-file','forecast-rows','interval-rows','directional-rows','error-rows','reliability-rows','log-loss-rows','paired-log-loss-rows','log-loss-status','paired-log-loss-status','error-status','pair-rows','paired-interval-rows','paired-probability-rows','pair-status','compare-a','compare-b','auto-pairs','asset-filter','state-filter','horizon-filter','sort-order','visible-count','load-status','forecast-count','resolved-count','correction-count','report-asof','clear-report'])ids[id]=new Element();ids['state-filter'].value='ALL';ids['horizon-filter'].value='ALL';ids['sort-order'].value='target-asc';return {ids,getElementById:id=>ids[id],createElement:()=>new Element()};}
function browserReport(report){const text=JSON.stringify(report);return JSON.stringify({schema:'AFI_BROWSER_REPORT_V1',report_json:text,payload_sha256:createHash('sha256').update(text).digest('hex')});}
async function load(doc,id,report){const text=browserReport(report);await doc.ids[id].listeners.change({target:{files:[{size:Buffer.byteLength(text),text:async()=>text}]}});}
test('mounted original uncertainty impact shows coverage change and exact nominal level',async()=>{const doc=document();api.mount(doc);await load(doc,'report-file',producer.interval[2]);await load(doc,'prior-report-file',producer.interval[1]);assert.equal(doc.ids['vintage-impact-rows'].children.length,1);const cells=doc.ids['vintage-impact-rows'].children[0].children.map(item=>item.textContent);assert.ok(cells.includes('0.8'));assert.ok(cells.includes('true'));assert.ok(cells.includes('false'));assert.ok(cells.includes('RECORDED'));doc.ids['clear-report'].listeners.click();assert.equal(doc.ids['vintage-impact-rows'].children.length,0);});
test('declared impossible event is visible as a state, never a numeric zero loss',async()=>{const doc=document();api.mount(doc);await load(doc,'report-file',declared.positive.reports[1]);await load(doc,'prior-report-file',declared.positive.reports[0]);assert.equal(doc.ids['vintage-impact-rows'].children.length,1);const cells=doc.ids['vintage-impact-rows'].children[0].children.map(item=>item.textContent);assert.ok(cells.includes('POSITIVE_INFINITY'));assert.ok(cells.includes('INFINITE'));assert.equal(cells.at(-1),'Unavailable');});
test('invalid baseline replacement removes uncertainty impacts without clearing main report',async()=>{const doc=document();api.mount(doc);await load(doc,'report-file',producer.interval[2]);await load(doc,'prior-report-file',producer.interval[1]);await doc.ids['prior-report-file'].listeners.change({target:{files:[{size:1,text:async()=>'{'}]}});assert.equal(doc.ids['vintage-impact-rows'].children.length,0);assert.equal(doc.ids['forecast-rows'].children.length,1);});


test('signed error impact follows immutable correction histories without new cases',()=>{
  for(const reports of Object.values(producer)){
    const bytes=JSON.stringify(reports),packet=JSON.stringify(compare(reports));
    const result=api.signedErrorVintageImpact(reports[1],reports[2]);
    assert.equal(result.rows.length,1);assert.equal(result.history_ancestry_verified,false);
    const row=result.rows[0],a=reports[1].rows[0],b=reports[2].rows[0];
    assert.equal(row.state,'FINITE');assert.equal(row.left_signed_error,a.forecast_point-a.actual);
    assert.equal(row.right_signed_error,b.forecast_point-b.actual);
    assert.equal(row.right_minus_left_signed_error,a.actual-b.actual);
    assert.equal(JSON.stringify(reports),bytes);assert.equal(JSON.stringify(compare(reports)),packet);
  }
});

test('signed impact refuses pending, missing original binding and identity conflicts',()=>{
  assert.equal(api.signedErrorVintageImpact(producer.interval[0],producer.interval[1]).rows[0].left_signed_error,null);
  const a=structuredClone(producer.interval[1]),b=structuredClone(producer.interval[2]);
  b.rows[0].forecast_artifact_sha256='f'.repeat(64);
  const refused=api.signedErrorVintageImpact(a,b).rows[0];
  assert.equal(refused.state,'REFUSED_IDENTITY');assert.equal(refused.right_minus_left_signed_error,null);
});

test('mounted signed correction impact clears on invalid baseline and main clear',async()=>{
  const doc=document();api.mount(doc);
  await load(doc,'report-file',producer.interval[2]);await load(doc,'prior-report-file',producer.interval[1]);
  const body=doc.ids['vintage-signed-rows'];assert.equal(body.children.length,1);
  assert.ok(body.children[0].children.map(item=>item.textContent).includes('FINITE'));
  await doc.ids['prior-report-file'].listeners.change({target:{files:[{size:1,text:async()=>'{'}]}});
  assert.equal(body.children.length,0);assert.equal(doc.ids['forecast-rows'].children.length,1);
  await load(doc,'prior-report-file',producer.interval[1]);assert.equal(body.children.length,1);
  doc.ids['clear-report'].listeners.click();assert.equal(body.children.length,0);
});

function legacyPair(point=100,oldActual=99,newActual=101){
  const row={asset_id:'CRYPTO:BTC-USD',asset_class:'CRYPTO',model:'NO_CHANGE',horizon:'1D',issued_at:'2026-10-17T00:01:00+00:00',target_at:'2026-10-18T00:00:00+00:00',forecast_point:point,reference:100,actual:oldActual,status:'RESOLVED',forecast_sha256:'a'.repeat(64),source_available_at:'2026-10-18T00:00:00+00:00',last_reconciled_asof:'2026-10-18T12:00:00+00:00',correction_n:0,history_n:1,expected_head:'b'.repeat(64),forecast_artifact_sha256:'c'.repeat(64),forecast_dataset_sha256:'d'.repeat(64),forecast_code_sha256:'e'.repeat(64)};
  const a={schema:'AFI_ACCOUNTABILITY_REPORT_V1',evidence_class:'SYNTHETIC',asof:'2026-10-19T00:00:00+00:00',rows:[row],score:{issued_n:1,scored_n:1,pending_n:0,cohorts:[{n:1}]},forecast_n:1,correction_n:0,production_approved:false,trading_authority:false,recovery_authorized:false,calibration_established:false,live_feed_freshness_verified:false,history_completeness_verified:false};
  const b=structuredClone(a);Object.assign(b.rows[0],{actual:newActual,history_n:2,correction_n:1,expected_head:'f'.repeat(64)});b.correction_n=1;return [a,b];
}

test('signed correction delta preserves small labels beneath rounded large errors',()=>{
  const reports=legacyPair(1e300,100,101),row=api.signedErrorVintageImpact(...reports).rows[0];
  assert.equal(row.left_signed_error,row.right_signed_error);
  assert.equal(row.right_minus_left_signed_error,-1);assert.equal(row.state,'FINITE');
});

test('absolute cancellation refusal does not erase independently finite signed impact',()=>{
  const reports=legacyPair();assert.equal(api.compareReportVintages(...reports).rows[0].metric_state,'UNAVAILABLE_NUMERIC_RANGE');
  const row=api.signedErrorVintageImpact(...reports).rows[0];assert.equal(row.state,'FINITE');
  assert.equal(row.left_signed_error,1);assert.equal(row.right_signed_error,-1);assert.equal(row.right_minus_left_signed_error,-2);
});

test('legacy missing bindings, contradictory history and unmatched cases remain unavailable',()=>{
  for(const mode of ['binding','history','unmatched','regression']){
    const reports=legacyPair();
    if(mode==='binding')for(const report of reports)delete report.rows[0].forecast_code_sha256;
    if(mode==='history')reports[1].rows[0].expected_head=reports[0].rows[0].expected_head;
    if(mode==='unmatched')reports[1].rows[0].forecast_sha256='9'.repeat(64);
    if(mode==='regression')reports[0].rows[0].history_n=3;
    for(const row of api.signedErrorVintageImpact(...reports).rows){assert.equal(row.left_signed_error,null);assert.equal(row.right_signed_error,null);assert.equal(row.right_minus_left_signed_error,null);assert.notEqual(row.state,'FINITE');}
  }
});
