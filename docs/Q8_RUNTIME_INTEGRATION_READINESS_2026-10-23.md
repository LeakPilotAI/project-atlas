# Q8 runtime integration readiness — executed offline interfaces

Base 1d548b3aaa8596a5ba9227675bba3adf4f92576c; branch chatgpt/atlas-rebuild-v1.
**PAPER startup NO; production NO-GO. B1/C1/D1/E1 BLOCKED. All 21 decisions unchanged; Phase 2 HOLD; Phase 3 BLOCKED; AFI-1–10 PENDING.**

The complete master roadmap, permanent instructions, queue/state, Q7 recovery/acceptance and multi-strategy inventory were read. Branch/HEAD matched; tracked tree was clean at entry. Existing untracked artifacts were inspected through Git status and preserved, without opening private financial evidence. Source text/AST only was used for runtime inspection; application modules with singletons were not imported. No running process census, Docker operation, provider request or operational storage access occurred. Frontend instructions were read; no frontend source changed.

## Actual startup and selected-lane paths

`backend/app/main.py:lifespan` calls `require_startup_authorization()` and then the provider gate before lifespan startup I/O. Existing module-level imports occur before lifespan, however; source refusal is not proof that imports have no store initialization effects. `_boot_services` hydrates shadow runtime, requires the provider gate, connects the Hyperliquid adapter, invokes `PaperJournal.bootstrap_session`, then starts multiple strategy/research workers. Bootstrap/individual service exceptions may be logged while subsequent services continue. Those are current integration conflicts, not safe canonical READY semantics. Nothing in this execution imported or ran this entry point.

### Quality Dips

1. `investment/scan.py` / `engine.py` produce investment research/plans/book activity. `api/investment_board.py:_build_quality_dips_board` reads source research/plans, schedules target refresh and obtains quote overlays, builds the board and attaches V2/V3 evidence.
2. That board refresh calls accumulation-store `sync`, `append_v3_forward_observation`, V3 state/event `mark_event`/`remember`/`save`, delivery, lot marking and terminal closure. It is not a write-free financial view, even though much of its output is research.
3. The lot entry path is distinct: `investment/prospective_evidence.py:collect_board` appends a frozen observation, then calls `quality_dips_paper.mirror_forward_observation`. Eligible frozen levels create native long-only lots through `open_lot`. The source observation append and financial append are separate commits without one canonical operation/projection receipt.
4. Native `mark_lot` / `close_lot` append V1 lot events. `quality_dips_paper_terminal.close_terminal_quality_dips_paper` requires the thesis/integrity terminal policy and supplied fresh quotes. V1 is whole-lot/gross-only; it has no partial quantity/cost/cash account contract equivalent to Q4–Q7. Native event-ID retry is not proof of cross-process exactly-once publication or acknowledged commit.
5. `api/archive.py` reads `portfolio_snapshot`; `services/cross_strategy_scorecard.py` also reads it. On reconstruction failure, the latter can supply zero-count fallback rows alongside `FAILED_ISOLATED` metadata; such a payload must not be accepted as authoritative financial flatness. No existing fallback behavior was modified here.
6. `static/quality_dips.html` polls `/api/investments/quality-dips`; `static/investment.html` polls that surface plus `/api/live` and prospective reports. These are current legacy/research contracts, not the Q7 account-summary contract. Q7 data is not connected to those pages.

### Hyperliquid

