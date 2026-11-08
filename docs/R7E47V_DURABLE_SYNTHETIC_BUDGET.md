# R7E47V — Durable Synthetic Attempt Budget

## Scope

Standalone, synthetic-only SQLite attempt-budget prototype.

This milestone does not authorize real provider traffic, production
startup, PAPER trading, live trading, Discord delivery, or Genesis changes.

## Verified evidence

- Windows compatibility repair: 10 focused tests passed.
- Fail-closed reopening repair: 14 focused tests passed.
- Explicit enrollment and reset regression: 16 tests passed.
- Combined R7E47S/T/U/V regression: 193 passed across 7 test files.
- Combined regression duration: 23.33 seconds.

## Implemented behavior

- Persistent SQLite accounting for synthetic attempt consumption.
- Bounded per-provider attempt allowance.
- Transactional attempt increments.
- Tested contention across separate Python processes.
- Explicit first-time enrollment.
- Ordinary reopening refuses missing databases.
- Existing databases refuse missing provider rows or budget tables.
- Windows SQLite connections are explicitly closed.
- Invalid stored counters and corrupt database content are refused.

## Important limitations

- Explicit enrollment is a caller-controlled operation, not an
  independently authorized production admission decision.
- Database deletion followed by deliberate reenrollment can reset
  accounting; this prototype is not tamper-resistant.
- Concurrent enrollment races and hostile filesystem replacement
  have not been comprehensively proven safe.
- No independently protected admission manifest exists.
- No verified aggregate wire-level provider request budget exists.
- No provider rights or rate-limit approvals are established here.
- No real provider integration or continuous background runtime
  is demonstrated by these tests.
- The R7E47T callable-based synthetic collector remains a separate
  prototype and must not be treated as a network security boundary.

## Release decision

R7E47V synthetic regression: GREEN.

Production and real-provider activation: NO-GO.

## Next steps

1. Preserve the combined regression evidence in the master roadmap.
2. Review enrollment authorization and concurrency assumptions.
3. Design an independently controlled observation-only runtime.
4. Verify provider rights and aggregate wire-level request budgets.
5. Prove isolated startup, stop, recovery, and observation persistence.
6. Keep PAPER/live orders, Discord, and Genesis disabled.