# Atlas core scope, FS1 acceptance and Monday readiness

Base `3a005593eb98b5f69fe5e0c6118f8b6f4bb2fb2c`; branch `chatgpt/atlas-rebuild-v1`.
**Product scope consolidated by explicit operator directive. FS1 pure engineering verified; operational readiness NOT achieved. B1/C1/D1/E1 BLOCKED; all 21 decisions unchanged; PAPER startup NO; production NO-GO.**

## Standing current product scope

Atlas is a professional Windows-local trading research and PAPER execution platform. Stabilize existing core strategies, then measure multi-session reliability and net-of-realistic-cost performance. Profitability is not presumed. Live trading, wallet access, external orders and automatic Discord remain unauthorized. Preserve PAPER_ONLY/MANUAL_ONLY until each separately accepted scope says otherwise. No VPS requirement.

| Core family | Current scope and acceptance boundary |
|---|---|
| Quality Dips | Stocks/ETFs; preserve V1/V2/V3 research and originals. New isolated simulated account first; initial MSFT/manual/long-only proposal remains subject to capital/exposure/policy acceptance. Explicit inception, partial/full quantities, costs, cash/P&L and reports. Patient-capital positions may remain overnight; shutdown is not automatic liquidation. |
| Hyperliquid perpetuals | Existing manual PAPER lane; BTC/ETH/SOL and other already supported instruments only when approved. Preserve $1 simulated entry risk/max3/stricter3R and cost contracts for the selected manual scope. Existing eligible automatic mirrors/strategies remain separately gated, not implicitly enabled. No real orders or wallets. |
| Equity day trading | Existing eligible intraday strategies with separate PAPER capital/units/cost/session/risk accounting. No invented fills or balances. Pending/cancel durability and writer acceptance remain required. |
| Prediction markets — **ATLAS NEW-LISTING PRICE DISCOVERY AND REPRICING (NLPD)** | Category-agnostic within existing supported, licensed and permitted provider categories; football is one historical example, not the product boundary. Genuine new listing identity/timestamps, executable spread/depth/liquidity, supportable probability/edge after costs, accepted/rejected candidate history and unbiased evaluation required. Initially one position. Reject unsupported categories, unclear rules, stale/insufficient liquidity or unverified estimates. Prefer executable pre-resolution repricing where compatible with accepted policy; no guaranteed mispricing/profit. Explicitly excludes deferred 15-minute crypto prediction markets. |
| Financial dashboard | Independently reconciled account/epoch cash, positions, remaining quantities, fees/slippage, realized P&L and only evidence-supported unrealized P&L. UNKNOWN/INCOMPLETE and unavailable values explicit; no pooled unrelated balances. Read-only calls must not create financial events or refresh unauthorized providers. Q9 remains unregistered until accepted source/API connection. |
| Windows operations | Accepted one-click startup, exact ownership, closure/drain/reports/owned shutdown and restart refusal; no unrelated termination or Genesis effects. On-demand gaming remains core follow-on work, but its incomplete optimization must not by itself delay an otherwise accepted first session. Keep gaming off unless separately accepted; do not change the 21 gate decisions or waive applicability review. |

NLPD is a **current product/roadmap naming decision**, not a source-schema/API rename or an assertion that every new-listing feature already exists. Existing prediction engine, depth/fees, single-market/no-combo/no-parlay/no-stacking and pre-event controls remain. `prediction/policy.py` currently requires exit before event start and forbids hold-to-settlement; the general NLPD wording does not weaken that stronger rule. Unsupported category/cutoff mappings remain refusal cases until separately accepted. Local first-seen time is not provider-authenticated listing time. No provider or discovery loop was contacted or activated.

## Deferred — preserved, not deleted

Freeze optional strategy expansion, 15-minute crypto prediction markets, experimental market families/speculative engines, new AI monetization, unnecessary UI redesign, VPS/cloud deployment and work unrelated to core stability/accuracy/safety/existing strategy operation. Retain source, tests, evidence and legitimate governance obligations. Research-only signals/alerts/AFI are not newly funded accounts.

