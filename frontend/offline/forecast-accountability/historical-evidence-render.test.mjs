import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const view = require('./view.cjs');
const { classifyHistoricalEvidence } =
  require('./historical-evidence.cjs');

test('renderer exposes prior-case entry point', () => {
  assert.equal(typeof view.renderPriorCases, 'function');
});

test('missing historical evidence cannot imply authentication', () => {
  const result = classifyHistoricalEvidence({
    classification: 'CLAIMED_HISTORICAL_AVAILABILITY',
    integrity_verified: true,
    historical_availability_authenticated: false,
  });

  assert.equal(result.historical_availability_authenticated, false);
  assert.equal(result.predictive_skill_established, false);
});

test('structural consistency cannot become historical authority', () => {
  const result = classifyHistoricalEvidence({
    classification: 'STRUCTURALLY_CONSISTENT_UNAUTHENTICATED',
    integrity_verified: true,
    historical_availability_authenticated: false,
  });

  assert.equal(result.historical_availability_authenticated, false);
});

test('contradictory authority claim is refused', () => {
  assert.throws(() => classifyHistoricalEvidence({
    classification: 'STRUCTURALLY_CONSISTENT_UNAUTHENTICATED',
    integrity_verified: true,
    historical_availability_authenticated: true,
  }));
});
