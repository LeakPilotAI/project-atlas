# Quality Dips V2 — Active Position Trend & Thesis Monitor

Date: 2026-09-17
Status: specification only; not wired to brokerage execution

## Purpose

After a manual L1/L2/L3/L4 entry, Atlas must continue evaluating whether the original patient-capital thesis is strengthening, stable, weakening, or broken. Buying a quality dip is not the end of the decision process.

## Required monitoring inputs

- frozen entry snapshot and L-level hit
- cost basis and staged allocation history when available
- current price and drawdown versus entry / normalization values
- short-, intermediate-, and long-term price trend
- momentum and relative strength
- market and sector regime
- valuation change versus the frozen entry thesis
- fundamentals / earnings / free-cash-flow evidence
- estimate revisions when supported by the evidence pipeline
- thesis-integrity flags and invalidation conditions
- evidence freshness and provenance

No missing input may be invented. UNKNOWN remains UNKNOWN.

## Position states

The future monitor must emit research states rather than automatic brokerage instructions:

- HOLD — thesis intact and evidence broadly stable/constructive
- HOLD_WATCH — thesis intact but trend/evidence has weakened enough to require attention
- ADD_ELIGIBLE — thesis intact and a pre-defined lower V2 accumulation level is reached with evidence still valid
- STOP_ADDING — thesis not broken, but trend/fundamental/valuation evidence no longer justifies further allocation
- THESIS_BROKEN — explicit invalidation; no further accumulation
- EXIT_REVIEW — manual review state when valuation objectives are reached or thesis materially degrades

These are decision-support states. Brokerage execution remains MANUAL_ONLY.

## Important behavior

A falling price alone must not trigger THESIS_BROKEN or EXIT_REVIEW. A rising price alone must not force HOLD. The monitor must compare current evidence against the frozen evidence that justified the L-level entry.

Trend analysis is contextual, not a guarantee of future price direction.

## Planned implementation order

1. Phase 2 evidence adapter surfaces all existing trend fields read-only.
2. Phase 3 adds freshness/thesis/value-trap hard gates.
3. Phase 4 adds normalization-value provenance.
4. Phase 5 adds staged entry zones and frozen entry snapshots.
5. Phase 6 adds active-position trend/thesis state engine with regression tests.
6. Phase 7+ validates position-state behavior on PIT historical data before dashboard alerts.

## Safety boundary

- execution = MANUAL_ONLY
- live_capital_allowed = false during research validation
- automatic_real_money_execution = false
- no guaranteed bottom, hold duration, return, or exit price
