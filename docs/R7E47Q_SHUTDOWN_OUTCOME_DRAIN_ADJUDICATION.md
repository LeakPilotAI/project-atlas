# R7E47Q — bounded shutdown outcome and drain-budget adjudication

**Offline corrections and isolated acceptance complete; production NO-GO.** Work crossed October18–19,2026 America/Chicago CDT UTC-05:00; finalized 2026-10-19T00:08:07.158742-05:00. Evidence directory retains its start-date label logs/diagnostics/r7e47q-20261018. Branch chatgpt/atlas-rebuild-v1;HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0 unchanged. STOPPED is operator-reported inherited status; no fresh production process/Docker audit.

## Complete teardown call-path findings

1. Verified Windows manager writes exact-run stop request and waits30seconds for owned PID exit; timeout retains owner/process, never force-kills. DesktopControl._watch raises SIGTERM; Uvicorn drains requests before lifespan. Its pre-lifespan connection/task drain is outside this new application budget. No manager/launcher change.
2. Lifespan previously ran cleanup only after a plain yield, not finally. Watchdog failure or waiting indefinitely for canceled boot could abort remaining cleanup. Watchdog stopped heartbeat without proving sampler-thread exit. Boot invokes to_thread and creates unretained paper_session_announce/discord_bot tasks; cancellation is not proof that off-loop work exited.
3. Cash stop wrapper and InvestmentScanner.stop hid task errors. Research stop cancels its loop and collector, retaining collections/commits on timeout. That20s wait followed by quote shutdown20s could exceed manager30s before other cleanup. Research universe-loader to_thread ownership is not fully proven by collector drain.
4. Discord.close error was logged then stopped success; failed already-completed bot task could be discarded. The14service stoppers and2optional accumulation stoppers mostly propagated errors, but prediction hid task failures, coach hid HTTP/mark/flush failures, and manual planner hid persistence errors. Multi-task legacy stoppers can still stop awaiting siblings after a failure; refusal, not a successful exit inference, is required.
5. Quote shutdown closes admission, cancels coalesced requests, concurrently drains provider supervisors within passed budget. Provider dispatcher rejects queues and keeps real non-daemon workers owned; caller cancellation is not thread termination. A failed commit drain can finish later; failure never establishes no-writes. If shared budget expires before a later stopper is entered, that step is NOT attempted and cannot confirm closure. Early all-consumer admission closure remains operational work.
6. Registered Hyperliquid WebSocket/client transport was not closed by lifespan; now registry closure is requested only after producer stops are acknowledged. Individual adapter errors aggregate; unrelated adapters still get an independent close attempt.
7. PAPER pending reconciliation, open marks and interruption previously only logged exceptions. persist_open_marks swallowed row errors; _append suppressed fsync failure. flush is a no-op because append performs flush/fsync; therefore a successful flush return alone is not durability proof. Existing ATLAS_SHUTDOWN pending-mirror reason still preserves manual pending orders; no PAPER event/authority policy changed.
8. Redis and engine.dispose exceptions were discarded and final success depended only on service flags/provider drain. P Redis correction preserves both-close failure; Q now includes it in application result. Desktop manifest errors were swallowed and matching manifest removed despite earlier cleanup errors; failures now retain evidence and mismatched identity refuses deletion.
9. Logs were the only final result and logger failure could abort cleanup. Application now owns a structured in-memory report, with exact original exceptions/task references, and raises a grouped ASGI teardown failure if incomplete. The existing manager still verifies process exit, not this report; durable manager acknowledgement is NOT implemented or approved.

## Outcome contract

| Outcome | Evidence |
|---|---|
| COMPLETE | Sealed required cleanup acknowledgements, no recorded failures/unknown evidence, no owned cleanup task pending, budget not expired; final reporting succeeds. Scoped application cleanup, never database-restoration/process/global-writer proof. |
| INCOMPLETE | Required cleanup failed with an original exception, without an additional unresolved-exit condition. Independent safe cleanup continues. |
| TIMED_OUT | Shared or child drain deadline expired. Pending cleanup supervisors remain referenced, uncanceled by the timeout wrapper. Late completion never upgrades outcome. |
| UNKNOWN | Interrupted cleanup/startup, unverified legacy boot-task exit, unverified producer exit, missing evidence or reporting failure. Never silently upgraded. |