1. `perp_manual_service.refresh` uses adapter data -> discovery/setup reconciliation/board -> last snapshot and persisted metadata. `api/perp_manual.py` exposes manual board/status, risk/control and manual plan/entry/close routes.
2. `/api/perps/manual/setups/{setup_key}/enter` calls `enter_discovered_setup` -> `enter_setup` -> memory plan/setup updates -> `_persist_state` -> response. `/manual/plans/{setup_key}/close` similarly calls `close_entered_plan` -> `close_plan` -> memory updates -> persistence. These are manual snapshot transitions, not an atomic shared PaperJournal fill or canonical receipt. Per-plan whole-close assumptions and memory-before-persistence behavior need accepted versioned routing.
3. `perp_alert_delivery.paper_once` independently calls `perp_setup_paper_mirror.sync`. That mirror maintains pending instructions and opens/marks/closes shared PaperJournal positions. The micro coach/instrumented try-symbol path and equity day mirror are other writers of that same native journal, not excluded merely by selecting manual BTC/ETH/SOL.
4. `paper_risk_controls.save`, risk-window readers, observability, recap, V4 shadow/journal observer and hardening hooks add control/projection/report dependencies. `api/diagnostics.py:diagnostics_paper_test` can create/update/close a simulated journal position and must be denied or independently excluded from a selected operational epoch.
5. `api/perp_manual.py` status/board combines native manual plans, automatic mirror and journal observability. `api/live.py`/Command Center/archive surfaces read legacy journal/cache state. `static/command_center*.html` and `dashboard_shell.html` fetch those APIs; `frontend/src/app/page.tsx` fetches `/api/live`. None consumes the new unregistered Q8 adapter.

## Source-derived writer/resource inventory

This is the complete reviewed source-role inventory for the two selected lanes and the shared resources/adjacent writers they can collide with. It is not an authenticated inventory of actual files, runtime instances, plugins or undisclosed external clients. Resource roles below are source constants/interfaces, not a published private financial-source inventory.

| Writer / entry surface | Resource / mutation role | Admission, receipt and drain requirement |
|---|---|---|
| `investment/scan.py`, `engine.py`, `paper_book.py` | Investment research/plans, book ledger/account snapshot, marks | Separate investment account; exclude from selected canonical resources or independently admit; split publication audit is not a joint commit |
| `prospective_evidence.collect_board` / `append_record` | Frozen research observation, then Quality Dips lot mirror | Admit both evidence and financial operation; bind versions and durable intent/ack; no blind retry on unknown second commit |
| `quality_dips_paper.record_decision/open_lot/mark_lot/close_lot` | V1 decision/lot journal | Exact lot/operation identity, complete source inventory, version-aware partial/cash adapter; no whole-close substitution |
| `quality_dips_paper_marking`, `_terminal` | Quote-based marks and thesis-terminal closes | Fresh bound evidence; report/close must wait for all financial acknowledgements |
| `api/investment_board._build_quality_dips_board` | Fan-out of forward evidence, ladder/state/event, mark and terminal writers | UI refresh is a mutation origin; must not bypass writer roster or admission closure |
| `quality_dips_v3_forward_store`, `_state`, `_alerts`, `_delivery` | Forward observations, state/event/alert dedupe and delivery metadata | Metadata writers have their own durability/ownership needs; observations/alert sent status are not financial receipts |
| `quality_dips_v2_target_cache`, quote service/providers | Target/evidence/quote/cache refresh and tasks | Account separately for in-flight work; cache freshness is not financial commit proof or provider permission |
| `services/quality_dip_scanner` and investment accumulation store | Alert cooldown, ladder state and research monitor loops | Stop/exclude background/ladder tasks; include metadata publication in final drain |
| `services/accumulation_ladder`, `services/btc_accumulation` | Stock/BTC manual-buy alert ladders and Redis hit/near dedupe | Alert/research services,not separate funded PAPER accounts; shared Redis/provider/delivery ownership still matters |
| `perp_manual_service` entry/close/create/refresh/ack/stop | Manual snapshot, setup history, plan cache and metadata | Route approved financial mutations through accepted canonical authority; independent metadata admissions and pending publication refusal |
| `ManualPerpStateStore.save` | Atomic snapshot/temp/pending publication surface | Protect full namespace; preserve failed publication evidence and applied revisions; source path alone not trust |
| `perp_alert_delivery.paper_once`, `perp_setup_paper_mirror` | Automatic pending/filled/cancelled instructions; journal entry/excursion/exit | Competing financial writer; disable/exclude for manual-only scope or explicitly admit; per-order and canonical receipts required |
| `perp_micro_coach`, `paper_try_symbol`, pipeline hooks | Automatic micro entries, excursion/exit/cache mutations | Shared journal means roster membership/exclusion is mandatory; no hidden automatic entries |
| `equity_daytrade_paper_mirror` | Equity pending events plus same journal entries/exits | Distinct cash/calendar/cost model; exclude or route independently; pending fsync/cancel gaps remain |
| `PaperJournal` bootstrap/open/mark/flush/close/interruption methods | Shared journal, session and in-memory position state | Administrative INTERRUPTED/session rollover is not a priced liquidation; native V1 partial assumptions remain incompatible |
| `api/perp_manual` kill-switch and `paper_risk_controls` | Risk control cache/file, UTC-day/session source readers | Admission and durable acknowledgement for controls; no caller flag grants accepted authority |
| `api/diagnostics` test helpers and standalone native store users | Direct synthetic journal mutations outside manual flow | Explicitly deny/exclude; an API route name is not authorization |
| `runtime_hardening`, `v4_journal_observer`, shadow bridge/runtime | Secondary manual save, shadow/event/checkpoint records | Secondary failure cannot become financial success; keep shadow resources/accounts separate and drain own writers |
| `daily_paper_recap`, cross-strategy/attribution/observability/archive consumers | Derived reports/caches/checkpoints and possible delivery state | Financial reports must bind complete sources/applied revisions; failed-read zero fallback not authoritative |
| Prediction/investment/crypto-research writers | Separate native stores, possible shared process/provider/control dependencies | Preserve separate account semantics; prove resource separation/exclusion rather than omit from process shutdown roster |
| `main.py`, `desktop_control`, Windows manager/worker | Bootstrap/session/stop/runtime ownership and lifecycle artifacts | Durable operation identity and truthful shutdown outcome; process exit alone is not financial reconciliation |
| Q4–Q7 fixture publishers/reports | Explicit disposable canonical/native/report resources only | No production imports/dispatch; caller-supplied fixture pins are never trusted operational authority |

