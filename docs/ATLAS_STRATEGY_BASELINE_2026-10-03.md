# Project Atlas Strategy Baseline Freeze — 2026-10-03

Status: ACTIVE EVIDENCE BASELINE
Scope: Day Trading + Investment/Quality Dips
Execution impact: NONE. This document does not change runtime behavior, thresholds, services, or live-capital permissions.

## Purpose

Freeze the currently implemented strategy/evidence identities before the next attribution and scorecard work. Runtime logic may receive integrity/reliability fixes, but material strategy changes must create a new version/cohort rather than silently rewriting this baseline.

## Day Trading / Hyperliquid PAPER

Canonical performance journal:
- backend/data/paper_journal.jsonl

Canonical candidate journal:
- backend/data/paper_candidates.jsonl

Runtime strategy/service:
- backend/app/services/perp_micro_coach.py
- module identity: Perp micro coach v3.1
- canonical strategy identifier used by recovered/owned rows: rsi_extension_v1
- source: perp_micro
- domain: HYPERLIQUID_PERPS
- PAPER evidence only for automated strategy evaluation; live-capital promotion remains separately gated.

Existing open/close evidence supports, among other fields:
- symbol / side
- signal and entry timestamps
- signal price / actual entry
- stop / TP1 / TP2
- strategy / source / tier
- signal score
- regime and regime_normalized
- feature payload
- paper execution model version
- MFE / MAE
- working stop / target and adaptive-exit state
- fees / slippage assumptions
- counts_for_live flag

Legacy paper_trade_tracker is intentionally a NO-OP and MUST NOT become a second source of Hyperliquid performance truth.

Historical holdout preserved:
- 546 trades
- total R: -26.7235
- expectancy: -0.04894R
- status: FAILED_NEGATIVE
- immutable: true

Do not delete, relabel, cherry-pick, or blend that historical holdout into a newer cohort.

## Investment / Quality Dips

Strategy:
- QUALITY_DIPS_V3

Policy:
- quality-dips-v3-mos-15-20-25-30-v1

Execution model:
- investment-forward-observation-v1-no-assumed-fill

Primary prospective evidence:
- backend/data/investment/prospective_v3_observations.jsonl
- backend/data/investment/prospective_v3_outcomes.jsonl

Supporting runtime evidence includes:
- backend/data/investment/quality_dips_v3_forward_pit.jsonl
- backend/data/investment/quality_dips_v3_state.json
- backend/data/investment/provider_health.jsonl
- backend/data/investment/scan_log.jsonl
- backend/data/investment/snapshots.jsonl

Prospective observations are append-only FORWARD_COLLECTION records. They freeze strategy, policy, execution model, policy hash, classification, confidence, source snapshot, features, valuation and missing-data state before later outcomes mature.

Existing reporting already supports:
- 1d / 5d / 20d / 60d / 252d forward horizons
- policy / execution-model / confidence / classification buckets
- sector and market-regime buckets
- unresolved outcomes
- valuation-range coverage
- opportunity-cost observations
- matched benchmark reference comparisons where point-in-time evidence permits them

Investment execution remains MANUAL_ONLY and LONG ONLY. No investment shorting is part of Atlas.

## Baseline change control

From this freeze forward:
1. Do not tune thresholds silently inside this cohort.
2. Bug/data-integrity/reliability fixes must preserve historical evidence and be documented.
3. Material signal, entry, exit, sizing, filter, cost-model or policy changes require a new explicit version/cohort.
4. Negative evidence remains evidence.
5. UNKNOWN / INSUFFICIENT_EVIDENCE remains valid when attribution cannot be supported.
6. Development/tuning evidence must not be presented as untouched holdout evidence.
7. Live-capital permissions remain false unless a later explicit evidence review and operator authorization changes them.

## Next implementation target

Build read-only Day Trading attribution + scorecards from the canonical paper journal without changing the running strategy:
- direction/signal failure
- entry timing evidence where supportable
- spread/slippage/cost drag
- stop/exit behavior
- target/repricing failure
- time-of-day
- regime mismatch
- macro/event interference only when point-in-time evidence exists
- execution/data issue
- negative edge / unresolved

Then aggregate by strategy/version/regime with sample size, W/L/scratch, expectancy, profit factor where defined, cumulative R, drawdown, MFE/MAE, costs, holding time and unresolved/invalid counts.

No attribution may invent causality from outcome alone.
