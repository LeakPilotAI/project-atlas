# Q7 disposable end-to-end PAPER integration

Base 516a7ef04bff9539453e71dbe709983ea98e4bdf; branch chatgpt/atlas-rebuild-v1.
**Engineering acceptance only. PAPER startup NO; production NO-GO; B1/C1/D1/E1 BLOCKED; all 21 governance decisions unchanged. Phase 2 HOLD; Phase 3 BLOCKED; AFI-1–10 PENDING.**

## Implemented integration

`backend/app/services/paper_workflow_fixture.py` connects actual Quality Dips V3 policy outputs to the existing disposable canonical command adapter. It compares the explicit quote with the strategy input, freezes the input/plan digest and derives classification/reached levels from `build_v3_entry_plan`; tests no longer supply an invented actionable classification as the whole signal. These are explicitly synthetic forward fixtures, not authenticated forward market observations or a provider receipt.

The Quality Dips scenario now runs: eligible actual policy -> explicit manual entry -> canonical receipt/cash debit -> partial exit -> remaining quantity -> actual thesis-terminal policy -> final exit -> costs/net/cash -> immutable daily report -> new reader/replay. Different partial/final prices are represented canonically without fabricating a native V1 whole-position close. A separate retained legacy fixture stays byte-identical and OPEN. Unsupported balances/equity are not inferred. Explicit synthetic capital and the versioned fixture cost policy are not operationally accepted opening cash or costs.

The same module supplies `NativePerpProjectionFixture`, an injected publisher/observer using actual disposable PaperJournal and ManualPerpStateStore instances. No singleton import, default store, provider or startup path exists. BTC/ETH/SOL manual canonical entry is associated with the exact native trade; symbol/side, entry, quantity, risk, costs, PAPER type and no-live flag are verified. Canonical partial/final current state is projected additively. Native V1 opens and ENTERED plans remain retained; the overlay's zero quantity is not a false native FLAT or historical liquidation claim.

The three-asset scenario covers long/short partial/final legs, stable duplicate receipts, cost-aware cash/P&L, report publication and restart through a new canonical reader/native observer. Existing $1 maximum simulated entry risk, max3 remaining positions, stricter3R refusal and2bpsfee/2bpsslippage assumptions remain. No margin/funding/USDC, real fill, venue unit or live-capital authority is inferred.

## Demonstrated defect and bounded correction

Original regression reproduced a native-writer admission gap: after an independent disposable manual-store write, a new bridge command could commit and overwrite the conflicting projection instead of refusing before financial mutation. `NativeProjectionFixture.apply` now verifies retained native state before new financial commits. Its reader also rejects canonical operations that lack required native projection intents. The Q7 seam optionally binds an explicit initial fixture observation digest, so interference before the first entry refuses before commit.

The publisher checks its retained observation before publication as well. Interference injected after canonical commit but before external publication preserves the pending/UNKNOWN intent; it does not roll back, fabricate a projection receipt or replay the financial callback. Interrupted publication/acknowledgement retains the existing no-replay/report refusal. Acknowledged retries remain idempotent. This detects tested interference, not directory-wide/native writer exclusion: independent writers can still race observations and commits. C1 remains unaccepted.

Canonical and bridge snapshot reads now use SQLite `mode=ro`; the actual write-denial behavior is tested. Reports remain explicitly separate writes requested by tests. Read-only SQLite access can still require filesystem/sidecar metadata access depending on storage mode; no production ACL, VFS or physical namespace guarantee is claimed.

## Versioned portfolio and presentation contract

`backend/app/services/paper_portfolio_fixture.py` implements:

- `PAPER_ACCOUNT_SUMMARY_FIXTURE_V1`: strategy/epoch/currency, explicit simulated opening cash, reconciled cash, gross/cost/net, remaining position identity/quantity/revision, canonical source head/revision, observation/event clocks and reason codes.
- An independent arithmetic audit reads the verified canonical events and recomputes original positions, remaining quantities, cash debits/proceeds, fees/slippage and realized totals without calling the financial `_apply` implementation. This is independent local arithmetic, not an independent archive custodian or real financial-source acceptance.
- Required native projections must be supplied through the matching bridge reader. Missing/changed/pending/corrupt evidence yields UNKNOWN with null financial totals/inventory; it never becomes an empty or zero balance. Open positions or aged financial events yield INCOMPLETE. Event-age freshness explicitly **does not** establish market-quote freshness. Equity/unrealized P&L/live feed freshness stay unavailable.
- `PAPER_PORTFOLIO_FIXTURE_V1`: deterministic sorted account rows, duplicate epoch/account rejection and **no combined balances or performance**. The reader validates schema, authority flags, exact financial arithmetic, freshness, source metadata and remaining-position shape. No currency conversion/consolidation permission exists.
- An escaped inert HTML table fragment exercises the presentation contract. Empty/replaced/cleared accounts do not retain earlier rows; UNKNOWN renders unavailable values. This is not another dashboard, registered API, running host or browser acceptance. No protected endpoint or actual Atlas dashboard is connected.