Independent external Docker clients, local privileged actors and unenumerated writers remain outside a cooperative Atlas lock's demonstrated authority. No source-only table proves C1 complete ownership.

## Actual shutdown and restart gaps

`main.py` creates `ShutdownReport(timeout=20.0)`, stops watchdog/boot, then investment/research/delivery and listed service loops; manual/mirror/micro/metadata writers have distinct stop methods. It then drains quote providers, reconciles pending native PAPER instructions, persists native open marks and calls `interrupt_open_for_shutdown`; dependency cleanup runs only when existing outcome checks allow it. This is not Q7's entry-close -> financial drain -> price-backed remaining exit -> canonical reconciliation -> immutable report -> final drain sequence. Provider teardown before priced canonical exit is an integration conflict. There is no admitted all-selected-writer roster or canonical UNKNOWN/report barrier in this path.

Windows `Atlas-Background.ps1` has parent/direct-worker/worker-function refusal checks; `Stop-OwnedApi` uses verified process identity and a30s bounded wait. `DesktopControl` writes a run manifest, observes a matching stop request and signals its own process for Uvicorn lifespan cleanup. `Invoke-StopWorker` checks run/process identity, records timeout and avoids force termination. Its `finally` removes its matching stop lock even after failure; this is not equivalent to retaining a canonical financial uncertainty fence. No stop behavior or deadline was altered.

Restart currently depends on legacy session/bootstrap/manual/journal semantics, not accepted new-epoch revision/projection/cash proofs. Main startup refusal remains intact. Future integration must refuse unknown admission/storage/clock/financial state before all operational side effects, preserve uncertain intent and independently establish writer/helper exit. Import-time singleton side effects and off-loop task ownership need separate accepted evidence. No forced kill, unrelated process action, Docker Desktop/Engine stop or automatic uncertainty clearing was introduced.