The complete historical seven-phase roadmap remains intact: (1) core stabilization/operations, (2) research Evidence Engine, (3) historical 15-minute crypto research **currently deferred**, (4) cross-market intelligence, (5) SaaS, (6) institutional platform, (7) commercial expansion. Phases 4–7 remain long-term objectives, not current optional-build priorities. Current category-agnostic NLPD core acceptance is tracked with Phase 1/2 reliability/evidence work; it does not silently activate or rewrite historical Phase 3. Phase 2 HOLD, Phase 3 BLOCKED and AFI-1–10 PENDING remain.

## FS1 implemented

- New `backend/app/services/paper_financial_replay.py`: storage-neutral inception helpers, explicit `PAPER_EVENT_STREAM_RECORD_V1`, deterministic transition/receipt computation and receipt/hash-chain replay. Inputs are not authenticated authority. Apply returns a copied next state; failed transitions do not mutate the supplied prior state or command.
- New `backend/app/services/paper_financial_audit.py`: independent stream arithmetic for original/remaining quantities, gross/cost/net, cash, trade-R, revisions and original position identities. It does not call the financial transition/replay implementation. Structural completeness, native projections, trust and writer exclusion remain separate requirements.
- Existing `paper_epoch_fixture.py` and `paper_portfolio_fixture.py` delegate to these functions while retaining SQL fixture persistence, existing import names, schemas and output semantics. Projection intents/UNKNOWN barriers stay in the existing compatibility adapter. No protected financial storage or native API/issuer imports were added.
- V1-compatible computations explicitly use 28-digit HALF_EVEN Decimal context without modifying the caller's ambient context. Synthetic goldens captured from the base before refactoring reproduce exact events, receipts, source heads, snapshots and report bytes. They are generated test evidence, not private records, financial authority or market-performance evidence. Nonstandard historical context cannot be silently accepted: inconsistent stored receipt/hash evidence still refuses. No original records were opened or migrated.

The selected storage design remains **A**: native handle-bound immutable per-operation financial records, canonical event/receipt together with separate durable intent/commit/ack and accepted current-pin custody. FS1 supplies pure computation only; it does not make fixture SQLite trusted or replace control snapshots with finance. Proposed MSFT/$100/one-position limits are still not an accepted/enforced selected-account contract; no quiet policy change was made to general V1 fixtures.

Overnight reports retain V1 INCOMPLETE when positions remain, and valuation remains unavailable. No successful financial/lifecycle status is invented. A future accepted version may distinguish clean owned-process shutdown from open holdings and incomplete valuation; that has not been operationally accepted here.

## Exact validation

Final combined selection: **100 passed, 0 failed, 0 skipped in 3.98s**, including **37 new FS1 cases**. Selection: `test_fs1_financial_replay.py`, `test_paper_epoch_fixture.py`, `test_paper_strategy_fixture.py`, `test_q7_paper_portfolio.py`. The earlier 32 focused passes overlap and are not added. This regression is justified by the changed transition and independent-audit delegation; no full Q4–Q9 rerun. Native security's 45/1 and older Python/JavaScript totals are retained, not rerun or added.

Coverage: exact pre-refactor synthetic receipt/head/snapshot/report reconstruction for both strategies; independent Decimal context; input nonmutation on failure; malformed/missing/duplicate/revision/hash/receipt/epoch refusal; contradictory cash/P&L/cost/quantity/side/symbol/revision rejection; proof the independent audit does not invoke replay; storage/service import isolation; existing receipt/retry/concurrency/crash/projection/daily-report compatibility. Only disposable fixture files were used; no FS2 Win32 identity/ACL tests, protected processes, providers, services or original financial stores.

Targeted Ruff and in-memory Python compilation pass. Initial four mechanical import/export findings were corrected without suppressions; one deliberate typed-receipt reproducer failed before correction and is retained at ignored logs/diagnostics/fs1-roadmap-20261024/receipt-type-repro.txt; final failures zero. CRLF-aware diff checks and approved checkpoint preservation pass. No frontend changes/build or operational acceptance claim.

Demonstrated correction: the old receipt comparison used Python equality, so `True` could equal integer revision1. A new reproducer confirmed that malformed receipt was accepted. Canonical serialized receipt comparison and exact integer checks in the independent audit now refuse boolean revisions without changing valid golden bytes. Original failure evidence retained; no startup/recovery authority change. The intermediate95passes preceded these five additional typed-revision cases and are not added to the final100.

## Monday October 26 target — honest readiness

