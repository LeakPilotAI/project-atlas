# Quality Dips V2 — Patient Capital Research Cycle

Date opened: 2026-09-17

## Purpose

Quality Dips V2 is a new isolated equity-investment research cycle. It does not rewrite the closed historical perps experiment or its evidence. The goal is to make Atlas materially more patient: wait for unusually attractive prices in high-quality businesses rather than treating ordinary corrections as buying opportunities.

A 29–50% upside objective is a valuation-screening hurdle, not a guarantee, probability, or promised return. No equity or ETF can guarantee that outcome.

## State model

`WATCH -> ACCUMULATION -> DEEP_VALUE -> GENERATIONAL`

Any failed thesis can move directly to `THESIS_BROKEN`.

- WATCH: quality name may be interesting, but price/evidence/margin of safety is not sufficient.
- ACCUMULATION: intact thesis, acceptable evidence and quality, no value-trap flag, and at least 29% conservative normalization upside with base upside also clearing the hurdle.
- DEEP_VALUE: stronger quality/fundamentals/valuation, unusually deep historical drawdown, and at least 40% conservative upside.
- GENERATIONAL: intentionally rare. HIGH evidence, >=90 quality/fundamentals/valuation, >=95th drawdown percentile, intact thesis, no trap flag, and >=50% conservative normalization upside.
- THESIS_BROKEN: business thesis failed; price decline alone cannot make the asset attractive.

## V2 evidence stack

The production implementation should combine independent evidence rather than a single indicator: business/fundamental quality, balance-sheet durability, valuation versus normalized history/peers, earnings and free-cash-flow trajectory, estimate revisions where reliable, drawdown extremity, sector/market regime, technical capitulation/base evidence, current evidence freshness, and thesis integrity.

## Price-first patience model

Atlas works backward from valuation. If a conservative normalization target is $129, a $100 entry leaves 29% arithmetic upside. If price is $110, Atlas waits unless another conservative valuation model supports the required margin. The system must never raise fair value merely to manufacture the desired upside.

## Exit research

V2 should eventually display conservative/base/optimistic normalization values and staged TP zones. A fixed +29% automatic sale is not part of Phase 1. Exit behavior must be researched separately and remain manual until validated.

## Safety / execution boundary

- research and decision support only during V2 development
- manual brokerage action only
- no broker credentials
- no automatic order placement
- live_capital_allowed=false in the V2 policy metadata
- automatic_real_money_execution=false
- no claim that a bottom, gain, fair value, or recovery is guaranteed

## Phase roadmap

1. COMPLETE IN CODE / LOCAL TEST PENDING — inspect existing Quality Dips and freeze V2 policy contract.
2. Build V2 evidence adapter from existing investment research rows without changing legacy scoring.
3. Build value-trap/thesis-integrity hard gate and evidence freshness requirements.
4. Build conservative/base/optimistic normalization-value model with provenance.
5. Build patient state classifier integration and staged entry-zone planner.
6. Build historical/PIT validation dataset and evaluate 29/40/50% hurdle behavior without lookahead.
7. Freeze DEVELOPMENT policy, then evaluate untouched HOLDOUT period.
8. Integrate validated V2 fields into Quality Dips API/dashboard while preserving MANUAL_ONLY execution.
9. Add alerting for state transitions and exceptional price-zone hits, with cooldown/deduplication.
10. Desktop regression + operational smoke; record V2 evidence decision. Live brokerage automation remains out of scope unless a future separately validated cycle explicitly changes that boundary.

## Phase 1 implementation

`backend/app/investment/quality_dips_v2.py` defines the isolated policy, arithmetic upside helpers, entry-price reverse calculation, valuation scenarios, and research-only patient-state contract.

`tests/test_quality_dips_v2_policy.py` locks the 29% patience hurdle, 50% GENERATIONAL hurdle, thesis-broken override, value-trap rejection, state separation, and no-live/no-guarantee boundary.

The V2 module is intentionally not wired into the existing production Quality Dips board in Phase 1.