## Executable inert adapters

Implemented `services/paper_summary_contract.py`, a store-free extraction of Q7 validation/canonical presentation values. `paper_portfolio_fixture.py` re-exports the existing public functions. Q7V1 renderer AST remains identical and its output is checked against exact golden bytes; no retained format/layout change.

Implemented `services/paper_runtime_boundary.py` with no store, fixture-store, API/router, provider or startup import. Default construction is inert. Every mutation submission refuses unconditionally before calling injected dependencies, including caller-supplied approval/receipt claims. There is no successful mutation switch, accepted-authority shortcut or environment override.

Explicit read injection binds expected strategy/epoch rows and validates the entire existing versioned portfolio envelope. Stale/future observations, missing/substituted accounts, malformed financial/authority data, source exceptions and revision/head contradictions refuse. UNKNOWN is displayed honestly and never resets a prior revision watermark. Concurrent reads fail fast rather than accept racing stale results; no worker thread or daemon is created. These in-memory read checks are not durable anti-rollback, trusted clocks or native ownership proof. An injected source must satisfy an independently accepted bounded-read contract before operational use; this adapter does not pretend to cancel an indefinitely blocked callback.

`PaperReadOnlyPresentation` emits deterministic JSON and an inert escaped HTML fragment with version2 layout: strategy/epoch, state, simulated opening cash, reconciled cash, gross/cost/net, remaining quantities, source revision and financial-event freshness. Equity and cross-account totals remain unavailable. It does not register an endpoint, instantiate a source or expose a write selector. Actual dashboard/API integration status: **NOT CONNECTED**. The existing UI/GET mutation paths described above remain unchanged and must not be silently relabeled read-only.

## Strategy continuity and reusable next component

The full Q7multi-strategy matrix remains in force: Quality Dips; long-term stocks/ETF accumulation; equity day trading; Hyperliquid manual/mirrors/micro and meme tiers; A+technical profiles/context; V4shadow; V5/V6/E28/E29 research; prediction PAPER; crypto Quality Dips evidence; portfolio/ETF/benchmark/manual research; AFI/replay/holdouts and extended-hours observation. None has new operational acceptance. Q8 adds inert read/refusal-only interfaces,not runtime activation, financial account consolidation or additional execution strategies.

Source inventory clarification: `services/accumulation_ladder.py` and `services/btc_accumulation.py` are existing stock/BTC manual-buy alert services, distinct from `investment/accumulation_ladder.py`'s persisted board ladder. They write alert/dedupe state and must be rostered/excluded; they do not provide an independently funded PAPER entry/exit/cash engine. Default price/notional levels are configuration,not accepted capital or fills. They remain research/manual alert lanes; automatic Discord remains denied. This supplements the prior inventory without altering history.

Most reusable expansion component after Quality Dips/Hyperliquid: the store-free versioned read/receipt boundary plus an accepted all-writer admission/drain interface, reused by a separately scoped investment book adapter. Strategy-specific buy/sell/partial/corporate-action/cost/calendar semantics still need implementation/acceptance. Do not duplicate a ledger for each signal profile or pool prediction/spot/derivative/shadow cash.

## Actionable independent acceptance checklist

