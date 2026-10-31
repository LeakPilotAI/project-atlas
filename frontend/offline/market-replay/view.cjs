/* Read-only replay response consumer. No fetch, storage, credentials or actions. */
'use strict';
const reject = message => { throw new Error(message); };
const finite = x => typeof x === 'number' && Number.isFinite(x);
function timestamp(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00$/.test(value)) reject('Explicit UTC timestamp required');
  const result = Date.parse(value);
  if (!Number.isFinite(result) || new Date(result).toISOString().slice(0, 19) !== value.slice(0, 19)) reject('Invalid timestamp');
  return result;
}
function microsecondTimestamp(value) {
  const epoch = timestamp(value) * 1000;
  const fraction = (/\.(\d{1,6})\+00:00$/.exec(value)?.[1] || '').padEnd(6, '0');
  const result = epoch + Number(fraction.slice(3));
  if (!Number.isSafeInteger(epoch) || !Number.isSafeInteger(result)) reject('Unsafe microsecond timestamp range');
  return result;
}
// BEGIN GENERATED BOUNDED EXCHANGE CALENDAR
// Source SHA256: ac1b63a64d565f16b1ad53889e553c5eee9632e753aeebe6248c2db2b4de648d
const exchangeCalendar = {"years":[2026,2027,2028],"holidays":["2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25","2026-06-19","2026-07-03","2026-09-07","2026-11-26","2026-12-25","2027-01-01","2027-01-18","2027-02-15","2027-03-26","2027-05-31","2027-06-18","2027-07-05","2027-09-06","2027-11-25","2027-12-24","2028-01-17","2028-02-21","2028-04-14","2028-05-29","2028-06-19","2028-07-04","2028-09-04","2028-11-23","2028-12-25"],"early_closes":["2026-11-27","2026-12-24","2027-11-26","2028-07-03","2028-11-24"]};
// END GENERATED BOUNDED EXCHANGE CALENDAR
function equitySession(value) {
  const micros = microsecondTimestamp(value);
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',weekday:'short',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(micros/1000)).filter(part => part.type !== 'literal').map(part => [part.type,part.value]));
  if (!exchangeCalendar.years.includes(Number(parts.year))) reject('Unsupported calendar year');
  const date = parts.year+'-'+parts.month+'-'+parts.day;
  if (['Sat','Sun'].includes(parts.weekday) || exchangeCalendar.holidays.includes(date)) return 'CLOSED';
  const minute = Number(parts.hour)*60+Number(parts.minute);
  if (minute < 240 || minute >= 1200) return 'CLOSED';
  if (minute < 570) return 'PRE_MARKET';
  return minute < (exchangeCalendar.early_closes.includes(date) ? 780 : 960) ? 'REGULAR' : 'AFTER_HOURS';
}
function decode(text) {
  if (typeof text !== 'string' || new TextEncoder().encode(text).length > 1000000) reject('Bounded replay export required');
  const result = JSON.parse(text, (key, item) => {
    if (['__proto__', 'constructor', 'prototype'].includes(key)) reject('Unsafe object key');
    return item;
  });
  // Native JSON parsing proves syntax; this separate token walk rejects key
  // ambiguity before any consumer trusts the parsed object. Values are inert.
  const stack = [];
  const tokens = text.match(/"(?:\\.|[^"\\])*"|[{}\[\]:,]|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g) || [];
  for (const token of tokens) {
    if (token === '{') stack.push({object:true,keys:new Set(),key:true});
    else if (token === '[') stack.push({object:false});
    else if (token === '}' || token === ']') stack.pop();
    else {
      const top = stack.at(-1);
      if (top?.object && token === ',') top.key = true;
      else if (top?.object && top.key && token.startsWith('"')) {
        const key = JSON.parse(token);
        if (top.keys.has(key)) reject('Duplicate JSON object key');
        top.keys.add(key); top.key = false;
      }
    }
  }
  return result;
}
function parseExport(text) {
  const value = decode(text);
  const expected = ['schema','mode','asof','network_authorized','trading_enabled','coverage','rows','quote_rows'];
  if (!value || typeof value !== 'object' || Object.keys(value).sort().join('|') !== expected.sort().join('|') ||
      value.schema !== 'ATLAS_MARKET_REPLAY_V1' || value.mode !== 'SYNTHETIC_REPLAY' ||
      value.network_authorized !== false || value.trading_enabled !== false ||
      value.coverage !== 'OBSERVED_BARS_ONLY_NO_GAP_IMPUTATION') reject('Replay identity/authority mismatch');
  const asof = microsecondTimestamp(value.asof);
  for (const [name, kind, source, ttl] of [
    ['rows','COMPLETED_MINUTE_BAR_CLOSE','YAHOO_CHART_SHAPED_FIXTURE',180],
    ['quote_rows','REFERENCE_QUOTE_NOT_EXECUTABLE','YAHOO_QUOTE_RESPONSE_SHAPED_FIXTURE',30]]) {
    if (!Array.isArray(value[name]) || value[name].length < 1 || value[name].length > 100) reject('Bounded rows required');
    const seen = new Set();
    for (const row of value[name]) {
      if (!row || typeof row !== 'object' || typeof row.symbol !== 'string' || !/^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(row.symbol) || seen.has(row.symbol)) reject('Unique symbols required');
      seen.add(row.symbol);
      if (['UNAVAILABLE','NOT_YET_OBSERVED'].includes(row.status)) {
        if (row.price !== null || Object.keys(row).some(k => !['symbol','status','price','reference_close'].includes(k)) ||
            ('reference_close' in row && row.reference_close !== null)) reject('Unavailable data exposed');
        continue;
      }
      const fields = name === 'rows'
        ? 'symbol asset_class currency source data_mode price_kind interval_seconds timestamp bar_end observed_at session open high low close volume status age_seconds price reference_close coverage'
        : 'symbol asset_class currency timestamp observed_at price session provider_reported_delay provider_delay_unit source data_mode price_kind status age_seconds reference_price';
      if (Object.keys(row).sort().join('|') !== fields.split(' ').sort().join('|')) reject('Unexpected or missing row fields');
      if (!['FRESH','STALE','DELAYED'].includes(row.status) || row.price_kind !== kind || row.source !== source ||
          row.data_mode !== 'SYNTHETIC_REPLAY' || row.currency !== 'USD' || !['US_EQUITY','US_ETF'].includes(row.asset_class) ||
          !['PRE_MARKET','REGULAR','AFTER_HOURS'].includes(row.session)) reject('Record identity mismatch');
      if (row.session !== equitySession(row.timestamp)) reject('Event session/calendar contradiction');
      const event = microsecondTimestamp(row.timestamp), received = microsecondTimestamp(row.observed_at);
      const effective = name === 'rows' ? microsecondTimestamp(row.bar_end) : event;
      if (received > asof || received < effective || event > asof || !Number.isSafeInteger(asof - effective) || !finite(row.age_seconds) || (asof - effective)/1000000 !== row.age_seconds) reject('Event/receipt age contradiction');
      if (name === 'rows') {
        if (effective - event !== 60000000 || event % 60000000 || row.interval_seconds !== 60 || !Number.isSafeInteger(row.volume) || row.volume < 0 ||
            !['open','high','low','close'].every(k => finite(row[k]) && row[k] > 0) ||
            row.low > Math.min(row.open,row.close) || row.high < Math.max(row.open,row.close) || row.low > row.high || row.reference_close !== row.close) reject('OHLCV contradiction');
        const coverage = row.coverage;
        if (!coverage || !['WINDOW_LIMIT','GAPS','OBSERVED_WINDOW_CONTIGUOUS'].includes(coverage.status)) reject('Coverage evidence required');
        if (coverage.status === 'WINDOW_LIMIT') {
          if (coverage.missing_minutes !== null || Object.keys(coverage).sort().join('|') !== 'missing_minutes|status') reject('Unmeasured gaps cannot be zero');
        } else {
          if (Object.keys(coverage).sort().join('|') !== 'missing_minutes|observed_bars|scope|status|window_end|window_start') reject('Unexpected coverage fields');
          if (!Number.isSafeInteger(coverage.observed_bars) || coverage.observed_bars < 1 || !Number.isSafeInteger(coverage.missing_minutes) || coverage.missing_minutes < 0 ||
              coverage.scope !== 'FIRST_TO_LAST_OBSERVED_BAR_NOT_FULL_SESSION' || microsecondTimestamp(coverage.window_end) !== event ||
              (microsecondTimestamp(coverage.window_end)-microsecondTimestamp(coverage.window_start))/60000000+1 !== coverage.observed_bars+coverage.missing_minutes ||
              (coverage.status === 'GAPS') !== (coverage.missing_minutes > 0)) reject('Coverage contradiction');
        }
      } else if (!Number.isSafeInteger(row.provider_reported_delay) || row.provider_reported_delay < 0 || row.provider_reported_delay > 86400 ||
                 row.provider_delay_unit !== 'UNVERIFIED_FIXTURE_METADATA' || !finite(row.reference_price) || row.reference_price <= 0 ||
                 (row.status === 'DELAYED') !== (row.provider_reported_delay > 0)) reject('Quote delay contradiction');
      const reference = name === 'rows' ? row.close : row.reference_price;
      if (row.status === 'FRESH') {
        if (row.age_seconds < 0 || row.age_seconds > ttl || row.price !== reference) reject('Freshness/price contradiction');
      } else if (row.price !== null) reject('Stale/delayed current price exposed');
    }
  }
  if (value.rows.map(r=>r.symbol).sort().join('|') !== value.quote_rows.map(r=>r.symbol).sort().join('|')) reject('Quote/bar universe mismatch');
  return value;
}
function reportRefusal(display, frame, error) {
  try { display(frame); }
  catch (displayError) { throw new AggregateError([error, displayError], 'Import and refusal display failed'); }
  throw error;
}
function parseMarketRefusal(text) {
  const value=decode(text);
  const fields=['schema','mode','status','http_status','reason','rows','quote_rows','source_authenticated',
    'network_authorized','startup_authorized','recovery_authorized','trading_authorized'];
  if(!value||Object.keys(value).sort().join('|')!==fields.sort().join('|')||
     value.schema!=='ATLAS_MARKET_DATA_REFUSAL_V1'||value.mode!=='SYNTHETIC_REPLAY'||value.status!=='REFUSED'||
     !Number.isSafeInteger(value.http_status)||value.http_status<400||value.http_status>599||value.http_status===409||
     !Array.isArray(value.rows)||value.rows.length||!Array.isArray(value.quote_rows)||value.quote_rows.length)reject('Exact non-success empty-data refusal required');
  for(const flag of ['source_authenticated','network_authorized','startup_authorized','recovery_authorized','trading_authorized'])if(value[flag]!==false)reject('Refusal cannot grant authority');
  const reason=({400:'INVALID_REQUEST',404:'UNKNOWN_RESOURCE',405:'METHOD_NOT_ALLOWED',422:'INVALID_REQUEST',
    500:'INTERNAL_ERROR',503:'DATA_UNAVAILABLE'})[value.http_status]??'REQUEST_REFUSED';
  if(value.reason!==reason)reject('Refusal status/reason contradiction');
  return value;
}
function createController(display) {
  if (typeof display !== 'function') reject('Explicit display adapter required');
  let current = null;
  return {
    load(text) {
      current = null; display({state:'EMPTY', rows:[], quote_rows:[]});
      try {
        current = parseExport(text);
        display({state:'REPLAY_LOADED', ...current, notice:'Synthetic replay at recorded as-of; not a live feed.'});
        return current;
      } catch (error) {
        current = null;
        return reportRefusal(display,{state:'REFUSED', rows:[], quote_rows:[], notice:'Invalid replay; prior evidence cleared.'},error);
      }
    },
    loadResponse(status,text) {
      current=null;display({state:'EMPTY',rows:[],quote_rows:[]});
      try {
        if(status===200) {
          current=parseExport(text);
          display({state:'REPLAY_LOADED',...current,notice:'Synthetic replay at recorded as-of; not a live feed.'});
          return current;
        }
        if(!Number.isSafeInteger(status)||status<400||status>599)reject('Explicit supported response status required');
        const refusal=parseMarketRefusal(text);
        if(refusal.http_status!==status)reject('Transport and refusal status disagree');
        display({state:'SOURCE_REFUSED',...refusal,notice:'Data unavailable; prior prices cleared. No cached data is current and no automatic retry is authorized.'});
        return refusal;
      } catch(error) {
        current=null;
        return reportRefusal(display,{state:'REFUSED',rows:[],quote_rows:[],notice:'Invalid response; prior prices cleared.'},error);
      }
    },
    clear() { current = null; display({state:'EMPTY',rows:[],quote_rows:[]}); },
    current() { return current; }
  };
}
function parseQuality(text) {
  const value = decode(text);
  const fields = ['schema','mode','symbol','asof','source_asof','current_market_session','freshness_threshold_seconds',
    'status','observed_bar_n','repeated_receipt_n','windows','history_window_truncated','lifecycle',
    'provider_freshness_verified','session_completeness_verified','missed_market_events_established',
    'network_authorized','startup_authorized','recovery_authorized','trading_authorized'];
  if (!value || typeof value !== 'object' || Object.keys(value).sort().join('|')!==fields.sort().join('|') ||
      value.schema!=='ATLAS_SESSION_QUALITY_V1' || value.mode!=='SYNTHETIC_REPLAY' ||
      typeof value.symbol!=='string' || !/^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(value.symbol)) reject('Quality identity mismatch');
  for (const flag of ['provider_freshness_verified','session_completeness_verified','missed_market_events_established',
    'network_authorized','startup_authorized','recovery_authorized','trading_authorized']) {
    if(value[flag]!==false) reject('Quality cannot grant acceptance or authority');
  }
  const asof=microsecondTimestamp(value.asof), source=microsecondTimestamp(value.source_asof);
  if (value.current_market_session !== equitySession(value.asof)) reject('Quality current-session contradiction');
  const count=x=>Number.isSafeInteger(x)&&x>=0&&x<=1000;
  const exchangeDate=x=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(x/1000));
  if(source>asof || !count(value.observed_bar_n) || !count(value.repeated_receipt_n) ||
     !Number.isSafeInteger(value.freshness_threshold_seconds) || value.freshness_threshold_seconds<1 || value.freshness_threshold_seconds>900 ||
     !['CLOSED','PRE_MARKET','REGULAR','AFTER_HOURS'].includes(value.current_market_session) ||
     typeof value.history_window_truncated!=='boolean' || !Array.isArray(value.windows) || value.windows.length>1000 ||
     value.observed_bar_n+value.repeated_receipt_n>1000) reject('Quality bounds/clock mismatch');
  let observed=0, previous=-Infinity;
  const keys=new Set();
  for(const row of value.windows) {
    const expected=['exchange_date','session','first_bar','last_bar','observed_bar_n','missing_minutes_between_observed_bars',
      'receipt_delay_min_seconds','receipt_delay_max_seconds','latest_completed_bar_age_seconds','status','scope'];
    if(!row || typeof row!=='object' || Object.keys(row).sort().join('|')!==expected.sort().join('|')) reject('Quality window fields mismatch');
    const first=microsecondTimestamp(row.first_bar), last=microsecondTimestamp(row.last_bar), end=last+60000000;
    if (row.session !== equitySession(row.first_bar) || row.session !== equitySession(row.last_bar)) reject('Quality window session contradiction');
    const key=row.exchange_date+'|'+row.session;
    if(!['PRE_MARKET','REGULAR','AFTER_HOURS'].includes(row.session) || keys.has(key) || first<=previous ||
       first>last || first%60000000 || last%60000000 || end>source || exchangeDate(first)!==row.exchange_date || exchangeDate(last)!==row.exchange_date ||
       !count(row.observed_bar_n) || row.observed_bar_n<1 || !count(row.missing_minutes_between_observed_bars) ||
       (last-first)/60000000+1!==row.observed_bar_n+row.missing_minutes_between_observed_bars ||
       !finite(row.receipt_delay_min_seconds) || !finite(row.receipt_delay_max_seconds) || row.receipt_delay_min_seconds<0 ||
       row.receipt_delay_max_seconds<row.receipt_delay_min_seconds || row.receipt_delay_max_seconds>(source-first-60000000)/1000000 ||
       row.receipt_delay_min_seconds>(source-end)/1000000 || !finite(row.latest_completed_bar_age_seconds) ||
       (asof-end)/1000000!==row.latest_completed_bar_age_seconds ||
       row.scope!=='FIRST_TO_LAST_OBSERVED_BAR_NOT_FULL_SESSION') reject('Quality window arithmetic mismatch');
    const current=row.exchange_date===exchangeDate(asof)&&row.session===value.current_market_session;
    const status=current?(row.latest_completed_bar_age_seconds<=value.freshness_threshold_seconds?'FRESH_AT_REPORT_CLOCK':'STALE_AT_REPORT_CLOCK'):'PAST_SESSION';
    if(row.status!==status) reject('Quality stale/session contradiction');
    previous=last;keys.add(key);observed+=row.observed_bar_n;
  }
  if(observed!==value.observed_bar_n || value.status!==(observed?'OBSERVED_WINDOWS_ONLY':'NO_OBSERVATIONS')) reject('Quality count mismatch');
  const life=value.lifecycle;
  if(!life || typeof life!=='object' || life.authenticated!==false) reject('No authenticated lifecycle authority');
  if(life.status==='NOT_SUPPLIED') {
    if(Object.keys(life).sort().join('|')!=='authenticated|status') reject('Unexpected absent lifecycle evidence');
  } else {
    if(Object.keys(life).sort().join('|')!=='authenticated|expected_head|live_process_state_verified|record_n|status' ||
       !['RECOVERY_REQUIRED','OPEN_RECORDED_SESSION','RECORDED_COMPLETE','NO_SESSION_RECORDS'].includes(life.status) ||
       !Number.isSafeInteger(life.record_n) || life.record_n<0 || life.record_n>2048 || life.live_process_state_verified!==false ||
       typeof life.expected_head!=='string' || !/^[a-f0-9]{64}$/.test(life.expected_head) ||
       (life.status==='NO_SESSION_RECORDS'?(life.record_n!==0||life.expected_head!=='0'.repeat(64)):
        life.record_n<(life.status==='OPEN_RECORDED_SESSION'?1:2))) reject('Recorded lifecycle shape mismatch');
  }
  return value;
}
function createQualityController(display) {
  if(typeof display!=='function') reject('Explicit quality display required');
  let current=null;
  return {
    load(text) {
      current=null;display({state:'EMPTY',windows:[]});
      try {
        current=parseQuality(text);
        display({state:'QUALITY_LOADED',...current,notice:current.lifecycle.status==='RECOVERY_REQUIRED'
          ?'Recorded interruption requires reconciliation; no recovery permission.'
          :'Synthetic quality at recorded clock; no live-feed or startup acceptance.'});
        return current;
      } catch(error) {
        current=null;
        return reportRefusal(display,{state:'REFUSED',windows:[],notice:'Invalid quality evidence; previous view cleared.'},error);
      }
    },
    clear(){current=null;display({state:'EMPTY',windows:[]});},
    current(){return current;}
  };
}
function parseQuoteQuality(text) {
  const value=decode(text);
  const fields=['schema','mode','asof','current_market_session','freshness_threshold_seconds','rows','status_counts',
    'provider_service_health','provider_freshness_verified','monitoring_completeness_verified','network_authorized',
    'startup_authorized','recovery_authorized','trading_authorized'];
  const states=['FRESH','STALE','DELAYED','UNAVAILABLE','NOT_YET_OBSERVED'];
  if(!value||typeof value!=='object'||Object.keys(value).sort().join('|')!==fields.sort().join('|')||
     value.schema!=='ATLAS_QUOTE_QUALITY_V1'||value.mode!=='SYNTHETIC_REPLAY'||value.provider_service_health!=='NOT_OBSERVED') reject('Quote quality identity mismatch');
  for(const flag of ['provider_freshness_verified','monitoring_completeness_verified','network_authorized','startup_authorized','recovery_authorized','trading_authorized']) {
    if(value[flag]!==false) reject('Quote quality cannot grant authority');
  }
  const asof=microsecondTimestamp(value.asof), seen=new Set(), counts=Object.fromEntries(states.map(s=>[s,0]));
  if(!Number.isSafeInteger(value.freshness_threshold_seconds)||value.freshness_threshold_seconds<1||value.freshness_threshold_seconds>120||
     !['CLOSED','PRE_MARKET','REGULAR','AFTER_HOURS'].includes(value.current_market_session)||!Array.isArray(value.rows)||value.rows.length<1||value.rows.length>100) reject('Quote quality bounds mismatch');
  for(const row of value.rows) {
    const expected=['symbol','status','event_time','receipt_time','event_age_seconds','receipt_delay_seconds',
      'reported_delay_value','reported_delay_unit','event_stale_at_report_clock','scope'];
    if(!row||typeof row!=='object'||Object.keys(row).sort().join('|')!==expected.sort().join('|')||
       typeof row.symbol!=='string'||!/^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(row.symbol)||seen.has(row.symbol)||
       !states.includes(row.status)||row.scope!=='LATEST_SUPPLIED_REFERENCE_ONLY') reject('Quote quality record mismatch');
    seen.add(row.symbol);counts[row.status]++;
    if(['UNAVAILABLE','NOT_YET_OBSERVED'].includes(row.status)) {
      if(['event_time','receipt_time','event_age_seconds','receipt_delay_seconds','reported_delay_value','reported_delay_unit','event_stale_at_report_clock'].some(k=>row[k]!==null)) reject('Unavailable quote metadata exposed');
      continue;
    }
    const event=microsecondTimestamp(row.event_time), receipt=microsecondTimestamp(row.receipt_time);
    if(event>receipt||receipt>asof||!Number.isSafeInteger(asof-event)||!Number.isSafeInteger(receipt-event)||!finite(row.event_age_seconds)||!finite(row.receipt_delay_seconds)||
       (asof-event)/1000000!==row.event_age_seconds||(receipt-event)/1000000!==row.receipt_delay_seconds||
       !Number.isSafeInteger(row.reported_delay_value)||row.reported_delay_value<0||row.reported_delay_value>86400||
       row.reported_delay_unit!=='UNVERIFIED_FIXTURE_METADATA'||typeof row.event_stale_at_report_clock!=='boolean'||
       ((row.event_age_seconds>value.freshness_threshold_seconds||value.current_market_session==='CLOSED')&&!row.event_stale_at_report_clock)) reject('Quote quality time/delay contradiction');
    const status=row.reported_delay_value?'DELAYED':row.event_stale_at_report_clock?'STALE':'FRESH';
    if(row.status!==status) reject('Quote quality state contradiction');
  }
  if(!value.status_counts||typeof value.status_counts!=='object'||Object.keys(value.status_counts).sort().join('|')!==states.sort().join('|')||
     states.some(s=>value.status_counts[s]!==counts[s])) reject('Quote quality count mismatch');
  return value;
}
function createQuoteQualityController(display) {
  if(typeof display!=='function') reject('Explicit quote quality display required');
  let current=null;
  return {
    load(text) {
      current=null;display({state:'EMPTY',rows:[],status_counts:null});
      try {
        current=parseQuoteQuality(text);
        display({state:'QUOTE_QUALITY_LOADED',...current,notice:'Synthetic quote-reference quality; no executable prices or live-feed acceptance.'});
        return current;
      } catch(error) {
        current=null;
        return reportRefusal(display,{state:'REFUSED',rows:[],status_counts:null,notice:'Invalid quote-quality evidence; previous view cleared.'},error);
      }
    },
    clear(){current=null;display({state:'EMPTY',rows:[],status_counts:null});},
    current(){return current;}
  };
}
function parseRetainedResearch(text) {
  const value=decode(text);
  const fields=['schema','mode','symbol','asof','status','analysis','sessions','source_authenticated','corporate_actions_reconciled',
    'startup_authorized','recovery_authorized','network_authorized','trading_authorized'];
  if(!value||typeof value!=='object'||Object.keys(value).sort().join('|')!==fields.sort().join('|')||
     value.schema!=='ATLAS_RETAINED_RESEARCH_V1'||value.mode!=='SYNTHETIC_REPLAY'||
     typeof value.symbol!=='string'||!/^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(value.symbol)) reject('Research identity mismatch');
  for(const flag of ['source_authenticated','corporate_actions_reconciled','startup_authorized','recovery_authorized','network_authorized','trading_authorized']) {
    if(value[flag]!==false) reject('Research cannot grant evidence/operational authority');
  }
  const asof=microsecondTimestamp(value.asof);
  if(['INSUFFICIENT_REFERENCE','INSUFFICIENT_HISTORY','REFUSED'].includes(value.status)) {
    if(value.analysis!==null||!Array.isArray(value.sessions)||value.sessions.length) reject('Unavailable research exposed metrics');
    return value;
  }
  const a=value.analysis;
  const expected=['bar_close','bar_timestamp','session','price_kind','previous_close','previous_session_date',
    'reference_source','reference_available_at','observed_change_percent','session_momentum_percent','relative_volume',
    'relative_volume_status','baseline_sessions','baseline_minimum_sessions','volume_window_completed_minutes',
    'rvol_window_policy','freshness_policy','history_window_truncated'];
  if(a&&Object.hasOwn(a,'premarket_gap_percent'))expected.push('premarket_gap_percent');
  if(value.status!=='DESCRIPTIVE_RESEARCH_ONLY'||!a||typeof a!=='object'||Object.keys(a).sort().join('|')!==expected.sort().join('|')) reject('Research metric fields mismatch');
  if (a.session !== equitySession(a.bar_timestamp)) reject('Research session/calendar contradiction');
  const bar=microsecondTimestamp(a.bar_timestamp), available=microsecondTimestamp(a.reference_available_at);
  const day=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(bar/1000));
  if(typeof a.previous_session_date!=='string'||!/^\d{4}-\d\d-\d\d$/.test(a.previous_session_date)) reject('Dated reference required');
  const referenceDay=microsecondTimestamp(a.previous_session_date+'T00:00:00+00:00');
  if(bar+60000000>asof||bar%60000000||!Number.isSafeInteger(asof-bar)||(asof-bar)>180000000||available>asof||available<referenceDay||a.previous_session_date>=day||
     !finite(a.bar_close)||a.bar_close<=0||!finite(a.previous_close)||a.previous_close<=0||
     typeof a.reference_source!=='string'||!a.reference_source.trim()||a.reference_source.length>128||a.reference_source.trim().toUpperCase()==='UNKNOWN'||
     !finite(a.observed_change_percent)||!finite((a.bar_close/a.previous_close-1)*100)||
     Math.abs(a.observed_change_percent-(a.bar_close/a.previous_close-1)*100)>0.00051||
     a.price_kind!=='COMPLETED_MINUTE_BAR_CLOSE_NOT_EXECUTABLE'||
     a.rvol_window_policy!=='EXISTING_ANALYZER_EXCLUDES_LATEST_BAR'||a.freshness_policy!=='EXISTING_ANALYZER_BAR_START_TTL_180_SECONDS'||
     typeof a.history_window_truncated!=='boolean') reject('Research clock/reference/metric contradiction');
  if(!Number.isSafeInteger(a.baseline_sessions)||a.baseline_sessions<0||a.baseline_sessions>1000||
     !Number.isSafeInteger(a.baseline_minimum_sessions)||a.baseline_minimum_sessions<2||a.baseline_minimum_sessions>60||
     !Number.isSafeInteger(a.volume_window_completed_minutes)||a.volume_window_completed_minutes<0||a.volume_window_completed_minutes>1440||
     !['BASELINE_REQUIRED','BASELINE_INSUFFICIENT','CURRENT_WINDOW_INCOMPLETE','ZERO_BASELINE','COMPARABLE_HISTORY'].includes(a.relative_volume_status)) reject('Research baseline evidence mismatch');
  if(a.relative_volume_status==='COMPARABLE_HISTORY') {
    if(!finite(a.relative_volume)||a.relative_volume<0||a.baseline_sessions<a.baseline_minimum_sessions||a.volume_window_completed_minutes<1) reject('Unsupported relative volume');
  } else if(a.relative_volume!==null) reject('Unknown relative volume must remain null');
  if((a.relative_volume_status==='BASELINE_REQUIRED'&&(a.baseline_sessions!==0||a.volume_window_completed_minutes!==0))||
     (a.relative_volume_status==='BASELINE_INSUFFICIENT'&&a.baseline_sessions>=a.baseline_minimum_sessions)||
     (a.relative_volume_status==='ZERO_BASELINE'&&(a.baseline_sessions<a.baseline_minimum_sessions||a.volume_window_completed_minutes<1))) reject('Research baseline status contradiction');
  const sessions=['PRE_MARKET','REGULAR','AFTER_HOURS'];
  if(!sessions.includes(a.session)||!Array.isArray(value.sessions)||value.sessions.length!==3) reject('Research session scope mismatch');
  let count=0;
  for(const [i,row] of value.sessions.entries()) {
    if(!row||typeof row!=='object'||Object.keys(row).sort().join('|')!=='coverage|observed_bar_n|observed_volume|session'||
       row.session!==sessions[i]||!Number.isSafeInteger(row.observed_bar_n)||row.observed_bar_n<0||row.observed_bar_n>1000) reject('Observed session metadata mismatch');
    count+=row.observed_bar_n;
    if(row.observed_bar_n===0) {
      if(row.observed_volume!==null||row.coverage!=='NO_OBSERVATIONS') reject('Unobserved volume is not zero activity');
    } else if(!Number.isSafeInteger(row.observed_volume)||row.observed_volume<0||row.coverage!=='OBSERVED_BARS_ONLY') reject('Observed volume mismatch');
  }
  const current=value.sessions.find(row=>row.session===a.session);
  const pre=value.sessions[0];
  if(pre.observed_bar_n>0?!finite(a.premarket_gap_percent):Object.hasOwn(a,'premarket_gap_percent')) reject('Premarket gap evidence mismatch');
  if(current.observed_volume===0&&a.relative_volume!==null&&a.relative_volume!==0) reject('Positive RVOL contradicts zero observed session volume');
  if(count>1000||current.observed_bar_n<1||(current.observed_bar_n<2?a.session_momentum_percent!==null:!finite(a.session_momentum_percent))) reject('Momentum evidence mismatch');
  return value;
}
function createResearchController(display) {
  if(typeof display!=='function') reject('Explicit research display required');
  let current=null;
  return {
    load(text) {
      current=null;display({state:'EMPTY',analysis:null,sessions:[]});
      try {
        current=parseRetainedResearch(text);
        display({state:'RESEARCH_LOADED',...current,notice:'Synthetic descriptive research; no forecast, order or authenticated adjustment claim.'});
        return current;
      } catch(error) {
        current=null;
        return reportRefusal(display,{state:'REFUSED',analysis:null,sessions:[],notice:'Invalid research evidence; previous view cleared.'},error);
      }
    },
    clear(){current=null;display({state:'EMPTY',analysis:null,sessions:[]});},
    current(){return current;}
  };
}
function validateResearchReplay(value) {
  const fields=['schema','mode','symbol','archive_asof','archive_sha256','references_sha256','reference_vintage_n',
    'planned_decision_n','status_counts','cases','row_decision_work','reference_policy','bar_revisions_supported',
    'source_authenticated','monitoring_completeness_verified','predictive_skill_established','network_authorized',
    'startup_authorized','recovery_authorized','trading_authorized'];
  const hash=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
  const count=(x,max)=>Number.isSafeInteger(x)&&x>=0&&x<=max;
  const states=['DESCRIPTIVE_RESEARCH_ONLY','INSUFFICIENT_REFERENCE','INSUFFICIENT_HISTORY','REFUSED'];
  if(!value||typeof value!=='object'||Object.keys(value).sort().join('|')!==fields.sort().join('|')||
     value.schema!=='ATLAS_DESCRIPTIVE_REPLAY_V1'||value.mode!=='SYNTHETIC_REPLAY'||typeof value.symbol!=='string'||
     !/^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(value.symbol)||!hash(value.archive_sha256)||!hash(value.references_sha256)||
     !count(value.reference_vintage_n,512)||!count(value.planned_decision_n,128)||value.planned_decision_n<1||
     !Array.isArray(value.cases)||value.cases.length!==value.planned_decision_n||!count(value.row_decision_work,200000)||
     value.reference_policy!=='LATEST_AVAILABLE_EXPECTED_PREVIOUS_SESSION_NO_TIE') reject('Replay identity/denominator mismatch');
  for(const flag of ['bar_revisions_supported','source_authenticated','monitoring_completeness_verified','predictive_skill_established',
    'network_authorized','startup_authorized','recovery_authorized','trading_authorized'])if(value[flag]!==false)reject('Replay cannot grant acceptance or authority');
  const cutoff=microsecondTimestamp(value.archive_asof), ids=new Set(), refs=new Set(), counts=Object.fromEntries(states.map(s=>[s,0]));
  let prior=-Infinity,work=0;
  for(const [i,row] of value.cases.entries()) {
    const expected=['index','symbol','decision_at','visible_history_sha256','reference_sha256','report_sha256','decision_sha256',
      'visible_bar_n','status','refusal_reason','report'];
    if(!row||typeof row!=='object'||Object.keys(row).sort().join('|')!==expected.sort().join('|')||row.index!==i||
       row.symbol!==value.symbol||!hash(row.visible_history_sha256)||!hash(row.report_sha256)||!hash(row.decision_sha256)||
       ids.has(row.decision_sha256)||!count(row.visible_bar_n,10000)||!states.includes(row.status)||
       (row.reference_sha256!==null&&!hash(row.reference_sha256)))reject('Replay decision identity mismatch');
    const clock=microsecondTimestamp(row.decision_at);
    if(clock<=prior||clock>cutoff)reject('Replay decision clocks must increase within archive cutoff');
    prior=clock;ids.add(row.decision_sha256);work+=row.visible_bar_n;counts[row.status]++;
    if(row.reference_sha256!==null)refs.add(row.reference_sha256);
    const report=parseRetainedResearch(JSON.stringify(row.report));
    if(report.symbol!==value.symbol||report.asof!==row.decision_at||report.status!==row.status||
       (row.status==='DESCRIPTIVE_RESEARCH_ONLY'&&(row.visible_bar_n===0||row.reference_sha256===null))||
       (row.status==='INSUFFICIENT_HISTORY'&&(row.visible_bar_n!==0||row.reference_sha256===null))||
       (row.status==='INSUFFICIENT_REFERENCE'&&row.reference_sha256!==null)||
       (row.status==='REFUSED'?!['REFERENCE_SELECTION_REFUSED','DESCRIPTIVE_ANALYSIS_REFUSED'].includes(row.refusal_reason):row.refusal_reason!==null))reject('Replay decision/report contradiction');
  }
  if(work!==value.row_decision_work||refs.size>value.reference_vintage_n||!value.status_counts||
     Object.keys(value.status_counts).sort().join('|')!==states.sort().join('|')||states.some(s=>value.status_counts[s]!==counts[s]))reject('Replay counts contradict planned decisions');
  return value;
}
async function replayDigest(text) {
  if(!globalThis.crypto?.subtle)reject('Cryptographic verification unavailable');
  const bytes=await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
  return [...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');
}
async function verifyResearchReplay(text, hash=replayDigest) {
  const envelope=decode(text);
  if(!envelope||Object.keys(envelope).sort().join('|')!=='payload_sha256|report_json|schema'||
     envelope.schema!=='ATLAS_DESCRIPTIVE_REPLAY_BROWSER_V1'||typeof envelope.report_json!=='string'||
     typeof envelope.payload_sha256!=='string'||!/^[a-f0-9]{64}$/.test(envelope.payload_sha256))reject('Exact replay browser envelope required');
  if(await hash(envelope.report_json)!==envelope.payload_sha256)reject('Replay payload digest mismatch');
  return validateResearchReplay(decode(envelope.report_json));
}
function createReplayController(display,hash=replayDigest) {
  if(typeof display!=='function')reject('Explicit replay display required');
  let current=null,revision=0;
  return {
    async load(text) {
      const own=++revision;current=null;display({state:'EMPTY',cases:[],status_counts:null});
      try {
        const report=await verifyResearchReplay(text,hash);
        if(own!==revision)return {status:'SUPERSEDED'};
        current=report;
        display({state:'REPLAY_RESEARCH_LOADED',...current,notice:'Synthetic descriptive replay; refusals remain in the denominator. No forecasting skill or trading permission.'});
        return current;
      } catch(error) {
        if(own!==revision)return {status:'SUPERSEDED'};
        current=null;
        return reportRefusal(display,{state:'REFUSED',cases:[],status_counts:null,notice:'Invalid replay; previous evidence cleared.'},error);
      }
    },
    clear(){revision++;current=null;display({state:'EMPTY',cases:[],status_counts:null});},
    current(){return current;}
  };
}
async function verifyResearchComparison(text, hash=replayDigest) {
  const envelope=decode(text);
  if(!envelope||Object.keys(envelope).sort().join('|')!=='payload_sha256|report_json|schema'||
     envelope.schema!=='ATLAS_DESCRIPTIVE_COMPARISON_BROWSER_V1'||typeof envelope.report_json!=='string'||
     typeof envelope.payload_sha256!=='string'||!/^[a-f0-9]{64}$/.test(envelope.payload_sha256))reject('Exact comparison envelope required');
  if(await hash(envelope.report_json)!==envelope.payload_sha256)reject('Comparison payload digest mismatch');
  const value=decode(envelope.report_json);
  const fields=['schema','mode','symbol','left_manifest_sha256','right_manifest_sha256','planned_pair_n','both_descriptive_n',
    'not_both_descriptive_n','same_evidence_n','changed_evidence_n','status_pair_counts','pairs','comparison_policy',
    'sources_reproduced','source_archives_required','source_authenticated','predictive_skill_established','network_authorized',
    'startup_authorized','recovery_authorized','trading_authorized'];
  const states=['DESCRIPTIVE_RESEARCH_ONLY','INSUFFICIENT_REFERENCE','INSUFFICIENT_HISTORY','REFUSED'];
  const metrics=['observed_change_percent','session_momentum_percent','relative_volume','premarket_gap_percent'];
  const digest=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
  if(!value||Object.keys(value).sort().join('|')!==fields.sort().join('|')||
     value.schema!=='ATLAS_DESCRIPTIVE_COMPARISON_V1'||value.mode!=='SYNTHETIC_REPLAY'||
     typeof value.symbol!=='string'||!/^[A-Z0-9][A-Z0-9.\-]{0,11}$/.test(value.symbol)||
     !digest(value.left_manifest_sha256)||!digest(value.right_manifest_sha256)||
     !Number.isSafeInteger(value.planned_pair_n)||value.planned_pair_n<1||value.planned_pair_n>128||
     !Array.isArray(value.pairs)||value.pairs.length!==value.planned_pair_n||
     value.comparison_policy!=='IDENTICAL_SYMBOL_EXACT_ORDERED_CLOCKS_NO_DROPPED_DECISIONS'||
     value.sources_reproduced!==true||value.source_archives_required!==true)reject('Comparison scope/denominator mismatch');
  for(const flag of ['source_authenticated','predictive_skill_established','network_authorized','startup_authorized','recovery_authorized','trading_authorized'])if(value[flag]!==false)reject('Comparison cannot grant authority or skill');
  const matrix=Object.fromEntries(states.map(a=>[a,Object.fromEntries(states.map(b=>[b,0]))]));
  let prior=-Infinity,bothN=0,sameN=0;
  for(const row of value.pairs) {
    if(!row||Object.keys(row).sort().join('|')!=='both_descriptive|decision_at|left_decision_sha256|left_status|metrics|right_decision_sha256|right_status|same_evidence'||
       !digest(row.left_decision_sha256)||!digest(row.right_decision_sha256)||!states.includes(row.left_status)||!states.includes(row.right_status))reject('Comparison pair identity mismatch');
    const clock=microsecondTimestamp(row.decision_at),both=row.left_status===row.right_status&&row.left_status==='DESCRIPTIVE_RESEARCH_ONLY';
    const same=row.left_decision_sha256===row.right_decision_sha256;
    if(clock<=prior||row.both_descriptive!==both||row.same_evidence!==same||(same&&row.left_status!==row.right_status))reject('Comparison pair evidence contradiction');
    prior=clock;bothN+=Number(both);sameN+=Number(same);matrix[row.left_status][row.right_status]++;
    if(!row.metrics||Object.keys(row.metrics).sort().join('|')!==metrics.toSorted().join('|'))reject('Exact comparison metrics required');
    for(const name of metrics) {
      const m=row.metrics[name];
      if(!m||Object.keys(m).sort().join('|')!=='availability|left|right|right_minus_left'||
         (m.left!==null&&!finite(m.left))||(m.right!==null&&!finite(m.right))||(!both&&(m.left!==null||m.right!==null)))reject('Comparison observed metric mismatch');
      const available=m.left!==null&&m.right!==null;
      const label=available?'BOTH_OBSERVED':m.left!==null?'LEFT_ONLY':m.right!==null?'RIGHT_ONLY':'UNAVAILABLE';
      if(m.availability!==label||(available?(!finite(m.right_minus_left)||m.right_minus_left!==m.right-m.left):m.right_minus_left!==null)||
         (same&&m.left!==m.right)||(name==='relative_volume'&&((m.left!==null&&m.left<0)||(m.right!==null&&m.right<0))))reject('Missing metric cannot become zero or observed difference');
    }
  }
  if(value.both_descriptive_n!==bothN||value.not_both_descriptive_n!==value.planned_pair_n-bothN||
     value.same_evidence_n!==sameN||value.changed_evidence_n!==value.planned_pair_n-sameN||
     !value.status_pair_counts||Object.keys(value.status_pair_counts).sort().join('|')!==states.toSorted().join('|'))reject('Comparison totals mismatch');
  for(const a of states)if(!value.status_pair_counts[a]||Object.keys(value.status_pair_counts[a]).sort().join('|')!==states.toSorted().join('|')||
    states.some(b=>value.status_pair_counts[a][b]!==matrix[a][b]))reject('Comparison status matrix mismatch');
  return value;
}
function createComparisonController(display,hash=replayDigest) {
  if(typeof display!=='function')reject('Explicit comparison display required');
  let current=null,revision=0;
  return {
    async load(text) {
      const own=++revision;current=null;display({state:'EMPTY',pairs:[],status_pair_counts:null});
      try {
        const report=await verifyResearchComparison(text,hash);
        if(own!==revision)return {status:'SUPERSEDED'};
        current=report;display({state:'COMPARISON_LOADED',...report,notice:'Synthetic descriptive comparison. Unknown values stay unknown; no forecast winner or trading permission.'});
        return current;
      } catch(error) {
        if(own!==revision)return {status:'SUPERSEDED'};
        current=null;
        return reportRefusal(display,{state:'REFUSED',pairs:[],status_pair_counts:null,notice:'Invalid comparison; previous evidence cleared.'},error);
      }
    },
    clear(){revision++;current=null;display({state:'EMPTY',pairs:[],status_pair_counts:null});},
    current(){return current;}
  };
}
async function verifyVintageReplay(text,hash=replayDigest) {
  const envelope=decode(text);
  if(!envelope||Object.keys(envelope).sort().join('|')!=='payload_sha256|report_json|schema'||
     envelope.schema!=='ATLAS_VINTAGE_REPLAY_BROWSER_V1'||typeof envelope.report_json!=='string'||
     typeof envelope.payload_sha256!=='string'||!/^[a-f0-9]{64}$/.test(envelope.payload_sha256))reject('Exact vintage envelope required');
  if(await hash(envelope.report_json)!==envelope.payload_sha256)reject('Vintage payload digest mismatch');
  const value=decode(envelope.report_json);
  const fields=['schema','mode','symbol','archive_asof','archive_sha256','references_sha256','planned_decision_n','status_counts',
    'cases','receipt_decision_work','bar_revision_policy','bar_revisions_supported','source_authenticated',
    'monitoring_completeness_verified','predictive_skill_established','network_authorized','startup_authorized','recovery_authorized','trading_authorized'];
  if(!value||Object.keys(value).sort().join('|')!==fields.sort().join('|')||value.schema!=='ATLAS_VINTAGE_RESEARCH_REPLAY_V1'||
     value.bar_revisions_supported!==true||value.bar_revision_policy!=='RECEIPT_ORDERED_VALUE_CHANGES_UNCHANGED_CONFIRMATIONS_KEEP_FIRST_RECEIPT'||
     !Array.isArray(value.cases)||value.cases.length<1||value.cases.length>128||
     !Number.isSafeInteger(value.receipt_decision_work)||value.receipt_decision_work<0||value.receipt_decision_work>200000)reject('Vintage replay policy/work mismatch');
  const extra=['visible_receipt_n','receipt_head','correction_n','confirmation_n','vintage_decision_sha256'];
  const refs=new Set(),selected=[];
  let work=0,barWork=0,priorN=0,priorBarN=0,priorCorrections=0,priorConfirmations=0,priorHead='0'.repeat(64);
  for(const row of value.cases) {
    if(!row||typeof row!=='object'||extra.some(key=>!Object.hasOwn(row,key))||
       ['visible_receipt_n','correction_n','confirmation_n','visible_bar_n'].some(key=>!Number.isSafeInteger(row[key])||row[key]<0||row[key]>10000)||
       typeof row.receipt_head!=='string'||!/^[a-f0-9]{64}$/.test(row.receipt_head)||
       typeof row.vintage_decision_sha256!=='string'||!/^[a-f0-9]{64}$/.test(row.vintage_decision_sha256)||
       row.visible_receipt_n!==row.visible_bar_n+row.correction_n+row.confirmation_n||row.visible_receipt_n<priorN||
       row.visible_bar_n<priorBarN||row.correction_n<priorCorrections||row.confirmation_n<priorConfirmations||
       (row.visible_receipt_n===priorN?row.receipt_head!==priorHead:row.receipt_head===priorHead))reject('Vintage receipt accounting mismatch');
    // This audit commitment contains only ASCII hashes and bounded integers, so
    // exact Python canonical JSON can be reproduced without float re-encoding.
    const audit={confirmation_n:row.confirmation_n,correction_n:row.correction_n,decision_sha256:row.decision_sha256,
      receipt_head:row.receipt_head,visible_receipt_n:row.visible_receipt_n};
    if(await hash(JSON.stringify(audit)+'\n')!==row.vintage_decision_sha256)reject('Vintage decision commitment mismatch');
    priorN=row.visible_receipt_n;priorBarN=row.visible_bar_n;priorCorrections=row.correction_n;
    priorConfirmations=row.confirmation_n;priorHead=row.receipt_head;work+=priorN;barWork+=priorBarN;
    if(row.reference_sha256!==null)refs.add(row.reference_sha256);
    selected.push(Object.fromEntries(Object.entries(row).filter(([key])=>!extra.includes(key))));
  }
  if(work!==value.receipt_decision_work)reject('Vintage work denominator mismatch');
  // Reuse strict checks on each selected single-vintage descriptive decision.
  // This internal validation view grants no authority and is never returned.
  const {receipt_decision_work,bar_revision_policy,...base}=value;
  void receipt_decision_work;void bar_revision_policy;
  validateResearchReplay({...base,schema:'ATLAS_DESCRIPTIVE_REPLAY_V1',cases:selected,
    bar_revisions_supported:false,reference_vintage_n:refs.size,row_decision_work:barWork,
    reference_policy:'LATEST_AVAILABLE_EXPECTED_PREVIOUS_SESSION_NO_TIE'});
  return value;
}
function createVintageController(display,hash=replayDigest) {
  if(typeof display!=='function')reject('Explicit vintage display required');
  let current=null,revision=0;
  return {
    async load(text) {
      const own=++revision;current=null;display({state:'EMPTY',cases:[],status_counts:null});
      try {
        const report=await verifyVintageReplay(text,hash);
        if(own!==revision)return {status:'SUPERSEDED'};
        current=report;display({state:'VINTAGE_REPLAY_LOADED',...report,notice:'Synthetic receipt-vintage research, not authenticated arrival times or forecasting skill.'});
        return current;
      } catch(error) {
        if(own!==revision)return {status:'SUPERSEDED'};
        current=null;
        return reportRefusal(display,{state:'REFUSED',cases:[],status_counts:null,notice:'Invalid vintage evidence; previous data cleared.'},error);
      }
    },
    clear(){revision++;current=null;display({state:'EMPTY',cases:[],status_counts:null});},
    current(){return current;}
  };
}
module.exports = {equitySession,parseExport, createController, parseQuality, createQualityController,parseQuoteQuality,createQuoteQualityController,
                  parseRetainedResearch,createResearchController,verifyResearchReplay,createReplayController,
                  verifyResearchComparison,createComparisonController,verifyVintageReplay,createVintageController,parseMarketRefusal};
