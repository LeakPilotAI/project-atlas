# Autonomous Quality Dips PAPER engine V1 â€” 2026-10-24

Status: SOURCE IMPLEMENTED / DISPOSABLE VERIFIED. Operational authority is not granted.

## Implementation

`backend/app/services/quality_dips_autonomous_paper.py` composes the existing CandidateEvidenceAdapter, entry ladder, position monitor, thesis exit policy and canonical EpochFixture transaction/replay/audit functions. It introduces explicit PAPER_EPOCH_AUTONOMOUS_QD_V1, QD_AUTO_COMMAND_V1 and QD_AUTO_RECEIPT_V1 contracts. Existing manual and operational schemas retain their authorization semantics. No operational dispatch, API registration, startup hook or default authority was added.

Injected bounded session grants authorize automatic decisions without individual trade confirmations. Fresh, mapped, provenance-bound QD_AUTO_L1_V1 evidence supplies ASK entries and BID exits. Session/calendar, entitlement declaration, spread, displayed share size, participation, sequence reuse and fractional execution rules are checked. An injected source verifier must authenticate the entire evidence request; synthetic tests do not authenticate real feeds, rights, exchange calendars or liquidity.

Sizing enforces $100 notional, available cost-inclusive cash, one long position and no scale-in. The existing monitor's deterioration review triggers a versioned cumulative partial target; terminal thesis evidence triggers remaining-quantity exit, subject to valid liquidity. Price appreciation alone does not invalidate the patient thesis. Every hypothetical receipt is SIMULATED.

The shared accounting kernel now has an explicitly versioned automatic branch: entry fees/slippage debit cash immediately, entry costs allocate proportionally to exits, and exit cash deducts only exit-side costs. Independent arithmetic audit recomputes quantities, deferred costs, gross/net realized P&L, cash and L1 consumption. Existing historical/manual cost contracts remain unchanged.

RUNNING, PAUSED, STOPPING, STOPPED and STOP_INCOMPLETE are recorded in a chained disposable control history. Pause blocks entries while allowing authorized protective management. Stop closes local entry/dispatch admission before waiting for the ledger transaction, drains acknowledged work and preserves open positions. It never liquidates. Restart has no active grant and never resumes automatically; reused grants refuse. Commit-before-ack remains UNKNOWN and prevents replay, complete reports and clean Stop.

## Files

- backend/app/services/quality_dips_autonomous_paper.py â€” orchestrator, evidence, sessions and lifecycle.
- backend/app/services/paper_financial_replay.py â€” explicit autonomous accounting dispatch.
- backend/app/services/paper_financial_audit.py â€” independent autonomous arithmetic verification.
- backend/app/services/paper_epoch_fixture.py â€” transactional command callback and disposable control history.
- tests/test_quality_dips_autonomous_paper.py â€” 35 new cases.

## Validation

Final native combined selection: **402 passed, 0 failed, 0 skipped in 23.51 seconds**. This is 35 new cases plus 367 neighboring cases, counted once. Selection: autonomous engine, epoch fixture, strategy fixture, selected policy, operational contract, QD integration V1, one-time publisher, PAPER release policy and production startup lock. Earlier 399-case run and focused runs overlap and are not added.

The automatic buy/partial/full scenario ends with cash 1015.9136, gross realized 16, costs 0.0864 and net realized 15.9136 from synthetic opening cash 1000. Tests include ranked ETF selection, stale/missing/closed/halted/insufficient L1 refusal, cumulative quote consumption, duplicate/concurrent entries, cost-inclusive cash constraints, partial target limits, Pause/Stop races, expired/revoked grants, clock rollback, malformed quantities, corruption and independent audit. Two actual disposable subprocess exits exercise commit-before-ack and after-ack restart boundaries. These are not physical power-loss tests.

Original failure evidence is retained locally: an initial string-format assertion expected trailing zeroes although Decimal value was correct; assertion now compares exact Decimal values. A sandbox combined attempt stalled after 62 progress cases and was interrupted by terminating only its verified test-owned process. It is not counted as a successful run or a completed failed-test count; the exact stalled cause is unproven. The native final selection above completed without changing safeguards. No privilege-dependent attack probe was added or claimed.

Ruff, Python compilation, release-policy source audit and diff checks are required for publication; their final results are recorded in the continuation/state. No frontend or Windows source changed, and no browser/HTTP/native operational acceptance is claimed.

## Remaining boundaries and next work

The durable integration in this milestone is the existing disposable SQLite ledger, not an operational FS2/FS3 financial writer. Synthetic session/source authorities are injected test doubles, never operational approval. Next bounded source task: adapt the existing native publication/projection interface to the explicit autonomous contract in disposable application tests, expose its read-only session/L1/decision/account status through the existing selected-account presentation, and verify UNKNOWN/admission/report ordering end to end. Do not create another accounting engine or register protected dispatch without separate approval.

Live L1 requires independently accepted provider rights, instrument mapping, authenticated current ranking/quote/calendar/halt evidence, realistic size/participation policy and disconnection acceptance. Runtime completion additionally requires accepted autonomous profile, B1 account scope, C1 actual writer/process roster and drain, D1 issuer/storage/current custody/clock/recovery and E1 provider/supervised release evidence. Existing strict contracts are not relabeled. Seven-session and 30â€“60-session trials remain unstarted.

All seven roadmap phases and 21 decisions remain unchanged: Phase 2 HOLD, Phase 3 BLOCKED. B1/C1/D1/E1 BLOCKED. Real 13 directories and historical financial sources were not accessed or changed. Original frontend unchanged. D:-only, existing Windows account, no VPS, Genesis untouched, no live-money implementation. PAPER startup NO; production NO-GO.

Final publication checks: Ruff passed for all five changed Python files; all five compiled; PAPER static audit inspected 560 runtime source files with zero issues; diff whitespace check passed. Raw roadmap backup equality, managed exact read-back, unchanged historical prefix/suffix and retained prior checkpoint bytes passed. Gate, provisioning and trial state remained unchanged.
