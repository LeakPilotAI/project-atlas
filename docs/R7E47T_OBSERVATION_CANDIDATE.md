# R7E47T - Synthetic Provider Admission and Budget Prototype

Status: SCOPED PASS - SYNTHETIC ONLY
Production release: NO-GO

## Implementation
- scripts/observation_runtime/r7e47t_candidate.py
- tests/test_r7e47t_observation_candidate.py

## Verified evidence
- R7E47T focused tests: 16 passed.
- R7E47S + R7E47T combined regression: 151 passed in 22.67 seconds.
- New candidate and test files were created without overwriting existing files.
- Existing R7E47S source and production startup paths were not modified by this milestone.

## Supported behavior
- Synthetic provider admission validation.
- Positive fixed request allowance.
- Failed fixture attempts consume allowance.
- Provider mismatch and exhausted allowance are refused.
- Explicit capability execution is refused.
- Stop prevents subsequent collection calls.

## Limitations and blocked gates
- Admission flags are synthetic inputs, not provider-rights evidence.
- Arbitrary Python fixture callbacks can perform external side effects.
- Budget accounting is in-memory, synchronous, and not durable.
- No concurrency, process isolation, network containment, or worker-drain proof.
- No real provider permissions or aggregate wire-level budgets verified.
- No protected production storage or runtime-development isolation proven.
- No production integration, real network collection, or trading authorization.

## Next action
Design and test a stricter isolated fixture interface and durable
admission/budget contract without enabling production startup.