Desired milestone: **Monday 2026-10-26 08:30 America/Chicago (CDT, UTC−05:00; 13:30 UTC)**. Offline timezone/date conversion verifies Monday and the UTC instant; this is not exchange-calendar/feed-coverage validation, a scheduled startup, a promise or a gate waiver.

| Track | Actual state |
|---|---|
| Offline engineering | **FS1 COMPLETE in scoped fixtures; overall selected-lane engineering INCOMPLETE** pending native record protocol, accepted policy/routing/readers and lifecycle integration |
| Disposable native acceptance | Control primitives tested; true-symlink capability unexecuted; **new financial FS2/FS3 NOT EXECUTED / NOT AUTHORIZED** |
| Operational integration | **INCOMPLETE**, protected dispatch and startup unchanged |
| Independent governance | **INCOMPLETE**: B1/C1/D1/E1 and applicable release evidence remain blocked |
| First supervised PAPER session | **NOT AUTHORIZED**; Monday target remains conditional |

No defensible readiness percentage or Monday completion promise follows from test counts. If prerequisites remain absent, the honest Monday result is NO-GO with refusal preserved.

## Remaining execution order and stabilization

1. FS2 requires explicit **P-D1-FINANCIAL-RECORDS-PROTOTYPE**: scoped exact-creation-handle `write_bound` and disposable immutable financial records/native tests in a newly authorized test root, no operational enrollment/routing/startup.
2. FS3 pure compatibility is partly covered by FS1; complete the new storage replay, independent audit, partial/overnight/report/restart/native-failure acceptance under its approved scope. Current SQLite compatibility is not FS3 native acceptance.
3. Obtain independent B1 epoch/exclusion/capital/policy, C1 actual writer/resource ownership/drain, D1 financial storage/issuer/clock/revision/recovery acceptance. Advisory suitability remains advisory.
4. Separately approve accepted native Quality Dips routing, then read-only dashboard projection and Windows lifecycle integration. Preserve legacy evidence and patient holdings. Hyperliquid/equity/NLPD follow only their accepted boundaries.
5. Complete E1 rights and actual wire/reconnect budgets, fresh/continuous data, backup/isolated restore and native lifecycle evidence, applicable 21-gate review and exact supervised-session permission. Startup locks stay active until independently accepted changes and explicit authorization.
6. After an approved first bounded session, enter formal bug-hunting/stability measurement: feed/order-book integrity; stale/missing quotes; disconnect/reconnect; partials/duplicates; cash/cost/P&L and account isolation; risk controls; overnight holdings; crashes/restart/UNKNOWN; dashboard consistency; Windows startup/shutdown; NLPD false positives/liquidity and accepted/rejected denominators; multi-session reliability and net-of-cost strategy viability. Define run/source versions, expected invariants, incident logs, incomplete states and independent reconciliation for every observation. Real observations require their own approved runtime window; no soak or collection was started.

Technical stability and strategy viability must both be evidenced before any future separate live-trading review. No current live-money design/activation, speculative expansion or monetization task is introduced.

## Exact continuation

FS1 and this requested consolidation are verified. Next genuine boundary: obtain P-D1-FINANCIAL-RECORDS-PROTOTYPE and an independently reviewable accepted native test plan before FS2 execution. Do not repeat goldens/refactor or create another ledger/dashboard to avoid that boundary. All strategy accounts remain separate; all original evidence and untracked work retained. State and queue point here; current core-scope decision must remain referenced in subsequent master checkpoints even when the managed current milestone changes.


Verified master checkpoint: approved updater backup byte equality,exact managed-section read-back and historical outside-section equality against pre-update/base all PASS;all21decision/startup-lock raw hashes unchanged. Complete seven phases,core/deferred scope,NLPD and Mondaytarget recorded in actual existing master;no shortened replacement. Initial updater invocation refused missing required Evidence field before modifying the roadmap;original failure/input retained and corrected metadata reapplied successfully. No test failure or history loss. Verification artifacts retained locally.


## FS2 superseding execution status - 2026-10-24

Explicit P-D1-FINANCIAL-RECORDS-PROTOTYPE was subsequently granted. FS2_NATIVE_FINANCIAL_RECORDS_ACCEPTANCE_2026-10-24.md now records the completed disposable FS2 protocol:59passed0failed1notexecuted;100separate compatibilitypassed. Earlier FS2 unauthorized/not-executed statements in this FS1 report are historical,not current. FS3 remains partial/pending;operational integration and B1/C1/D1/E1 remain BLOCKED. Product/deferred scope,Monday target,all21decisions and all7phases unchanged;startupNO,productionNO-GO.


