/* Read-only selected-account presentation. No providers, writers or command POST. */
(function (root) {
  'use strict';
  const ENDPOINT = '/api/investments/quality-dips/selected-paper';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[ch]));
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const decimal = value => typeof value === 'string' && value.length <= 160 && /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value) && Number.isFinite(Number(value));
  const amount = value => decimal(value) ? '$' + esc(value) : 'UNAVAILABLE';
  const text = value => typeof value === 'string' && value.length > 0 && value.length <= 512;
  const revision = value => Number.isSafeInteger(value) && value >= 0;
  const stable = value => JSON.stringify(value, function (key, item) {
    return object(item) ? Object.fromEntries(Object.keys(item).sort().map(name => [name, item[name]])) : item;
  });
  const date = value => revision(value) ? new Date(value * 1000).toISOString() : 'UNAVAILABLE';
  const fact = (label, value) => `<div><dt>${esc(label)}</dt><dd>${value}</dd></div>`;
  const label = value => text(value) ? esc(value) : 'UNAVAILABLE';

  function renderUnified(data, now, historyFilter = "ALL") {
    if (!object(data) || data.schema !== 'ATLAS_UNIFIED_PAPER_VIEW_V1' ||
        data.startup_authorized !== false || data.total_cash !== null || data.total_equity !== null ||
        !object(data.lanes) || !['RUNNING','PAUSED','STOPPING','STOPPED','STOP_INCOMPLETE'].includes(data.state))
      return '<p>Multi-market supervision: UNAVAILABLE. No financial or startup authority.</p>';
    const rows = ['QUALITY_DIPS','HYPERLIQUID'].map(lane => {
      const row = data.lanes[lane];
      if (!object(row) || row.lane !== lane || !Number.isSafeInteger(row.at))
        return `<tr><td>${lane}</td><td colspan="4">UNAVAILABLE</td></tr>`;
      const age = now / 1000 - row.at;
      const connection = age < 0 || age > 5 ? 'STALE' :
        ['CONNECTED','DISCONNECTED','UNAVAILABLE','STALE'].includes(row.connection) ? row.connection : 'UNAVAILABLE';
      const signal = connection !== 'CONNECTED' ? 'UNAVAILABLE' : row.signal === null ? 'No validated signal — monitoring continues' : label(row.signal);
      return `<tr><td>${lane}</td><td>${connection}</td><td>${['OPEN','CLOSED','UNKNOWN'].includes(row.session) ? row.session : 'UNKNOWN'}</td><td>${signal}</td><td>${date(row.at)}</td></tr>`;
    }).join('');
    return `<h3>Unified PAPER supervision</h3><p>${esc(data.state)} · ${label(data.financial_state)}</p><div class="paperTable"><table><tr><th>Market</th><th>Connection</th><th>Session</th><th>Signal</th><th>Observation</th></tr>${rows}</table></div>${renderAccounts(data.accounts, now)}${renderTradeHistory(data.trade_history, historyFilter)}<p>Stocks respect exchange sessions; Hyperliquid monitoring runs during explicitly started desktop sessions when its feed is healthy. Perpetual collateral, funding and leverage require separate accounting. Combined cash/equity: UNAVAILABLE. No implied trading authorization.</p>`;
  }

  function renderTradeHistory(data, filter = 'ALL') {
    const groups = {ALL:null, STRATEGY:['STRATEGY_EXIT','TAKE_PROFIT'], USER:['USER_SHUTDOWN'], RISK:['STOP_LOSS','RISK_SHUTDOWN'], STOP_LOSS:['STOP_LOSS'], TAKE_PROFIT:['TAKE_PROFIT'], RISK_SHUTDOWN:['RISK_SHUTDOWN'], UNRESOLVED:['UNKNOWN']};
    if (!Object.hasOwn(groups, filter)) filter = 'ALL';
    if (!object(data) || data.schema !== 'ATLAS_EXIT_HISTORY_V1' || data.status !== 'ACKNOWLEDGED' ||
        data.startup_authorized !== false || data.total_cash !== null || data.total_net !== null || (!Array.isArray(data.rows) || data.rows.length > 256))
      return '<h3>PAPER trade history</h3><label>Exit reason <select data-paper-exit-filter aria-label="PAPER exit reason"><option value="ALL">All trades</option><option value="STRATEGY">Strategy exits</option><option value="USER">User shutdown exits</option><option value="RISK">Risk exits</option><option value="STOP_LOSS">Stop losses</option><option value="TAKE_PROFIT">Take profits</option><option value="RISK_SHUTDOWN">Risk shutdown exits</option><option value="UNRESOLVED">Unresolved exits</option></select></label><p role="status">INCOMPLETE / unresolved exits — no verified closed-trade claim.</p>' +
        (object(data) && Array.isArray(data.unresolved) ? data.unresolved.slice(0,256).map(r => object(r) ? `<p>UNKNOWN acknowledgement: ${label(r.lane)} / ${label(r.session_id)} / ${label(r.operation_id)}</p>` : '').join('') : '');
    const reasons = ['STRATEGY_EXIT','STOP_LOSS','TAKE_PROFIT','USER_SHUTDOWN','RISK_SHUTDOWN','UNKNOWN'];
    if (data.rows.some(r => !object(r) || !reasons.includes(r.reason) || !['QUALITY_DIPS','HYPERLIQUID'].includes(r.lane) ||
        r.currency !== (r.lane === 'QUALITY_DIPS' ? 'USD' : 'USDC') || !text(r.operation_id) || !text(r.session_id) ||
        !decimal(r.quantity) || !decimal(r.remaining) || !decimal(r.gross) || !decimal(r.costs) || !decimal(r.net) ||
        r.execution !== 'SIMULATED' || (r.reason === 'USER_SHUTDOWN' && !text(r.stop_command_id))))
      return '<p role="status">Trade history UNKNOWN — inconsistent evidence.</p>';
    const options = [['ALL','All trades'],['STRATEGY','Strategy exits'],['USER','User shutdown exits'],['RISK','Risk exits'],['STOP_LOSS','Stop losses'],['TAKE_PROFIT','Take profits'],['RISK_SHUTDOWN','Risk shutdown exits'],['UNRESOLVED','Unresolved exits']]
      .map(([v,n]) => `<option value="${v}"${filter === v ? ' selected' : ''}>${n}</option>`).join('');
    const rows = data.rows.filter(r => groups[filter] === null || groups[filter].includes(r.reason)).map(r =>
      `<tr><td>${esc(r.lane)} / ${esc(r.currency)}</td><td>${esc(r.session_id)}</td><td>${esc(r.reason)}</td><td>${esc(r.quantity)}</td><td>${esc(r.remaining)}</td><td>${esc(r.gross)}</td><td>${esc(r.costs)}</td><td>${esc(r.net)}</td></tr>`).join('');
    const unresolved = ['ALL','UNRESOLVED'].includes(filter) && Array.isArray(data.unresolved) ? data.unresolved.slice(0,256).map(r => object(r) ? `<p role="status">Unresolved: ${label(r.lane)} / ${label(r.position_id)} · ${label(r.state)} · remaining ${decimal(r.quantity) ? esc(r.quantity) : 'UNAVAILABLE'}. This is not a completed exit.</p>` : '').join('') : '';
    const analysis = object(data.analysis) ? ['QUALITY_DIPS','HYPERLIQUID'].map(lane => {
      const a = object(data.analysis[lane]) ? data.analysis[lane][filter] : null;
      if (!object(a) || a.currency !== (lane === 'QUALITY_DIPS' ? 'USD' : 'USDC') || !decimal(a.gross) || !decimal(a.costs) || !decimal(a.net)) return '';
      return `<p>${esc(lane)} / ${esc(a.currency)} filtered exit-fill P&amp;L: gross ${esc(a.gross)} · costs ${esc(a.costs)} · net ${esc(a.net)}. Includes committed entry-cost and realized funding allocations; complete account P&amp;L unchanged.</p>`;
    }).join('') : '';
    return `<h3>PAPER trade history</h3><label>Exit reason <select data-paper-exit-filter aria-label="PAPER exit reason">${options}</select></label>${analysis}${unresolved}<p>SIMULATED · Filtering never removes exits from complete account P&amp;L. USD and USDC remain separate. UNKNOWN means attribution unavailable, not a proven strategy exit.</p><div class="paperTable"><table><tr><th>Account</th><th>Session</th><th>Exit reason</th><th>Exit quantity</th><th>Remaining</th><th>Gross</th><th>Costs</th><th>Net</th></tr>${rows}</table></div>`;
  }

  function renderAccounts(data, now) {
    if (data == null) return '';
    if (!object(data) || data.schema !== 'ATLAS_UNIFIED_ACCOUNT_CUTS_V1' || data.state !== 'ACKNOWLEDGED' ||
        data.startup_authorized !== false || data.total_cash !== null || data.total_equity !== null || !object(data.accounts))
      return '<p role="status">Separate strategy financial cuts: UNKNOWN / UNAVAILABLE.</p>';
    return ['QUALITY_DIPS','HYPERLIQUID'].map(lane => {
      const a = data.accounts[lane], currency = lane === 'QUALITY_DIPS' ? 'USD' : 'USDC';
      if (!object(a) || a.currency !== currency || !text(a.epoch) || !revision(a.source_revision) ||
          !text(a.source_head) || !revision(a.observed_at) || !object(a.positions) || Object.keys(a.positions).length > 3 ||
          !['opening_cash','cash','gross','realized_costs','net'].every(k => decimal(a[k])) ||
          (a.available_cash !== null && !decimal(a.available_cash)) ||
          a.valuation !== null || a.valuation_status !== 'UNAVAILABLE')
        return `<p>${lane}: financial evidence UNAVAILABLE.</p>`;
      const value = v => decimal(v) ? `${esc(v)} ${currency}` : 'UNAVAILABLE';
      const age = now / 1000 - a.observed_at;
      const freshness = age < 0 || age > 5 ? 'STALE / CLOCK UNCERTAIN' : 'ACKNOWLEDGED';
      const positions = Object.values(a.positions).map(p => object(p) && text(p.symbol) && decimal(p.remaining) ?
        `${label(p.symbol)} ${label(p.side)} · ${esc(p.remaining)} remaining` : 'UNAVAILABLE').join('; ') || 'No open positions';
      const resting = object(a.resting_orders) ? Object.values(a.resting_orders).map(o => object(o) && text(o.symbol) && decimal(o.quantity) && decimal(o.limit_price) ?
        `${label(o.symbol)} ${label(o.state)} · ${esc(o.quantity)} at ${esc(o.limit_price)} (not a fill)` : 'UNAVAILABLE').join('; ') || 'None' : 'UNAVAILABLE';
      return `<h4>${lane} · separate simulated ${currency} account</h4><p>${freshness}</p><dl class="paperFacts">${fact('Epoch', label(a.epoch))}${fact('Source revision', esc(a.source_revision))}${fact('Source head', label(a.source_head))}${fact('Observed at (UTC)', date(a.observed_at))}${fact('Hypothetical opening cash', value(a.opening_cash))}${fact('Reconciled cash', value(a.cash))}${fact('Available cash', value(a.available_cash))}${fact('Realized gross P&L', value(a.gross))}${fact('Realized trading costs', value(a.realized_costs))}${fact('Realized net P&L', value(a.net))}${fact('Modeled fees', value(a.fees))}${fact('Modeled slippage', value(a.slippage))}${fact('Settled funding', value(a.funding))}${fact('Positions', positions)}${fact('Resting orders', resting)}${fact('Unrealized valuation / equity', 'UNAVAILABLE')}</dl>`;
    }).join('');
  }

  function renderMarket(data, now) {
    if (!object(data) || data.schema !== 'ATLAS_ALPACA_IEX_VIEW_V1' ||
        data.feed !== 'IEX' || data.scope !== 'SINGLE_EXCHANGE_NOT_NBBO' ||
        data.size_units !== 'ROUND_LOTS' || data.paper_startup_authorized !== false ||
        !['CONNECTED','DISCONNECTED'].includes(data.connection) ||
        typeof data.authenticated !== 'boolean' || typeof data.subscribed !== 'boolean' ||
        !Number.isFinite(data.observed_at) || !Array.isArray(data.quotes) || data.quotes.length > 30)
      return '<p class="empty">Live L1 data: UNAVAILABLE or refused. No PAPER authority.</p>';
    const rows = data.quotes.map(q => {
      if (!object(q) || !text(q.symbol) || !['FRESH','STALE','UNAVAILABLE'].includes(q.state) ||
          (q.state === 'FRESH' && (!decimal(q.bid) || !decimal(q.ask))) ||
          (q.bid != null && (!decimal(q.bid) || Number(q.bid) <= 0)) ||
          (q.ask != null && (!decimal(q.ask) || Number(q.ask) < Number(q.bid)))) throw Error('INVALID_IEX_VIEW');
      let state = q.state;
      const stamp = typeof q.timestamp === 'string' ? Date.parse(q.timestamp) : NaN;
      if (state === 'FRESH' && (data.connection !== 'CONNECTED' || !data.authenticated || !data.subscribed ||
          !Number.isFinite(stamp) || now-stamp < 0 || now-stamp > 5000 || now-data.observed_at*1000 < 0 || now-data.observed_at*1000 > 5000)) state='STALE';
      return `<tr><td>${esc(q.symbol)}</td><td>${amount(q.bid)}</td><td>${amount(q.ask)}</td><td>${Number.isSafeInteger(q.bid_lots) && q.bid_lots > 0 ? q.bid_lots : 'UNAVAILABLE'}</td><td>${Number.isSafeInteger(q.ask_lots) && q.ask_lots > 0 ? q.ask_lots : 'UNAVAILABLE'}</td><td>${esc(q.timestamp || 'UNAVAILABLE')}</td><td>${esc(state)}</td></tr>`;
    }).join('');
    return `<h3>Live L1 — Alpaca IEX</h3><p>Single exchange — NOT consolidated NBBO. Sizes are round lots, not assumed shares. Data readiness does not authorize PAPER trading.</p><p>${esc(data.connection)} · ${data.authenticated ? 'AUTHENTICATED' : 'NOT AUTHENTICATED'} · ${data.subscribed ? 'SUBSCRIBED' : 'NOT SUBSCRIBED'}</p><table><tr><th>Symbol</th><th>Bid</th><th>Ask</th><th>Bid lots</th><th>Ask lots</th><th>Exchange timestamp</th><th>State</th></tr>${rows}</table>`;
  }

  function validate(data) {
    if (!object(data) || data.schema !== 'QD_SELECTED_FINANCIAL_VIEW_V1' ||
        !['ACKNOWLEDGED','UNKNOWN','UNAVAILABLE','INCOMPLETE'].includes(data.status)) throw Error('INVALID_FINANCIAL_RESPONSE');
    if (data.status !== 'ACKNOWLEDGED') return data;
    if (!text(data.account_id) || !text(data.epoch) || !/^[a-f0-9]{64}$/.test(data.policy_digest) ||
        !revision(data.source_revision) || !revision(data.observed_at) || !data.source_identity ||
        !decimal(data.cash) || Number(data.cash) < 0 || !object(data.realized) || !object(data.positions) ||
        !['COMPLETE','INCOMPLETE','UNKNOWN','UNAVAILABLE'].includes(data.report_status) ||
        Object.keys(data.positions).length > 128) throw Error('INCOMPLETE_FINANCIAL_EVIDENCE');
    for (const key of ['gross','costs','net']) if (!decimal(data.realized[key])) throw Error('INVALID_REALIZED_EVIDENCE');
    if (Number(data.realized.costs) < 0) throw Error('INVALID_COST_EVIDENCE');
    for (const position of Object.values(data.positions)) {
      if (!object(position) || !text(position.symbol) || !decimal(position.quantity) || !decimal(position.remaining) ||
          Number(position.quantity) <= 0 || Number(position.remaining) <= 0 || Number(position.remaining) > Number(position.quantity)) throw Error('INVALID_POSITION_EVIDENCE');
    }
    if (data.projection_revision != null && (!revision(data.projection_revision) || data.projection_revision !== data.source_revision)) throw Error('PROJECTION_REVISION_MISMATCH');
    if (data.inception != null && (!object(data.inception) || data.inception.schema !== 'QD_SELECTED_INCEPTION_VIEW_V1' ||
        data.inception.account_id !== data.account_id || data.inception.epoch !== data.epoch ||
        data.inception.policy_digest !== data.policy_digest || data.inception.currency !== 'USD' ||
        !decimal(data.inception.opening_cash) || Number(data.inception.opening_cash) <= 0)) throw Error('INCEPTION_SCOPE_MISMATCH');
    if (data.report != null && (!object(data.report) || data.report.schema !== 'FS3_DAILY_REPORT_V1' ||
        data.report.account_id !== data.account_id || data.report.epoch !== data.epoch ||
        data.report.status !== data.report_status || !object(data.report.period))) throw Error('REPORT_SCOPE_MISMATCH');
    if (data.autonomous != null) {
      const a = data.autonomous;
      if (!object(a) || a.schema !== 'QD_AUTO_ACTIVITY_V1' || a.execution !== 'SIMULATED' ||
          !['RUNNING','PAUSED','STOPPING','STOPPED','STOP_INCOMPLETE'].includes(a.session_state) ||
          a.controls !== 'DISABLED_NOT_OPERATIONALLY_ACCEPTED' || !revision(a.observed_at) ||
          !['FRESH','STALE','UNAVAILABLE'].includes(a.l1_state) ||
          (a.l1 != null && (!object(a.l1) || a.l1.schema !== 'QD_AUTO_L1_V1' || !decimal(a.l1.bid) || !decimal(a.l1.ask)))) throw Error('INVALID_FINANCIAL_RESPONSE');
      if (a.shutdown_outcome != null && (!object(a.shutdown_outcome) || a.shutdown_outcome.schema !== 'QD_AUTO_SHUTDOWN_V1' ||
          a.shutdown_outcome.mode !== 'SHUTDOWN_FLATTEN' || !['FLATTENED','SHUTDOWN_INCOMPLETE'].includes(a.shutdown_outcome.status) ||
          !['FLAT','POSITION_OPEN','UNKNOWN'].includes(a.shutdown_outcome.position_state))) throw Error('INVALID_FINANCIAL_RESPONSE');
    }
    if (data.cash_cost_evidence != null && (!object(data.cash_cost_evidence) ||
        data.cash_cost_evidence.schema !== 'QD_AUTO_CASH_COSTS_V1' ||
        ['fees','slippage','unallocated_entry_costs'].some(k => !decimal(data.cash_cost_evidence[k]) || Number(data.cash_cost_evidence[k]) < 0))) throw Error('INVALID_COST_EVIDENCE');
    return data;
  }

  function render(data) {
    const positions = Object.entries(data.positions);
    const positionRows = positions.map(([id, p]) => `<tr><td>${esc(p.symbol)}</td><td class="mono">${esc(p.remaining)}</td><td class="mono">${esc(p.quantity)}</td><td>${esc(id)}</td></tr>`).join('');
    const selection = data.selection;
    let candidates = '<p class="note">Candidate selection and rejection evidence: UNAVAILABLE.</p>';
    if (object(selection) && selection.schema === 'QD_SELECTION_PRESENTATION_V1' && Array.isArray(selection.candidates) && selection.candidates.length <= 100) {
      candidates = selection.candidates.length ? selection.candidates.map(row => {
        const state = ['SELECTED','REJECTED','RESEARCH_ONLY'].includes(row.status) ? row.status : 'UNAVAILABLE';
        const reasons = Array.isArray(row.reasons) && row.reasons.length && row.reasons.every(text) ? row.reasons.map(esc).join(' · ') : 'Reasons UNAVAILABLE';
        return `<li><strong>${label(row.symbol)}</strong> · ${label(row.asset_class)} · ${state} · Rank ${revision(row.rank) && row.rank > 0 ? row.rank : 'UNAVAILABLE'}<p class="note">${reasons}</p></li>`;
      }).join('') : '<li>No candidates in this verified presentation.</li>';
      candidates = `<p class="note">Evidence basis: ${label(selection.basis)} · Cohort: ${label(selection.cohort_id)} · Generation: ${revision(selection.generation) ? selection.generation : 'UNAVAILABLE'}</p><ul class="paperCandidates">${candidates}</ul>`;
    }
    const report = data.report;
    const reportFacts = object(report) ? fact('Report date', label(report.date)) + fact('Report timezone', label(report.timezone)) +
      fact('Reporting cutoff (exclusive)', date(report.period.end_exclusive)) + fact('Effective cutoff (exclusive)', date(report.period.effective_end_exclusive)) +
      fact('Report realized fees', amount(report.realized?.fees)) + fact('Report realized slippage', amount(report.realized?.slippage)) : fact('Reporting cutoff', 'UNAVAILABLE');
    const a = data.autonomous;
    const activity = object(a) ? `<h3>Autonomous PAPER activity - SIMULATED</h3><p class="note">Informational only. Financial Start/Stop controls are disabled pending operational acceptance. Quotes are last committed evidence, not a connected live feed.</p><dl class="paperFacts">${fact('Session state', label(a.session_state))}${fact('Latest shutdown outcome', label(a.shutdown_outcome?.status))}${fact('Shutdown progress', label(a.shutdown_outcome?.phase))}${fact('Shutdown position state', label(a.shutdown_outcome?.position_state))}${fact('Shutdown unresolved error', label(a.shutdown_outcome?.reason))}${fact('Modeled fees debited from cash', amount(data.cash_cost_evidence?.fees))}${fact('Modeled slippage debited from cash', amount(data.cash_cost_evidence?.slippage))}${fact('Unallocated entry costs', amount(data.cash_cost_evidence?.unallocated_entry_costs))}${fact('Available reconciled cash', amount(data.available_cash))}${fact('Latest acknowledged decision', label(a.decision?.kind))}${fact('Decision identity', label(a.decision?.id))}${fact('Simulated quantity', label(a.decision?.quantity))}${fact('Exit reason', label(a.decision?.reason))}${fact('Last verified ranked candidate', label(a.candidate?.symbol))}${fact('L1 evidence state', label(a.l1_state))}${fact('Observed bid', amount(a.l1?.bid))}${fact('Observed ask', amount(a.l1?.ask))}${fact('Quote timestamp (UTC)', date(a.l1?.source_timestamp))}${fact('Quote provenance', label(a.l1?.provider_id))}${fact('Feed / entitlement', label(a.l1?.feed_id) + ' / ' + label(a.l1?.entitlement_id))}${fact('Latest refusal / uncertainty', label(a.latest_refusal?.reason))}${fact('Pending exit evidence', a.pending_exits == null ? 'UNAVAILABLE' : label(a.pending_exits))}</dl>` : '';
    return `${activity}<dl class="paperFacts">${fact('Account', label(data.account_id))}${fact('Epoch', label(data.epoch))}
      ${fact('Selected policy', label(data.inception?.policy_schema))}${fact('Policy identity', label(data.policy_digest))}
      ${fact('Hypothetical starting cash', amount(data.inception?.opening_cash))}${fact('Verified cash at snapshot', amount(data.cash))}
      ${fact('Source revision', String(data.source_revision))}${fact('Projection revision', revision(data.projection_revision) ? String(data.projection_revision) : 'UNAVAILABLE')}
      ${fact('Realized gross P&L', amount(data.realized.gross))}${fact('Realized net P&L', amount(data.realized.net))}
      ${fact('Realized trading costs', amount(data.realized.costs))}${fact(object(a) ? 'Realized fees' : 'Aggregate fees', amount(data.realized.fees))}${fact(object(a) ? 'Realized slippage' : 'Aggregate slippage', amount(data.realized.slippage))}
      ${fact('Total equity / unrealized valuation', 'UNAVAILABLE')}${fact('Source observed (UTC)', date(data.observed_at))}
      ${fact('Report completeness', label(data.report_status))}${fact('Lifecycle acceptance', label(data.lifecycle_status))}${reportFacts}</dl>
      <h3>Open positions in this selected account</h3><p class="note">Patient overnight holdings are permitted. This read does not close positions.</p>
      <div class="paperTable" role="region" tabindex="0" aria-label="Selected PAPER positions"><table><thead><tr><th scope="col">Instrument</th><th scope="col">Exact remaining shares</th><th scope="col">Original shares</th><th scope="col">Position identity</th></tr></thead><tbody>${positionRows || '<tr><td colspan="4">No open positions in this acknowledged projection.</td></tr>'}</tbody></table></div>
      <h3>Candidate selection / rejection</h3><p class="note">Explanations are not trade authorization. Current ranking evidence is independently required for commands.</p>${candidates}`;
  }

  function createController({document, fetch: read = root.fetch?.bind(root), clock = () => Date.now(), schedule = root.setTimeout?.bind(root), cancel = root.clearTimeout?.bind(root), Abort = root.AbortController}) {
    const status = document.getElementById('paperStatus');
    const content = document.getElementById('paperContent');
    const freshness = document.getElementById('paperFreshness');
    const market = document.getElementById('paperMarket');
    const multi = document.getElementById('paperMultiMarket');
    let historyFilter = 'ALL';
    function paintMulti(force = false) {
      if (!multi || !multiLast) return;
      const prior = multi.querySelector ? multi.querySelector('[data-paper-exit-filter]') : null;
      if (!force && prior && document.activeElement === prior) return;
      multi.innerHTML = renderUnified(multiLast, clock(), historyFilter);
      const next = multi.querySelector ? multi.querySelector('[data-paper-exit-filter]') : null;
      if (prior && next && next.replaceWith) { next.replaceWith(prior); prior.value = historyFilter; }
    }
    if (multi && multi.addEventListener) multi.addEventListener('change', event => {
      if (event.target && event.target.hasAttribute && event.target.hasAttribute('data-paper-exit-filter')) {
        historyFilter = event.target.value;
        if (multiLast) paintMulti(true);
      }
    });
    let multiLast = null;
    let marketLast = null;
    let active = false, busy = false, generation = 0, abort = null, last = null, pinned = null, high = -1, fingerprint = null, readFailed = false;
    const announce = (state, reason) => { if (status.textContent !== state) status.textContent = state; freshness.textContent = reason; };
    const clear = (state, reason) => { last = null; content.innerHTML = '<p class="empty">Financial amounts and positions are UNAVAILABLE.</p>'; announce(state, reason); };
    const age = () => {
      if (market && marketLast) { try { market.innerHTML = renderMarket(marketLast, clock()); } catch { market.innerHTML = '<p>Live L1: UNAVAILABLE</p>'; } }
      if (multi && multiLast) paintMulti();
      if (!last) return;
      const elapsed = Math.floor(clock() / 1000) - last.observed_at;
      announce(readFailed || elapsed < 0 || elapsed > 30 ? 'STALE' : 'ACKNOWLEDGED · report ' + last.report_status,
        readFailed || elapsed < 0 || elapsed > 30 ? 'Last acknowledged snapshot only — not current financial evidence.' : `${elapsed}s since source observation · cash is not total equity · no trading authority.`);
    };
    async function load() {
      if (!active || busy) return;
      age();
      busy = true;
      const ticket = generation;
      const controller = new Abort();
      abort = controller;
      const timer = schedule(() => controller.abort(), 6500);
      try {
        const response = await read(ENDPOINT, {method:'GET', cache:'no-store', credentials:'same-origin', signal:controller.signal});
        if (!response.ok) throw Error('FINANCIAL_READ_REFUSED');
        const data = validate(await response.json());
        if (!active || ticket !== generation) return;
        if (controller.signal.aborted) throw Error('FINANCIAL_READ_TIMEOUT');
        if (market) { marketLast = data.market_data || null; market.innerHTML = renderMarket(marketLast, clock()); }
        if (multi) { multiLast = data.multi_market || null; paintMulti(); }
        if (data.status !== 'ACKNOWLEDGED') { clear(data.status, Array.isArray(data.reasons) ? data.reasons.join(' · ') : 'Verified financial evidence unavailable.'); return; }
        const identity = stable([data.account_id, data.epoch, data.policy_digest]);
        if (pinned !== null && pinned !== identity) throw Error('ACCOUNT_OR_POLICY_REPLACED');
        const fresh = Math.floor(clock() / 1000) - data.observed_at;
        if (fresh < 0 || fresh > 30) { clear('STALE', 'Response source is stale or future-dated; no current amounts displayed.'); return; }
        const nextFingerprint = stable([data.cash, data.realized, data.positions, data.source_identity, data.projection_revision]);
        if (data.source_revision < high || (data.source_revision === high && fingerprint !== nextFingerprint)) throw Error('SOURCE_REVISION_ROLLBACK_OR_CONFLICT');
        const markup = render(data);
        pinned = identity; high = data.source_revision; fingerprint = nextFingerprint; last = data; readFailed = false;
        content.innerHTML = markup;
        age();
      } catch (error) {
        if (!active || ticket !== generation) return;
        if (market) { marketLast = null; market.innerHTML = '<p>Live L1: UNAVAILABLE — network or evidence refusal.</p>'; }
        if (multi) { multiLast = null; multi.innerHTML = '<p>Multi-market supervision: UNAVAILABLE — read refused.</p>'; }
        readFailed = true;
        const unsafe = ['ACCOUNT_OR_POLICY_REPLACED','SOURCE_REVISION_ROLLBACK_OR_CONFLICT','INCEPTION_SCOPE_MISMATCH','REPORT_SCOPE_MISMATCH','INCOMPLETE_FINANCIAL_EVIDENCE','INVALID_FINANCIAL_RESPONSE','INVALID_POSITION_EVIDENCE','INVALID_REALIZED_EVIDENCE','INVALID_COST_EVIDENCE','PROJECTION_REVISION_MISMATCH'].includes(error.message);
        if (unsafe) clear('UNKNOWN', error.message);
        else if (last) announce('STALE · financial read unavailable', 'Last acknowledged snapshot only — not current. No fallback to research or legacy accounts.');
        else clear('UNAVAILABLE', 'Financial read unavailable or refused. No fallback, provider refresh or startup attempted.');
      } finally {
        cancel(timer);
        if (abort === controller) abort = null;
        busy = false;
      }
    }
    return {
      load, refreshAge: age,
      setActive(value) { const next = value === true; if (active === next) return; active = next; generation += 1; if (abort) abort.abort(); if (active) { if (last) age(); else clear('UNAVAILABLE', 'Awaiting verified selected-account read. Operational endpoint is not registered.'); } },
      destroy() { active = false; generation += 1; if (abort) abort.abort(); }
    };
  }
  const api = {ENDPOINT, createController, validate, renderMarket, renderUnified, renderTradeHistory};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.AtlasSelectedPaper = api;
})(globalThis);
