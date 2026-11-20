# Historical PAPER compatibility policy V1 — DRAFT, inactive

This document describes retained September 2026 evidence. It does not grant a replay exception, amend the current no-rearm rule, change PAPER accounting authority, or authorize any trade, startup, migration, or production use. Phase 2 remains HOLD; production remains NO-GO.

## Historical interpretation

An exact `setup_instance_id` that was armed after a prior terminal event remains incompatible with the current no-rearm rule. The 19 retained identities have 65 such rearms. Every preceding terminal in the retained pending ledger is a cancellation with reason `PAPER_POSITION_ALREADY_OPEN`. That reason is a recorded claim, not independent proof that another position was open at that instant.

For descriptive review, classify each identity as **historical exception required, not granted**. Seventeen have no linked fill/open. Two have one pending fill, one linked PAPER open and one close each; their retained net R values are locally consistent with the documented fee/slippage formula. Neither fact permits replay or retroactive validation of every cancellation. Never drop terminal rows, rewrite identities, or turn a recorded cancellation into a fill.

## Accounting authority and evidence threshold

The read-only V1 accounting audit (`scripts/diagnostics/audit_historical_paper_accounting.py`) parses both retained JSONL files strictly, checks linked trade identities and chronology, reports duplicate/orphan/missing events, and recomputes net R only when all formula inputs exist. It reports recorded mark values as historical observations, never as current unrealized P&L. The exact per-identity result is `logs/diagnostics/phase2-paper-reconciliation-20261022/per-identity-v5-accounting.json`. Local consistency is not independent proof of complete source history, atomic cross-file capture, historic implementation equivalence, or external writer exclusion.

No independent reviewer has approved a versioned historical accounting authority. A future reviewer must verify immutable journal provenance, complete source coverage (including any separate execution or adjustment records), writer/version chronology, each cancellation's claimed context, and the intended interpretation of older fee and close semantics. Any later migration or compatibility implementation requires its own explicit decision, tests and authorization; current replay must keep refusing these identities.

## Trading authority

PAPER_ONLY and MANUAL_ONLY remain in force. This draft gives no unattended PAPER, live-money, prediction-order, Discord, or production authority. The 21 release-gate decisions remain unchanged. Phase 3 cannot begin while Phase 2 acceptance is HOLD.
