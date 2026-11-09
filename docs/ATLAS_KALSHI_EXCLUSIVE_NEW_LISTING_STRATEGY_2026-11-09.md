# Kalshi strategy exclusivity and retirement of legacy PAPER entry — 2026-11-09

**User direction reconfirmed:** the only intended operational Kalshi strategy is brand-new *exchange-confirmed* single YES/NO market mispricing and early price discovery, intended to exit promptly for net gains when depth/fees/slippage and observed price movement justify it. This **REPLACES**, not supplements, the legacy generalized pre-event recent-reclaim strategy. Historical example screenshots are explanatory concepts, NOT authenticated order or profitability evidence. No prediction PAPER activation or real trading is approved.

## What actually existed

- Old `backend/app/prediction/paper_engine.py` supports `PRE_EVENT_RECENT_RECLAIM_V1` PAPER simulation, with historical candle/high research, 24-hour listing-age gate, volume/OI, and order-book/fee models. These rules overlap but are NOT the same as genuine initial-listing mispricing.
- `backend/app/prediction/prediction_paper_automation.py` is launched by the legacy app's startup service loop, but its status reports `unattended_paper_open_enabled=false`, `automatic_paper_position_opening=false`, and `unattended_paper_open_blocked=true`. It is not authorized to start unattended entry trades. It retains research scans and a legacy safety auto-flat worker. Research scans are not an approved strategy.
- `backend/app/api/prediction.py` previously exposed a manual **`POST /api/prediction/paper/open/{ticker}`** that could append a PAPER position under the old pre-event-reclaim evaluation. The API has never had authenticated Kalshi brokerage order submission.

## Code change in workspace

- `backend/app/prediction/policy.py` explicitly identifies `NEWLY_LISTED_SINGLE_YES_NO_PRICE_DISCOVERY_V1` as the only future PAPER strategy. `legacy_repricing_paper_entry_enabled=false`, `target_new_listing_paper_entry_commissioned=false`, a required independently verified new listing, single YES/NO leg, no combo/parlay/multivariate/stacking, no simultaneous positions, and an early repricing **objective**, not a guarantee. Legacy reclaim models are classified research-only.
- The **old manual PAPER-entry API route** now unconditionally refuses with HTTP 409 `KALSHI_LEGACY_PAPER_ENTRY_RETIRED_NEW_LISTING_ONLY` **before provider calls, candidate journals or any PAPER trade write**. It cannot accidentally become usable by flipping a policy flag. Existing `POST /api/prediction/paper/close` remains so legacy test/PAPER positions can still be closed safely, and public Kalshi research, historical diagnostics, and comparison tools remain available. No new approved Kalshi PAPER-entry endpoint was created.
- `tests/test_kalshi_new_listing_exclusive_entry_policy.py` validates exclusive strategy direction, mandatory operator-nonactivation flags, exact refusal of the old YES and NO endpoint before provider/journal access, preservation of close route and public research, and legacy unattended opening disabled.
- Combined legacy Kalshi research + API + automation + new-listing/forward-observer regression: **76 passed, zero failures**, two unrelated library deprecation warnings.

## Remaining work for this strategy

A future separate implementation must conclusively bind market creation/open timestamps and **first real exchange appearance** (pagination changes are NOT new listings), compare genuinely chronological executable prices and costs in early hours/days, choose at most one YES or NO side per contract, require positive **independently justified projected net edge**, enforce short holds, fixed small risk, no settlement holds, durable stop/close, and qualified two-account/clock/provider rights. First run as supervised new-listing-only PAPER; no general reclaim entries. Thin early markets may lack entry/exit liquidity and should be SKIPPED, not treated as instant profit. The old 24h gate is a provisional research window, not a requirement to trade any market just because it's under 24h.

These are **development-workspace changes only**: selected native r12 is untouched. Financial PAPER still 0/9 accepted for the QD/Hyperliquid workstreams, and Kalshi remains an additional separately unaccepted third strategy. Do not treat old research/automation code, user approval of strategy direction, or unit tests as operational entry authorization.

No access to Kalshi private accounts, market orders, funded wallet, Alpaca credentials, PAPER accounts, Project Genesis, native selection, Windows shortcuts/boot, or GitHub push.
