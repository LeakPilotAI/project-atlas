// Isolated render fixtures. These are never served by the application.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('backend/app/static/quality_dips.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = {};
let payload, unavailable = false, pollMs, requested;
const document = {
  getElementById(id) {
    return elements[id] ??= {
      textContent: '', innerHTML: '', hidden: false, value: id === 'stateFilter' ? 'all' : '',
      style: {}, addEventListener() {}, scrollIntoView() {},
    };
  },
  addEventListener() {}, querySelectorAll() { return []; },
  querySelector() { return {scrollIntoView() {}}; },
};
const context = vm.createContext({
  document,
  atlasPoll(fn, ms) { pollMs = ms; },
  async atlasFetch(url) {
    requested = url;
    if (unavailable) throw Error('offline');
    return {ok: true, json: async () => payload};
  },
});
vm.runInContext(script, context);
const run = code => vm.runInContext(code, context);
const row = (symbol, state = 'WATCH') => ({
  symbol, quote_display_price: 100, quote_quality: 'LIVE', opportunity_score: 80,
  stance: 'ACCUMULATE', thesis: 'STRONG', evidence_quality: 'HIGH',
  quality_dips_v2: {patient_state: 'WATCH', quality_dips_v3: {
    patient_state: state, fair_value_anchor: 150, discount_to_fair_value_pct: 33.3,
    blockers: ['test evidence blocker'], entry_ladder: {ready: false, levels: [
      {level: 'L1', margin_of_safety_pct: 15, limit_price: 127.5},
      {level: 'L4', margin_of_safety_pct: 30, limit_price: 105},
    ]},
  }},
});
async function check() {
  assert.equal(pollMs, 10000);
  assert.equal(run('num(null)'), '—');
  assert.equal(run('pct(undefined)'), '—');
  assert.equal(run('num(0)'), '0');
  assert.equal(run('money(null)'), '—');
  // Initial network failure differs from an empty, valid research universe.
  unavailable = true;
  await context.load();
  assert.match(elements.status.textContent, /temporarily unavailable/);
  assert.equal(elements.selectedPrice.textContent, '—');
  unavailable = false;
  payload = {board: [], runtime_refresh: {state: 'WARMING'}};
  await context.load();
  assert.equal(requested, '/api/investments/quality-dips?limit=50');
  assert.match(elements.board.innerHTML, /warming/);
  assert.equal(elements.evidenceCount.textContent, '— / —');
  assert.equal(elements.evidenceProgress.hidden, true);
  // Legacy ACCUMULATE and a large discount must not create V3 qualification.
  payload = {board: [row('AAA'), row('BBB', 'ACCUMULATION')], runtime_refresh: {state: 'FRESH', age_sec: 1}};
  await context.load();
  assert.match(elements.candidateNote.textContent, /^1 V3 qualified/);
  run("setView('qualified')");
  assert.doesNotMatch(elements.board.innerHTML, /Inspect AAA/);
  assert.match(elements.board.innerHTML, /Inspect BBB/);
  run("setView('watch')");
  assert.match(elements.board.innerHTML, /Inspect AAA/);
  assert.doesNotMatch(elements.board.innerHTML, /Inspect BBB/);
  run("setView('overview'); selectedSymbol='BBB'; renderSelection()");
  assert.match(elements.selectedTitle.textContent, /BBB/);
  assert.match(elements.levels.innerHTML, /L4/);
  assert.match(elements.eligibility.innerHTML, /test evidence blocker/);
  payload.board[1].quote_display_price = 102;
  await context.load();
  assert.match(elements.selectedTitle.textContent, /BBB/);
  assert.equal(elements.selectedPrice.textContent, '$102');
  const priorBoard = elements.board.innerHTML;
  unavailable = true;
  await context.load();
  assert.equal(elements.board.innerHTML, priorBoard);
  assert.equal(elements.selectedPrice.textContent, '$102');
  assert.equal(elements.priceLabel.textContent, 'LAST SUPPORTED PRICE');
  assert.equal(elements.selectedState.textContent, 'STALE');
  assert.match(elements.status.textContent, /last good research preserved/);
  unavailable = false;
  await context.load();
  assert.equal(elements.priceLabel.textContent, 'LIVE SUPPORTED PRICE');
  payload.runtime_refresh.state = 'STALE';
  await context.load();
  assert.equal(elements.priceLabel.textContent, 'LAST SUPPORTED PRICE');
  // Untrusted symbols/strings remain text, and absent valuations remain absent.
  payload = {board: [{symbol: '<img onerror="bad">', opportunity_score: null}], runtime_refresh: {state: 'FRESH'}};
  await context.load();
  assert.doesNotMatch(elements.board.innerHTML, /<img/);
  assert.match(elements.board.innerHTML, /&lt;img/);
  assert.equal(elements.fairValue.textContent, '—');
  assert.match(elements.levels.innerHTML, /INSUFFICIENT EVIDENCE/);
  assert.match(elements.eligibility.innerHTML, /UNAVAILABLE/);
  assert.match(elements.researchDetails.innerHTML, /INSUFFICIENT EVIDENCE/);
  payload = {board: [], runtime_refresh: {state: 'FRESH'}};
  await context.load();
  assert.equal(elements.selectedPrice.textContent, '—');
  assert.match(elements.board.innerHTML, /No investment research/);
  // Malformed response must not destroy the last valid snapshot.
  payload = {board: null};
  await context.load();
  assert.match(elements.status.textContent, /STALE/);
  console.log('Quality Dips render, selection, qualification, missing data, and recovery contracts passed');
}
check().catch(error => { console.error(error); process.exitCode = 1; });
