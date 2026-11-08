# Prospective research operation

Start Atlas normally. The existing Quality Dips monitor collects the first eligible UTC-day snapshot per symbol and policy without a dashboard visit or notification. Open **Daily manual investment research** from the main dashboard. The page is `/api/investments/prospective/view`.

The first 36 observations and 36 UNKNOWN outcome records are genuine evidence and must remain unchanged. Outcomes append revisions separately. No observation is a PAPER fill merely because a target was touched. Missing frozen execution rules leave fills, stops and R unknown. Completed daily bars strictly after the observation date are eligible for outcome measurement; today's incomplete daily bar is excluded.

Local evidence files under `backend/data/investment/`:

| File | Purpose |
|---|---|
| `prospective_v3_observations.jsonl` | Immutable original predictions and decision inputs |
| `prospective_v3_outcomes.jsonl` | Append-only outcome revisions |
| `daily_manual_research_plans.jsonl` | First saved plan per UTC day |
| `valuation_revisions.jsonl` | Evidence-based valuation changes; old and new levels |
| `prospective_policy_freezes.jsonl` | Prospective experiment definitions |

Legacy V3 records retain their original format and identity. These new files do not manufacture historical V3 observations or repair negative historical performance.

## Manual inputs

Existing `holdings.json` supplies portfolio value, available cash, holdings, reserve, risk tolerance, horizon, position/sector limits and benchmark symbol. The existing portfolio loader defines the accepted schema. No brokerage login is needed.

Optional `daily_research_config.json` supplies `target_allocations` (QUALITY_DIPS, ETF_CORE, RESERVE_CASH), `stage_weights` (CURRENT, L1, L2, L3, L4), `minimum_conservative_upside` as a decimal research hurdle, optional `etf_symbols`, and `etf_evidence`. Weights must be nonnegative and sum to at most one. These are explicit research assumptions, not optimized recommendations. No capital amounts or risk preferences are inferred for the user.

ETF evidence fields require `value`, `source`, and `as_of`. Available stored daily bars support price/adjusted-return, volatility and drawdown research. Unavailable expense, distribution, holdings, overlap and methodology fields remain UNKNOWN. Adjusted total return is never added to distributions again. Portfolio suitability and overlap remain necessary before ETF allocation.

Missing capital or risk inputs produce BUY_NOTHING_TODAY. A later configuration change does not rewrite an already saved plan. The next genuine daily plan uses the new configuration.

## Evidence boundaries

Valuation and actionability are separate. V2 hurdles remain 29/35/40/50%; V3 margins remain 15/20/25/30%. A configurable actionable zone does not move these levels. Valuation revisions preserve their evidence and previous values. Price-only changes must not raise targets.

Policy freezes require timezone-aware future development/holdout boundaries, a unique version, policy definition and rationale. TEST, DIAGNOSTIC and DEVELOPMENT records cannot be upgraded into untouched holdout. The champion remains the existing version; challenger evaluation never promotes a production policy automatically. A promotion requires an explicit reviewed policy change with reproducible mature evidence and validation.

The first forward sample is immature. Calibration, waiting costs and benchmark conclusions require later eligible observations. Unknown or unfavorable results remain visible. Valuation ranges are not probability intervals. Readiness remains INSUFFICIENT_EVIDENCE while economic acceptance criteria, mature untouched outcomes, execution consistency and benchmark evidence are missing. No readiness result enables live execution.

## Operating cost and external dependency audit

No dependency, container, database, paid provider or external monitoring service was added by this continuation. **NEW PAID SERVICES ADDED = 0.** This audit describes repository usage; it does not assert the user's pre-existing account billing or Docker licensing status.

| Service/component | Purpose | Location | Cost in this change | Account / secret | Required? |
|---|---|---|---|---|---|
| Python, FastAPI, local JSONL and calculations | Research/API/evidence | Local | Existing open-source stack; no paid service | None | Yes |
| PostgreSQL/Timescale and Redis | Existing Atlas runtime | Local Docker | Existing containers; no new service | Local DB configuration | Yes for normal runtime |
| Docker Desktop | Existing container runtime | Local | Existing installation/license unchanged | Existing installation | Yes for desktop workflow |
| Yahoo/yfinance | Existing quotes, history and valuation sources | External | Existing public-data path; no subscription added | No paid API credential added | Needed for fresh supported market data; local evidence remains readable offline |
| Robinhood public quote endpoints | Existing quote-only fallback | External | Existing public-data path | No brokerage execution credentials | Optional |
| Hyperliquid public info/WebSocket | Existing perps market data | External | Existing public-data path | No order signing key | Perps research |
| Binance public archive | Existing historical research downloads | External | Existing public-data path | No account/key in acquisition path | Optional historical research |
| Discord / Telegram | Existing notifications | External | No new service or subscription | Existing bot token if enabled | Optional; collection does not depend on delivery |
| Google Fonts | Existing main dashboard typography | External | Existing asset requests unchanged | None | Optional visual asset |

Quality Dips/Robinhood stays MANUAL_ONLY. Automatic real-money perps stays DISABLED. `live_capital_allowed=false` and `automatic_real_money_execution=false` remain mandatory.
