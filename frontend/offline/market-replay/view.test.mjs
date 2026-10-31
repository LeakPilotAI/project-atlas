import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import consumer from './view.cjs';
const {parseExport,createController,parseQuality,createQualityController,parseQuoteQuality,createQuoteQualityController,
       parseRetainedResearch,createResearchController} = consumer;
const raw = fs.readFileSync(fileURLToPath(new URL('../../../tests/fixtures/market-replay-v1/api.json',import.meta.url)),'utf8');
const qualityRaw = fs.readFileSync(fileURLToPath(new URL('../../../tests/fixtures/market-replay-v1/quality.json',import.meta.url)),'utf8');
const quoteQualityRaw = fs.readFileSync(fileURLToPath(new URL('../../../tests/fixtures/market-replay-v1/quote-quality.json',import.meta.url)),'utf8');
const researchRaw = fs.readFileSync(fileURLToPath(new URL('../../../tests/fixtures/market-replay-v1/research.json',import.meta.url)),'utf8');
const replayRaw = fs.readFileSync(fileURLToPath(new URL('../../../tests/fixtures/market-replay-v1/research-replay.json',import.meta.url)),'utf8');
const comparisonRaw = fs.readFileSync(fileURLToPath(new URL('../../../tests/fixtures/market-replay-v1/research-comparison.json',import.meta.url)),'utf8');
const vintageRaw = fs.readFileSync(fileURLToPath(new URL('../../../tests/fixtures/market-replay-v1/bar-vintages.json',import.meta.url)),'utf8');
const vintageApiRaw = fs.readFileSync(fileURLToPath(new URL('../../../tests/fixtures/market-replay-v1/bar-vintages-api.json',import.meta.url)),'utf8');
const refusalRaw = fs.readFileSync(fileURLToPath(new URL('../../../tests/fixtures/market-replay-v1/market-refusal.json',import.meta.url)),'utf8');
const digest=text=>createHash('sha256').update(text).digest('hex');
function changedReplay(change) {
  const envelope=JSON.parse(replayRaw),report=JSON.parse(envelope.report_json);
  change(report);envelope.report_json=JSON.stringify(report);envelope.payload_sha256=digest(envelope.report_json);
  return JSON.stringify(envelope);
}
function changedComparison(change) {
  const envelope=JSON.parse(comparisonRaw),report=JSON.parse(envelope.report_json);
  change(report);envelope.report_json=JSON.stringify(report);envelope.payload_sha256=digest(envelope.report_json);
  return JSON.stringify(envelope);
}
function changedVintage(change) {
  const envelope=JSON.parse(vintageRaw),report=JSON.parse(envelope.report_json);
  change(report);envelope.report_json=JSON.stringify(report);envelope.payload_sha256=digest(envelope.report_json);
  return JSON.stringify(envelope);
}
test('actual ASGI refusal clears loaded prices without treating a source failure as fresh data',()=>{
  const views=[],controller=createController(v=>views.push(v));controller.load(raw);
  const refusal=controller.loadResponse(503,refusalRaw);
  assert.equal(refusal.reason,'DATA_UNAVAILABLE');assert.equal(controller.current(),null);
  assert.equal(views.at(-1).state,'SOURCE_REFUSED');assert.deepEqual(views.at(-1).rows,[]);assert.deepEqual(views.at(-1).quote_rows,[]);
});
test('successful response adapter preserves existing replay validation',()=>{
  const controller=createController(()=>{});assert.deepEqual(controller.loadResponse(200,raw),parseExport(raw));
});
for(const fault of ['status','reason','rows','quote_rows','authority','authenticated','unexpected','mode'])test(`refusal rejects ${fault} contradiction`,()=>{
  const body=JSON.parse(refusalRaw);
  if(fault==='status')body.http_status=200;
  if(fault==='reason')body.reason='PRIVATE_PROVIDER_ERROR';
  if(fault==='rows')body.rows=[{price:101}];
  if(fault==='quote_rows')body.quote_rows=[{price:103}];
  if(fault==='authority')body.startup_authorized=true;
  if(fault==='authenticated')body.source_authenticated=true;
  if(fault==='unexpected')body.secret='SYNTHETIC_PRIVATE_VALUE';
  if(fault==='mode')body.mode='LIVE';
  assert.throws(()=>consumer.parseMarketRefusal(JSON.stringify(body)));
});
for(const [status,body] of [[200,refusalRaw],[500,refusalRaw],[503,raw],[0,refusalRaw],[true,refusalRaw],[204,''],[503,'SYNTHETIC_PRIVATE_VALUE']])test(`transport/body disagreement clears stale state: ${status}/${body.length}`,()=>{
  const views=[],controller=createController(v=>views.push(v));controller.load(raw);
  assert.throws(()=>controller.loadResponse(status,body));assert.equal(controller.current(),null);
  assert.equal(views.at(-1).state,'REFUSED');assert.deepEqual(views.at(-1).rows,[]);
  assert.ok(!JSON.stringify(views).includes('SYNTHETIC_PRIVATE_VALUE'));
});
test('refusal display failure preserves original rendering failure with empty model',()=>{
  const controller=createController(v=>{if(v.state==='SOURCE_REFUSED')throw Error('refusal renderer failed');});
  controller.load(raw);assert.throws(()=>controller.loadResponse(503,refusalRaw),/refusal renderer failed/);
  assert.equal(controller.current(),null);
});
test('actual vintage exporter keeps original and corrected decisions using native WebCrypto',async()=>{
  const report=await consumer.verifyVintageReplay(vintageRaw);
  assert.deepEqual(report.cases.map(r=>r.report.analysis.bar_close),[103,120]);
  assert.deepEqual(report.cases.map(r=>r.correction_n),[0,1]);
  assert.equal(report.startup_authorized,false);assert.equal(report.bar_revisions_supported,true);
});
test('actual read-only ASGI response verifies and displays corrected current research',async()=>{
  const report=await consumer.verifyVintageReplay(vintageApiRaw);
  assert.equal(report.planned_decision_n,1);assert.equal(report.cases[0].report.analysis.bar_close,120);
  assert.equal(report.cases[0].correction_n,1);assert.equal(report.source_authenticated,false);
});
for(const fault of ['payload','count','head','correction','confirmation','audit','policy','authority','unexpected','clock'])test(`vintage consumer refuses ${fault}`,async()=>{
  const raw=changedVintage(r=>{
    if(fault==='payload')r.cases[1].report.analysis.bar_close=121;
    if(fault==='count')r.receipt_decision_work--;
    if(fault==='head')r.cases[1].receipt_head=r.cases[0].receipt_head;
    if(fault==='correction')r.cases[1].correction_n=0;
    if(fault==='confirmation')r.cases[1].confirmation_n=1;
    if(fault==='audit')r.cases[1].vintage_decision_sha256='0'.repeat(64);
    if(fault==='policy')r.bar_revision_policy='LATEST_REVISED_AT_ALL_CLOCKS';
    if(fault==='authority')r.source_authenticated=true;
    if(fault==='unexpected')r.cases[1].provider_secret='forbidden';
    if(fault==='clock')r.cases[1].decision_at=r.cases[0].decision_at;
  });
  await assert.rejects(consumer.verifyVintageReplay(raw,digest));
});
test('legacy replay consumer refuses new receipt-vintage envelope',async()=>{
  await assert.rejects(consumer.verifyResearchReplay(vintageRaw,digest));
});
test('failed vintage replacement clears earlier corrected evidence',async()=>{
  const views=[],controller=consumer.createVintageController(v=>views.push(v),digest);
  await controller.load(vintageRaw);await assert.rejects(controller.load('{}'));
  assert.equal(controller.current(),null);assert.equal(views.at(-1).state,'REFUSED');assert.deepEqual(views.at(-1).cases,[]);
});
test('late vintage verification cannot restore an explicitly cleared view',async()=>{
  let release,n=0;
  const controller=consumer.createVintageController(()=>{},text=>++n===1?new Promise(resolve=>{release=()=>resolve(digest(text));}):digest(text));
  const pending=controller.load(vintageRaw);controller.clear();release();
  assert.equal((await pending).status,'SUPERSEDED');assert.equal(controller.current(),null);
});
test('vintage rendering failure preserves error and clears corrected view',async()=>{
  const controller=consumer.createVintageController(v=>{if(v.state==='VINTAGE_REPLAY_LOADED')throw Error('vintage render failed');},digest);
  await assert.rejects(controller.load(vintageRaw),/vintage render failed/);assert.equal(controller.current(),null);
});
test('actual paired Python export keeps complete matrix and unknown metric',async()=>{
  const report=await consumer.verifyResearchComparison(comparisonRaw,digest);
  assert.equal(report.planned_pair_n,3);assert.equal(report.both_descriptive_n,1);
  assert.equal(report.pairs[1].metrics.relative_volume.availability,'LEFT_ONLY');
  assert.equal(report.pairs[1].metrics.relative_volume.right_minus_left,null);
});
test('actual paired envelope verifies through native WebCrypto default',async()=>{
  assert.equal((await consumer.verifyResearchComparison(comparisonRaw)).planned_pair_n,3);
});
test('actual replay envelope verifies through native WebCrypto default',async()=>{
  assert.equal((await consumer.verifyResearchReplay(replayRaw)).planned_decision_n,3);
});
for(const fault of ['count','matrix','unknown_zero','negative_rvol','delta','authority','clock','same','scope','nested_fields'])test(`paired comparison refuses rehashed ${fault}`,async()=>{
  const raw=changedComparison(r=>{
    if(fault==='count')r.not_both_descriptive_n=0;
    if(fault==='matrix')r.status_pair_counts.REFUSED.REFUSED=0;
    if(fault==='unknown_zero')r.pairs[1].metrics.relative_volume.right_minus_left=0;
    if(fault==='negative_rvol')r.pairs[1].metrics.relative_volume.left=-1;
    if(fault==='delta')r.pairs[1].metrics.observed_change_percent.right_minus_left=100;
    if(fault==='authority')r.predictive_skill_established=true;
    if(fault==='clock')r.pairs[1].decision_at=r.pairs[0].decision_at;
    if(fault==='same')r.pairs[1].same_evidence=true;
    if(fault==='scope')r.source_archives_required=false;
    if(fault==='nested_fields')r.pairs[1].metrics.relative_volume.extra='secret';
  });
  await assert.rejects(consumer.verifyResearchComparison(raw,digest));
});
test('paired export rejects digest mismatch before use',async()=>{
  const envelope=JSON.parse(comparisonRaw);envelope.payload_sha256='0'.repeat(64);
  await assert.rejects(consumer.verifyResearchComparison(JSON.stringify(envelope),digest));
});
test('failed paired replacement clears all old pairs',async()=>{
  const views=[],controller=consumer.createComparisonController(v=>views.push(v),digest);
  await controller.load(comparisonRaw);await assert.rejects(controller.load('{}'));
  assert.equal(controller.current(),null);assert.equal(views.at(-1).state,'REFUSED');assert.deepEqual(views.at(-1).pairs,[]);
});
test('late paired verification cannot undo an explicit clear',async()=>{
  let release;const controller=consumer.createComparisonController(()=>{},text=>new Promise(resolve=>{release=()=>resolve(digest(text));}));
  const pending=controller.load(comparisonRaw);controller.clear();release();
  assert.equal((await pending).status,'SUPERSEDED');assert.equal(controller.current(),null);
});
test('paired render failure preserves error and clears model',async()=>{
  const controller=consumer.createComparisonController(v=>{if(v.state==='COMPARISON_LOADED')throw Error('paired render failed');},digest);
  await assert.rejects(controller.load(comparisonRaw),/paired render failed/);assert.equal(controller.current(),null);
});
test('actual Python replay export preserves all planned refused decisions',async()=>{
  const report=await consumer.verifyResearchReplay(replayRaw,digest);
  assert.equal(report.planned_decision_n,3);assert.equal(report.status_counts.REFUSED,2);
  assert.equal(report.predictive_skill_established,false);
});
for(const fault of ['count','authority','clock','nested','work','duplicate','reference'])test(`replay refuses rehashed ${fault} contradiction`,async()=>{
  const raw=changedReplay(r=>{
    if(fault==='count')r.status_counts.REFUSED=0;
    if(fault==='authority')r.startup_authorized=true;
    if(fault==='clock')r.cases[1].decision_at=r.cases[0].decision_at;
    if(fault==='nested')r.cases[1].report.trading_authorized=true;
    if(fault==='work')r.row_decision_work++;
    if(fault==='duplicate')r.cases[1].decision_sha256=r.cases[0].decision_sha256;
    if(fault==='reference')r.cases[1].reference_sha256=null;
  });
  await assert.rejects(consumer.verifyResearchReplay(raw,digest));
});
test('replay verifies exact bytes rather than trusting claimed digest',async()=>{
  const envelope=JSON.parse(replayRaw);envelope.report_json+=' ';
  await assert.rejects(consumer.verifyResearchReplay(JSON.stringify(envelope),digest));
});
test('late replay cannot overwrite a newer decision',async()=>{
  let release,n=0;const views=[];
  const controller=consumer.createReplayController(v=>views.push(v),text=>++n===1?new Promise(resolve=>{release=()=>resolve(digest(text));}):digest(text));
  const old=controller.load(replayRaw);await controller.load(replayRaw);release();
  assert.equal((await old).status,'SUPERSEDED');assert.equal(controller.current().planned_decision_n,3);
  assert.equal(views.at(-1).state,'REPLAY_RESEARCH_LOADED');
});
test('replay clear prevents delayed load from restoring cleared evidence',async()=>{
  let release;const controller=consumer.createReplayController(()=>{},text=>new Promise(resolve=>{release=()=>resolve(digest(text));}));
  const pending=controller.load(replayRaw);controller.clear();release();
  assert.equal((await pending).status,'SUPERSEDED');assert.equal(controller.current(),null);
});
test('replay rendering failure clears evidence and preserves refusal',async()=>{
  const controller=consumer.createReplayController(v=>{if(v.state==='REPLAY_RESEARCH_LOADED')throw Error('render failed');},digest);
  await assert.rejects(controller.load(replayRaw),/render failed/);assert.equal(controller.current(),null);
});
test('actual offline ASGI response retains separate quote and bar evidence',()=>{
  const data = parseExport(raw);
  assert.equal(data.rows.find(r=>r.symbol==='SPY').price,101);
  assert.equal(data.quote_rows.find(r=>r.symbol==='SPY').price,103);
  assert.equal(data.rows.find(r=>r.symbol==='SPY').session,'PRE_MARKET');
});
for (const mutation of ['schema','authority','row_authority','future','age','kind','ohlc','coverage','delay','unavailable','universe']) {
  test(`refuses ${mutation} contradiction`,()=>{
    const data = JSON.parse(raw), bar=data.rows.find(r=>r.symbol==='SPY'), quote=data.quote_rows.find(r=>r.symbol==='SPY');
    if(mutation==='schema')data.schema='LIVE';
    if(mutation==='authority')data.network_authorized=true;
    if(mutation==='row_authority')bar.live_trading_enabled=true;
    if(mutation==='future')bar.observed_at='2026-10-21T12:00:00+00:00';
    if(mutation==='age')bar.age_seconds=-10;
    if(mutation==='kind')quote.price_kind=bar.price_kind;
    if(mutation==='ohlc')bar.high=1;
    if(mutation==='coverage')bar.coverage.missing_minutes=3;
    if(mutation==='delay')quote.provider_reported_delay=15;
    if(mutation==='unavailable')data.rows.find(r=>r.symbol==='MISSING').price=100;
    if(mutation==='universe')data.quote_rows.pop();
    assert.throws(()=>parseExport(JSON.stringify(data)));
  });
}
test('failed replacement clears prior display and retained controller state',()=>{
  const frames=[],controller=createController(frame=>frames.push(frame));
  controller.load(raw);assert.ok(controller.current());
  assert.throws(()=>controller.load('{}'));
  assert.equal(controller.current(),null);
  assert.equal(frames.at(-1).state,'REFUSED');
  assert.deepEqual(frames.at(-1).rows,[]);
  assert.deepEqual(frames.at(-1).quote_rows,[]);
});
test('actual quality API export retains exchange-date gap and delay evidence',()=>{
  const data=parseQuality(qualityRaw);
  assert.equal(data.windows[0].exchange_date,'2026-11-02');
  assert.equal(data.windows[0].missing_minutes_between_observed_bars,1);
  assert.equal(data.windows[0].receipt_delay_max_seconds,190);
  assert.equal(data.session_completeness_verified,false);
});
for(const fault of ['schema','authority','future','count','gaps','delay','age','status','exchange_date',
                   'unknown_field','window_order','repeated_bounds','lifecycle_auth','lifecycle_unknown','threshold']) {
  test(`quality refuses ${fault}`,()=>{
    const data=JSON.parse(qualityRaw), row=data.windows[0];
    if(fault==='schema')data.schema='LIVE';
    if(fault==='authority')data.recovery_authorized=true;
    if(fault==='future')data.source_asof='2026-11-04T00:00:00+00:00';
    if(fault==='count')data.observed_bar_n=0;
    if(fault==='gaps')row.missing_minutes_between_observed_bars=0;
    if(fault==='delay')row.receipt_delay_min_seconds=-1;
    if(fault==='age')row.latest_completed_bar_age_seconds=1;
    if(fault==='status')row.status='STALE_AT_REPORT_CLOCK';
    if(fault==='exchange_date')row.exchange_date='2026-11-03';
    if(fault==='unknown_field')row.startup_authorized=true;
    if(fault==='window_order')data.windows.push({...row});
    if(fault==='repeated_bounds')data.repeated_receipt_n=1000;
    if(fault==='lifecycle_auth')data.lifecycle.authenticated=true;
    if(fault==='lifecycle_unknown')data.lifecycle.status='RUNNING';
    if(fault==='threshold')data.freshness_threshold_seconds=0;
    assert.throws(()=>parseQuality(JSON.stringify(data)));
  });
}
test('quality replacement refusal clears old windows and controller state',()=>{
  const frames=[], controller=createQualityController(frame=>frames.push(frame));
  controller.load(qualityRaw);assert.equal(controller.current().windows.length,1);
  assert.throws(()=>controller.load(raw));
  assert.equal(controller.current(),null);
  assert.equal(frames.at(-1).state,'REFUSED');
  assert.deepEqual(frames.at(-1).windows,[]);
});
test('recorded interruption retains explicit non-clearing warning',()=>{
  const data=JSON.parse(qualityRaw);
  data.lifecycle={status:'RECOVERY_REQUIRED',record_n:2,expected_head:'a'.repeat(64),authenticated:false,live_process_state_verified:false};
  const frames=[], controller=createQualityController(frame=>frames.push(frame));
  controller.load(JSON.stringify(data));
  assert.match(frames.at(-1).notice,/no recovery permission/);
  assert.equal(controller.current().recovery_authorized,false);
});
for(const [name,factory,input,loaded] of [['market',createController,raw,'REPLAY_LOADED'],
                                        ['quality',createQualityController,qualityRaw,'QUALITY_LOADED'],
                                        ['quote quality',createQuoteQualityController,quoteQualityRaw,'QUOTE_QUALITY_LOADED'],
                                        ['research',createResearchController,researchRaw,'RESEARCH_LOADED']]) {
  test(`${name} render failure clears retained model and preserves original error`,()=>{
    const failure=new Error('synthetic render failure'), frames=[];
    const controller=factory(frame=>{frames.push(frame);if(frame.state===loaded)throw failure;});
    assert.throws(()=>controller.load(input),error=>error===failure);
    assert.equal(controller.current(),null);
    assert.equal(frames.at(-1).state,'REFUSED');
  });
  test(`${name} repeated display failure retains both errors and no model`,()=>{
    const first=new Error('synthetic loaded display failure'), second=new Error('synthetic refusal display failure');
    const controller=factory(frame=>{if(frame.state===loaded)throw first;if(frame.state==='REFUSED')throw second;});
    assert.throws(()=>controller.load(input),error=>error instanceof AggregateError&&error.errors[0]===first&&error.errors[1]===second);
    assert.equal(controller.current(),null);
  });
}
test('actual quote quality API preserves delayed and stale as separate evidence',()=>{
  const value=parseQuoteQuality(quoteQualityRaw);
  assert.equal(value.rows.find(r=>r.symbol==='DIA').event_stale_at_report_clock,true);
  assert.equal(value.rows.find(r=>r.symbol==='IWM').event_stale_at_report_clock,false);
  assert.equal(value.status_counts.DELAYED,2);
});
for(const fault of ['authority','unit','age','receipt','count','price','unavailable','stale','state','duplicate',
                   'closed','boolean_delay','null_stale','receipt_delay','health']) {
  test(`quote quality refuses ${fault}`,()=>{
    const value=JSON.parse(quoteQualityRaw), fresh=value.rows.find(r=>r.symbol==='SPY');
    if(fault==='authority')value.startup_authorized=true;
    if(fault==='unit')fresh.reported_delay_unit='SECONDS';
    if(fault==='age')fresh.event_age_seconds=-1;
    if(fault==='receipt')fresh.receipt_time='2026-10-21T14:00:00+00:00';
    if(fault==='count')value.status_counts.FRESH=0;
    if(fault==='price')fresh.price=103;
    if(fault==='unavailable')value.rows.find(r=>r.symbol==='MISSING').event_time=fresh.event_time;
    if(fault==='stale')value.rows.find(r=>r.symbol==='QQQ').event_stale_at_report_clock=false;
    if(fault==='state')fresh.status='DELAYED';
    if(fault==='duplicate')value.rows.push({...fresh});
    if(fault==='closed')value.current_market_session='CLOSED';
    if(fault==='boolean_delay')fresh.reported_delay_value=true;
    if(fault==='null_stale')fresh.event_stale_at_report_clock=null;
    if(fault==='receipt_delay')fresh.receipt_delay_seconds=0;
    if(fault==='health')value.provider_service_health='ONLINE';
    assert.throws(()=>parseQuoteQuality(JSON.stringify(value)));
  });
}
test('invalid quote quality import clears rows and counts',()=>{
  const frames=[], controller=createQuoteQualityController(frame=>frames.push(frame));
  controller.load(quoteQualityRaw);
  assert.throws(()=>controller.load(raw));
  assert.equal(controller.current(),null);
  assert.deepEqual(frames.at(-1).rows,[]);
  assert.equal(frames.at(-1).status_counts,null);
});
test('actual retained research API preserves observed and unknown evidence',()=>{
  const value=parseRetainedResearch(researchRaw);
  assert.equal(value.analysis.relative_volume,2);
  assert.equal(value.analysis.observed_change_percent,3);
  assert.equal(value.sessions[0].observed_volume,null);
  assert.equal(value.sessions[1].observed_volume,600);
  assert.equal(value.trading_authorized,false);
});
for(const fault of ['schema','authority','clock','partial_bar','reference_future','undated','date','change','unseen_premarket_gap','zero_volume_rvol',
                   'unseen_volume','rvol','baseline','unknown_field','price_kind','momentum','overflow_volume']) {
  test(`research refuses ${fault}`,()=>{
    const value=JSON.parse(researchRaw), a=value.analysis;
    if(fault==='schema')value.schema='LIVE';
    if(fault==='authority')value.corporate_actions_reconciled=true;
    if(fault==='clock')value.asof='2026-10-20T13:40:00+00:00';
    if(fault==='partial_bar')a.bar_timestamp='2026-10-20T13:33:00+00:00';
    if(fault==='reference_future')a.reference_available_at='2026-10-21T20:00:00+00:00';
    if(fault==='undated')a.reference_source=' UNKNOWN ';
    if(fault==='date')a.previous_session_date='2026-10-20';
    if(fault==='change')a.observed_change_percent=0;
    if(fault==='unseen_premarket_gap')a.premarket_gap_percent=3;
    if(fault==='zero_volume_rvol')value.sessions[1].observed_volume=0;
    if(fault==='unseen_volume')value.sessions[0].observed_volume=0;
    if(fault==='rvol')a.relative_volume_status='BASELINE_REQUIRED';
    if(fault==='baseline')a.baseline_sessions=1;
    if(fault==='unknown_field')a.execution_authority=true;
    if(fault==='price_kind')a.price_kind='EXECUTABLE_QUOTE';
    if(fault==='momentum')a.session_momentum_percent=null;
    if(fault==='overflow_volume')value.sessions[1].observed_volume=Number.MAX_SAFE_INTEGER+1;
    assert.throws(()=>parseRetainedResearch(JSON.stringify(value)));
  });
}
test('unavailable research has no metrics and failed replacement clears prior view',()=>{
  const frames=[], controller=createResearchController(frame=>frames.push(frame));
  controller.load(researchRaw);
  const empty={...JSON.parse(researchRaw),status:'INSUFFICIENT_REFERENCE',analysis:null,sessions:[]};
  assert.equal(parseRetainedResearch(JSON.stringify(empty)).analysis,null);
  assert.throws(()=>controller.load('{}'));
  assert.equal(controller.current(),null);
  assert.equal(frames.at(-1).analysis,null);
  assert.deepEqual(frames.at(-1).sessions,[]);
});
test('insufficient historical baseline keeps relative volume null',()=>{
  const value=JSON.parse(researchRaw);
  value.analysis.relative_volume=null;
  value.analysis.relative_volume_status='BASELINE_INSUFFICIENT';
  value.analysis.baseline_sessions=4;
  assert.equal(parseRetainedResearch(JSON.stringify(value)).analysis.relative_volume,null);
});
test('recorded zero observed volume is permitted without inventing unobserved volume',()=>{
  const value=JSON.parse(researchRaw);
  value.analysis.relative_volume=0;
  value.sessions[1].observed_volume=0;
  const parsed=parseRetainedResearch(JSON.stringify(value));
  assert.equal(parsed.sessions[1].observed_volume,0);
  assert.equal(parsed.sessions[0].observed_volume,null);
});