Caller-provided presentation data remains untrusted fixture data and cannot grant authority. Read-before/read-after consistency checks detect tested source/projection changes; they do not create an atomic snapshot across independent native stores or prove writer exclusion. No recovery fence or UNKNOWN operation is automatically cleared.

## Full strategy coverage status

The source inventory in `MULTI_STRATEGY_PAPER_COVERAGE_2026-10-23.md` remains authoritative for discovered families and detailed file paths. The following distinguishes implementation from source routing and actual acceptance. "Legacy wiring" means existing source call sites, not an activated or accepted run. Prior tests are retained evidence, not new Q7 passes.

| Discovered system | IMPLEMENTED | DISPOSABLE VERIFIED | RUNTIME INTEGRATED | OPERATIONALLY ACCEPTED | BLOCKED / strategy-specific work |
|---|---|---|---|---|---|
| Quality Dips legacy/V2/V3 | Existing policies/native lots; Q7signal-to-cash/report seam | Q7actualV3/partial/final/restart/legacy preservation | Legacy board/terminal wiring; Q7NO | NO | Accepted cost/currency/cash, native receipt routing, ownership and protection; no intraday forced liquidation policy |
| Long-term stock/ETF accumulation | Research/plans/buys/marks/book | Prior book/audit fixtures; Q7account foundation reusable | Legacy scanner/book wiring; Q7NO | NO | Sell/partial/corporate-action and cash/fee semantics; long-term holding policy |
| Equity day-trade L1 mirror | Simulated pending/fill/stop/target code | Prior pending/journal fixtures; not Q7end-to-end | Legacy mirror wiring; Q7NO | NO | Pending fsync/cancel/UNKNOWN boundaries, calendar/session and separate cash |
| Hyperliquid manual lane | Canonical fixture entries/partial/full/native overlays | Q7BTC/ETH/SOL long/short workflow and failures | Legacy manual API; Q7NO | NO | N3/N4/N5/N6acceptance; no direct fixture-module production promotion |
| Hyperliquid automatic setup mirror/adaptive exits | Existing automatic simulated mirror/policy | Prior mirror/partial fixtures; not enabled | Legacy source wiring; Q7NO | NO | Excluded from manual-only first session; separate scope, pending/source/risk/drain acceptance |
| Crypto micro coach incl. major/alt/meme/junk tiers | Existing automatic PAPER journal path | Prior coach/journal fixtures; Q7infrastructure reusable | Legacy coach wiring; Q7NO | NO | Distinct frozen tier/risk/source/cash policy; no dedicated spot/meme wallet engine found |
| A+ scanner: balanced, mean-reversion, momentum, breakout | Signals/decisions | Existing pure signal tests,not funded account acceptance | Legacy signal wiring only | NO trading acceptance | Accepted downstream consumer; do not create four ledgers from profile names |
| ATR/Keltner, squeeze, anomaly/funding/whale/context | Supporting signal engines | Prior research fixtures | Existing signal consumers only | NO trading acceptance | Provenance/rights/freshness; no separate funded account required |
| V4 deterministic/shadow PAPER | Pure execution, event replay and shadow runtime | Prior event/runtime fixtures | Existing shadow bridge only | NO | Shadow remains separate; receipt/cash/exclusion acceptance if later selected |
| V5/V6 and E28/E29 challenger/rejection research | Research subsets/prospective diagnostics | Prior research tests | Research readers/hooks only | NO trading acceptance | Licensed independent evidence; not independent execution strategies |
| Prediction pre-event PAPER | Depth-aware simulation/journal/optional loop | Prior prediction fixtures | Legacy API/automation source; not activated | NO | Separate contract units/fees/cash; expired_unclosed unresolved; excluded scope |
| Crypto Quality Dips research | Evidence normalization/store | Prior research tests | Inactive research interface | NO | No approved trading/valuation/cost/position model; no invented engine |
| Portfolio/ETF/benchmark/manual investment/morning brief | Inputs/plans/diagnostics | Prior local research/book fixtures | Existing research surfaces | NO account execution acceptance | Complete holding/cash provenance; no broker or portfolio rebalance authority |
| AFI/historical/prospective/holdout research | Forecast/replay/accountability | Retained offline tests | Existing read-only viewers | AFI0/10; NO trading acceptance | Licensed/witnessed evidence; forecast is not a fill/entry authority |
| Extended-hours observation research | Opt-in collector source | Prior collector/normalization fixtures | Gated source wiring only | NO current collection acceptance | Provider rights/budgets and separately permitted runtime window |