TIMED_OUT takes precedence over UNKNOWN, then INCOMPLETE; unsealed reports are UNKNOWN. Successful duplicate step names/finish are idempotent; failed/active step replay refuses, not retry permission. Completion/failure is independent of a log message. BaseExceptionGroup preserves each original cleanup exception, including CancelledError; failure of teardown during an exception from the yielded context retains that earlier exception as context. No API route/response schema or trading interface changed; failed lifespan teardown now raises instead of falsely succeeding. app.state.shutdown_report is ephemeral evidence, not a durable recovery/startup registry.

## Bounded corrections

Same stop order and existing service APIs retained except additive DesktopControl preserve_manifest keyword and private manual persistence strict keyword. No production startup admission integration.

- core/shutdown.py supervises named asynchronous cleanup with asyncio.wait under one20s absolute monotonic deadline, original exception aggregation, owned late-task retention, safe logging and explicit final outcome. It never uses wait_for to await cancellation indefinitely or forcibly kills workers.
- main.py executes teardown in finally, records watchdog/boot/service/provider/reconciliation/Redis/database/desktop errors, passes decreasing remaining budget to research/quote drains, and suppresses false final success. If producer exit is unverified, adapters and downstream dependencies are conservatively retained; PAPER reconciliation is skipped. Boot interruption or a still-active legacy named boot task yields UNKNOWN, without terminating a task by name. Desktop stop retains runtime manifest on prior failure/uncertainty.
- Investment shutdown propagates its original task error through the wrapper. C1-C4 scanner AST outside the2stop functions is unchanged.
- Prediction, Discord, adapter registry and coach aggregate hidden errors and continue independent safe work. Failed references retained. Coach attempts marks/flush and retains failed HTTP client; journal formats/positions untouched by this execution.
- Manual-state persistence remains nonthrowing on normal calls; stop drains its task then requests strict persistence, preserving the original exception on failure.
- PAPER marks attempt every row and aggregate failures. Normal fsync handling remains compatible, but its first original failure is retained on the journal instance; shutdown checks it before/after interruption and refuses success. This is volatile failure evidence, not retroactive disk-integrity certification or an authorization to retry possibly committed writes.
- Desktop stop propagates corrupt/unavailable/mismatched synthetic manifest errors; explicit preserve_manifest retains evidence while stopping its watcher. Watchdog awaits observed sampler exit within the outer deadline.

Changed/new source/test files:
- backend/app/core/shutdown.py
- backend/app/main.py
- backend/app/investment/scan.py
- backend/app/alerts/discord.py
- backend/app/adapters/registry.py
- backend/app/prediction/prediction_paper_automation.py
- backend/app/services/perp_micro_coach.py
- backend/app/services/desktop_control.py
- tests/test_r7e47q_shutdown_outcomes.py
- tests/test_r7e46r_shutdown_contract.py
- tests/test_r7e46h_startup_integration.py
- backend/app/services/runtime_watchdog.py
- backend/app/services/perp_manual_service.py
- backend/app/services/paper_journal.py
- tests/test_paper_shutdown_reconciliation.py

## Drain and security limitations

No timeout increased: previous20s research and20s quote defaults remain unchanged for standalone users; lifespan shares a single20s budget across its teardown. Manager30s unchanged. This removes sequential budget renewal, but cannot establish an end-to-end30s process bound. An event-loop timer cannot preempt synchronous file I/O, fsync, imports, logger calls or arbitrary non-yielding Python/native code; finish detects overrun after control returns. Uvicorn pre-lifespan draining, executor/to_thread work and external writers remain outside demonstrated coverage. No claim of no orphan/global quiescence, writer exclusion, durability after unknown fsync, or recovery clearance. Timeout may leave work and dependencies alive; operator evidence review required. Inspection startup/recovery refusal contracts unchanged. Normal PAPER8s/default Gaming discovery>=180s, provider3per/6combined workers, pacing/queues/quarantine and both central Discord restrictions unchanged.

## Tests and static validation

Original actual-source AST reproducer confirms false complete after Redis failure (original-confirmed.txt); preserved before repair. Tests execute actual teardown/child-method AST with inert dependencies, not app startup. Synthetic files only.

