/* Offline-only client. No fetch, sockets, storage, execution actions or server. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root.document) api.mount(root.document);
})(typeof globalThis === 'object' ? globalThis : this, function (root) {
  'use strict';
  // Evidence receipts are not imported by this standalone viewer.
  // The current display is intentionally limited to NOT_SUPPLIED.
  const LIMIT = 1000000;
  const states = new Set(['FORECAST_ONLY', 'PENDING_TARGET', 'PENDING_PUBLICATION', 'MISSING_OUTCOME', 'RESOLVED']);
  const safety = new Set(['production_approved', 'trading_authority', 'recovery_authorized', 'calibration_established', 'live_feed_freshness_verified', 'history_completeness_verified', 'dataset_authenticated', 'live_capital_allowed', 'automatic_real_money_execution', 'predictive_skill_established', 'coverage_guarantee','independent_samples_established','winner_established']);
  const fail = (reason) => { const error = new Error(reason); error.name = 'AtlasEvidenceRefusal'; throw error; };
  const count = (n, max = 10000) => Number.isSafeInteger(n) && n >= 0 && n <= max;
  function parse(text) {
    if (typeof text !== 'string' || new TextEncoder().encode(text).length > LIMIT) fail('Report exceeds the local-file limit.');
    const value = JSON.parse(text, (key, item) => {
      if (['__proto__', 'constructor', 'prototype'].includes(key)) fail('Unsafe object key refused.');
      return item;
    });
    // Native JSON parsing proves syntax; this separate token walk rejects key
    // ambiguity before any consumer trusts the parsed object. Values are inert.
    const keyStack = [];
    const tokens = text.match(/"(?:\\.|[^"\\])*"|[{}\[\]:,]|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g) || [];
    for (const token of tokens) {
      if (token === '{') keyStack.push({object:true,keys:new Set(),key:true});
      else if (token === '[') keyStack.push({object:false});
      else if (token === '}' || token === ']') keyStack.pop();
      else {
        const top = keyStack.at(-1);
        if (top?.object && token === ',') top.key = true;
        else if (top?.object && top.key && token.startsWith('"')) {
          const key = JSON.parse(token);
          if (top.keys.has(key)) fail('Duplicate JSON object key');
          top.keys.add(key); top.key = false;
        }
      }
    }
    const stack = [[value, 0]];
    while (stack.length) {
      const [item, depth] = stack.pop();
      if (depth > 20) fail('Report nesting exceeds the limit.');
      if (typeof item === 'number' && !Number.isFinite(item)) fail('Nonfinite evidence refused.');
      if (Array.isArray(item) && item.length > 2048) fail('Report array exceeds the limit.');
      if (item && typeof item === 'object') {
        for (const [key, child] of Object.entries(item)) {
          if (safety.has(key) && child !== false) fail('Authority or acceptance claims are not supported.');
          stack.push([child, depth + 1]);
        }
      }
    }
    return value;
  }
  function instant(value) {
    if (typeof value !== 'string') fail('Explicit evidence time required.');
    const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|([+-])(\d{2}):(\d{2}))$/.exec(value);
    if (!m) fail('Timezone-aware evidence time required.');
    const [year, month, day, hour, minute, second] = m.slice(1, 7).map(Number);
    if (year < 1900 || year > 2200 || month < 1 || month > 12 || day < 1 || day > new Date(Date.UTC(year, month, 0)).getUTCDate() || hour > 23 || minute > 59 || second > 59 || Number(m[10] || 0) > 23 || Number(m[11] || 0) > 59) fail('Invalid evidence time.');
    const offset = (Number(m[10] || 0) * 60 + Number(m[11] || 0)) * (m[9] === '-' ? -1 : 1);
    return BigInt(Date.UTC(year, month - 1, day, hour, minute, second) - offset * 60000) * 1000n + BigInt((m[7] || '').padEnd(6, '0') || '0');
  }
  function diagnosticCohort(row, bindProvenance = true) {
    if (!row || !states.has(row.status) || !['US_EQUITY','ETF','CRYPTO'].includes(row.asset_class) || typeof row.asset_id!=='string' || !row.asset_id.startsWith(row.asset_class+':') || typeof row.model!=='string' || !/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(row.model) || !['1D','5D'].includes(row.horizon) || ![row.reference,row.forecast_point].every(v=>Number.isFinite(v)&&v>0) || (row.status==='RESOLVED' ? !(Number.isFinite(row.actual)&&row.actual>0) : row.actual!==null)) fail('Exact diagnostic identity/outcome evidence required.');
      if (('model_version' in row)!==('lookback' in row) || ('model_version' in row && (typeof row.model_version!=='string' || !/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(row.model_version) || !Number.isSafeInteger(row.lookback) || row.lookback<2 || row.lookback>10000))) fail('Incomplete or invalid model configuration binding.');
      const cohort = {asset_class:row.asset_class,asset_id:row.asset_id,horizon:row.horizon,model:row.model,...('model_version' in row ? {model_version:row.model_version,lookback:row.lookback}:{})};
      if('model_configuration_sha256' in row){if(typeof row.model_configuration_sha256!=='string'||!/^[0-9a-f]{64}$/.test(row.model_configuration_sha256))fail('Invalid model configuration commitment.');cohort.model_configuration_sha256=row.model_configuration_sha256;}
      if (bindProvenance) {
        if (['release_source_sha256','forecast_code_sha256','forecast_dataset_manifest_sha256','forecast_dataset_id','forecast_dataset_version'].some(k=>k in row) && !('forecast_dataset_sha256' in row)) fail('Incomplete diagnostic dataset/source binding.');
        for (const name of ['forecast_dataset_sha256','release_source_sha256','forecast_dataset_manifest_sha256','forecast_code_sha256']) {
          if (!(name in row)) continue;
          if (!(name === 'release_source_sha256' && row[name] === null) && (typeof row[name] !== 'string' || !/^[0-9a-f]{64}$/.test(row[name]))) fail('Invalid diagnostic dataset/source commitment.');
          cohort[name] = row[name];
        }
      }
      const manifestFields=['forecast_dataset_manifest_sha256','forecast_dataset_id','forecast_dataset_version'];
      if(bindProvenance && manifestFields.some(k=>k in row)){
        if(!manifestFields.every(k=>k in row))fail('Incomplete diagnostic manifest/version binding.');
        for(const k of ['forecast_dataset_id','forecast_dataset_version']){
          if(typeof row[k]!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(row[k]))fail('Invalid diagnostic dataset/version.');
          cohort[k]=row[k];
        }
      }
      return cohort;
  }
  function directionalDiagnostics(rows, bindProvenance = true) {
    if (!Array.isArray(rows) || rows.length>64) fail('Bounded diagnostic rows required.');
    const groups=new Map(), directions=['DOWN','FLAT','UP'];
    const direction=(v,r)=>v>r?'UP':v<r?'DOWN':'FLAT';
    for(const row of rows) {
      const cohort=diagnosticCohort(row,bindProvenance),key=JSON.stringify(cohort);
      if(!groups.has(key))groups.set(key,{cohort,resolved_n:0,pending_n:0,matrix:Object.fromEntries(directions.map(d=>[d,Object.fromEntries(directions.map(a=>[a,0]))]))});
      const g=groups.get(key);
      if(row.status!=='RESOLVED'){g.pending_n++;continue;}
      g.resolved_n++;g.matrix[direction(row.forecast_point,row.reference)][direction(row.actual,row.reference)]++;
    }
    const cohorts=[...groups.values()].map(g=>{
      const n=g.resolved_n,m=g.matrix,correct=directions.reduce((sum,d)=>sum+m[d][d],0);
      const result={...g,correct_n:correct,directional_accuracy:n?correct/n:null,status:n?'DIAGNOSTIC_ONLY':'INSUFFICIENT_EVIDENCE'};
      for(const side of ['UP','DOWN']){
        const predicted=directions.reduce((sum,a)=>sum+m[side][a],0),actual=directions.reduce((sum,p)=>sum+m[p][side],0),truePositive=m[side][side];
        result[side.toLowerCase()]={true_positive_n:truePositive,false_positive_n:predicted-truePositive,false_negative_n:actual-truePositive,predicted_n:predicted,actual_n:actual,precision:predicted?truePositive/predicted:null,recall:actual?truePositive/actual:null};
      }
      return result;
    });
    return {matrix_rows:'FORECAST_DIRECTION',matrix_columns:'OBSERVED_DIRECTION',flat_is_separate:true,pending_excluded_from_accuracy:true,trade_opportunity_or_profitability_established:false,cohorts};
  }
  function signedErrorDiagnostics(rows) {
    const checked=directionalDiagnostics(rows),canonical=c=>JSON.stringify(c);
    const groups=new Map(checked.cohorts.map(c=>[canonical(c.cohort),{cohort:c.cohort,resolved_n:c.resolved_n,pending_n:c.pending_n,over_n:0,under_n:0,equal_n:0,errors:[]}]));
    for(const row of rows){
      if(row.status!=='RESOLVED')continue;
      const error=row.forecast_point-row.actual,g=groups.get(canonical(diagnosticCohort(row)));
      g.over_n+=Number(error>0);g.under_n+=Number(error<0);g.equal_n+=Number(error===0);g.errors.push(error);
    }
    const cohorts=[...groups.values()].map(g=>{
      const {errors,...rest}=g;let mean=null,status='NO_RESOLVED_OUTCOMES';
      if(errors.length){const total=compensatedSum(errors);mean=total/errors.length;status=Number.isFinite(mean)&&!(total!==0&&mean===0)?'DESCRIPTIVE_ONLY':'UNAVAILABLE_NUMERIC_RANGE';if(status==='UNAVAILABLE_NUMERIC_RANGE')mean=null;}
      return {...rest,mean_signed_error:mean,status};
    });
    return {definition:'FORECAST_MINUS_ACTUAL',pending_excluded_from_mean:true,predictive_skill_established:false,independent_samples_established:false,cohorts};
  }
  function intervalTargetSupport(rows) {
    const cohorts=intervalDiagnostics(rows).cohorts.map(c=>({...c,distinct_recorded_target_n:0,missing_target_n:0,repeated_target_n:0,target_support_status:'NO_RESOLVED_TARGETS'}));
    const groups=new Map(cohorts.map(c=>[JSON.stringify(c.cohort),{cohort:c,targets:new Set()}]));
    for(const row of rows){
      if(row.status!=='RESOLVED'||!row.interval)continue;
      const key=JSON.stringify({...diagnosticCohort(row,true),level:row.interval.level}),g=groups.get(key);
      try{g.targets.add(instant(row.target_at));}catch{g.cohort.missing_target_n++;}
    }
    for(const {cohort:c,targets} of groups.values()){
      c.distinct_recorded_target_n=targets.size;c.repeated_target_n=c.resolved_n-c.missing_target_n-targets.size;
      c.target_support_status=!c.resolved_n?'NO_RESOLVED_TARGETS':c.missing_target_n?'UNRECORDED_TARGET_EVIDENCE':c.repeated_target_n?'REPEATED_TARGET_EVIDENCE':'RECORDED_TARGETS_ONLY';
    }
    return {cohorts,independent_samples_established:false,calibration_established:false};
  }
  function intervalDiagnostics(rows, bindProvenance = true) {
    if (!Array.isArray(rows) || rows.length>64) fail('Bounded diagnostic rows required.');
    const groups = new Map(); let without = 0;
    for (const row of rows) {
      const originalCohort=diagnosticCohort(row,bindProvenance);
      const i = row.interval;
      if (i === null || i === undefined) { without++; continue; }
      if (typeof i !== 'object' || Object.keys(i).sort().join(',') !== 'level,lower,upper' || ![i.lower,i.upper,i.level].every(Number.isFinite) || i.lower < 0 || i.lower > row.forecast_point || row.forecast_point > i.upper || i.level <= 0 || i.level >= 1) fail('Incomplete or invalid original interval.');
      const cohort={...originalCohort,level:i.level};
      const key = JSON.stringify(cohort);
      if (!groups.has(key)) groups.set(key,{cohort,forecast_n:0,pending_n:0,covered_n:0,below_n:0,above_n:0,resolved_n:0,widths:[],scores:[]});
      const g = groups.get(key); g.forecast_n++;
      if (row.status !== 'RESOLVED') { g.pending_n++; continue; }
      const width = i.upper-i.lower, score = width+2*(Math.max(i.lower-row.actual,0)+Math.max(row.actual-i.upper,0))/(1-i.level);
      if (![width,score].every(Number.isFinite)) fail('Interval score exceeds finite range.');
      g.resolved_n++; g.covered_n += row.actual>=i.lower && row.actual<=i.upper ? 1:0;
      g.below_n += row.actual<i.lower ? 1:0; g.above_n += row.actual>i.upper ? 1:0;
      g.widths.push(width);g.scores.push(score);
    }
    const mean = values => { if (!values.length) return null; const sum=values.reduce((total,v)=>total+v,0); if (!Number.isFinite(sum)) fail('Interval aggregate exceeds finite range.'); return sum/values.length; };
    const cohorts = [...groups.values()].map(g=>{
      const {widths,scores,...rest}=g;
      return {...rest,coverage:g.resolved_n ? g.covered_n/g.resolved_n:null,mean_width:mean(widths),mean_interval_score:mean(scores),status:g.resolved_n>=20 ? 'DIAGNOSTIC_ONLY':'INSUFFICIENT_EVIDENCE'};
    });
    return {minimum_samples:20,without_interval_n:without,pending_excluded_from_scores:true,boundary_policy:'INCLUSIVE',calibration_established:false,coverage_guarantee:false,cohorts};
  }
  const scoreFields=['asset_id','asset_class','horizon','model_id','model_version','dataset_id','dataset_sha256','code_sha256','evidence_class','interval_level','dataset_manifest_sha256','dataset_version'];
  function probabilityReliability(probability,minimumSamples=20){
    if(!Array.isArray(probability)||probability.length>10000||!Number.isSafeInteger(minimumSamples)||minimumSamples<1||minimumSamples>10000)fail('Bounded probability cohort and sample minimum required.');
    for(const pair of probability)if(!Array.isArray(pair)||pair.length!==2||typeof pair[0]!=='number'||!Number.isFinite(pair[0])||pair[0]<0||pair[0]>1||!Number.isInteger(pair[1])||![0,1].includes(pair[1]))fail('Recorded probability and binary outcome required.');
    const mean=v=>v.reduce((s,n)=>s+n,0)/v.length,bins=[];
    for(let i=0;i<10;i++){const sample=probability.filter(([p])=>Math.min(Math.floor(p*10),9)===i);if(sample.length)bins.push({bin:i,n:sample.length,mean_probability:mean(sample.map(([p])=>p)),observed_up_fraction:mean(sample.map(([,y])=>y)),status:sample.length>=minimumSamples?'DIAGNOSTIC_ONLY':'INSUFFICIENT_EVIDENCE'});}
    return {probability_n:probability.length,calibration_bins:bins,brier:probability.length?mean(probability.map(([p,y])=>(p-y)**2)):null,uninformative_half_probability_brier:probability.length?.25:null,expected_calibration_error:probability.length?bins.reduce((s,b)=>s+b.n*Math.abs(b.mean_probability-b.observed_up_fraction),0)/probability.length:null};
  }
  function rowMetrics(rows) {
    const pairs=rows.filter(r=>r.status==='RESOLVED'),n=pairs.length;
    if(!n)return {n:0,status:'INSUFFICIENT_EVIDENCE',mae:null,rmse:null,no_change_mae:null,no_change_rmse:null,mape_percent:null,smape_percent:null,mae_ratio_to_no_change:null,directional_accuracy:null,brier:null,flat_outcome_n:0,probability_n:0,expected_calibration_error:null,uninformative_half_probability_brier:null,interval_n:0,interval_coverage:null,mean_interval_width:null,mean_interval_score:null,calibration_bins:[]};
    const mean=values=>{const total=values.reduce((sum,v)=>sum+v,0);if(!Number.isFinite(total))fail('Score arithmetic exceeds finite range.');return total/values.length;};
    const errors=pairs.map(r=>r.forecast_point-r.actual),base=pairs.map(r=>r.actual-r.reference),abs=values=>values.map(Math.abs),square=values=>values.map(v=>v*v);
    const probability=pairs.filter(r=>r.probability_up!==null&&r.probability_up!==undefined),interval=pairs.filter(r=>r.interval!==null&&r.interval!==undefined);
    const reliability=probabilityReliability(probability.map(r=>[r.probability_up,r.actual>r.reference?1:0]));
    const baseline=mean(abs(base)),mae=mean(abs(errors)),sign=v=>v>0?1:v<0?-1:0;
    const result={n,status:n>=20?'DIAGNOSTIC_ONLY':'INSUFFICIENT_EVIDENCE',mae,rmse:Math.sqrt(mean(square(errors))),no_change_mae:baseline,no_change_rmse:Math.sqrt(mean(square(base))),mape_percent:mean(pairs.map(r=>100*Math.abs((r.forecast_point-r.actual)/r.actual))),smape_percent:mean(pairs.map(r=>200*Math.abs(r.forecast_point-r.actual)/(Math.abs(r.forecast_point)+Math.abs(r.actual)))),mae_ratio_to_no_change:baseline?mae/baseline:null,directional_accuracy:mean(pairs.map(r=>sign(r.forecast_point-r.reference)===sign(r.actual-r.reference)?1:0)),flat_outcome_n:pairs.filter(r=>r.actual===r.reference).length,...reliability,interval_n:interval.length,interval_coverage:interval.length?mean(interval.map(r=>r.actual>=r.interval.lower&&r.actual<=r.interval.upper?1:0)):null,mean_interval_width:interval.length?mean(interval.map(r=>r.interval.upper-r.interval.lower)):null,mean_interval_score:interval.length?mean(interval.map(r=>r.interval.upper-r.interval.lower+2*(Math.max(r.interval.lower-r.actual,0)+Math.max(r.actual-r.interval.upper,0))/(1-r.interval.level))):null,calibration_bins:reliability.calibration_bins};
    if(Object.values(result).some(v=>typeof v==='number'&&!Number.isFinite(v)))fail('Score arithmetic exceeds finite range.');
    return result;
  }
  function reconstructScore(rows,asof,contract) {
    const fields=contract==='ROW_BOUND_SCORE_V2'?[...scoreFields,'model_configuration_sha256']:scoreFields;
    const groups=new Map(),cases=new Map(),mapping={model_id:'model',dataset_id:'forecast_dataset_id',dataset_sha256:'forecast_dataset_sha256',code_sha256:'forecast_code_sha256',dataset_manifest_sha256:'forecast_dataset_manifest_sha256',dataset_version:'forecast_dataset_version'};
    for(const row of rows){
      const c=row.score_cohort;
      const required=contract==='ROW_BOUND_SCORE_V2'&& !('model_configuration_sha256' in row)?scoreFields:fields;
      if(contract==='ROW_BOUND_SCORE_V1'&& 'model_configuration_sha256' in row)fail('Configuration-aware score requires V2.');
      if(!c || typeof c!=='object' || Object.keys(c).sort().join(',')!==required.slice().sort().join(',') || !('probability_up' in row)||!('interval' in row))fail('Complete original row score binding required.');
      if(row.probability_up!==null && (!Number.isFinite(row.probability_up)||row.probability_up<0||row.probability_up>1))fail('Invalid original row probability.');
      for(const name of ['model_id','model_version','dataset_id'])if(typeof c[name]!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(c[name]))fail('Invalid score identity.');
      if('model_configuration_sha256' in c && (typeof c.model_configuration_sha256!=='string'||!/^[0-9a-f]{64}$/.test(c.model_configuration_sha256)))fail('Invalid score configuration commitment.');
      for(const name of ['dataset_sha256','code_sha256','dataset_manifest_sha256'])if(!(name==='dataset_manifest_sha256'&&c[name]===null)&&(typeof c[name]!=='string'||!/^[0-9a-f]{64}$/.test(c[name])))fail('Invalid score source commitment.');
      if((c.dataset_manifest_sha256===null)!==(c.dataset_version===null)||(c.dataset_version!==null&&(typeof c.dataset_version!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(c.dataset_version))))fail('Incomplete score manifest/version binding.');
      for(const name of fields){
        const field=mapping[name]||name;
        if(name==='evidence_class'){if(c[name]!=='SYNTHETIC')fail('Invalid score evidence class.');}
        else if(name==='interval_level'){if(c[name]!== (row.interval?row.interval.level:null))fail('Score interval binding contradicts row.');}
        else if(field in row && c[name]!==row[field])fail('Score identity contradicts original row.');
      }
      const key=JSON.stringify(fields.map(k=>c[k])),caseKey=JSON.stringify([JSON.stringify(scoreFields.map(k=>c[k])),String(instant(row.issued_at)),String(instant(row.target_at))]),configuration=c.model_configuration_sha256??null;
      const known=cases.get(caseKey)||new Set();if(known.has(configuration)||(known.size&&(configuration===null||known.has(null))))fail('Repeated or ambiguous configured forecast case.');known.add(configuration);cases.set(caseKey,known);
      if(!groups.has(key))groups.set(key,{cohort:c,rows:[]});groups.get(key).rows.push(row);
    }
    const cohorts=[...groups.values()].map(g=>({cohort:g.cohort,...rowMetrics(g.rows)})),resolved=rows.filter(r=>r.status==='RESOLVED').length;
    return {scope:'OFFLINE_DIAGNOSTIC',asof,issued_n:rows.length,scored_n:resolved,pending_n:rows.length-resolved,cohorts,status:cohorts.some(c=>c.status==='DIAGNOSTIC_ONLY')?'DIAGNOSTIC_ONLY':'INSUFFICIENT_EVIDENCE',binary_event:'PRICE_STRICTLY_ABOVE_REFERENCE; FLAT_IS_NOT_UP',baseline:'PAIRED_NO_PRICE_CHANGE_AND_UNINFORMATIVE_P_UP_0.5',calendar_horizon_semantics:'CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED',dataset_authenticated:false,calibration_established:false,production_approved:false,trading_authority:false};
  }
  function sameDiagnostic(expected, supplied, key = '') {
    if (key==='matrix') return supplied && Object.keys(expected).sort().join(',')===Object.keys(supplied).sort().join(',') && Object.keys(expected).every(p=>supplied[p] && Object.keys(expected[p]).sort().join(',')===Object.keys(supplied[p]).sort().join(',') && Object.keys(expected[p]).every(a=>Number.isSafeInteger(supplied[p][a]) && supplied[p][a]===expected[p][a]));
    if (/_n$/.test(key) || ['n','bin','minimum_samples','lookback','level'].includes(key)) return expected === supplied;
    if (typeof expected === 'number') return Number.isFinite(expected) && typeof supplied === 'number' && Number.isFinite(supplied) && Math.abs(expected-supplied)<=1e-12*Math.max(1,Math.abs(expected));
    if (expected === null || typeof expected !== 'object') return expected === supplied;
    if (!supplied || typeof supplied !== 'object' || Object.keys(expected).sort().join(',')!==Object.keys(supplied).sort().join(',')) return false;
    return Object.keys(expected).every(k=>sameDiagnostic(expected[k],supplied[k],k));
  }
  function validate(report) {
    if (!report || report.schema !== 'AFI_ACCOUNTABILITY_REPORT_V1' || report.evidence_class !== 'SYNTHETIC') fail('Only synthetic Atlas accountability exports are supported.');
    for (const key of ['production_approved', 'trading_authority', 'recovery_authorized', 'calibration_established', 'live_feed_freshness_verified', 'history_completeness_verified']) if (report[key] !== false) fail('Required safety evidence is missing.');
    if (!Array.isArray(report.rows) || !count(report.forecast_n, 64) || report.forecast_n < 1 || report.rows.length !== report.forecast_n) fail('Forecast count does not match the evidence.');
    const asof = instant(report.asof), ids = new Set(), declaredCases = new Set();
    let resolved = 0, corrections = 0;
    for (const row of report.rows) {
      if (!row || !['US_EQUITY', 'ETF', 'CRYPTO'].includes(row.asset_class) || !['1D', '5D'].includes(row.horizon) || !row.asset_id?.startsWith(row.asset_class + ':') || typeof row.asset_id !== 'string' || row.asset_id.length > 128 || typeof row.model !== 'string' || row.model.length > 128 || !states.has(row.status)) fail('Invalid forecast row.');
      if (!/^[0-9a-f]{64}$/.test(row.forecast_sha256) || ids.has(row.forecast_sha256)) fail('Repeated or invalid forecast identity.');
      ids.add(row.forecast_sha256);
      const issued = instant(row.issued_at), target = instant(row.target_at);
      if (issued > asof || target <= issued || !Number.isFinite(row.forecast_point) || row.forecast_point <= 0 || !Number.isFinite(row.reference) || row.reference <= 0) fail('Invalid forecast chronology or price.');
      const inputFields=['input_observed_at','input_available_at','input_source_id','input_source_revision','input_source_sha256'];
      if(inputFields.some(key=>key in row)){
        if(!inputFields.every(key=>key in row)||typeof row.input_source_id!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(row.input_source_id)||
           typeof row.input_source_revision!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(row.input_source_revision)||
           (row.input_source_sha256!==null&&(typeof row.input_source_sha256!=='string'||!/^[0-9a-f]{64}$/.test(row.input_source_sha256))))fail('Incomplete forecast input provenance.');
        const inputObserved=instant(row.input_observed_at),inputAvailable=instant(row.input_available_at);
        if(inputObserved>inputAvailable||inputAvailable>issued)fail('Forecast input was unavailable at issue time.');
      }
      const c=diagnosticCohort(row),caseKey=JSON.stringify([c.asset_class,c.asset_id,c.horizon,c.model,c.model_version||'',c.lookback||0,c.forecast_dataset_sha256||'',c.release_source_sha256||'',c.forecast_dataset_manifest_sha256||'',c.forecast_dataset_id||'',c.forecast_dataset_version||'',c.forecast_code_sha256||'',c.model_configuration_sha256||'',String(issued),String(target),row.interval?.level??null]);
      if(declaredCases.has(caseKey))fail('Repeated declared report forecast case.');declaredCases.add(caseKey);
      if (!count(row.correction_n, 128) || !count(row.history_n, 128) || row.correction_n > row.history_n) fail('Invalid history counts.');
      if ((row.status === 'FORECAST_ONLY') !== (row.history_n === 0) || (row.history_n > 0 && !/^[0-9a-f]{64}$/.test(row.expected_head))) fail('History identity is incomplete.');
      if (row.history_n === 0 && (row.expected_head !== null || row.last_reconciled_asof !== null || row.source_available_at !== null || row.actual !== null)) fail('Forecast-only row contains unsupported outcome evidence.');
      if (row.history_n > 0 && row.last_reconciled_asof === null) fail('History requires a reconciliation cutoff.');
      corrections += row.correction_n;
      if (row.last_reconciled_asof !== null) {
        const cutoff = instant(row.last_reconciled_asof);
        if (cutoff > asof || cutoff < issued) fail('Reconciliation time is inconsistent.');
        if ((row.status === 'PENDING_TARGET') !== (cutoff < target)) fail('Pending target state contradicts reconciliation time.');
        if (row.source_available_at !== null && (instant(row.source_available_at) < target || instant(row.source_available_at) > cutoff)) fail('Outcome publication is inconsistent with its target and cutoff.');
      }
      if (row.actual !== null) {
        if (row.status !== 'RESOLVED' || !Number.isFinite(row.actual) || row.actual <= 0 || target > asof || row.last_reconciled_asof === null || instant(row.source_available_at) > instant(row.last_reconciled_asof)) fail('Resolved outcome is not supported by its timing.');
        resolved++;
      } else if (row.status === 'RESOLVED') fail('Resolved outcome has no observation.');
    }
    const score = report.score;
    if (!score || score.issued_n !== report.forecast_n || score.scored_n !== resolved || score.pending_n !== report.forecast_n - resolved || report.correction_n !== corrections || !Array.isArray(score.cohorts) || score.cohorts.reduce((n, c) => n + (count(c.n) ? c.n : NaN), 0) !== resolved) fail('Outcome/sample counts contradict the rows.');
    if (report.diagnostic_partition !== undefined && report.diagnostic_partition !== 'DATASET_RELEASE_V1') fail('Unknown diagnostic partition contract.');
    intervalDiagnostics(report.rows); // Validate present provenance even for legacy aggregates.
    const intervals = intervalDiagnostics(report.rows, report.diagnostic_partition === 'DATASET_RELEASE_V1');
    if (report.interval_diagnostics !== undefined) {
      const supplied=report.interval_diagnostics;
      if (!supplied || !Array.isArray(supplied.cohorts)) fail('Interval diagnostics are incomplete.');
      const byKey = cohorts => new Map(cohorts.map(c=>[JSON.stringify([c.cohort.asset_class,c.cohort.asset_id,c.cohort.horizon,c.cohort.model,c.cohort.model_version||'',c.cohort.lookback||0,c.cohort.forecast_dataset_sha256||'',c.cohort.release_source_sha256||'',c.cohort.forecast_dataset_manifest_sha256||'',c.cohort.forecast_dataset_id||'',c.cohort.forecast_dataset_version||'',c.cohort.forecast_code_sha256||'',c.cohort.model_configuration_sha256||'',c.cohort.level]),c]));
      const actual=byKey(supplied.cohorts),expected=byKey(intervals.cohorts);
      if (actual.size!==supplied.cohorts.length || actual.size!==expected.size || !sameDiagnostic({...intervals,cohorts:[]},{...supplied,cohorts:[]}) || [...expected].some(([k,v])=>!sameDiagnostic(v,actual.get(k)))) fail('Interval diagnostics contradict the original intervals or outcomes.');
    } else if (intervals.cohorts.length) fail('Interval accountability is missing.');
    const directional=directionalDiagnostics(report.rows,report.diagnostic_partition==='DATASET_RELEASE_V1');
    if(report.directional_diagnostics!==undefined){
      const supplied=report.directional_diagnostics;
      if(!supplied || !Array.isArray(supplied.cohorts))fail('Directional diagnostics are incomplete.');
      const key=c=>JSON.stringify([c.cohort.asset_class,c.cohort.asset_id,c.cohort.horizon,c.cohort.model,c.cohort.model_version||'',c.cohort.lookback||0,c.cohort.forecast_dataset_sha256||'',c.cohort.release_source_sha256||'',c.cohort.forecast_dataset_manifest_sha256||'',c.cohort.forecast_dataset_id||'',c.cohort.forecast_dataset_version||'',c.cohort.forecast_code_sha256||'',c.cohort.model_configuration_sha256||'']);
      const actual=new Map(supplied.cohorts.map(c=>[key(c),c])),expected=new Map(directional.cohorts.map(c=>[key(c),c]));
      if(actual.size!==supplied.cohorts.length || actual.size!==expected.size || !sameDiagnostic({...directional,cohorts:[]},{...supplied,cohorts:[]}) || [...expected].some(([k,v])=>!sameDiagnostic(v,actual.get(k))))fail('Directional diagnostics contradict the original rows.');
    } else if(report.diagnostic_partition==='DATASET_RELEASE_V1')fail('Directional accountability is missing.');
    if(report.score_rows_contract===undefined && report.rows.some(r=>'score_cohort' in r || 'probability_up' in r))fail('Recorded score inputs require their score contract.');
    if(report.score_rows_contract!==undefined){
      if(!['ROW_BOUND_SCORE_V1','ROW_BOUND_SCORE_V2'].includes(report.score_rows_contract))fail('Unknown row score contract.');
      const expected=reconstructScore(report.rows,report.asof,report.score_rows_contract),fields=report.score_rows_contract==='ROW_BOUND_SCORE_V2'?[...scoreFields,'model_configuration_sha256']:scoreFields,key=c=>JSON.stringify(fields.map(k=>c.cohort[k]));
      const actual=new Map(score.cohorts.map(c=>[key(c),c])),wanted=new Map(expected.cohorts.map(c=>[key(c),c]));
      if(actual.size!==score.cohorts.length || actual.size!==wanted.size || !sameDiagnostic({...expected,cohorts:[]},{...score,cohorts:[]}) || [...wanted].some(([k,v])=>!sameDiagnostic(v,actual.get(k))))fail('Score contradicts original row evidence.');
    }
    if('paired_probability_contract' in report || 'paired_probability_diagnostics' in report){
      if(report.paired_probability_contract!=='MATCHED_PROBABILITY_V1'||!sameDiagnostic(pairedProbabilityDiagnostics(report.rows,report.asof),report.paired_probability_diagnostics))fail('Substituted matched probability diagnostics.');
    }
    if('paired_interval_contract' in report || 'paired_interval_diagnostics' in report){
      if(report.paired_interval_contract!=='MATCHED_INTERVAL_V1'||!sameDiagnostic(pairedIntervalDiagnostics(report.rows,report.asof),report.paired_interval_diagnostics))fail('Substituted matched interval diagnostics.');
    }
    if('paired_model_contract' in report || 'paired_model_diagnostics' in report){
      if(report.paired_model_contract!=='MATCHED_CASE_V1'||!sameDiagnostic(pairedDiagnostics(report.rows,report.asof),report.paired_model_diagnostics))fail('Substituted matched-case model diagnostics.');
    }
    return report;
  }
  async function digest(text) {
    if (!root.crypto || !root.crypto.subtle) fail('Cryptographic verification is unavailable in this browser.');
    const raw = await root.crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
    return Array.from(new Uint8Array(raw), b => b.toString(16).padStart(2, '0')).join('');
  }
  async function verifyEnvelope(text, hash = digest) {
    const envelope = parse(text);
    if (['AFI_ASSUMPTION_SCENARIOS_V1','AFI_ASSUMPTION_SCENARIO_REQUEST_V1'].includes(envelope?.schema)) fail('Declared scenario plans and illustrations cannot be scored as forecasts. Open the separately generated scenario HTML. Scenario validity and source authenticity are not established. Previous forecast evidence cleared.');
    if (!envelope || Object.keys(envelope).sort().join(',') !== 'payload_sha256,report_json,schema' || envelope.schema !== 'AFI_BROWSER_REPORT_V1' || typeof envelope.report_json !== 'string' || !/^[0-9a-f]{64}$/.test(envelope.payload_sha256)) fail('Load the browser export produced by the offline bundle CLI.');
    if (await hash(envelope.report_json) !== envelope.payload_sha256) fail('Report byte digest does not match.');
    return validate(parse(envelope.report_json));
  }
  function vintageScoreImpact(a,b,eligible,reason) {
    const interval={state:reason,level:null,left_covered:null,right_covered:null,left_score:null,right_score:null,right_minus_left_score:null};
    const probability={state:reason,probability_up:null,left_actual_up:null,right_actual_up:null,left_brier:null,right_brier:null,right_minus_left_brier:null,left_log_loss_state:reason,right_log_loss_state:reason,left_log_loss:null,right_log_loss:null,log_loss_difference_state:reason,right_minus_left_log_loss:null};
    if(!eligible)return {interval,probability};
    if(!Object.hasOwn(a,'interval'))interval.state='UNRECORDED_INTERVAL';
    else if(a.interval===null)interval.state='NO_INTERVAL';
    else{
      const x=intervalDiagnostics([a]).cohorts[0],y=intervalDiagnostics([b]).cohorts[0],i=a.interval;
      const outsideOpposite=(a.actual<i.lower&&b.actual>i.upper)||(b.actual<i.lower&&a.actual>i.upper);
      let delta=a.actual<i.lower&&b.actual<i.lower ? 2*(a.actual-b.actual)/(1-i.level) : a.actual>i.upper&&b.actual>i.upper ? 2*(b.actual-a.actual)/(1-i.level) :
        2*((Math.max(i.lower-b.actual,0)+Math.max(b.actual-i.upper,0))-(Math.max(i.lower-a.actual,0)+Math.max(a.actual-i.upper,0)))/(1-i.level);
      const unavailable=!Number.isFinite(delta)||(outsideOpposite&&Math.abs(delta)<=32*Number.EPSILON*Math.max(x.mean_interval_score,y.mean_interval_score));
      if(unavailable)delta=null;
      Object.assign(interval,{state:unavailable?'UNAVAILABLE_NUMERIC_RANGE':'FINITE',level:i.level,left_covered:x.covered_n===1,right_covered:y.covered_n===1,left_score:x.mean_interval_score,right_score:y.mean_interval_score,right_minus_left_score:delta});
    }
    if(!Object.hasOwn(a,'probability_up'))probability.state='UNRECORDED_PROBABILITY';
    else if(a.probability_up===null)probability.state='NO_PROBABILITY';
    else{
      const x=logLossDiagnostics([a]).cohorts[0].cases[0],y=logLossDiagnostics([b]).cohorts[0].cases[0],p=a.probability_up;
      const left=(p-Number(x.actual_up))**2,right=(p-Number(y.actual_up))**2;
      const underflow=(left===0&&p!==Number(x.actual_up))||(right===0&&p!==Number(y.actual_up));
      const brierDelta=x.actual_up===y.actual_up?0:y.actual_up?1-2*p:2*p-1;
      let state,delta=null;
      if(x.loss_state==='INFINITE'&&y.loss_state==='INFINITE')state='UNDEFINED_BOTH_INFINITE';
      else if(y.loss_state==='INFINITE')state='POSITIVE_INFINITY';
      else if(x.loss_state==='INFINITE')state='NEGATIVE_INFINITY';
      else{
        delta=y.log_loss-x.log_loss;
        state=x.actual_up!==y.actual_up&&p!==0.5&&Math.abs(delta)<=32*Number.EPSILON*Math.max(x.log_loss,y.log_loss)?'UNAVAILABLE_NUMERIC_RANGE':'FINITE';
        if(state!=='FINITE')delta=null;
      }
      Object.assign(probability,{state:underflow?'UNAVAILABLE_NUMERIC_RANGE':'RECORDED',probability_up:p,left_actual_up:x.actual_up,right_actual_up:y.actual_up,
        left_brier:underflow?null:left,right_brier:underflow?null:right,right_minus_left_brier:underflow?null:brierDelta,
        left_log_loss_state:x.loss_state,right_log_loss_state:y.loss_state,left_log_loss:x.log_loss,right_log_loss:y.log_loss,
        log_loss_difference_state:state,right_minus_left_log_loss:delta});
    }
    if(['UNRECORDED_PROBABILITY','NO_PROBABILITY'].includes(probability.state))for(const key of ['left_log_loss_state','right_log_loss_state','log_loss_difference_state'])probability[key]=probability.state;
    return {interval,probability};
  }

  function compareReportVintages(before, after) {
    validate(before); validate(after);
    if (instant(before.asof) > instant(after.asof)) fail('Report vintages must be ordered by evidence cutoff.');
    const mutable = new Set(['actual','status','latest_event','last_reconciled_asof','source_revision','source_available_at','correction_n','history_n','expected_head','outcome_dataset_sha256','reconciliation_freshness']);
    const canonical = value => JSON.stringify(value === null || typeof value !== 'object' ? value : Array.isArray(value) ? value.map(item => JSON.parse(canonical(item))) : Object.fromEntries(Object.keys(value).sort().map(key => [key,JSON.parse(canonical(value[key]))])));
    const identity = row => canonical(Object.fromEntries(Object.entries(row).filter(([key]) => !mutable.has(key))));
    const left = new Map(before.rows.map(row => [row.forecast_sha256,row]));
    const right = new Map(after.rows.map(row => [row.forecast_sha256,row]));
    const hashes = [...new Set([...left.keys(),...right.keys()])].sort();
    const counts = {}, rows = [];
    for (const hash of hashes) {
      const a = left.get(hash), b = right.get(hash), row = b || a;
      let status, metricState = 'NOT_BOTH_RESOLVED', leftError = null, rightError = null, difference = null;
      const bound = a && b && ['forecast_artifact_sha256','forecast_dataset_sha256','forecast_code_sha256'].every(key => typeof a[key] === 'string' && /^[a-f0-9]{64}$/.test(a[key]) && a[key] === b[key]);
      if (!a) status = 'RIGHT_ONLY';
      else if (!b) status = 'LEFT_ONLY';
      else if (identity(a) !== identity(b)) { status = 'FORECAST_IDENTITY_CONFLICT'; metricState = 'REFUSED_IDENTITY'; }
      else if (b.history_n < a.history_n || b.correction_n < a.correction_n ||
          (a.last_reconciled_asof !== null && (b.last_reconciled_asof === null || instant(b.last_reconciled_asof) < instant(a.last_reconciled_asof))) ||
          (a.status === 'RESOLVED' && b.status !== 'RESOLVED') ||
          (a.source_available_at !== null && (b.source_available_at === null || instant(b.source_available_at) < instant(a.source_available_at)))) {
        status = 'REPORTED_EVIDENCE_REGRESSION'; metricState = 'REFUSED_HISTORY';
      } else if ((a.history_n === b.history_n && canonical(Object.fromEntries([...mutable].filter(key => key !== 'reconciliation_freshness').map(key => [key,a[key] ?? null]))) !== canonical(Object.fromEntries([...mutable].filter(key => key !== 'reconciliation_freshness').map(key => [key,b[key] ?? null])))) ||
          (a.history_n !== b.history_n && a.expected_head === b.expected_head)) {
        status = 'REPORTED_HISTORY_CONFLICT'; metricState = 'REFUSED_HISTORY';
      } else {
        status = a.status !== 'RESOLVED' ? (b.status === 'RESOLVED' ? 'RESOLUTION_REPORTED' : a.status === b.status ? 'PENDING_UNCHANGED' : 'PENDING_STATE_CHANGED') :
          a.actual !== b.actual ? 'OUTCOME_VALUE_CHANGED' : a.source_revision !== b.source_revision || a.outcome_dataset_sha256 !== b.outcome_dataset_sha256 || a.source_available_at !== b.source_available_at ? 'OUTCOME_PROVENANCE_CHANGED' : 'OUTCOME_UNCHANGED';
        if (a.status === 'RESOLVED' && b.status === 'RESOLVED') {
          metricState = bound ? 'FINITE' : 'INSUFFICIENT_ORIGINAL_BINDING';
          if (bound) {
            leftError = Math.abs(a.forecast_point-a.actual); rightError = Math.abs(b.forecast_point-b.actual);
            // Same-side algebra avoids subtracting two rounded large errors.
            const point=a.forecast_point;
            difference = a.actual<=point&&b.actual<=point ? a.actual-b.actual : a.actual>=point&&b.actual>=point ? b.actual-a.actual : rightError-leftError;
            if (a.actual!==b.actual && ((a.actual<point&&b.actual>point)||(b.actual<point&&a.actual>point)) && Math.abs(difference)<=32*Number.EPSILON*Math.max(leftError,rightError)) metricState='UNAVAILABLE_NUMERIC_RANGE';
            if (metricState==='UNAVAILABLE_NUMERIC_RANGE' || ![leftError,rightError,difference].every(Number.isFinite)) { metricState = 'UNAVAILABLE_NUMERIC_RANGE'; leftError = null; rightError = null; difference = null; }
          }
        }
      }
      counts[status] = (counts[status] || 0) + 1;
      rows.push({forecast_sha256:hash,asset_id:row.asset_id,model:row.model,horizon:row.horizon,status,
        left_status:a?.status??null,right_status:b?.status??null,left_actual:a?.actual??null,right_actual:b?.actual??null,
        left_correction_n:a?.correction_n??null,right_correction_n:b?.correction_n??null,
        left_head:a?.expected_head??null,right_head:b?.expected_head??null,
        left_source_revision:a?.source_revision??null,right_source_revision:b?.source_revision??null,
        left_outcome_dataset_sha256:a?.outcome_dataset_sha256??null,right_outcome_dataset_sha256:b?.outcome_dataset_sha256??null,
        left_source_available_at:a?.source_available_at??null,right_source_available_at:b?.source_available_at??null,
        outcome_provenance_changed:a&&b ? canonical([a.source_revision??null,a.outcome_dataset_sha256??null,a.source_available_at??null])!==canonical([b.source_revision??null,b.outcome_dataset_sha256??null,b.source_available_at??null]):null,metric_state:metricState,
        left_absolute_error:leftError,right_absolute_error:rightError,right_minus_left_absolute_error:difference,
        score_impact:vintageScoreImpact(a,b,bound&&status.startsWith('OUTCOME_'),metricState)});
    }
    return {schema:'AFI_REPORT_VINTAGE_COMPARISON_V1',left_asof:before.asof,right_asof:after.asof,left_forecast_n:before.rows.length,right_forecast_n:after.rows.length,
      union_forecast_n:hashes.length,matched_forecast_n:hashes.filter(hash => left.has(hash)&&right.has(hash)).length,status_counts:counts,rows,
      history_ancestry_verified:false,source_authenticated:false,predictive_skill_established:false,production_approved:false,trading_authority:false,recovery_authorized:false};
  }

  // Derived presentation only: keep the immutable comparison packet model unchanged.
  function signedErrorVintageImpact(before, after) {
    const comparison=compareReportVintages(before,after);
    const left=new Map(before.rows.map(row=>[row.forecast_sha256,row]));
    const right=new Map(after.rows.map(row=>[row.forecast_sha256,row]));
    return {definition:'FORECAST_MINUS_ACTUAL',history_ancestry_verified:false,
      predictive_skill_established:false,production_approved:false,trading_authority:false,recovery_authorized:false,rows:comparison.rows.map(row=>{
        let state=row.metric_state,leftError=null,rightError=null,difference=null;
        if(row.status.startsWith('OUTCOME_') && ['FINITE','UNAVAILABLE_NUMERIC_RANGE'].includes(state)) {
          const a=left.get(row.forecast_sha256),b=right.get(row.forecast_sha256);
          leftError=a.forecast_point-a.actual;rightError=b.forecast_point-b.actual;
          // The original point is fixed. Preserve small label changes even when
          // subtracting the rounded signed errors would misleadingly yield zero.
          difference=a.actual-b.actual;
          state=[leftError,rightError,difference].every(Number.isFinite)?'FINITE':'UNAVAILABLE_NUMERIC_RANGE';
          if(state!=='FINITE')leftError=rightError=difference=null;
        }
        return {asset_id:row.asset_id,model:row.model,horizon:row.horizon,
          forecast_sha256:row.forecast_sha256,status:row.status,state,
          left_signed_error:leftError,right_signed_error:rightError,
          right_minus_left_signed_error:difference};
      })};
  }

  const PACKET_LIMIT=2000000,PACKET_SCOPE='SUPPLIED_SOURCE_BYTES_NOT_EXECUTED_MEMORY_ATTESTATION';
  function comparisonSourcePins(pins){
    const fields=['comparator_source_sha256','exporter_source_sha256','artifact_io_source_sha256'];
    if(!pins||typeof pins!=='object'||Array.isArray(pins)||Object.keys(pins).sort().join('|')!==fields.slice().sort().join('|')||fields.some(key=>typeof pins[key]!=='string'||!/^[0-9a-f]{64}$/.test(pins[key])))fail('Explicit trusted-build source pins required.');
    return Object.freeze(Object.fromEntries(fields.map(key=>[key,pins[key]])));
  }
  async function packetSourceReport(text,hash){
    const value=parse(text);
    return ['AFI_LOG_LOSS_BROWSER_V1','AFI_LOG_LOSS_BROWSER_V2'].includes(value?.schema)?(await verifyLogLossEnvelope(text,hash)).source_report:verifyEnvelope(text,hash);
  }
  async function createComparisonPacket(leftBrowser,rightBrowser,pins,hash=digest){
    const trusted=comparisonSourcePins(pins),left=await packetSourceReport(leftBrowser,hash),right=await packetSourceReport(rightBrowser,hash);
    const comparisonText=JSON.stringify(compareReportVintages(left,right));
    const packet={schema:'AFI_REPORT_VINTAGE_PACKET_V1',left_browser_json:leftBrowser,left_sha256:await hash(leftBrowser),right_browser_json:rightBrowser,right_sha256:await hash(rightBrowser),
      ...trusted,source_binding_scope:PACKET_SCOPE,comparison_json:comparisonText,comparison_sha256:await hash(comparisonText),
      source_authenticated:false,history_ancestry_verified:false,runtime_provenance_verified:false,production_approved:false,trading_authority:false,recovery_authorized:false};
    const text=JSON.stringify(packet)+'\n';if(new TextEncoder().encode(text).length>PACKET_LIMIT)fail('Bounded comparison packet required.');return text;
  }
  async function verifyComparisonPacket(text,pins,hash=digest){
    const trusted=comparisonSourcePins(pins);
    if(typeof text!=='string'||new TextEncoder().encode(text).length>PACKET_LIMIT)fail('Bounded comparison packet required.');
    let packet;try{packet=JSON.parse(text);}catch{fail('Invalid comparison packet.');}
    const expected=['schema','left_browser_json','left_sha256','right_browser_json','right_sha256',...Object.keys(trusted),'source_binding_scope','comparison_json','comparison_sha256','source_authenticated','history_ancestry_verified','runtime_provenance_verified','production_approved','trading_authority','recovery_authorized'];
    if(!packet||typeof packet!=='object'||Array.isArray(packet)||Object.keys(packet).sort().join('|')!==expected.sort().join('|')||packet.schema!=='AFI_REPORT_VINTAGE_PACKET_V1'||JSON.stringify(packet)+'\n'!==text)fail('Canonical comparison packet required.');
    for(const field of ['source_authenticated','history_ancestry_verified','runtime_provenance_verified','production_approved','trading_authority','recovery_authorized'])if(packet[field]!==false)fail('Comparison cannot grant authority or authenticity.');
    if(packet.source_binding_scope!==PACKET_SCOPE||Object.keys(trusted).some(key=>packet[key]!==trusted[key]))fail('Matching archived comparator source required.');
    for(const [body,commitment] of [['left_browser_json','left_sha256'],['right_browser_json','right_sha256'],['comparison_json','comparison_sha256']]){
      if(typeof packet[body]!=='string'||new TextEncoder().encode(packet[body]).length>LIMIT||typeof packet[commitment]!=='string'||!/^[a-f0-9]{64}$/.test(packet[commitment])||await hash(packet[body])!==packet[commitment])fail('Comparison evidence digest mismatch.');
    }
    const left=await packetSourceReport(packet.left_browser_json,hash),right=await packetSourceReport(packet.right_browser_json,hash),comparison=compareReportVintages(left,right);
    if(JSON.stringify(comparison)!==packet.comparison_json)fail('Comparison differs from supplied report reproduction.');
    return {comparison,source_binding_scope:PACKET_SCOPE,source_authenticated:false,history_ancestry_verified:false,runtime_provenance_verified:false,production_approved:false};
  }

  function selectRows(report, query = '', state = 'ALL', sort = 'target-asc', horizon = 'ALL') {
    if (!['ALL','1D','5D'].includes(horizon) || !['ALL', ...states].includes(state) || !['target-asc', 'target-desc', 'asset'].includes(sort)) fail('Unsupported filter/sort choice.');
    const q = String(query).slice(0, 80).toLowerCase();
    return report.rows.filter(r => r.asset_id.toLowerCase().includes(q) && (horizon === 'ALL' || r.horizon === horizon) && (state === 'ALL' || r.status === state)).slice().sort((a, b) => {
      const first = sort === 'asset' ? a.asset_id.localeCompare(b.asset_id) : (instant(a.target_at) < instant(b.target_at) ? -1 : instant(a.target_at) > instant(b.target_at) ? 1 : 0) * (sort === 'target-desc' ? -1 : 1);
      return first || a.forecast_sha256.localeCompare(b.forecast_sha256);
    });
  }
  function createLoader(onState, hash = digest, verify = verifyEnvelope) {
    let revision = 0;
    async function perform(read) {
      const current = ++revision;
      onState({ status: 'VERIFYING', report: null, message: 'Verifying local report bytes…' });
      try {
        const report = await verify(await read(), hash);
        if (current === revision) onState({ status: 'VERIFIED', report, message: ['ROW_BOUND_SCORE_V1','ROW_BOUND_SCORE_V2'].includes(report.score_rows_contract) ? 'Recorded score inputs reconciled. Byte consistency only; source truth and market skill are not established.' : 'Legacy report loaded. Some original score inputs were not recorded; source truth and market skill are not established.' });
      } catch (error) {
        if (current === revision) onState({ status: 'REFUSED', report: null, message: error.name === 'AtlasEvidenceRefusal' ? error.message : 'Report format or local-file verification failed.' });
      }
    }
    return {
      load: text => perform(async () => text),
      loadFile: file => perform(async () => {
        if (!file || !count(file.size, LIMIT) || typeof file.text !== 'function') fail('Choose a JSON file within the size limit.');
        return file.text();
      }),
      clear() { revision++; onState({ status: 'EMPTY', report: null, message: 'No report loaded. Local files only; no live connection.' }); },
    };
  }
  function visibleErrors(report, query='', state='ALL', sort='target-asc', horizon='ALL') {
    validate(report);
    const rows=selectRows(report,query,state,sort,horizon),groups=new Map();
    if(!rows.length)return {status:'NO_VISIBLE_CASES',visible_n:0,cohorts:[],message:'No visible forecasts. No error or probability score is inferred.'};
    const bound=['ROW_BOUND_SCORE_V1','ROW_BOUND_SCORE_V2'].includes(report.score_rows_contract);
    for(const row of rows){
      const c=diagnosticCohort(row),identity=bound?row.score_cohort:null;
      const key=JSON.stringify([identity?scoreFields.map(k=>identity[k]):null,identity?.model_configuration_sha256??null,c]);
      if(!groups.has(key))groups.set(key,{cohort:c,rows:[]});groups.get(key).rows.push(row);
    }
    const cohorts=[...groups.entries()].sort(([a],[b])=>a<b?-1:a>b?1:0).map(([,g])=>{
      const resolved=g.rows.filter(r=>r.status==='RESOLVED');let metrics,numericUnavailable=false;
      try{metrics=rowMetrics(g.rows);}catch(error){
        if(error.name!=='AtlasEvidenceRefusal')throw error;
        numericUnavailable=true;metrics={n:resolved.length,status:'UNAVAILABLE_NUMERIC_RANGE',mae:null,rmse:null,no_change_mae:null,mae_ratio_to_no_change:null,brier:null,expected_calibration_error:null,probability_n:null,interval_n:null,interval_coverage:null,mean_interval_width:null,mean_interval_score:null};
      }
      const missingProbability=resolved.filter(r=>!('probability_up' in r)).length,missingInterval=resolved.filter(r=>!('interval' in r)).length;
      const recordedProbability=resolved.filter(r=>r.probability_up!==null&&r.probability_up!==undefined).length;
      if(missingProbability){for(const k of ['probability_n','brier','expected_calibration_error','uninformative_half_probability_brier','calibration_bins'])metrics[k]=null;}
      if(missingInterval){for(const k of ['interval_n','interval_coverage','mean_interval_width','mean_interval_score'])metrics[k]=null;}
      return {...metrics,cohort:g.cohort,issued_n:g.rows.length,pending_n:g.rows.length-resolved.length,recorded_probability_n:recordedProbability,missing_probability_n:missingProbability,missing_interval_n:missingInterval,input_status:bound?'ROW_BOUND_INPUTS':'PARTIAL_LEGACY_INPUTS',numeric_unavailable:numericUnavailable};
    });
    return {status:cohorts.some(c=>c.numeric_unavailable)?'PARTIAL_NUMERIC_EVIDENCE':bound?'DIAGNOSTIC_ONLY':'PARTIAL_LEGACY_INPUTS',visible_n:rows.length,cohorts,message:cohorts.some(c=>c.numeric_unavailable)?'Some errors exceed the supported numeric range. Unavailable values are not zero.':bound?'Errors recalculated from visible original rows. Small or overlapping samples do not establish skill.':'Legacy price errors use recorded values only. Missing probability and interval inputs remain unavailable; provenance is not inferred.'};
  }
  function pairedDiagnostics(rows,asof,modelPairs=null,minimumSamples=20) {
    intervalDiagnostics(rows);const cutoff=instant(asof),groups=new Map(),seen=new Set();
    if(!Number.isSafeInteger(minimumSamples)||minimumSamples<2||minimumSamples>10000)fail('Bounded paired sample threshold required.');
    const canonical=c=>JSON.stringify(Object.fromEntries(Object.entries(c).sort(([a],[b])=>a<b?-1:a>b?1:0)));
    const hash=v=>{if(typeof v!=='string'||!/^[0-9a-f]{64}$/.test(v))fail('Exact paired evidence commitment required.');return v;};
    const utc=us=>{const remainder=((us%1000000n)+1000000n)%1000000n;return new Date(Number((us-remainder)/1000n)).toISOString().slice(0,19)+(remainder?'.'+String(remainder).padStart(6,'0'):'')+'+00:00';};
    const sameDefinition=(a,b)=>['model','model_version','lookback','forecast_code_sha256','model_configuration_sha256'].every(k=>(a[k]??null)===(b[k]??null));
    for(const row of rows){
      hash(row.forecast_sha256);if(seen.has(row.forecast_sha256))fail('Repeated paired forecast identity.');seen.add(row.forecast_sha256);
      const issued=instant(row.issued_at),target=instant(row.target_at);if(issued>cutoff||target<=issued)fail('Invalid paired forecast chronology.');
      if(row.outcome_dataset_sha256!==null&&row.outcome_dataset_sha256!==undefined)hash(row.outcome_dataset_sha256);
      if(row.source_revision!==null&&row.source_revision!==undefined&&(typeof row.source_revision!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(row.source_revision)))fail('Invalid paired outcome revision.');
      const reconciled=row.last_reconciled_asof==null?null:instant(row.last_reconciled_asof),available=row.source_available_at==null?null:instant(row.source_available_at);
      if(reconciled!==null&&(reconciled<issued||reconciled>cutoff||(row.status==='PENDING_TARGET')!==(reconciled<target)))fail('Invalid paired reconciliation chronology.');
      if(available!==null&&(available<target||available>cutoff||(reconciled!==null&&available>reconciled)))fail('Invalid paired outcome publication.');
      let binding='UNRECORDED';if('interval' in row){binding='NONE';if(row.interval!==null){const view=new DataView(new ArrayBuffer(8));view.setFloat64(0,row.interval.level,false);binding='FLOAT64:'+Array.from({length:8},(_,i)=>view.getUint8(i).toString(16).padStart(2,'0')).join('');}}
      const cohort={...diagnosticCohort(row),interval_binding:binding},id=canonical(cohort),key=String(issued)+'/'+String(target);
      if(!groups.has(id))groups.set(id,{cohort,cases:new Map(),interval_level:row.interval?.level??null,interval_recorded:'interval' in row});
      const group=groups.get(id);if(group.cases.has(key))fail('Repeated paired model case.');group.cases.set(key,row);
    }
    const ids=[...groups.keys()].sort(),models=ids.map(id=>{const g=groups.get(id),values=[...g.cases.values()];return {id,cohort:g.cohort,interval_level:g.interval_level,interval_recorded:g.interval_recorded,forecast_n:values.length,resolved_n:values.filter(r=>r.status==='RESOLVED').length,pending_n:values.filter(r=>r.status!=='RESOLVED').length};});
    const candidates=[];for(let i=0;i<ids.length;i++)for(const b of ids.slice(i+1)){const a=ids[i],x=groups.get(a).cohort,y=groups.get(b).cohort;if(['asset_class','asset_id','horizon'].every(k=>x[k]===y[k])&&!sameDefinition(x,y))candidates.push([a,b]);}
    const result={schema:'AFI_PAIRED_MODEL_DIAGNOSTICS_V1',asof:utc(cutoff),minimum_samples:minimumSamples,maximum_automatic_pair_n:64,model_n:models.length,possible_pair_n:candidates.length,model_id_scope:'CANONICAL_SUPPLIED_CONTEXT_NOT_AUTHENTICATED',models,comparisons:[],independent_samples_established:false,predictive_skill_established:false,winner_established:false,calibration_established:false,production_approved:false,trading_authority:false};
    let selected;
    if(modelPairs===null){if(candidates.length>64)return {...result,status:'EXPLICIT_PAIR_SELECTION_REQUIRED',selection_mode:'AUTOMATIC'};selected=candidates;}
    else{
      if(!Array.isArray(modelPairs)||modelPairs.length<1||modelPairs.length>64)fail('Bounded explicit model pairs required.');
      const chosen=new Set();selected=[];for(const pair of modelPairs){
        if(!Array.isArray(pair)||pair.length!==2||pair.some(id=>typeof id!=='string'||id.length>4096||!groups.has(id))||pair[0]===pair[1])fail('Known distinct paired model identities required.');
        const key=JSON.stringify(pair.slice().sort());if(chosen.has(key))fail('Repeated comparison pair.');chosen.add(key);selected.push(pair.slice());
      }
    }
    const dataFields=['forecast_dataset_sha256','forecast_dataset_manifest_sha256','forecast_dataset_id','forecast_dataset_version'],modelFields=['model_version','lookback','forecast_code_sha256'];
    for(const [a,b] of selected){
      const left=groups.get(a),right=groups.get(b),ac=left.cohort,bc=right.cohort,am=left.cases,bm=right.cases,shared=[...am.keys()].filter(k=>bm.has(k));
      const pair={a,b,a_forecast_n:am.size,b_forecast_n:bm.size,a_resolved_n:[...am.values()].filter(r=>r.status==='RESOLVED').length,b_resolved_n:[...bm.values()].filter(r=>r.status==='RESOLVED').length,shared_n:shared.length,a_only_n:[...am.keys()].filter(k=>!bm.has(k)).length,b_only_n:[...bm.keys()].filter(k=>!am.has(k)).length,pending_shared_n:0,outcome_conflict_n:0,reference_conflict_n:0,missing_provenance_n:0,unassessed_shared_n:0,paired_n:0,distinct_target_n:0,a_mae:null,b_mae:null,a_rmse:null,b_rmse:null,a_minus_b_mae:null,baseline_mae:null,a_ratio_to_baseline:null,b_ratio_to_baseline:null,a_lower_error_n:0,b_lower_error_n:0,tied_error_n:0,cases:[]};
      let reason=null;if(['asset_class','asset_id','horizon'].some(k=>ac[k]!==bc[k]))reason='INCOMPARABLE_CONTEXT';
      else if([ac,bc].some(c=>dataFields.some(k=>c[k]==null)))reason='MISSING_FORECAST_DATA_BINDING';
      else if(dataFields.some(k=>ac[k]!==bc[k]))reason='INCOMPARABLE_FORECAST_DATA';
      else if([ac,bc].some(c=>modelFields.some(k=>c[k]==null)))reason='MISSING_MODEL_DEFINITION';
      else if(sameDefinition(ac,bc))reason='SAME_POINT_MODEL_DEFINITION';
      else if(modelFields.every(k=>ac[k]===bc[k])&&(ac.model_configuration_sha256==null)!==(bc.model_configuration_sha256==null))reason='AMBIGUOUS_CONFIGURATION_BINDING';
      const ea=[],eb=[],base=[],targets=new Set();
      for(const key of [...new Set([...am.keys(),...bm.keys()])].sort()){
        const x=am.get(key),y=bm.get(key),item={case_id:key,a_forecast_sha256:x?.forecast_sha256??null,b_forecast_sha256:y?.forecast_sha256??null,a_state:x?.status??null,b_state:y?.status??null,a_abs_error:null,b_abs_error:null,error_difference:null};
        if(!x)item.status='B_ONLY';else if(!y)item.status='A_ONLY';else if(reason!==null){item.status='UNASSESSED_CONTEXT';pair.unassessed_shared_n++;}
        else if(x.status!=='RESOLVED'||y.status!=='RESOLVED'){item.status='PENDING_SHARED_OUTCOME';pair.pending_shared_n++;}
        else if(x.reference!==y.reference){item.status='REFERENCE_CONFLICT';pair.reference_conflict_n++;}
        else if([x,y].some(r=>['source_revision','source_available_at','outcome_dataset_sha256','last_reconciled_asof'].some(k=>r[k]==null))){item.status='MISSING_OUTCOME_PROVENANCE';pair.missing_provenance_n++;}
        else if(x.actual!==y.actual||x.source_revision!==y.source_revision||x.outcome_dataset_sha256!==y.outcome_dataset_sha256||instant(x.source_available_at)!==instant(y.source_available_at)){item.status='OUTCOME_CONFLICT';pair.outcome_conflict_n++;}
        else{
          const av=Math.abs(x.forecast_point-x.actual),bv=Math.abs(y.forecast_point-y.actual);ea.push(av);eb.push(bv);base.push(Math.abs(x.reference-x.actual));targets.add(String(instant(x.target_at)));pair.paired_n++;
          pair.a_lower_error_n+=av<bv?1:0;pair.b_lower_error_n+=bv<av?1:0;pair.tied_error_n+=av===bv?1:0;
          Object.assign(item,{status:'PAIRED',a_abs_error:av,b_abs_error:bv,error_difference:av-bv});
        }
        pair.cases.push(item);
      }
      pair.distinct_target_n=targets.size;
      if(ea.length){
        const mean=v=>v.reduce((s,n)=>s+n,0)/v.length,ma=mean(ea),mb=mean(eb),baseline=mean(base);
        const values={a_mae:ma,b_mae:mb,a_rmse:Math.sqrt(mean(ea.map(v=>v*v))),b_rmse:Math.sqrt(mean(eb.map(v=>v*v))),a_minus_b_mae:mean(ea.map((v,i)=>v-eb[i])),baseline_mae:baseline,a_ratio_to_baseline:baseline?ma/baseline:null,b_ratio_to_baseline:baseline?mb/baseline:null};
        if(Object.values(values).some(v=>v!==null&&!Number.isFinite(v)))pair.status='UNAVAILABLE_NUMERIC_RANGE';
        else Object.assign(pair,values,{status:pair.paired_n<minimumSamples?'INSUFFICIENT_EVIDENCE':pair.distinct_target_n<minimumSamples?'OVERLAPPING_TARGET_EVIDENCE':'DIAGNOSTIC_ONLY'});
      }else pair.status=reason||(shared.length?'NO_COMPATIBLE_SHARED_OUTCOMES':'NO_SHARED_CASES');
      result.comparisons.push(pair);
    }
    return {...result,status:selected.length?'COMPARISONS_RECORDED':'NO_ELIGIBLE_MODEL_PAIRS',selection_mode:modelPairs===null?'AUTOMATIC':'EXPLICIT'};
  }
  function pairedIntervalDiagnostics(rows,asof,modelPairs=null,minimumSamples=20) {
    const source=pairedDiagnostics(rows,asof,modelPairs,minimumSamples),byHash=new Map(rows.map(r=>[r.forecast_sha256,r])),comparisons=[];
    for(const point of source.comparisons){
      const pair=Object.fromEntries(['a','b','shared_n','a_only_n','b_only_n','pending_shared_n','outcome_conflict_n','reference_conflict_n','missing_provenance_n','unassessed_shared_n'].map(k=>[k,point[k]]));
      Object.assign(pair,{point_paired_n:point.paired_n,interval_paired_n:0,missing_interval_n:0,level_mismatch_n:0,distinct_target_n:0,a_covered_n:0,b_covered_n:0,a_coverage:null,b_coverage:null,a_mean_width:null,b_mean_width:null,a_mean_interval_score:null,b_mean_interval_score:null,a_minus_b_interval_score:null,nominal_level:null,cases:[]});
      const sa=[],sb=[],wa=[],wb=[],targets=new Set();
      for(const c of point.cases){
        const record={case_id:c.case_id,a_forecast_sha256:c.a_forecast_sha256,b_forecast_sha256:c.b_forecast_sha256,status:c.status,a_interval_score:null,b_interval_score:null,a_covered:null,b_covered:null};
        if(c.status==='PAIRED'){
          const x=byHash.get(c.a_forecast_sha256),y=byHash.get(c.b_forecast_sha256),a=x.interval,b=y.interval;
          if(!a||!b){record.status='MISSING_INTERVAL';pair.missing_interval_n++;}
          else if(a.level!==b.level){record.status='NOMINAL_LEVEL_MISMATCH';pair.level_mismatch_n++;}
          else{
            const actual=x.actual,w1=a.upper-a.lower,w2=b.upper-b.lower,s1=w1+2*(Math.max(a.lower-actual,0)+Math.max(actual-a.upper,0))/(1-a.level),s2=w2+2*(Math.max(b.lower-actual,0)+Math.max(actual-b.upper,0))/(1-b.level),ca=a.lower<=actual&&actual<=a.upper,cb=b.lower<=actual&&actual<=b.upper;
            pair.interval_paired_n++;pair.a_covered_n+=Number(ca);pair.b_covered_n+=Number(cb);pair.nominal_level=a.level;
            sa.push(s1);sb.push(s2);wa.push(w1);wb.push(w2);targets.add(String(instant(x.target_at)));
            Object.assign(record,{status:'INTERVAL_PAIRED',a_interval_score:s1,b_interval_score:s2,a_covered:ca,b_covered:cb});
          }
        }
        pair.cases.push(record);
      }
      const n=pair.interval_paired_n;pair.distinct_target_n=targets.size;
      if(n){
        const mean=v=>v.reduce((s,n)=>s+n,0)/v.length,values={a_coverage:pair.a_covered_n/n,b_coverage:pair.b_covered_n/n,a_mean_width:mean(wa),b_mean_width:mean(wb),a_mean_interval_score:mean(sa),b_mean_interval_score:mean(sb),a_minus_b_interval_score:mean(sa.map((v,i)=>v-sb[i]))};
        if(Object.values(values).some(v=>!Number.isFinite(v)))pair.status='UNAVAILABLE_NUMERIC_RANGE';
        else Object.assign(pair,values,{status:n<minimumSamples?'INSUFFICIENT_EVIDENCE':targets.size<minimumSamples?'OVERLAPPING_TARGET_EVIDENCE':'DIAGNOSTIC_ONLY'});
      }else pair.status='NO_COMPATIBLE_SHARED_INTERVALS';
      comparisons.push(pair);
    }
    return {schema:'AFI_PAIRED_INTERVAL_DIAGNOSTICS_V1',asof:source.asof,minimum_samples:minimumSamples,status:source.status,selection_mode:source.selection_mode,model_n:source.model_n,possible_pair_n:source.possible_pair_n,comparisons,boundary_policy:'INCLUSIVE',same_nominal_level_required:true,independent_samples_established:false,winner_established:false,calibration_established:false,coverage_guarantee:false,production_approved:false,trading_authority:false};
  }
  function pairedProbabilityDiagnostics(rows,asof,modelPairs=null,minimumSamples=20){
    const source=pairedDiagnostics(rows,asof,modelPairs,minimumSamples),byHash=new Map(rows.map(r=>[r.forecast_sha256,r])),comparisons=[];
    for(const row of rows)if('probability_up' in row&&row.probability_up!==null&&(typeof row.probability_up!=='number'||!Number.isFinite(row.probability_up)||row.probability_up<0||row.probability_up>1))fail('Invalid original paired probability.');
    for(const point of source.comparisons){
      const pair=Object.fromEntries(['a','b','shared_n','a_only_n','b_only_n','pending_shared_n','outcome_conflict_n','reference_conflict_n','missing_provenance_n','unassessed_shared_n'].map(k=>[k,point[k]]));
      Object.assign(pair,{point_paired_n:point.paired_n,probability_paired_n:0,missing_probability_n:0,a_missing_probability_n:0,b_missing_probability_n:0,both_missing_probability_n:0,distinct_target_n:0,actual_up_n:0,flat_outcome_n:0,a_brier:null,b_brier:null,a_minus_b_brier:null,uninformative_baseline_brier:null,a_ratio_to_baseline:null,b_ratio_to_baseline:null,a_lower_brier_n:0,b_lower_brier_n:0,tied_brier_n:0,cases:[]});
      const sa=[],sb=[],targets=new Set();
      for(const c of point.cases){
        const record={case_id:c.case_id,a_forecast_sha256:c.a_forecast_sha256,b_forecast_sha256:c.b_forecast_sha256,status:c.status,a_probability_state:null,b_probability_state:null,actual_up:null,a_brier:null,b_brier:null};
        if(c.status==='PAIRED'){
          const x=byHash.get(c.a_forecast_sha256),y=byHash.get(c.b_forecast_sha256),a=x.probability_up,b=y.probability_up,missingA=a===null||a===undefined,missingB=b===null||b===undefined;
          Object.assign(record,{a_probability_state:!('probability_up' in x)?'UNRECORDED':a===null?'NONE':'RECORDED',b_probability_state:!('probability_up' in y)?'UNRECORDED':b===null?'NONE':'RECORDED'});
          if(missingA||missingB){record.status='MISSING_PROBABILITY';pair.missing_probability_n++;pair.a_missing_probability_n+=Number(missingA);pair.b_missing_probability_n+=Number(missingB);pair.both_missing_probability_n+=Number(missingA&&missingB);}
          else{
            const actual=Number(x.actual>x.reference),s1=(a-actual)**2,s2=(b-actual)**2;sa.push(s1);sb.push(s2);targets.add(String(instant(x.target_at)));
            pair.probability_paired_n++;pair.actual_up_n+=actual;pair.flat_outcome_n+=Number(x.actual===x.reference);pair.a_lower_brier_n+=Number(s1<s2);pair.b_lower_brier_n+=Number(s2<s1);pair.tied_brier_n+=Number(s1===s2);
            Object.assign(record,{status:'PROBABILITY_PAIRED',actual_up:actual,a_brier:s1,b_brier:s2});
          }
        }
        pair.cases.push(record);
      }
      const n=pair.probability_paired_n;pair.distinct_target_n=targets.size;
      if(n){const mean=v=>v.reduce((s,n)=>s+n,0)/v.length,a=mean(sa),b=mean(sb);Object.assign(pair,{a_brier:a,b_brier:b,a_minus_b_brier:mean(sa.map((v,i)=>v-sb[i])),uninformative_baseline_brier:.25,a_ratio_to_baseline:a/.25,b_ratio_to_baseline:b/.25,status:n<minimumSamples?'INSUFFICIENT_EVIDENCE':targets.size<minimumSamples?'OVERLAPPING_TARGET_EVIDENCE':'DIAGNOSTIC_ONLY'});}
      else pair.status='NO_COMPATIBLE_SHARED_PROBABILITIES';
      comparisons.push(pair);
    }
    return {schema:'AFI_PAIRED_PROBABILITY_DIAGNOSTICS_V1',asof:source.asof,minimum_samples:minimumSamples,status:source.status,selection_mode:source.selection_mode,model_n:source.model_n,possible_pair_n:source.possible_pair_n,comparisons,binary_event:'PRICE_STRICTLY_ABOVE_REFERENCE; FLAT_IS_NOT_UP',missing_inputs_not_inferred:true,independent_samples_established:false,winner_established:false,calibration_established:false,predictive_skill_established:false,production_approved:false,trading_authority:false};
  }
  function reliabilityDiagnostics(rows,minimumSamples=20){
    if(!Number.isSafeInteger(minimumSamples)||minimumSamples<1||minimumSamples>10000)fail('Bounded reliability sample minimum required.');
    intervalDiagnostics(rows);const groups=new Map(),seen=new Set(),cases=new Set(),canonical=c=>JSON.stringify(Object.fromEntries(Object.entries(c).sort(([a],[b])=>a<b?-1:a>b?1:0)));
    for(const row of rows){
      if(typeof row.forecast_sha256!=='string'||!/^[0-9a-f]{64}$/.test(row.forecast_sha256)||seen.has(row.forecast_sha256))fail('Repeated or invalid reliability forecast identity.');seen.add(row.forecast_sha256);
      if('probability_up' in row&&row.probability_up!==null&&(typeof row.probability_up!=='number'||!Number.isFinite(row.probability_up)||row.probability_up<0||row.probability_up>1))fail('Invalid recorded reliability probability.');
      let binding='UNRECORDED';if('interval' in row){binding='NONE';if(row.interval!==null){const view=new DataView(new ArrayBuffer(8));view.setFloat64(0,row.interval.level,false);binding='FLOAT64:'+Array.from({length:8},(_,i)=>view.getUint8(i).toString(16).padStart(2,'0')).join('');}}
      const cohort={...diagnosticCohort(row),interval_binding:binding},key=canonical(cohort),issued=instant(row.issued_at),target=instant(row.target_at),caseId=key+'/'+String(issued)+'/'+String(target);if(cases.has(caseId)||target<=issued)fail('Repeated or invalid reliability forecast case.');cases.add(caseId);if(!groups.has(key))groups.set(key,{cohort,rows:[]});groups.get(key).rows.push(row);
    }
    const cohorts=[...groups.entries()].sort(([a],[b])=>a<b?-1:a>b?1:0).map(([,g])=>{
      const resolved=g.rows.filter(r=>r.status==='RESOLVED'),recorded=resolved.filter(r=>r.probability_up!==null&&r.probability_up!==undefined),metrics=probabilityReliability(recorded.map(r=>[r.probability_up,Number(r.actual>r.reference)]),minimumSamples),populated=new Map(metrics.calibration_bins.map(b=>[b.bin,b]));
      const bins=Array.from({length:10},(_,index)=>{const sample=recorded.filter(r=>Math.min(Math.floor(r.probability_up*10),9)===index),targets=new Set(sample.map(r=>String(instant(r.target_at)))),n=sample.length;return {...(populated.get(index)||{bin:index,n:0,mean_probability:null,observed_up_fraction:null}),lower:index/10,upper:(index+1)/10,upper_inclusive:index===9,distinct_target_n:targets.size,status:!n?'EMPTY':n<minimumSamples?'INSUFFICIENT_EVIDENCE':targets.size<minimumSamples?'OVERLAPPING_TARGET_EVIDENCE':'DIAGNOSTIC_ONLY'};});
      const n=metrics.probability_n,distinct=new Set(recorded.map(r=>String(instant(r.target_at)))).size,unknown=resolved.filter(r=>!('probability_up' in r)).length;
      return {...metrics,calibration_bins:bins,cohort:g.cohort,forecast_n:g.rows.length,resolved_n:resolved.length,pending_n:g.rows.length-resolved.length,distinct_target_n:distinct,unrecorded_probability_n:unknown,no_probability_n:resolved.filter(r=>'probability_up' in r&&r.probability_up===null).length,input_status:unknown?'PARTIAL_LEGACY_INPUTS':'RECORDED_INPUTS',status:!n?'NO_RECORDED_PROBABILITIES':unknown?'PARTIAL_LEGACY_INPUTS':n<minimumSamples?'INSUFFICIENT_EVIDENCE':distinct<minimumSamples?'OVERLAPPING_TARGET_EVIDENCE':'DIAGNOSTIC_ONLY'};
    });
    return {schema:'AFI_FIXED_BIN_RELIABILITY_V1',minimum_samples:minimumSamples,fixed_bin_n:10,denominator_scope:'RESOLVED_RECORDED_PROBABILITIES_ONLY',cohorts,empty_bins_not_zero_error:true,independent_samples_established:false,calibration_established:false,predictive_skill_established:false,production_approved:false,trading_authority:false};
  }
  function compensatedSum(values){
    let sum=0,correction=0;
    for(const value of values){const next=sum+value;correction+=Math.abs(sum)>=Math.abs(value)?(sum-next)+value:(value-next)+sum;sum=next;}
    return sum+correction;
  }
  function logLossMean(values){return compensatedSum(values)/values.length;}
  function logLossDiagnostics(rows,minimumSamples=20){
    const source=reliabilityDiagnostics(rows,minimumSamples),canonical=c=>JSON.stringify(Object.fromEntries(Object.entries(c).sort(([a],[b])=>a<b?-1:a>b?1:0)));
    const groups=new Map(source.cohorts.map(c=>[canonical(c.cohort),[]]));
    for(const row of rows){
      let binding='UNRECORDED';if('interval' in row){binding='NONE';if(row.interval!==null){const view=new DataView(new ArrayBuffer(8));view.setFloat64(0,row.interval.level,false);binding='FLOAT64:'+Array.from({length:8},(_,i)=>view.getUint8(i).toString(16).padStart(2,'0')).join('');}}
      groups.get(canonical({...diagnosticCohort(row),interval_binding:binding})).push(row);
    }
    const cohorts=source.cohorts.map(context=>{
      const cases=[],losses=[];let infinite=0,zero=0,up=0,flat=0;
      for(const row of groups.get(canonical(context.cohort))){
        const probability=row.probability_up??null,state=!('probability_up' in row)?'UNRECORDED':probability===null?'NONE':'RECORDED';
        let actualUp=null,actualFlat=null,loss=null,outcomeState=row.status!=='RESOLVED'?'PENDING':state==='UNRECORDED'?'UNRECORDED_PROBABILITY':state==='NONE'?'NO_PROBABILITY':'FINITE';
        if(row.status==='RESOLVED'&&state==='RECORDED'){
          actualUp=row.actual>row.reference;actualFlat=row.actual===row.reference;up+=Number(actualUp);flat+=Number(actualFlat);
          if((actualUp&&probability===0)||(!actualUp&&probability===1)){outcomeState='INFINITE';infinite++;}
          else{loss=Math.max(0,actualUp?-Math.log(probability):-Math.log1p(-probability));losses.push(loss);zero+=Number(loss===0);}
        }
        cases.push({forecast_sha256:row.forecast_sha256,issued_at:row.issued_at,target_at:row.target_at,forecast_status:row.status,
          probability_state:state,probability_up:probability,actual_up:actualUp,actual_flat:actualFlat,loss_state:outcomeState,log_loss:loss});
      }
      const n=context.probability_n;if(losses.length+infinite!==n)fail('Log-loss denominator mismatch.');
      let mean=losses.length&&!infinite?logLossMean(losses):null;
      const baseline=n?Math.log(2):null,underflow=mean===0&&losses.some(v=>v>0);if(underflow)mean=null;
      const counts=Object.fromEntries(['cohort','forecast_n','resolved_n','pending_n','probability_n','distinct_target_n','unrecorded_probability_n','no_probability_n','input_status','status'].map(k=>[k,context[k]]));
      return {...counts,finite_loss_n:losses.length,infinite_loss_n:infinite,zero_loss_n:zero,actual_up_n:up,flat_outcome_n:flat,
        loss_state:!n?'UNAVAILABLE':infinite?'INFINITE':underflow?'UNAVAILABLE_NUMERIC_RANGE':'FINITE',mean_log_loss:mean,
        half_probability_mean_log_loss:baseline,mean_log_loss_minus_baseline:mean===null?null:mean-baseline,cases};
    });
    return {schema:'AFI_LOG_LOSS_DIAGNOSTICS_V1',minimum_samples:minimumSamples,input_scope:'CALLER_SUPPLIED_ACCOUNTABILITY_ROWS',
      denominator_scope:'RESOLVED_RECORDED_PROBABILITIES_ONLY',binary_event:'PRICE_STRICTLY_ABOVE_REFERENCE; FLAT_IS_NOT_UP',
      logarithm_base:'NATURAL',epsilon_clipping_applied:false,cohorts,original_forecast_history_verified:false,
      independent_samples_established:false,calibration_established:false,predictive_skill_established:false,winner_established:false,
      production_approved:false,trading_authority:false,startup_authorized:false,network_authorized:false,recovery_authorized:false};
  }
  function pairedLogLossDiagnostics(rows,asof,modelPairs=null,minimumSamples=20){
    const source=pairedProbabilityDiagnostics(rows,asof,modelPairs,minimumSamples),single=logLossDiagnostics(rows,minimumSamples),precision=32*Number.EPSILON;
    const byHash=new Map(rows.map(r=>[r.forecast_sha256,r])),scores=new Map(single.cohorts.flatMap(g=>g.cases.map(c=>[c.forecast_sha256,c])));
    const mean=logLossMean;
    const side=(cases,name)=>{
      if(!cases.length)return ['UNAVAILABLE',null];if(cases.some(c=>c[name+'_loss_state']==='INFINITE'))return ['INFINITE',null];
      const values=cases.map(c=>c[name+'_log_loss']),m=mean(values);return m===0&&values.some(v=>v>0)?['UNAVAILABLE_NUMERIC_RANGE',null]:['FINITE',m];
    };
    const comparisons=source.comparisons.map(original=>{
      const keys=['a','b','shared_n','a_only_n','b_only_n','pending_shared_n','outcome_conflict_n','reference_conflict_n','missing_provenance_n','unassessed_shared_n','point_paired_n','probability_paired_n','missing_probability_n','a_missing_probability_n','b_missing_probability_n','both_missing_probability_n','distinct_target_n','actual_up_n','flat_outcome_n','status'];
      const pair=Object.fromEntries(keys.map(k=>[k,original[k]])),targets=new Set();
      const cases=original.cases.map(c=>{
        const item=Object.fromEntries(['case_id','a_forecast_sha256','b_forecast_sha256','status','a_probability_state','b_probability_state'].map(k=>[k,c[k]]));
        Object.assign(item,{actual_up:null,a_loss_state:null,b_loss_state:null,a_log_loss:null,b_log_loss:null,difference_state:'UNAVAILABLE',a_minus_b_log_loss:null});
        if(c.status==='PROBABILITY_PAIRED'){
          const a=scores.get(c.a_forecast_sha256),b=scores.get(c.b_forecast_sha256),pa=byHash.get(c.a_forecast_sha256).probability_up,pb=byHash.get(c.b_forecast_sha256).probability_up;
          let state,delta=null;
          if(a.loss_state==='INFINITE'&&b.loss_state==='INFINITE')state='UNDEFINED_BOTH_INFINITE';
          else if(a.loss_state==='INFINITE')state='POSITIVE_INFINITY';else if(b.loss_state==='INFINITE')state='NEGATIVE_INFINITY';
          else{delta=a.log_loss-b.log_loss;if(pa!==pb&&Math.abs(delta)<=precision*Math.max(Math.abs(a.log_loss),Math.abs(b.log_loss))){state='UNAVAILABLE_NUMERIC_RANGE';delta=null;}else state='FINITE';}
          targets.add(String(instant(byHash.get(c.a_forecast_sha256).target_at)));
          Object.assign(item,{status:'LOG_LOSS_PAIRED',actual_up:a.actual_up,a_loss_state:a.loss_state,b_loss_state:b.loss_state,a_log_loss:a.log_loss,b_log_loss:b.log_loss,difference_state:state,a_minus_b_log_loss:delta});
        }return item;
      });
      const paired=cases.filter(c=>c.status==='LOG_LOSS_PAIRED'),n=paired.length;if(n!==original.probability_paired_n||targets.size!==pair.distinct_target_n)fail('Paired log-loss denominator mismatch.');
      const [aState,aMean]=side(paired,'a'),[bState,bMean]=side(paired,'b');
      const counts=Object.fromEntries(['FINITE','POSITIVE_INFINITY','NEGATIVE_INFINITY','UNDEFINED_BOTH_INFINITE','UNAVAILABLE_NUMERIC_RANGE'].map(state=>[state,paired.filter(c=>c.difference_state===state).length]));
      let state,delta=null;
      if(!n)state='UNAVAILABLE';else if(aState==='INFINITE'&&bState==='INFINITE')state='UNDEFINED_BOTH_INFINITE';
      else if(aState==='INFINITE')state='POSITIVE_INFINITY';else if(bState==='INFINITE')state='NEGATIVE_INFINITY';
      else if(aState!=='FINITE'||bState!=='FINITE'||counts.UNAVAILABLE_NUMERIC_RANGE)state='UNAVAILABLE_NUMERIC_RANGE';
      else{const values=paired.map(c=>c.a_minus_b_log_loss);delta=mean(values);const scale=Math.max(mean(values.map(Math.abs)),aMean,bMean);if(values.some(v=>v!==0)&&Math.abs(delta)<=precision*scale){state='UNAVAILABLE_NUMERIC_RANGE';delta=null;}else state='FINITE';}
      return {...pair,a_loss_state:aState,b_loss_state:bState,a_mean_log_loss:aMean,b_mean_log_loss:bMean,
        a_infinite_loss_n:paired.filter(c=>c.a_loss_state==='INFINITE').length,b_infinite_loss_n:paired.filter(c=>c.b_loss_state==='INFINITE').length,
        finite_difference_n:counts.FINITE,positive_infinite_difference_n:counts.POSITIVE_INFINITY,negative_infinite_difference_n:counts.NEGATIVE_INFINITY,
        undefined_difference_n:counts.UNDEFINED_BOTH_INFINITE,numeric_range_difference_n:counts.UNAVAILABLE_NUMERIC_RANGE,
        difference_state:state,a_minus_b_mean_log_loss:delta,half_probability_mean_log_loss:n?Math.log(2):null,cases};
    });
    return {schema:'AFI_PAIRED_LOG_LOSS_DIAGNOSTICS_V1',...Object.fromEntries(['asof','minimum_samples','status','selection_mode','model_n','possible_pair_n'].map(k=>[k,source[k]])),comparisons,binary_event:source.binary_event,
      logarithm_base:'NATURAL',epsilon_clipping_applied:false,difference_policy:'PAIRED_CASE_MEAN_NEAR_ZERO_REFUSAL_32_EPS',missing_inputs_not_inferred:true,
      independent_samples_established:false,winner_established:false,calibration_established:false,predictive_skill_established:false,production_approved:false,trading_authority:false};
  }
  function sameLogLoss(expected,supplied,key='',scale=0){
    if(typeof expected==='number'&&['a_minus_b_log_loss','a_minus_b_mean_log_loss'].includes(key)){
      return typeof supplied==='number'&&Number.isFinite(supplied)&&(expected===0?supplied===0:Math.sign(supplied)===Math.sign(expected)&&Math.abs(expected-supplied)<=Math.max(1e-12*Math.abs(expected),4*Number.EPSILON*scale));
    }
    if(typeof expected==='number'&&['log_loss','mean_log_loss','half_probability_mean_log_loss','a_log_loss','b_log_loss','a_mean_log_loss','b_mean_log_loss'].includes(key)){
      return typeof supplied==='number'&&Number.isFinite(supplied)&&(expected===0?supplied===0:supplied>0&&Math.abs(expected-supplied)<=1e-12*Math.abs(expected));
    }
    if(expected===null||typeof expected!=='object')return sameDiagnostic(expected,supplied,key);
    if(!supplied||typeof supplied!=='object'||Array.isArray(expected)!==Array.isArray(supplied)||Object.keys(expected).sort().join('|')!==Object.keys(supplied).sort().join('|'))return false;
    return Object.keys(expected).every(k=>{
      const lossScale=k==='a_minus_b_log_loss'?Math.max(Math.abs(expected.a_log_loss??0),Math.abs(expected.b_log_loss??0)):k==='a_minus_b_mean_log_loss'?Math.max(Math.abs(expected.a_mean_log_loss??0),Math.abs(expected.b_mean_log_loss??0)):0;
      return sameLogLoss(expected[k],supplied[k],k,lossScale);
    });
  }
  async function verifyLogLossEnvelope(text,hash=digest){
    const envelope=parse(text);
    const paired=envelope?.schema==='AFI_LOG_LOSS_BROWSER_V2';
    if(!envelope||Object.keys(envelope).sort().join('|')!==(paired?'diagnostics_json|diagnostics_sha256|model_pairs|schema|source_report_json|source_report_sha256':'diagnostics_json|diagnostics_sha256|schema|source_report_json|source_report_sha256')||
       !['AFI_LOG_LOSS_BROWSER_V1','AFI_LOG_LOSS_BROWSER_V2'].includes(envelope.schema)||typeof envelope.source_report_json!=='string'||typeof envelope.diagnostics_json!=='string'||
       !/^[a-f0-9]{64}$/.test(envelope.source_report_sha256)||!/^[a-f0-9]{64}$/.test(envelope.diagnostics_sha256))fail('Exact log-loss envelope required.');
    const report=await verifyEnvelope(JSON.stringify({schema:'AFI_BROWSER_REPORT_V1',report_json:envelope.source_report_json,payload_sha256:envelope.source_report_sha256}),hash);
    if(await hash(envelope.diagnostics_json)!==envelope.diagnostics_sha256)fail('Log-loss digest mismatch.');
    const diagnostics=parse(envelope.diagnostics_json);let expected=logLossDiagnostics(report.rows,diagnostics.minimum_samples);
    if(paired)expected={...expected,schema:'AFI_LOG_LOSS_DIAGNOSTICS_V2',paired_log_loss_diagnostics:pairedLogLossDiagnostics(report.rows,report.asof,envelope.model_pairs,diagnostics.minimum_samples)};
    if(!sameLogLoss(expected,diagnostics))fail('Log loss differs from original recorded row evidence.');
    return {source_report:report,diagnostics};
  }
  function forecastPlot(rows, selected = '') {
    if (!Array.isArray(rows) || rows.length > 64) fail('Bounded plot rows required.');
    intervalDiagnostics(rows);
    const groups = new Map(), seen = new Set();
    let unbound = 0;
    for (const row of rows) {
      const cohort = diagnosticCohort(row);
      if (!/^[0-9a-f]{64}$/.test(row.forecast_sha256) || seen.has(row.forecast_sha256)) fail('Unique plot identity required.');
      seen.add(row.forecast_sha256); instant(row.target_at);
      if (!['model_version','model_configuration_sha256','forecast_dataset_sha256','forecast_dataset_manifest_sha256','forecast_dataset_id','forecast_dataset_version','forecast_code_sha256'].every(k => cohort[k] != null)) { unbound++; continue; }
      const context = {...cohort,input_source_id:row.input_source_id??null,input_source_revision:row.input_source_revision??null,input_source_sha256:row.input_source_sha256??null,interval_level:row.interval?.level??null,interval_recorded:'interval' in row};
      const id = JSON.stringify(context);
      if (!groups.has(id)) groups.set(id, {id,cohort:context,rows:[]});
      groups.get(id).rows.push(row);
    }
    const cohorts = [...groups.values()].map(g => ({id:g.id,cohort:g.cohort,n:g.rows.length}));
    const result = {cohorts,unbound_n:unbound,points:[],status:rows.length?'SELECT_COHORT':'NO_VISIBLE_CASES',predictive_skill_established:false};
    if (!selected) return result;
    if (!groups.has(selected)) return {...result,status:'COHORT_NOT_VISIBLE'};
    const sample = groups.get(selected).rows.slice().sort((a,b) => instant(a.target_at)<instant(b.target_at)?-1:instant(a.target_at)>instant(b.target_at)?1:a.forecast_sha256.localeCompare(b.forecast_sha256));
    const values = sample.flatMap(r => [r.forecast_point,...(r.actual===null?[]:[r.actual]),...(r.interval?[r.interval.lower,r.interval.upper]:[])]);
    const min = Math.min(...values), max = Math.max(...values);
    const coordinate = value => max===min ? 0.5 : (value-min)/(max-min);
    return {...result,status:'DISPLAYED',min,max,points:sample.map((row,index) => ({row,index:index+1,forecast:coordinate(row.forecast_point),actual:row.actual===null?null:coordinate(row.actual),lower:row.interval?coordinate(row.interval.lower):null,upper:row.interval?coordinate(row.interval.upper):null}))};
  }
  function priorCaseContext(rows, selected = '') {
    const plotted=forecastPlot(rows), groups=new Map(), byHash=new Map();
    for(const row of rows){if(instant(row.issued_at)>=instant(row.target_at))fail('Prior-case issue must precede target.');byHash.set(row.forecast_sha256,row);}
    for(const group of plotted.cohorts)for(const p of forecastPlot(rows,group.id).points)groups.set(p.row.forecast_sha256,group.id);
    const base={status:rows.length?'SELECT_QUERY':'NO_VISIBLE_CASES',supplied_n:rows.length,unbound_n:plotted.unbound_n,other_cohort_n:0,not_prior_n:0,prior_n:0,known_outcome_n:0,unavailable_outcome_n:0,cases:[],query:null,
      historical_availability_authenticated:false,predictive_skill_established:false,similarity_ranking_established:false};
    if(!selected)return base;
    const query=byHash.get(selected);if(!query)return {...base,status:'QUERY_NOT_VISIBLE'};
    if(!groups.has(selected))return {...base,status:'QUERY_PROVENANCE_UNAVAILABLE'};
    const cutoff=instant(query.issued_at),cohort=groups.get(selected),cases=[];
    let other=0,notPrior=0;
    for(const row of rows){
      if(row.forecast_sha256===selected)continue;
      if(groups.get(row.forecast_sha256)!==cohort){other++;continue;}
      if(instant(row.issued_at)>=cutoff){notPrior++;continue;}
      let known=false;
      if(row.status==='RESOLVED'&&row.source_available_at!=null&&row.last_reconciled_asof!=null){
        const target=instant(row.target_at),available=instant(row.source_available_at),reconciled=instant(row.last_reconciled_asof);
        if(available<target||reconciled<available)fail('Prior-case outcome chronology contradiction.');
        known=target<=cutoff&&available<=cutoff&&reconciled<=cutoff;
      }
      cases.push({forecast_sha256:row.forecast_sha256,issued_at:row.issued_at,target_at:row.target_at,forecast_point:row.forecast_point,
        outcome_state:known?'RECORDED_BY_QUERY_CUTOFF':row.status==='RESOLVED'?'UNAVAILABLE_AT_QUERY_CUTOFF':'NOT_RESOLVED_IN_SUPPLIED_VINTAGE',
        actual:known?row.actual:null,source_available_at:known?row.source_available_at:null,last_reconciled_asof:known?row.last_reconciled_asof:null,
        outcome_dataset_sha256:known?(row.outcome_dataset_sha256??null):null,source_revision:known?(row.source_revision??null):null});
    }
    cases.sort((a,b)=>instant(a.issued_at)>instant(b.issued_at)?-1:instant(a.issued_at)<instant(b.issued_at)?1:a.forecast_sha256.localeCompare(b.forecast_sha256));
    const known=cases.filter(c=>c.actual!==null).length;
    return {...base,status:cases.length?'PRIOR_CASES':'NO_PRIOR_CASES',query:{forecast_sha256:selected,issued_at:query.issued_at,cohort},other_cohort_n:other,not_prior_n:notPrior,prior_n:cases.length,known_outcome_n:known,unavailable_outcome_n:cases.length-known,cases};
  }
  function evidenceDisplayModel(input) {
    if (input != null) {
      throw new Error('Historical evidence import is not enabled.');
    }
    return {
      classification: 'NOT_SUPPLIED',
      historical_availability_authenticated: false,
      predictive_skill_established: false,
      description: 'No historical evidence receipt classification supplied.'
    };
  }

  function renderPriorCases(document, rows) {
    const select=document.getElementById('memory-query'),body=document.getElementById('memory-rows'),status=document.getElementById('memory-status');
    if(!select||!body||!status)return;
    body.replaceChildren();const selected=select.value,model=priorCaseContext(rows,selected);select.replaceChildren();
    const option=(value,label)=>{const e=document.createElement('option');e.value=value;e.textContent=label;select.appendChild(e);};
    option('','Choose a query forecast');
    for(const row of rows)option(row.forecast_sha256,`${row.asset_id} / ${row.horizon} / ${row.issued_at} / ${row.forecast_sha256}`);
    select.value=rows.some(r=>r.forecast_sha256===selected)?selected:'';
    status.textContent=`${model.status}. ${model.supplied_n} supplied cases; ${model.prior_n} earlier same-cohort cases; ${model.known_outcome_n} outcomes recorded by query cutoff; ${model.unavailable_outcome_n} unavailable outcomes; ${model.other_cohort_n} other/unbound cohorts; ${model.not_prior_n} same-time/later cases. ${model.unbound_n} cases lack complete provenance. Query cutoff: ${model.query?.issued_at??'not selected'}. No historical availability authentication, similarity ranking or predictive skill.`;
    const evidence = evidenceDisplayModel(null);
    status.textContent += ` Historical evidence: ${evidence.classification}. ${evidence.description}`;
    for(const c of model.cases){const tr=document.createElement('tr');for(const value of [c.forecast_sha256,c.issued_at,c.target_at,c.forecast_point,c.outcome_state,c.actual,c.source_available_at,c.last_reconciled_asof,c.outcome_dataset_sha256,c.source_revision]){const td=document.createElement('td');td.textContent=value===null?'Unavailable':String(value);tr.appendChild(td);}body.appendChild(tr);}
  }
  function renderForecastPlot(document, rows) {
    const select=document.getElementById('plot-cohort'),host=document.getElementById('forecast-plot'),status=document.getElementById('plot-status');
    if (!select || !host || !status) return;
    host.replaceChildren();
    const selected=select.value,model=forecastPlot(rows,selected);
    select.replaceChildren();
    const option=(value,label)=>{const e=document.createElement('option');e.value=value;e.textContent=label;select.appendChild(e);};
    option('','Choose one recorded cohort');
    for(const [index,c] of model.cohorts.entries())option(c.id,`${index+1}. ${c.cohort.asset_id} / ${c.cohort.horizon} / ${c.cohort.model} / version ${c.cohort.model_version} / ${c.n} cases`);
    select.value=model.cohorts.some(c=>c.id===selected)?selected:'';
    status.textContent=`${model.status}. ${model.unbound_n} visible cases lack complete recorded provenance and are not plotted. Synthetic evidence only; no accuracy, calibration or independent-sample claim.`;
    if(model.status!=='DISPLAYED')return;
    const provenance=document.createElement('p');provenance.textContent='Exact recorded cohort (not authenticated): '+selected;provenance.setAttribute('class','plot-provenance');host.appendChild(provenance);
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox',`0 0 900 ${80+model.points.length*42}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','Discrete cases: blue circle forecast, orange square observed outcome, interval whiskers. Pending outcomes have no observed marker.');
    const add=(tag,attrs,text,parent=svg)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;parent.appendChild(e);return e;};
    add('title',{},'Synthetic forecast, observed outcome and original prediction intervals');
    add('desc',{},'Cases sorted by target then forecast identity, without connecting price paths. Exact values remain in the forecast table. Nominal interval levels are not coverage guarantees.');
    add('text',{x:260,y:20,fill:'currentColor'},String(model.min));add('text',{x:880,y:20,'text-anchor':'end',fill:'currentColor'},String(model.max));
    for(const p of model.points){
      const y=52+(p.index-1)*42,x=v=>260+620*v,r=p.row,g=add('g',{});
      add('title',{},`${r.forecast_sha256}: target ${r.target_at}; forecast ${r.forecast_point}; observed ${r.actual??'unavailable'}; ${r.status}; outcome dataset ${r.outcome_dataset_sha256??'unrecorded'}; source revision ${r.source_revision??'unrecorded'}; corrections ${r.correction_n}; interval ${r.interval?`${r.interval.lower} to ${r.interval.upper}, level ${r.interval.level}`:'unavailable'}`,g);
      add('text',{x:8,y:y+5,fill:'currentColor'},`${p.index}. ${r.status}`,g);
      if(p.lower!==null){add('line',{x1:x(p.lower),x2:x(p.upper),y1:y,y2:y,stroke:'currentColor','stroke-width':2},undefined,g);for(const v of [p.lower,p.upper])add('line',{x1:x(v),x2:x(v),y1:y-8,y2:y+8,stroke:'currentColor'},undefined,g);}
      add('circle',{cx:x(p.forecast),cy:y,r:6,fill:'#4aa8ff',stroke:'currentColor'},undefined,g);
      if(p.actual!==null)add('rect',{x:x(p.actual)-4,y:y-4,width:8,height:8,fill:'#ffad4a',stroke:'currentColor'},undefined,g);
    }
    host.appendChild(svg);
    const table=document.createElement('table'),caption=document.createElement('caption');
    caption.textContent='Exact plotted cases in chart order. Outcome corrections remain one original forecast; source identity is recorded, not independently authenticated.';table.appendChild(caption);
    const head=document.createElement('thead'),header=document.createElement('tr');
    for(const label of ['Case','Forecast identity','Target','Forecast','Observed','Outcome state','Original interval','Outcome dataset','Outcome revision','Corrections']){const th=document.createElement('th');th.setAttribute('scope','col');th.textContent=label;header.appendChild(th);}head.appendChild(header);table.appendChild(head);
    const body=document.createElement('tbody');
    for(const p of model.points){const r=p.row,tr=document.createElement('tr');for(const value of [p.index,r.forecast_sha256,r.target_at,r.forecast_point,r.actual,r.status,r.interval?`${r.interval.lower} to ${r.interval.upper} (level ${r.interval.level})`:null,r.outcome_dataset_sha256??null,r.source_revision??null,r.correction_n]){const td=document.createElement('td');td.textContent=value===null?'Unavailable':String(value);tr.appendChild(td);}body.appendChild(tr);}table.appendChild(body);host.appendChild(table);
  }
  function mount(document) {
    const byId = id => document.getElementById(id);
    if (!byId('report-file')) return;
    let active = null, activeLogLoss = null, priorReport = null;
    const logLossImport = Symbol('verified log-loss import');
    const body = byId('forecast-rows');
    function draw() {
      body.replaceChildren();
      byId('forecast-plot')?.replaceChildren();
      if (!active) { const select=byId('plot-cohort');if(select)select.value='';renderForecastPlot(document,[]);const memory=byId('memory-query');if(memory)memory.value='';renderPriorCases(document,[]); }
      byId('vintage-rows')?.replaceChildren();
      byId('vintage-impact-rows')?.replaceChildren();
      byId('vintage-signed-rows')?.replaceChildren();
      if(byId('vintage-status'))byId('vintage-status').textContent='Load both report vintages to compare reported outcomes.';
      byId('interval-rows')?.replaceChildren();
      byId('signed-error-rows')?.replaceChildren();
      byId('directional-rows')?.replaceChildren();
      byId('error-rows')?.replaceChildren();
      byId('reliability-rows')?.replaceChildren();
      byId('log-loss-rows')?.replaceChildren();
      byId('paired-log-loss-rows')?.replaceChildren();
      if(byId('paired-log-loss-status'))byId('paired-log-loss-status').textContent='Import a V2 log-loss companion for a matched-case plan.';
      if(byId('log-loss-status'))byId('log-loss-status').textContent='Load an explicit log-loss companion to display these diagnostics.';
      byId('pair-rows')?.replaceChildren();
      byId('paired-interval-rows')?.replaceChildren();
      byId('paired-probability-rows')?.replaceChildren();
      if(byId('pair-status'))byId('pair-status').textContent='No comparison evidence loaded.';
      if(byId('error-status'))byId('error-status').textContent='No score evidence loaded.';
      if (!active){for(const id of ['compare-a','compare-b']){const select=byId(id);if(select){select.replaceChildren();const option=document.createElement('option');option.value='';option.textContent='Automatic pairs';select.appendChild(option);select.value='';}}return;}
      const rows = selectRows(active, byId('asset-filter').value, byId('state-filter').value, byId('sort-order').value,byId('horizon-filter')?.value||'ALL');
      renderForecastPlot(document,rows);
      renderPriorCases(document,rows);
      for (const row of rows) {
        const tr = document.createElement('tr');
        for (const value of [row.asset_id, row.model, row.horizon, row.target_at, row.forecast_point,
          row.input_observed_at ?? null,row.input_available_at ?? null,row.input_source_id ?? null,
          row.input_source_revision ?? null,row.input_source_sha256 ?? null,
          row.interval ? `${row.interval.lower} to ${row.interval.upper} (level ${row.interval.level})` : ('interval' in row ? 'No fitted interval' : 'Not recorded in legacy report'), row.actual, row.status, row.correction_n, row.last_reconciled_asof]) {
          const td = document.createElement('td'); td.textContent = value === null ? 'Unavailable' : String(value); tr.appendChild(td);
        }
        body.appendChild(tr);
      }
      const vintageBody=byId('vintage-rows');
      if(vintageBody&&priorReport){
        try{
          const comparison=compareReportVintages(priorReport,active);
          const signedBody=byId('vintage-signed-rows');
          if(signedBody)for(const row of signedErrorVintageImpact(priorReport,active).rows){
            const tr=document.createElement('tr');
            for(const value of [row.asset_id,row.model,row.horizon,row.forecast_sha256,row.status,row.state,row.left_signed_error,row.right_signed_error,row.right_minus_left_signed_error]){
              const td=document.createElement('td');td.textContent=value===null?'Unavailable':String(value);tr.appendChild(td);
            }
            signedBody.appendChild(tr);
          }
          if(byId('vintage-status'))byId('vintage-status').textContent=`${comparison.matched_forecast_n} shared forecasts; ${comparison.union_forecast_n} in the full union. Reported changes only; chain ancestry is not verified. No cross-asset error aggregate.`;
          for(const row of comparison.rows){
            const tr=document.createElement('tr');
            for(const value of [row.asset_id,row.model,row.horizon,row.forecast_sha256,row.status,row.left_status,row.right_status,row.left_actual,row.right_actual,row.left_correction_n,row.right_correction_n,row.left_source_revision,row.right_source_revision,row.outcome_provenance_changed,row.metric_state,row.left_absolute_error,row.right_absolute_error,row.right_minus_left_absolute_error]){
              const td=document.createElement('td');td.textContent=value===null?'Unavailable':String(value);tr.appendChild(td);
            }
            vintageBody.appendChild(tr);
            const impactBody=byId('vintage-impact-rows');
            if(impactBody){
              const tr=document.createElement('tr'),i=row.score_impact.interval,p=row.score_impact.probability;
              for(const value of [row.asset_id,row.forecast_sha256,i.state,i.level,i.left_covered,i.right_covered,i.left_score,i.right_score,i.right_minus_left_score,p.state,p.probability_up,p.left_actual_up,p.right_actual_up,p.left_brier,p.right_brier,p.right_minus_left_brier,p.left_log_loss_state,p.right_log_loss_state,p.left_log_loss,p.right_log_loss,p.log_loss_difference_state,p.right_minus_left_log_loss]){
                const td=document.createElement('td');td.textContent=value===null?'Unavailable':String(value);tr.appendChild(td);
              }
              impactBody.appendChild(tr);
            }
          }
        }catch{
          vintageBody.replaceChildren();
          byId('vintage-impact-rows')?.replaceChildren();
          byId('vintage-signed-rows')?.replaceChildren();
          if(byId('vintage-status'))byId('vintage-status').textContent='Report vintages cannot be compared. Use valid reports ordered by evidence cutoff; no impact is inferred.';
        }
      }
      const intervalBody=byId('interval-rows');
      if (intervalBody) {
        intervalBody.replaceChildren();
        for (const c of intervalTargetSupport(rows).cohorts) {
          const tr=document.createElement('tr');
          for (const value of [c.cohort.asset_id,c.cohort.model,c.cohort.model_version||'LEGACY_UNBOUND',c.cohort.lookback||null,c.cohort.model_configuration_sha256||'LEGACY_UNBOUND',c.cohort.forecast_dataset_version||'LEGACY_UNBOUND',c.cohort.forecast_dataset_manifest_sha256||'LEGACY_UNBOUND',c.cohort.forecast_code_sha256||'LEGACY_UNBOUND',c.cohort.forecast_dataset_sha256||'LEGACY_UNBOUND',c.cohort.release_source_sha256||'UNBOUND',c.cohort.horizon,c.cohort.level,c.resolved_n,c.pending_n,c.coverage,c.mean_width,c.mean_interval_score,c.status,c.distinct_recorded_target_n,c.missing_target_n,c.repeated_target_n,c.target_support_status]) {
            const td=document.createElement('td');td.textContent=value===null ? 'Unavailable':String(value);tr.appendChild(td);
          }
          intervalBody.appendChild(tr);
        }
      }
      const directionalBody=byId('directional-rows');
      if(directionalBody){
        for(const c of directionalDiagnostics(rows).cohorts){
          const tr=document.createElement('tr'),k=c.cohort;
          for(const value of [k.asset_id,k.model,k.model_version||'LEGACY_UNBOUND',k.lookback||null,k.model_configuration_sha256||'LEGACY_UNBOUND',k.forecast_dataset_version||'LEGACY_UNBOUND',k.forecast_dataset_manifest_sha256||'LEGACY_UNBOUND',k.forecast_code_sha256||'LEGACY_UNBOUND',k.forecast_dataset_sha256||'LEGACY_UNBOUND',k.release_source_sha256||'UNBOUND',k.horizon,c.resolved_n,c.pending_n,c.directional_accuracy,c.up.precision,c.up.recall,c.up.false_positive_n,c.up.false_negative_n,c.status]){
            const td=document.createElement('td');td.textContent=value===null?'Unavailable':String(value);tr.appendChild(td);
          }
          directionalBody.appendChild(tr);
        }
      }
      const signedBody=byId('signed-error-rows');
      if(signedBody){
        signedBody.replaceChildren();
        for(const c of signedErrorDiagnostics(rows).cohorts){
          const k=c.cohort,tr=document.createElement('tr');
          for(const value of [k.asset_id,k.model,k.model_version||'LEGACY_UNBOUND',k.lookback??null,k.model_configuration_sha256||'LEGACY_UNBOUND',k.forecast_dataset_version||'LEGACY_UNBOUND',k.forecast_dataset_manifest_sha256||'LEGACY_UNBOUND',k.forecast_code_sha256||'LEGACY_UNBOUND',k.forecast_dataset_sha256||'LEGACY_UNBOUND',k.release_source_sha256||'UNBOUND',k.horizon,c.resolved_n,c.pending_n,c.over_n,c.under_n,c.equal_n,c.mean_signed_error,c.status]){
            const td=document.createElement('td');td.textContent=value===null?'Unavailable':String(value);tr.appendChild(td);
          }
          signedBody.appendChild(tr);
        }
      }
      const errorBody=byId('error-rows');
      if(errorBody){
        const evidence=visibleErrors(active,byId('asset-filter').value,byId('state-filter').value,byId('sort-order').value,byId('horizon-filter')?.value||'ALL');
        if(byId('error-status'))byId('error-status').textContent=evidence.message;
        for(const c of evidence.cohorts){
          const k=c.cohort,tr=document.createElement('tr');
          for(const value of [k.asset_id,k.model,k.lookback??null,k.horizon,c.issued_n,c.n,c.pending_n,c.mae,c.no_change_mae,c.mae_ratio_to_no_change,c.rmse,c.recorded_probability_n,c.missing_probability_n,c.brier,c.status,k.model_configuration_sha256||'LEGACY_UNBOUND',k.forecast_dataset_version||'LEGACY_UNBOUND',k.forecast_dataset_manifest_sha256||'LEGACY_UNBOUND',k.release_source_sha256||'UNBOUND']){
            const td=document.createElement('td');td.textContent=value===null||value===undefined?'Unavailable':typeof value==='number'?String(Number(value.toPrecision(6))):String(value);tr.appendChild(td);
          }
          errorBody.appendChild(tr);
        }
      }
      const reliabilityBody=byId('reliability-rows');
      if(reliabilityBody){
        const selected=selectRows(active,byId('asset-filter').value,byId('state-filter').value,byId('sort-order').value,byId('horizon-filter')?.value||'ALL'),evidence=reliabilityDiagnostics(selected);
        for(const c of evidence.cohorts)for(const b of c.calibration_bins){
          const tr=document.createElement('tr'),k=c.cohort;
          for(const value of [k.asset_id,k.model,k.lookback??null,k.horizon,c.resolved_n,c.pending_n,c.probability_n,c.unrecorded_probability_n,c.no_probability_n,c.distinct_target_n,b.lower,b.upper,b.upper_inclusive,b.n,b.distinct_target_n,b.mean_probability,b.observed_up_fraction,c.expected_calibration_error,b.status,c.status,k.model_configuration_sha256||'LEGACY_UNBOUND',k.forecast_dataset_manifest_sha256||'LEGACY_UNBOUND',k.interval_binding]){
            const td=document.createElement('td');td.textContent=value===null||value===undefined?'Unavailable':typeof value==='number'?String(Number(value.toPrecision(6))):String(value);tr.appendChild(td);
          }
          reliabilityBody.appendChild(tr);
        }
      }
      const pairBody=byId('pair-rows');
      if(pairBody){
        let comparisons=pairedDiagnostics(rows,active.asof);
        const describe=m=>{const c=m.cohort;return `${c.asset_id} / ${c.model} / window ${c.lookback??'unknown'} / ${c.horizon} / data ${c.forecast_dataset_version??'unbound'} / interval ${m.interval_recorded?(m.interval_level??'none'):'unknown'} / ${(c.model_configuration_sha256||c.model_version||'unbound').slice(0,12)}`;};
        for(const id of ['compare-a','compare-b']){
          const select=byId(id);if(!select)continue;const prior=select.value;select.replaceChildren();
          const automatic=document.createElement('option');automatic.value='';automatic.textContent='Automatic pairs';select.appendChild(automatic);
          for(const model of comparisons.models){const option=document.createElement('option');option.value=model.id;option.textContent=describe(model);select.appendChild(option);}
          select.value=comparisons.models.some(m=>m.id===prior)?prior:'';
        }
        const a=byId('compare-a')?.value||'',b=byId('compare-b')?.value||'';
        let message;
        if((a&&!b)||(!a&&b)){comparisons={...comparisons,comparisons:[]};message='Choose both models, or use automatic pairs.';}
        else if(a&&a===b){comparisons={...comparisons,comparisons:[]};message='Choose two different models.';}
        else{
          if(a&&b)comparisons=pairedDiagnostics(rows,active.asof,[[a,b]]);
          message=comparisons.status==='EXPLICIT_PAIR_SELECTION_REQUIRED'?'More than 64 possible comparisons. Choose two models.':comparisons.comparisons.length?'Matched outcomes only. No independent model winner is established.':'No distinct eligible model pairs in this view.';
        }
        if(byId('pair-status'))byId('pair-status').textContent=message;
        const models=new Map(comparisons.models.map(m=>[m.id,m.cohort]));
        const probabilityBody=byId('paired-probability-rows');
        if(probabilityBody&&comparisons.comparisons.length){
          const probabilities=pairedProbabilityDiagnostics(rows,active.asof,comparisons.comparisons.map(p=>[p.a,p.b]));
          for(const p of probabilities.comparisons){
            const ac=models.get(p.a),bc=models.get(p.b),tr=document.createElement('tr');
            for(const value of [ac.asset_id,ac.horizon,ac.model+' / window '+(ac.lookback??'unknown'),bc.model+' / window '+(bc.lookback??'unknown'),p.point_paired_n,p.probability_paired_n,p.distinct_target_n,p.missing_probability_n,p.a_missing_probability_n,p.b_missing_probability_n,p.actual_up_n,p.flat_outcome_n,p.a_brier,p.b_brier,p.a_minus_b_brier,p.uninformative_baseline_brier,p.a_ratio_to_baseline,p.b_ratio_to_baseline,p.status]){
              const td=document.createElement('td');td.textContent=value===null||value===undefined?'Unavailable':typeof value==='number'?String(Number(value.toPrecision(6))):String(value);tr.appendChild(td);
            }
            probabilityBody.appendChild(tr);
          }
        }
        const intervalBody=byId('paired-interval-rows');
        if(intervalBody&&comparisons.comparisons.length){
          const intervals=pairedIntervalDiagnostics(rows,active.asof,comparisons.comparisons.map(p=>[p.a,p.b]));
          for(const p of intervals.comparisons){
            const ac=models.get(p.a),bc=models.get(p.b),tr=document.createElement('tr');
            for(const value of [ac.asset_id,ac.horizon,ac.model+' / window '+(ac.lookback??'unknown'),bc.model+' / window '+(bc.lookback??'unknown'),p.point_paired_n,p.interval_paired_n,p.distinct_target_n,p.missing_interval_n,p.level_mismatch_n,p.nominal_level,p.a_coverage,p.b_coverage,p.a_mean_width,p.b_mean_width,p.a_mean_interval_score,p.b_mean_interval_score,p.a_minus_b_interval_score,p.status]){
              const td=document.createElement('td');td.textContent=value===null||value===undefined?'Unavailable':typeof value==='number'?String(Number(value.toPrecision(6))):String(value);tr.appendChild(td);
            }
            intervalBody.appendChild(tr);
          }
        }

        for(const p of comparisons.comparisons){
          const ac=models.get(p.a),bc=models.get(p.b),tr=document.createElement('tr');
          for(const value of [ac.asset_id===bc.asset_id?ac.asset_id:ac.asset_id+' / '+bc.asset_id,ac.horizon===bc.horizon?ac.horizon:ac.horizon+' / '+bc.horizon,ac.model+' / window '+(ac.lookback??'unknown'),bc.model+' / window '+(bc.lookback??'unknown'),p.shared_n,p.paired_n,p.distinct_target_n,p.a_only_n,p.b_only_n,p.pending_shared_n,p.outcome_conflict_n+p.reference_conflict_n,p.missing_provenance_n,p.unassessed_shared_n,p.a_mae,p.b_mae,p.a_minus_b_mae,p.baseline_mae,p.a_ratio_to_baseline,p.b_ratio_to_baseline,p.status]){
            const td=document.createElement('td');td.textContent=value===null?'Unavailable':typeof value==='number'?String(Number(value.toPrecision(6))):String(value);tr.appendChild(td);
          }
          pairBody.appendChild(tr);
        }
      }
      const logBody=byId('log-loss-rows');
      if(logBody&&activeLogLoss){
        const diagnostic=logLossDiagnostics(rows,activeLogLoss.minimum_samples);
        if(byId('log-loss-status'))byId('log-loss-status').textContent=rows.length?'Visible recorded probabilities only. Natural log; no clipping, calibration or winner claim.':'No visible forecasts; no loss is inferred.';
        for(const c of diagnostic.cohorts){
          const tr=document.createElement('tr'),k=c.cohort;
          for(const value of [k.asset_id,k.model,k.horizon,c.resolved_n,c.pending_n,c.probability_n,c.distinct_target_n,c.unrecorded_probability_n,c.no_probability_n,c.infinite_loss_n,c.loss_state,c.mean_log_loss,c.half_probability_mean_log_loss,c.status]){
            const td=document.createElement('td');td.textContent=value===null?'Unavailable':String(value);tr.appendChild(td);
          }logBody.appendChild(tr);
        }
      }
      const pairedLogBody=byId('paired-log-loss-rows'),pairedLog=activeLogLoss?.paired_log_loss_diagnostics;
      if(pairedLogBody&&pairedLog){
        const query=String(byId('asset-filter').value).slice(0,80).toLowerCase(),horizon=byId('horizon-filter')?.value||'ALL';let shown=0;
        for(const p of pairedLog.comparisons){
          const a=JSON.parse(p.a),b=JSON.parse(p.b);if((!a.asset_id.toLowerCase().includes(query)&&!b.asset_id.toLowerCase().includes(query)) || (horizon!=='ALL'&&a.horizon!==horizon&&b.horizon!==horizon))continue;shown++;
          const tr=document.createElement('tr');
          for(const value of [a.asset_id===b.asset_id?a.asset_id:a.asset_id+' / '+b.asset_id,a.model+' / '+String(a.lookback??'unknown'),b.model+' / '+String(b.lookback??'unknown'),p.shared_n,p.point_paired_n,p.probability_paired_n,p.a_only_n,p.b_only_n,p.pending_shared_n,p.missing_probability_n,p.outcome_conflict_n,p.reference_conflict_n,p.distinct_target_n,p.a_loss_state,p.b_loss_state,p.a_mean_log_loss,p.b_mean_log_loss,p.difference_state,p.a_minus_b_mean_log_loss,p.status]){
            const td=document.createElement('td');td.textContent=value===null?'Unavailable':String(value);tr.appendChild(td);
          }pairedLogBody.appendChild(tr);
        }
        if(byId('paired-log-loss-status'))byId('paired-log-loss-status').textContent=`${shown} of ${pairedLog.comparisons.length} imported pairs shown. ${pairedLog.status}. Asset/horizon display only; outcome-state and model controls do not rescore this fixed paired plan.`;
      }
      byId('visible-count').textContent = `${rows.length} of ${active.rows.length} forecasts shown`;
    }
    const loader = createLoader(state => {
      const withLogLoss=state.report?.[logLossImport]===true;
      active = withLogLoss?state.report.source_report:state.report;
      activeLogLoss=withLogLoss?state.report.diagnostics:null;
      byId('load-status').textContent = withLogLoss?'Recorded log loss reconciled with supplied report rows. Source truth, calibration and market skill remain unestablished.':state.message;
      byId('load-status').setAttribute('role', state.status === 'REFUSED' ? 'alert' : 'status');
      byId('forecast-count').textContent = active ? String(active.forecast_n) : '—';
      byId('resolved-count').textContent = active ? String(active.score.scored_n) : '—';
      byId('correction-count').textContent = active ? String(active.correction_n) : '—';
      byId('report-asof').textContent = active ? active.asof : 'No evidence loaded';
      byId('visible-count').textContent = active ? '' : 'No forecasts shown';
      draw();
    },digest,async(text,hash)=>{
      if(['AFI_LOG_LOSS_BROWSER_V1','AFI_LOG_LOSS_BROWSER_V2'].includes(parse(text)?.schema))return {...await verifyLogLossEnvelope(text,hash),[logLossImport]:true};
      return verifyEnvelope(text,hash);
    });
    const priorLoader=createLoader(state=>{
      priorReport=state.report;
      if(byId('prior-load-status'))byId('prior-load-status').textContent=state.message;
      draw();
    },digest,async(text,hash)=>{
      if(['AFI_LOG_LOSS_BROWSER_V1','AFI_LOG_LOSS_BROWSER_V2'].includes(parse(text)?.schema))return (await verifyLogLossEnvelope(text,hash)).source_report;
      return verifyEnvelope(text,hash);
    });
    byId('prior-report-file')?.addEventListener('change',event=>priorLoader.loadFile(event.target.files[0]));
    byId('report-file').addEventListener('change', event => loader.loadFile(event.target.files[0]));
    byId('clear-report').addEventListener('click', () => { byId('report-file').value = ''; if(byId('prior-report-file'))byId('prior-report-file').value=''; loader.clear(); priorLoader.clear(); });
    const redraw=()=>{try{draw();}catch{loader.clear();byId('load-status').textContent='Visible evidence could not be calculated. Reload a valid report.';byId('load-status').setAttribute('role','alert');}};
    byId('horizon-filter')?.addEventListener('input', redraw);
    byId('plot-cohort')?.addEventListener('input', redraw);
    byId('memory-query')?.addEventListener('input', redraw);
    for (const id of ['asset-filter', 'state-filter', 'sort-order']) byId(id).addEventListener('input', redraw);
    for(const id of ['compare-a','compare-b'])byId(id)?.addEventListener('input',redraw);
    byId('auto-pairs')?.addEventListener('click',()=>{byId('compare-a').value='';byId('compare-b').value='';redraw();});
    loader.clear();
  }
  return { priorCaseContext, renderPriorCases, forecastPlot, renderForecastPlot, PACKET_LIMIT, signedErrorVintageImpact, comparisonSourcePins, createComparisonPacket, verifyComparisonPacket, compareReportVintages, verifyEnvelope, validate, instant, signedErrorDiagnostics, intervalTargetSupport, intervalDiagnostics, directionalDiagnostics, visibleErrors, pairedDiagnostics, pairedIntervalDiagnostics, pairedProbabilityDiagnostics, probabilityReliability, reliabilityDiagnostics, logLossDiagnostics, pairedLogLossDiagnostics, verifyLogLossEnvelope, selectRows, createLoader, mount, LIMIT };
});
