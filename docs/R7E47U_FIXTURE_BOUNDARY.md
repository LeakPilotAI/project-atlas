# R7E47U - Data-Only Synthetic Fixture Boundary

Status: SCOPED PASS - SYNTHETIC ONLY
Production authorization: NO-GO

## Files
- scripts/observation_runtime/r7e47u_fixture_boundary.py
- tests/test_r7e47u_fixture_boundary.py

## Verified evidence
- R7E47U focused tests: 26 passed in 0.25 seconds.
- Combined R7E47S/T/U regression: 177 passed in 23.01 seconds.
- New files created without overwriting existing source.
- SHA-256 hashes recorded in terminal output.

## Implemented behavior
- Accepts bounded JSON bytes, not executable fixture callbacks.
- Requires an exact five-field snapshot schema.
- Validates provider identity, symbol, timestamp, price, and volume.
- Rejects malformed data and invalid market values.
- Enforces an in-memory synthetic record-attempt allowance.
- Refuses further ingestion after stop.

## Known limitations
- No cryptographic fixture provenance or source authentication.
- No operating-system sandbox or protection from external code.
- No durable or concurrent budget enforcement.
- No real provider rights or aggregate wire-budget authorization.
- No production storage, network transport, or collector integration.
- No proof of real background-runtime safety.
- R7E47T still exposes a separate callable-based prototype;
  R7E47U does not retroactively secure that interface.
- JSON duplicate-key rejection and strict numeric-range edge
  coverage require further hardening.

## Next action
Develop durable, fail-closed synthetic budget accounting with
restart, concurrency, corruption, and recovery tests. Preserve
all existing production NO-GO decisions.