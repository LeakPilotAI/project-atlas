
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync(
  'backend/app/static/quality_dips.html', 'utf8'
);

const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function harness() {
  const elements = {};
  let response = null;
  const requests = [];

  const document = {
    getElementById(id) {
      return elements[id] ??= {
        textContent: '',
        innerHTML: '',
        hidden: false,
        value: id === 'stateFilter' ? 'all' : '',
        style: {},
        classList: {
          toggle() {},
          remove() {},
          add() {}
        },
        setAttribute() {},
        addEventListener() {},
        scrollIntoView() {}
      };
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector(selector) {
      if (selector === 'meta[name="atlas-observation"]') {
        return { content: 'readonly' };
      }
      return { scrollIntoView() {} };
    },
    body: {
      classList: {
        toggle() {}
      }
    }
  };

  const context = vm.createContext({
    document,
    location: { search: '' },
    URLSearchParams,
    AbortController,
    atlasPoll() {},
    async atlasFetch(url) {
      requests.push(url);

      if (response instanceof Error) {
        throw response;
      }

      return response;
    }
  });

  vm.runInContext(script, context);

  return {
    elements,
    requests,
    context,
    setResponse(value) {
      response = value;
    },
    run(code) {
      return vm.runInContext(code, context);
    },
    async load() {
      return context.load();
    }
  };
}

function research(symbol) {
  return {
    board: [{
      symbol,
      quote_display_price: 100,
      quote_quality: 'LIVE',
      opportunity_score: 80,
      stance: 'WATCH',
      evidence_quality: 'HIGH',
      quality_dips_v2: {
        patient_state: 'WATCH',
        quality_dips_v3: {
          patient_state: 'WATCH',
          blockers: [],
          entry_ladder: {
            ready: false,
            levels: []
          }
        }
      }
    }],
    runtime_refresh: {
      state: 'FRESH',
      age_sec: 1
    }
  };
}

function success(payload) {
  return {
    ok: true,
    status: 200,
    json: async () => payload
  };
}

function unavailable() {
  return {
    ok: false,
    status: 503,
    json: async () => ({ detail: 'UNAVAILABLE' })
  };
}

test('observation research clears on 503 and recovers', async () => {
  const h = harness();

  h.setResponse(success(research('MSFT')));
  await h.load();

  assert.ok(
    h.requests.includes('/api/observation/quality-dips'),
    'Observation endpoint was not requested'
  );

  assert.match(h.elements.board.innerHTML, /MSFT/);

  h.run("selectedSymbol='MSFT'; renderSelection()");
  assert.match(h.elements.selectedTitle.textContent, /MSFT/);

  h.setResponse(unavailable());
  await h.load();

  assert.match(
    h.elements.status.textContent,
    /VERIFIED RESEARCH UNAVAILABLE/
  );

  assert.doesNotMatch(h.elements.board.innerHTML, /MSFT/);
  assert.doesNotMatch(h.elements.selectedTitle.textContent, /MSFT/);
  assert.equal(h.elements.evidenceCount.textContent, 'UNAVAILABLE');
  assert.equal(h.elements.quoteCount.textContent, 'UNAVAILABLE');
  assert.equal(h.elements.candidateCount.textContent, 'UNAVAILABLE');
  assert.equal(h.elements.evidenceProgress.hidden, true);
  assert.equal(h.elements.pipeline.innerHTML, '');
  assert.equal(h.elements.forwardSummary.innerHTML, '');
  assert.equal(h.elements.diagnostics.innerHTML, '');

  h.run("setView('watch')");

  assert.doesNotMatch(h.elements.board.innerHTML, /MSFT/);

  h.setResponse(success(research('AAPL')));
  await h.load();

  assert.match(h.elements.board.innerHTML, /AAPL/);
  assert.doesNotMatch(h.elements.board.innerHTML, /MSFT/);
});

test('ordinary network failure preserves stale research', async () => {
  const h = harness();

  h.setResponse(success(research('MSFT')));
  await h.load();

  h.setResponse(new Error('offline'));
  await h.load();

  assert.match(
    h.elements.status.textContent,
    /last good research preserved/
  );

  assert.match(h.elements.board.innerHTML, /MSFT/);
});
test('real transport thrown HTTP503 clears prior research and navigation remains unavailable',async()=>{
 const h=harness();h.setResponse(success(research('MSFT')));await h.load();
 h.setResponse(Object.assign(new Error('HTTP 503'),{status:503}));await h.load();
 assert.equal(h.elements.candidateCount.textContent,'UNAVAILABLE');
 assert.doesNotMatch(h.elements.selectedTitle.textContent,/MSFT/);
 assert.match(h.elements.sourceHealth.textContent,/UNAVAILABLE/);
 h.run("setView('watch')");assert.match(h.elements.board.innerHTML,/No accepted research evidence/);
 h.setResponse(success(research('SPY')));await h.load();assert.match(h.elements.board.innerHTML,/SPY/);
});
