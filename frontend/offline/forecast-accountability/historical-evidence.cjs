'use strict';

const CLASSIFICATIONS = new Set([
  'INTEGRITY_REFUSED',
  'CLAIMED_HISTORICAL_AVAILABILITY',
  'EVIDENCE_REFUSED',
  'STRUCTURALLY_CONSISTENT_UNAUTHENTICATED',
]);

function classifyHistoricalEvidence(input) {
  if (!input || typeof input !== 'object' ||
      Array.isArray(input)) {
    throw new TypeError('Historical evidence must be an object');
  }

  if (!CLASSIFICATIONS.has(input.classification)) {
    throw new TypeError('Unknown historical evidence classification');
  }

  if (typeof input.integrity_verified !== 'boolean' ||
      input.historical_availability_authenticated !== false) {
    throw new TypeError('Historical evidence authority boundary refused');
  }

  if (input.classification === 'INTEGRITY_REFUSED' &&
      input.integrity_verified !== false) {
    throw new TypeError('Contradictory integrity classification');
  }

  if (input.classification !== 'INTEGRITY_REFUSED' &&
      input.integrity_verified !== true) {
    throw new TypeError('Missing verified dataset integrity');
  }

  const descriptions = {
    INTEGRITY_REFUSED:
      'Dataset or manifest integrity verification refused.',
    CLAIMED_HISTORICAL_AVAILABILITY:
      'Historical availability is claimed but not authenticated.',
    EVIDENCE_REFUSED:
      'Historical evidence receipt was refused.',
    STRUCTURALLY_CONSISTENT_UNAUTHENTICATED:
      'Evidence is structurally consistent but unauthenticated.',
  };

  return Object.freeze({
    classification: input.classification,
    integrity_verified: input.integrity_verified,
    historical_availability_authenticated: false,
    predictive_skill_established: false,
    description: descriptions[input.classification],
  });
}

module.exports = { classifyHistoricalEvidence };