- Final focused shutdown/provider/cash/Gaming/activation/repair suites: **187passed,0failed,0skipped;14.64s**.
- PAPER journal/prediction/persistence compatibility: **40passed,0failed,0skipped;2.45s**, one inherited discord audioop deprecation warning.
- Native isolated S/T/V ownership/lifecycle: **82passed,0failed,0skipped;35.26s**.
- **Non-overlapping final total309passed,0failed,0skipped,0xfail.** Earlier178/181/intermediate runs not added. E136 expected failures not rerun, remain blockers. Not a full canonical suite.

Cases include Redis primary/fallback failure(Ptests), DB/multiple failures, watchdog/desktop/provider/research/adapter/mark/fsync errors, cancellation-ignoring worker, pending queues/exhausted/shared budget, logging failure, caller/context interruption, original exception identity, late results, repeated shutdown report, manual strict persistence, sibling task errors, retained manifest and no forced termination.

Preserved interim evidence: sandbox asyncio launch stalled/canceled by exact tool session; first fixture lacked asyncio in isolated AST namespace(1failed169passed); evidence directory discord.py copy shadowed installed package(1collection error), runner now removes evidence directory from module search; legacy source-order assertion expected direct await(1failed39passed), updated to preserve ordering through bounded wrapper. Existing h/r tests adapted to actual finally/wrapper, not removed. No unresolved final product/test failure.

Targeted new shutdown/helper Ruff passes. Whole-tree Ruff3977 versusP3995. Raw file/rule/message multiset reports19resolved/1new; contextual review proves the apparent new item is an unchanged /health BLE001 whose occurrence matching shifted when identical teardown warnings disappeared. Full post-lifespan suffix bytes and health AST match original, so contextually18resolved/0new. No unrelated health edit, suppression or baseline waiver. Full lint remains BLOCKED. Static-results.json retains exact diagnostic and comparison evidence.

All15changed/new Python files compile and match guarded tested source. PS5.1 parses18scripts0errors; Git diff integrity passes. Twelve provider/Redis/cache/Gaming/Windows ownership controls hash-identical to P snapshot. Startup prefix/endpoints bytes unchanged; cash C1-C4 AST unchanged outside stop hooks. No dependencies installed/updated. Copied-source tests prohibit outbound sockets and production data/.env reads. Source archives not rebuilt; O structural packaging PASS remains historical only.

## Gate matrix

Only backend_current_runtime,complete_shutdown_contract,stuck_worker evidence/criteria updated. All21IDs/statuses, prior evidence, and18unrelated gate objects preserved. **5scopedPASS,13BLOCKED,3NOT_TESTED**. Isolated success is not real-container acceptance.

| Gate | Status |
|---|---|
| normal_admission | BLOCKED |
| nonclearing_quarantine | PASS |
| full_recovery | BLOCKED |
| backend_current_runtime | BLOCKED |
| complete_shutdown_contract | PASS |
| complete_shutdown_real | NOT_TESTED |
| shortcut_workflow | BLOCKED |
| backup_restore | BLOCKED |
| provider_logical_budget | PASS |
| provider_actual_http_budget | BLOCKED |
| provider_rights | BLOCKED |
| cash_scope | BLOCKED |
| stuck_worker | BLOCKED |
| ruff_disposition | BLOCKED |
| source_artifact | PASS |
| clean_machine | NOT_TESTED |
| gaming_configuration | PASS |
| gaming_performance | NOT_TESTED |
| e136_recovery | BLOCKED |
| discord_delivery | BLOCKED |
| extended_hours_activation | BLOCKED |

## Roadmap, next execution and restrictions

Mandatory verified updater only; result.json verifies original backup equality, exact checkpoint byte read-back, byte-identical outside-managed history and permanent strategy/recovery/PM-V2 anchors. Recommended separately authorized R7E47R: bounded remaining asynchronous ownership/early shutdown-admission review, including boot announcements, universe-loader/default executor work, producer exit checks and durable manager outcome handoff proposal. Source/synthetic work first; no real shutdown, no broad worker replacement without separate scope. Stop at Q.

No Atlas/Docker lifecycle, real-volume inspection/helper/backup/restoration, Genesis, protected config/ACL/shortcut, production startup registry/integration, live trading/Discord, cash scope/activation, Git stage/commit/push/reset/delete or VPS. PAPER_ONLY/MANUAL_ONLY and permanent Gaming efficiency/normal PAPER cadence unchanged.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