| Gate / responsible role | Required external artifact and decision | Codex-safe offline work versus boundary |
|---|---|---|
| B1 — source custodian plus independent accounting/scope reviewer | Authenticated complete original archive/exposure/cashflow/correction inventory and private discrepancy disposition; explicit new-epoch historical-isolation decision, hypothetical opening/cost/currency/risk inception and unique resource binding | Can validate supplied packages and math disposably. Cannot certify omitted history,declare legacy exposure closed,waive scope or manufacture independent source proof. No private evidence accessed/published here. |
| C1 — Windows lifecycle owner plus independent process/writer reviewer | Fresh actual PID/creation/image/command/owner/children and exact resource/writer roster; entry closure,in-flight/UNKNOWN inventory,complete drain/reconciliation/report/final-drain and independent exit proof | Can trace source and test injected/dummy writer contracts. Cannot promote fixture ownership or a stopped parent to actual all-writer quiescence; external writers require separate exclusion proof. |
| D1 — security/storage authority plus operator | Accepted identity-before-access namespace/sidecar design and native enforcement;trusted issuer/operator context,bounded clock validity,revision/rollback witness and explicit uncertain-state recovery rules;separate provisioning permission | Can implement pure/inert contracts and adversarial fixtures. Cannot use path-based fixtureSQLite,local files,clock arguments or UIYes as trusted operational authority. No provisioning/ACL/registry/key/TPM action. |
| E1 — data-rights owner,storage/lifecycle reviewer,independent release authority and operator | Endpoint/account/purpose rights;aggregate wire/reconnect budgets and authorized feed continuity;complete persistence/backup and isolated restore evidence;native owned lifecycle and deferred GUI/legacyStop acceptance;bounded manual session approval and21gate review | Can prepare acceptance cases and inspect supplied evidence offline. No provider contact/collection,backup/restore,protected startup or operational test without separate permission. |

For each artifact record producer,independent verifier and independence basis,scope/run/release/resource/schema/revision/cutoff,source provenance/hash,exact tests/failures/limits and explicit acceptance reference. No approval signature is issued here. B1/C1/D1/E1 remainBLOCKED until accepted by those roles.

## Next three bounded actions

1. Independent reviewers supply/adjudicate the selected-lane B1/C1/D1 evidence above;Codex validates the permitted package without adopting records or clearing uncertainty. No new implementation can substitute for that decision.
2. After prerequisites and separate file-level permission,implement accepted storage/receipt/writer interfaces for one selected lane. Limit initial native entry/exit routing to `perp_manual_service.py`/`api/perp_manual.py` or separately approved Quality Dips writer;do not import fixture stores as authority or enable protected dispatch.
3. After accepted routing,authorize and test the read-only API/dashboard connection and canonical shutdown/restart protocol under existing budgets. Start with disposable resources;actual provider/native/session acceptance is a separate authorized window. Preserve all other strategy scopes and startup refusal.

All eligible Q8offline interfaces and source-review work are complete after validation/publication. Runtime registration,protected financial writes,record migration,provisioning,provider access and startup remain outside this authorization. Verified validation/checkpoint/publication details are in the Q8continuation document.


## Exact validation

Final single combined selection182passed,0failed,0skipped in24.52s,including16newQ8cases. Q8boundary tests plus Q7workflow/portfolio,actualQualityDipsV3policy,Q4epoch/Q5-Q6strategy fixtures,QualityDips native handoff/lot/terminal/mark/exit policy,Hyperliquid epoch/nativefacade and Stage34D/E/Pythonstartup-refusal selections. Earlier32focusedpasses overlap;not added. Prior412Python/763JS not rerun. Targeted Ruff,compilation,four PowerShell file parses and diff checks passed. No frontend source changed,no build/browser/runtime acceptance claimed.

Tests cover inert default/unconditional mutation refusal,explicit disposable reads and V2presentation,missing/substituted/stale/future/malformed evidence,source failure without cached success or sensitive message,UNKNOWN watermark retention,revision/head conflicts,concurrent-read refusal,neutral import isolation and exact retained V1HTMLgolden bytes/renderer AST. Initial lint findings were corrected without suppressions;retained-source renderer was inspected structurally rather than executed dynamically. There are no current failed/skipped tests. Existing protected Python/Windows/API/financial writer sources match the base commit under repository newline normalization, with no Git diff.

Acceptance roles listed above are required responsibilities,not evidence that reviewers have been appointed or approvals supplied. No private financial evidence was opened during Q8. All new source/fixture/publication work remains within the authorized offline boundary.
