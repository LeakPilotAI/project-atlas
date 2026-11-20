# R7E47W — Synthetic Observation Runner Integration

## Scope

Standalone, bounded, synthetic-only ingestion runner.

This milestone integrates existing synthetic admission,
JSON fixture validation, and durable SQLite attempt accounting.

It does not start production Atlas or Genesis, authorize network
traffic, activate trading, or create a background service.

## Verified regression evidence

- Initial R7E47W focused tests: 13 passed in 0.36 seconds.
- R7E47W focused and hardening tests: 18 passed in 0.87 seconds.
- Combined R7E47S/T/U/V/W regression: 211 passed.
- Combined regression covered 9 test files.
- Combined regression duration: 25.41 seconds.
- No failures reported.

## Implemented behavior

- Synthetic-only ProviderAdmission validation.
- Data-only bytes ingestion; executable fixtures refused.
- Bounded JSON market snapshot validation.
- Durable SQLite attempt consumption before validation.
- Failed JSON validation consumes a durable attempt.
- Multiple runner instances share the same durable budget.
- Concurrent runner tests confirm shared-budget enforcement.
- Reopening preserves previously consumed attempts.
- Exhausted budgets refuse additional ingestion.
- Terminal runner stop refuses subsequent ingestion.
- Trading and other capabilities remain unavailable.

## Important limitations

- R7E47W is not yet integrated with the R7E47S
  session admission and history lifecycle.
- No independently controlled background process exists.
- No graceful process shutdown or crash recovery has
  been demonstrated for the combined runner.
- Provider approval flags are synthetic declarations,
  not real provider authorization.
- Explicit ledger enrollment remains caller-controlled.
- The SQLite ledger is not tamper-resistant.
- No independently protected admission manifest exists.
- No aggregate wire-level request budget has been proven.
- No OS-enforced network isolation is demonstrated.
- No approved real provider transport is connected.
- No continuous market-data collection is demonstrated.
- R7E47T callable-based collection remains a separate
  prototype and is not used by the R7E47W runner.

## Release decision

R7E47W synthetic regression: GREEN.

Production Atlas and real-provider activation: NO-GO.

## Next milestone

R7E47X — Controlled synthetic session integration.

Priorities:

1. Reuse the existing R7E47S lifecycle rather than
   creating a competing production startup mechanism.
2. Define an explicit, independently controlled synthetic
   session startup and shutdown contract.
3. Integrate bounded ingestion with session history.
4. Test interruption, restart refusal, and recovery.
5. Keep all network and trading capabilities disabled.
6. Preserve existing Atlas and Genesis production states.