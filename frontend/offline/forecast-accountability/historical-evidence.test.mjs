import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { classifyHistoricalEvidence } =
  require('./historical-evidence.cjs');

test('structural evidence remains unauthenticated', () => {
  const result = classifyHistoricalEvidence({
    classification: 'STRUCTURALLY_CONSISTENT_UNAUTHENTICATED',
    integrity_verified: true,
    historical_availability_authenticated: false,
  });

  assert.equal(result.historical_availability_authenticated, false);
  assert.equal(result.predictive_skill_established, false);
});

test('claimed availability is not authenticated', () => {
  const result = classifyHistoricalEvidence({
    classification: 'CLAIMED_HISTORICAL_AVAILABILITY',
    integrity_verified: true,
    historical_availability_authenticated: false,
  });

  assert.match(result.description, /not authenticated/);
});

test('integrity refusal remains fail closed', () => {
  const result = classifyHistoricalEvidence({
    classification: 'INTEGRITY_REFUSED',
    integrity_verified: false,
    historical_availability_authenticated: false,
  });

  assert.equal(result.integrity_verified, false);
});

test('receipt refusal does not grant authority', () => {
  const result = classifyHistoricalEvidence({
    classification: 'EVIDENCE_REFUSED',
    integrity_verified: true,
    historical_availability_authenticated: false,
  });

  assert.equal(result.historical_availability_authenticated, false);
});

test('unknown classification is refused', () => {
  assert.throws(() => classifyHistoricalEvidence({
    classification: 'AUTHENTICATED',
    integrity_verified: true,
    historical_availability_authenticated: false,
  }));
});

test('authentication claim is refused', () => {
  assert.throws(() => classifyHistoricalEvidence({
    classification: 'STRUCTURALLY_CONSISTENT_UNAUTHENTICATED',
    integrity_verified: true,
    historical_availability_authenticated: true,
  }));
});

test('contradictory integrity state is refused', () => {
  assert.throws(() => classifyHistoricalEvidence({
    classification: 'INTEGRITY_REFUSED',
    integrity_verified: true,
    historical_availability_authenticated: false,
  }));
});

test('missing integrity state is refused', () => {
  assert.throws(() => classifyHistoricalEvidence({
    classification: 'CLAIMED_HISTORICAL_AVAILABILITY',
    historical_availability_authenticated: false,
  }));
});
