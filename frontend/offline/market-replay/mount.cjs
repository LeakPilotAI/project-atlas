/* Inert local-file presentation; validators are supplied explicitly. */
'use strict';
const MAX_BYTES = 1000000;
function mount(document, api) {
  const file = document.getElementById('market-file');
  const clearButton = document.getElementById('clear-market');
  const status = document.getElementById('market-status');
  const clock = document.getElementById('market-clock');
  const results = document.getElementById('market-results');
  const symbolFilter = document.getElementById('market-symbol');
  const importIdentity = document.getElementById('market-import-identity');
  const methods = ['parseQuality','parseExport','parseQuoteQuality','parseRetainedResearch','verifyResearchReplay','verifyResearchComparison','verifyVintageReplay','parseMarketRefusal'];
  if (!file || !clearButton || !status || !clock || !results || !api || methods.some(key => typeof api[key] !== 'function')) throw new Error('Complete local viewer and validators required');
  let revision = 0, disposed = false, current = null;
  function node(tag, text) { const item = document.createElement(tag); if (text !== undefined) item.textContent = String(text); return item; }
  const show = value => value === null || value === undefined ? 'Unavailable' : typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value);
  const state = value => ({FRESH:'Fresh at report clock',STALE:'Stale at report clock',DELAYED:'Delay reported',UNAVAILABLE:'Unavailable',NOT_YET_OBSERVED:'Not observed by report clock',DESCRIPTIVE_RESEARCH_ONLY:'Descriptive research only',INSUFFICIENT_REFERENCE:'Dated reference missing',INSUFFICIENT_HISTORY:'More history needed',REFUSED:'Refused'})[value] || value;
  const asset = value => ({US_EQUITY:'U.S. stock',US_ETF:'U.S. ETF'})[value] || value;
  const session = value => ({PRE_MARKET:'Premarket',REGULAR:'Regular session',AFTER_HOURS:'After hours'})[value] || value;
  function empty(message) {
    current = null;
    if (importIdentity) importIdentity.textContent = 'No decoded export identity';
    if (symbolFilter) { symbolFilter.replaceChildren(); symbolFilter.value = ''; symbolFilter.disabled = true; }
    results.replaceChildren();
    clock.textContent = 'No report loaded';
    status.textContent = message;
  }
  function panel(root, title, caption, headings, rows) {
    const section = node('section'); section.className = 'panel';
    section.append(node('h2', title));
    const scroll = node('div'); scroll.className = 'scroll'; scroll.tabIndex = 0;
    scroll.setAttribute('aria-label', title);
    const table = node('table'); table.append(node('caption', caption));
    const head = node('thead'), tr = node('tr');
    for (const heading of headings) { const cell = node('th', heading); cell.setAttribute('scope', 'col'); tr.append(cell); }
    head.append(tr); table.append(head);
    const body = node('tbody');
    for (const row of rows) { const line = node('tr'); for (const value of row) line.append(node('td', show(value))); body.append(line); }
    table.append(body); scroll.append(table); section.append(scroll); root.append(section);
  }
  function summary(root, title, items) {
    panel(root, title, 'Recorded evidence only. Missing values are unavailable, never zero.', ['Measure', 'Recorded value'], items);
  }
  function render(report) {
    const root = node('div');
    switch (report.schema) {
      case 'ATLAS_MARKET_REPLAY_V1':
        panel(root, 'Freshness across supplied symbols', 'Counts cover the full supplied symbol universe separately for bars and quotes. Fresh means fresh at the recorded report clock, not current provider health or live coverage. Missing symbols stay in the denominator.',
          ['Evidence','Supplied symbols','Fresh at report clock','Stale at report clock','Delay reported','Unavailable','Not yet observed'],
          [['Completed bars',report.rows],['Quote references',report.quote_rows]].map(([label,rows]) =>
            [label,rows.length,...['FRESH','STALE','DELAYED','UNAVAILABLE','NOT_YET_OBSERVED'].map(value => rows.filter(row => row.status === value).length)]));
        root.append(node('p', 'Displayed symbols: ' + (symbolFilter?.value || 'All supplied symbols') + '. Freshness counts above always describe the full report.'));
        panel(root, 'Completed bar closes', 'FRESH means fresh at the report clock. USD bar closes are not executable quotes. Coverage is only the observed window.',
          ['Symbol','Asset','State at report clock','Session','Usable at report clock (USD)','Last recorded close (USD)','Volume','Event UTC','Received UTC','Source label','Age seconds','Observed coverage'],
          report.rows.filter(row => !symbolFilter?.value || row.symbol === symbolFilter.value).map(row => [row.symbol,asset(row.asset_class),state(row.status),session(row.session),row.price,row.close,row.volume,row.timestamp,row.observed_at,row.source,row.age_seconds,row.coverage?.status]));
        panel(root, 'Separate quote references', 'Reference prices are not bid/ask depth, order eligibility or a live-feed claim. Vendor-delay units remain unverified.',
          ['Symbol','Asset','State at report clock','Session','Usable at report clock (USD)','Last recorded reference (USD)','Event UTC','Received UTC','Source label','Age seconds','Vendor delay - unit unverified'],
          report.quote_rows.filter(row => !symbolFilter?.value || row.symbol === symbolFilter.value).map(row => [row.symbol,asset(row.asset_class),state(row.status),session(row.session),row.price,row.reference_price,row.timestamp,row.observed_at,row.source,row.age_seconds,row.provider_reported_delay]));
        break;
      case 'ATLAS_SESSION_QUALITY_V1':
        summary(root, 'Observed-window quality', [['Symbol',report.symbol],['Evidence state',report.status],['Source cutoff UTC',report.source_asof],['Session',session(report.current_market_session)],['Observed bars',report.observed_bar_n],['Repeated receipts',report.repeated_receipt_n],['History truncated',report.history_window_truncated],['Recorded lifecycle',report.lifecycle.status],['Lifecycle authenticated',false],['Live process state verified',false]]);
        panel(root, 'Observed windows', 'First-to-last observed bars only, never full-session completeness or proof of missed market events. Recorded lifecycle is not live process health or startup/recovery permission.',
          ['Exchange date','Session','First bar UTC','Last bar UTC','Observed bars','Missing interior minutes','Minimum receipt delay seconds','Maximum receipt delay seconds','Completed-bar age seconds','State'],
          report.windows.map(row => [row.exchange_date,session(row.session),row.first_bar,row.last_bar,row.observed_bar_n,row.missing_minutes_between_observed_bars,row.receipt_delay_min_seconds,row.receipt_delay_max_seconds,row.latest_completed_bar_age_seconds,row.status]));
        if (report.status === 'NO_OBSERVATIONS') root.append(node('p','No retained observations. No session coverage, freshness or missed-event conclusion is available.'));
        if (report.history_window_truncated) root.append(node('p','History is truncated. Counts describe only the supplied retained window.'));
        if (report.lifecycle.status === 'RECOVERY_REQUIRED') root.append(node('p','Recorded interruption requires reconciliation. Recovery remains prohibited.'));
        break;
      case 'ATLAS_QUOTE_QUALITY_V1':
        summary(root, 'Quote evidence counts', Object.entries(report.status_counts).map(([key,value]) => [state(key),value]));
        panel(root, 'Quote-reference quality', 'Service health is not observed. Missing and not-yet-observed records remain in the counts; vendor delay is separate from event staleness.',
          ['Symbol','State','Event UTC','Received UTC','Event age seconds','Receipt delay seconds','Vendor delay - unit unverified','Event stale'],
          report.rows.map(row => [row.symbol,state(row.status),row.event_time,row.receipt_time,row.event_age_seconds,row.receipt_delay_seconds,row.reported_delay_value,row.event_stale_at_report_clock]));
        break;
      case 'ATLAS_RETAINED_RESEARCH_V1': {
        summary(root, 'Descriptive research', [['Symbol',report.symbol],['State',state(report.status)],['Analysis kind','Descriptive only - not a forecast']]);
        if (report.analysis !== null) {
          const a = report.analysis;
          summary(root, 'Recorded analysis', [['Bar close (USD)',a.bar_close],['Bar event UTC',a.bar_timestamp],['Session',session(a.session)],['Prior close (USD)',a.previous_close],['Prior session date',a.previous_session_date],['Reference source',a.reference_source],['Reference available UTC',a.reference_available_at],['Observed change %',a.observed_change_percent],['Session momentum %',a.session_momentum_percent],['Relative volume',a.relative_volume],['Relative-volume evidence',a.relative_volume_status],['Baseline sessions',a.baseline_sessions],['Premarket gap %',a.premarket_gap_percent]]);
          panel(root, 'Observed sessions', 'Unobserved volume stays unavailable. These totals do not establish complete session coverage.', ['Session','Observed bars','Observed volume','Scope'], report.sessions.map(row => [session(row.session),row.observed_bar_n,row.observed_volume,row.coverage]));
        }
        break;
      }
      case 'ATLAS_VINTAGE_RESEARCH_REPLAY_V1':
        summary(root, 'Receipt-vintage replay', [['Planned decisions',report.planned_decision_n],['Receipt/decision work',report.receipt_decision_work],...Object.entries(report.status_counts).map(([key,value]) => [state(key),value])]);
        panel(root, 'Every vintage decision', 'Corrections and unchanged confirmations are separate. Receipt ordering is supplied synthetic evidence, not authenticated arrival history, complete monitoring or predictive skill.',
          ['Decision UTC','State','Visible bars','Visible receipts','Corrections','Unchanged confirmations','Refusal reason','Observed change %'],
          report.cases.map(row => [row.decision_at,state(row.status),row.visible_bar_n,row.visible_receipt_n,row.correction_n,row.confirmation_n,row.refusal_reason,row.report.analysis?.observed_change_percent]));
        break;
      case 'ATLAS_DESCRIPTIVE_REPLAY_V1':
        summary(root, 'Replay plan', [['Planned decisions',report.planned_decision_n],...Object.entries(report.status_counts).map(([key,value]) => [state(key),value])]);
        panel(root, 'Every planned decision', 'All refused and unavailable decisions remain visible. Payload integrity is not independent source reproduction or forecasting skill.',
          ['Index','Decision UTC','State','Visible bars','Refusal reason','Observed change %'], report.cases.map(row => [row.index,row.decision_at,state(row.status),row.visible_bar_n,row.refusal_reason,row.report.analysis?.observed_change_percent]));
        break;
      case 'ATLAS_DESCRIPTIVE_COMPARISON_V1':
        summary(root, 'Comparison plan', [['Planned pairs',report.planned_pair_n],['Both descriptive',report.both_descriptive_n],['Not both descriptive',report.not_both_descriptive_n],['Same evidence',report.same_evidence_n],['Changed evidence',report.changed_evidence_n]]);
        panel(root, 'Every planned pair', 'No winner or profitability claim. Both source archives are needed for Python reproduction; missing differences remain unavailable.',
          ['Decision UTC','Left state','Right state','Same evidence','Both descriptive','Observed-change difference, percentage points','Momentum difference, percentage points','Relative-volume difference','Premarket-gap difference, percentage points'],
          report.pairs.map(row => [row.decision_at,state(row.left_status),state(row.right_status),row.same_evidence,row.both_descriptive,...['observed_change_percent','session_momentum_percent','relative_volume','premarket_gap_percent'].map(key => row.metrics[key].right_minus_left)]));
        break;
      case 'ATLAS_MARKET_DATA_REFUSAL_V1':
        summary(root, 'Source refused the request', [['State',state(report.status)],['Reason',report.reason],['HTTP status',report.http_status]]);
        break;
      default: throw new Error('Unsupported verified report');
    }
    return root;
  }
  async function verify(raw) {
    if (typeof raw !== 'string' || new TextEncoder().encode(raw).length > MAX_BYTES) throw new Error('Bounded local evidence required');
    const header = JSON.parse(raw);
    switch (header?.schema) {
      case 'ATLAS_MARKET_REPLAY_V1': return api.parseExport(raw);
      case 'ATLAS_SESSION_QUALITY_V1': return api.parseQuality(raw);
      case 'ATLAS_QUOTE_QUALITY_V1': return api.parseQuoteQuality(raw);
      case 'ATLAS_RETAINED_RESEARCH_V1': return api.parseRetainedResearch(raw);
      case 'ATLAS_VINTAGE_REPLAY_BROWSER_V1': return api.verifyVintageReplay(raw);
      case 'ATLAS_DESCRIPTIVE_REPLAY_BROWSER_V1': return api.verifyResearchReplay(raw);
      case 'ATLAS_DESCRIPTIVE_COMPARISON_BROWSER_V1': return api.verifyResearchComparison(raw);
      case 'ATLAS_MARKET_DATA_REFUSAL_V1': return api.parseMarketRefusal(raw);
      default: throw new Error('Unsupported local evidence');
    }
  }
  async function loadFile(input) {
    if (disposed) return {status: 'DISPOSED'};
    if (revision >= Number.MAX_SAFE_INTEGER) throw new Error('Viewer revision exhausted; reopen this file');
    const own = ++revision;
    try {
      empty('Checking local evidence...');
      if (!input || !Number.isSafeInteger(input.size) || input.size < 1 || input.size > MAX_BYTES || typeof input.text !== 'function') throw new Error('Bounded explicit file required');
      const raw = await input.text();
      if (own !== revision || disposed) return {status: 'SUPERSEDED'};
      const report = await verify(raw);
      if (own !== revision || disposed) return {status: 'SUPERSEDED'};
      let identity = '';
      if (importIdentity) {
        const bytes = new TextEncoder().encode(raw);
        const digest = await crypto.subtle.digest('SHA-256', bytes);
        if (own !== revision || disposed) return {status: 'SUPERSEDED'};
        identity = 'Decoded export text SHA-256: ' + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('') +
          ' (' + bytes.length + ' UTF-8 bytes). Identifies decoded text only; not original file-byte attestation, provider authentication or live freshness.';
      }
      if (symbolFilter && report.schema === 'ATLAS_MARKET_REPLAY_V1') {
        const all = node('option', 'All supplied symbols'); all.value = '';
        const options = report.rows.map(row => row.symbol).sort().map(symbol => { const option = node('option', symbol); option.value = symbol; return option; });
        symbolFilter.replaceChildren(all, ...options); symbolFilter.value = ''; symbolFilter.disabled = false;
      }
      const content = render(report);
      results.replaceChildren(content);
      clock.textContent = 'Report clock (UTC): ' + (report.asof || report.archive_asof || 'Exact clocks shown per pair');
      status.textContent = report.schema === 'ATLAS_MARKET_DATA_REFUSAL_V1' ? 'Source refusal loaded. No usable prices.' : 'File checked. Its source and live status are not verified; nothing connected.';
      if (importIdentity) importIdentity.textContent = identity;
      current = report;
      return {status: 'LOADED'};
    } catch (error) {
      if (own !== revision || disposed) return {status: 'SUPERSEDED'};
      current = null;
      try { empty('File refused or could not be verified. Previous evidence cleared.'); }
      catch (cleanup) { throw new AggregateError([error, cleanup], 'Import and refusal display failed'); }
      return {status: 'REFUSED'};
    }
  }
  function clear() {
    revision++;
    file.value = '';
    empty('Evidence cleared. Select a local export to begin.');
  }
  const change = () => loadFile(file.files?.[0]);
  function selectSymbol() {
    if (disposed || current === null) return;
    try {
      if (current.schema !== 'ATLAS_MARKET_REPLAY_V1' || (symbolFilter.value && !current.rows.some(row => row.symbol === symbolFilter.value))) throw new Error('Supplied symbol required');
      results.replaceChildren(render(current));
    } catch (error) {
      try { empty('Symbol view refused. Previous evidence cleared.'); }
      catch (cleanup) { throw new AggregateError([error, cleanup], 'Symbol selection and refusal display failed'); }
    }
  }
  symbolFilter?.addEventListener('change', selectSymbol);
  clearButton.addEventListener('click', clear);
  file.addEventListener('change', change);
  empty('Select a local JSON export. Maximum 1 MB; nothing is uploaded.');
  return {loadFile, clear, current: () => current === null ? null : structuredClone(current),
    dispose() { disposed = true; revision++; file.removeEventListener('change', change); clearButton.removeEventListener('click', clear); symbolFilter?.removeEventListener('change', selectSymbol); clear(); }};
}
module.exports = {mount, MAX_BYTES};