All can reuse the versioned account/receipt/report/presentation interfaces where semantically appropriate. They cannot reuse another lane's cash, currency conversion, notional/risk definition, exit trigger, market calendar, fees or position units without separate accepted contracts. Signal/research-only systems do not need newly invented execution engines.

## Exact operational acceptance artifacts still missing

| Gate | Required artifact / producer and independent acceptance | Current disposition |
|---|---|---|
| B1 | Custodian-authenticated complete archive/exposure/cashflow/cost/correction inventory and discrepancy disposition; independent reviewer. For a new epoch: explicit independent historical-isolation/scope decision plus accepted hypothetical inception, risk baseline and unique epoch/resource binding. Preserve unresolved legacy positions and original evidence. | Q7synthetic manifests and local arithmetic supply neither archive authenticity nor a scope waiver. BLOCKED. |
| C1 | Fresh exact actual run/release/resource/writer roster, process PID/creation/image/command/owner/children; admitted operation identities, entry-close and complete drain/quiescence evidence; independent native reviewer. Cover financial, metadata, reports, diagnostics, investment/prediction/standalone paths or prove exclusion. | Native fixture observation/interference tests are scoped. No actual ownership or external-writer exclusion accepted. BLOCKED. |
| D1 | Accepted identity-before-access storage/sidecar contract and native proof; trusted issuer/operator authorization and bounded validity; independent clock/revision/rollback witness and explicit UNKNOWN recovery authority. Separate provisioning permission. | Caller pins, path-based disposable SQLite, local files and clock arguments are not those artifacts. No ACL/key/registry/TPM provisioning performed. BLOCKED. |
| E1 | Endpoint/account/purpose-specific provider rights and wire/request/reconnect budget evidence; expressly permitted data continuity; complete storage map and independently verified backup/isolated restoration; exact Windows/owned dependency lifecycle acceptance; approved session scope and independent release/operator permission. | No provider, runtime, backup, recovery or supervised-session acceptance performed. Deferred GUI close/legacy Stop acceptance remains relevant before one-click use. BLOCKED. |

## Smallest next integration boundary

Current authorization is exhausted after offline Q7validation/publication. The next proposed engineering change is a separately approved runtime-facing selected-lane adapter behind the accepted canonical storage/authority interface, **not** importing fixture stores as production authority. Limit the initial file list to approved entry/exit request/receipt routing in `services/perp_manual_service.py` / `api/perp_manual.py` (or separately approved Quality Dips writer), version-aware native projection readers and all-writer admission/shutdown hooks. Keep actual storage/provisioning/providers/migration/startup excluded until their own evidence and permissions exist. Preserve Python/Windows refusal and existing deadlines.

First-session sequence remains B1scope/evidence -> C1/D1acceptance -> separately approved narrow caller implementation/disposable regressions -> provider/storage/native lifecycle acceptance -> independent21gate review -> explicit supervised PAPER startup permission. No completion percentage or date is justified by test counts. No live trading, prediction automation, Discord, Docker/Genesis or unrelated processes were activated or modified.

Validation and verified roadmap backup/read-back/history results are recorded in `Q7_PAPER_WORKFLOW_CONTINUATION_2026-10-23.md`. Original failure evidence is retained privately; financial sources/logs/generated stores/backups are excluded from Git publication.


## Exact validation outcome

Final single combined selection:166passed,0failed,0skipped in21.98s,including29newQ7cases. Selection:test_q7_paper_workflows,test_q7_paper_portfolio,test_quality_dips_v3,test_paper_epoch_fixture,test_paper_strategy_fixture,test_quality_dips_fixture_handoff,test_quality_dips_paper_v1,test_quality_dips_paper_terminal,test_quality_dips_paper_marking,test_quality_dips_paper_exit_policy,test_hyperliquid_epoch_feasibility,test_hyperliquid_native_fixture,test_stage34d_admission,test_stage34e_refusal,test_r7e47cg_production_startup_lock. Earlier22/28focused and165combinedpasses overlap;not added. Prior412Python/763JS not rerun or added. Original1failed interference reproducer is retained at ignored logs/diagnostics/q7-repro.txt;final failure count iszero.

Targeted Ruff and compilation passed for four source modules and three affected test modules. Checkpoint PowerShell parser and diff checks passed. Production-import exclusion coverage now permits only the explicitly reviewed disposable workflow/portfolio consumers in addition to the original fixture modules;no operational directory exemption or startup path was added. SQLite read-only write refusal,malformed/unknown/stale summaries,HTML escaping,empty/replace/clear semantics and unassociated native inventory refusal are covered. No HTTP/browser/provider/runtime acceptance claimed.