## FS3 superseding execution status - 2026-10-24

FS3_FINANCIAL_REPORT_PROJECTION_ACCEPTANCE_2026-10-24.md now records authorized disposable FS3 daily reports,independent arithmetic,immutable report versions and separate native projection intent/view/ack:120passed0failed1notexecuted,100disjoint compatibilitypassed. Prior FS3 pending/unauthorized statements above are historical. Selected account limits/capital,actual routing/enrollment and B1/C1/D1/E1 remain unaccepted. No forced overnight liquidation,provider/startup authority,optional strategy activation or change to standing product/deferred scope. Monday targetonly;all21decisions and7phases preserved.


## FS1-FS3 handoff and Monday decision - 2026-10-24

FS123_OPERATIONAL_ACCEPTANCE_HANDOFF_2026-10-24.md and QUALITY_DIPS_B1_ACCEPTANCE_PROPOSAL_V2_2026-10-24.json are the current unaccepted reviewer packet/conditional walkthrough. Source-only handoff complete,0newtestcases;native FS3 evidence remains scoped. Actual ProjectAtlas/AtlasBackground shortcuts target ControlCenter;StopAtlas targets blocked legacy batch. Generalengine lacks proposed selected-account policy and no operational FS3 account screen/routing exists. B1/C1/D1/E1 and applicable21gate operational evidence/authorization absent:Monday08:30Central target currentlyNO-GO,not a promise/waiver. Core/deferred priorities,patient holdings,all7phases andall21decisions unchanged. ZeroACTIVE,BLOCKED_WAIT pending independent decisions/exact integration permission.


## Corrected Quality Dips selected policy — 2026-10-24

Operator correction supersedes MSFT-only scope; eligible ranked stocks and ETFs require verified instrument/execution identity and fresh evidence. QD_SELECTED_POLICY_V1_OFFLINE VERIFIED:133passed/0failed/0skipped (33new+100compatibility), not operational acceptance. See QUALITY_DIPS_SELECTED_POLICY_V1_2026-10-24.md and operator scope correction JSON. Exactly zero ACTIVE tasks;BLOCKED_WAIT for independent B1/C1/D1/E1 scope/evidence acceptance and separately authorized current-evidence/native-writer integration. All21decisions unchanged;startupNO;productionNO-GO. Original histories/proposals retained.


## Quality Dips integration V1 source-only acceptance — 2026-10-24

P-QD-INTEGRATION-V1-OFFLINE completed:3integrationmodules plus additive selectedV3 canonical binding;265passed/0failed/0skipped(74newintegration). ExistingFS2/FS3 protocol code exercised with ordinary-file primitives,not native enrollment/security acceptance. Current generations no longer require inception edits;manual/owner/execution/source/quote bindings,UNKNOWN andread-only GET verified. See QUALITY_DIPS_INTEGRATION_V1_ACCEPTANCE_2026-10-24.md. Source integration IMPLEMENTED,DISPOSABLE VERIFIED;RUNTIME REGISTERED NO;OPERATIONALLY ACCEPTED NO. ZeroACTIVE;BLOCKED_WAIT for exact existing-page read-side integration permission and independent B1/C1/D1/E1 acceptance. No protected registration or providers;all21decisions and7phases preserved,startupNO,productionNO-GO.


## Quality Dips frontend V1 offline acceptance — 2026-10-24

P-QD-FRONTEND-V1-OFFLINE completed. Existing screen selected-account mode reads only the unregistered selectedGET;no trade controls,legacy fallback,provider or startup calls. Exact decimal cash/positions,optional verified inception,reason/status/cutoff displays.271Pythonpassed/0failed/0skipped(includes5newapplicationcases+1retainedUIwrapper);25separateJSunitpassed. DOM/fetch fixtures only;no realbrowser/server/native acceptance. See QUALITY_DIPS_FRONTEND_V1_ACCEPTANCE_2026-10-24.md. ZeroACTIVE;BLOCKED_WAIT for independentB1/C1/D1/E1 and separately approved accepted read-capability binding/router registration/supervised acceptance. All21decisions and7phases preserved;PAPERstartupNO;productionNO-GO. No more standalone dashboard is required.
