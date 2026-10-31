# R7E47R — Durable PAPER and manual-state acknowledgement corrections

**Bounded source corrections and isolated acceptance PASS; global durability and production release remain NO-GO.** Executed October 19, 2026, America/Chicago (CDT, UTC−05:00). Exact UTC start/completion, hashes and checkpoint verification are in `logs/diagnostics/r7e47r-20261019/result.json`. Branch `chatgpt/atlas-rebuild-v1`, HEAD `f9df47b4cd80dd647d85043aba617cf00c4e6dc0` preserved. No production runtime verification or lifecycle action was performed; STOPPED remains inherited operator status.

This is the bounded correction requested after the October 19 lifecycle contract: the shared `services/paper_journal.py` ledger and `trading_core/perp_manual_state_store.py`, including their manual service acknowledgements and Q teardown integration. It is **not** certification of every separate PAPER engine or storage family. Additional required-record weaknesses found during tracing remain explicit release blockers below.

## Confirmed defects and acknowledgement paths

| Path | Before | Correction / acknowledgement boundary |
|---|---|---|
| PAPER `_append` | Unchecked text-write result; flush followed by suppressed fsync error. Callers could report success after failure. | Exact character count, flush and fsync must succeed. First append/flush I/O failure is re-raised and latched; later mutations/flush/reload retry cannot clear it. Existing `first_fsync_error` name retained for Q compatibility, now covers all ambiguous I/O failures. |
| `open_trade` | Inserts the new position into `_open` before append. | Append completes before confirmed in-memory insertion or successful return. |
| `update_excursion`, `note_be_armed`, `note_adaptive_exit` | Shared dictionaries and persisted watermarks changed before append. | Stage a copied row; publish it to confirmed memory only after a required append succeeds. Below-threshold live excursion updates remain explicitly volatile telemetry, not a durable-record acknowledgement. |
| `close_trade`, interruption and session roll | Existing close de-duplication existed, but errors could be suppressed; forced mark and close have separate commit points. | Required failures propagate; remove open only after close append succeeds. A separately committed final mark may survive a later close failure; this is not an invented close. Existing close and duplicate-open returns re-flush files before acknowledging persisted evidence. |
| Session start/bootstrap, candidates | Same shared suppressed fsync path; random candidate identity is not an exactly-once key. | Shared strict append; existing bootstrap session re-flushes. Candidates remain research telemetry; no exactly-once claim for candidate submissions or independently repeated mark/session requests. |
| PAPER `flush` and shutdown marks | `flush` was a no-op; Q only checked the volatile fsync latch. | Real file flush/fsync and tail check; prior failure remains original failure. Malformed loaded journal or incomplete tail refuses mutation. Marks aggregate errors; sticky failure also prevents empty/no-op mutation paths falsely succeeding. |
| Manual snapshot `save` | Fixed `.tmp` name, unchecked write count, suppressed fsync error, failed temporary evidence deleted. | Exclusive random temporary file, strict file writes, successful replacement and supported directory sync before return. No overwrite of a temporary file. Failed evidence is retained. |
| Manual interrupted publication | No durable publication-refusal record; retry could overwrite ambiguous state. | Exclusive sibling `<state>.pending` written/flushed before snapshot publication. It serializes cooperative publication, survives interrupted replace, and is removed only after successful replacement/sync. Existing pending, legacy `.tmp` or unique `.tmp` evidence refuses load/save; no auto-replay, repair, deletion or authority grant. |
| Manual service `_persist_state` | Normal callers log/suppress errors; strictness applied only at stop. | Every configured persistent operation is strict, including a legacy `strict=False` argument. Original error retained; last confirmed snapshot/history restored; further persistent actions and shutdown refuse. Success metadata for refresh is updated only after persistence succeeds. |
| Manual create/enter/close/alert acknowledgement/refresh | Return success or updated state after failed save; an existing entered plan could mask a prior error on retry. | Check persistence/recovery refusal before each action, including duplicate entry. Return only after required save; failed actions restore confirmed state. Corrupt recovered state cannot be overwritten by an action. |
| Manual API and wrappers | Routes return `ok` only after service method return. | No route schema changes. Storage errors propagate rather than returning `ok`; a generic HTTP error may still mean an UNKNOWN commit, so clients must not blindly retry. Runtime-hardening refresh wrapper re-raises its original error; it does not turn the failure into success. |

The manual store's clean existing JSON remains version 1 with the same fields. PAPER JSONL fields and event formats are unchanged. The new `.pending` and unique `.tmp` files are additive evidence, not production admission or recovery registries. An older binary that ignores them is **not** a safe automatic rollback while publication is unresolved. No existing real record or sidecar was touched.

## Required durability boundary and refusal semantics

The implemented acknowledgement means required file writes were full-length, Python buffers flushed, file fsync returned successfully, replacement returned successfully when applicable, and POSIX parent-directory sync succeeded where implemented. The original exception object/context is preserved on failure. An append that may already have written bytes remains UNKNOWN rather than being declared absent. Repeated operations on that instance refuse instead of appending again. `reload()` is not permission to clear a latched failure.

For manual publication, the intent is created exclusively before the temporary payload. Restart with unresolved evidence refuses even if the replacement JSON is valid. A failure after replacement does not imply the old snapshot survived. Once replacement and its supported namespace sync succeed, an error while retiring the intent still returns failure; the new snapshot may be fully committed. No transaction across ledger, manual state and separate pending-order stores is claimed.

`sync_parent` deliberately does not attempt unsupported directory fsync on Windows. **Windows acknowledgement is file flush plus successful replacement, not independently demonstrated directory-entry persistence across power loss.** The POSIX directory failure branch is tested through controlled operations; it is not native Linux or Windows power-cut acceptance. Successful fsync does not prove honest hardware/controller caches, prevent device loss, or substitute for independent backups.

PAPER lifecycle replay uses existing trade identity/open-symbol-side checks and terminal close evidence. Tests demonstrate no duplicate open/close for successful retry, and refusal after a possibly committed close. A new isolated journal instance can re-read a complete close and re-flush before returning it without appending. This is not full-machine rollback resistance or exactly-once execution across independent processes. Partial tails and malformed loaded rows are not silently truncated. Whole-record tail loss of this ledger still requires independent commitments/backup evidence; the extended-hours witness does not cover it.

The exclusive manual intent excludes overlapping cooperative publication to this exact pathname. It does not provide a versioned compare-and-swap of independently loaded plans, protect against external deletion/privileged writers, or prove directory-wide exclusion. Existing missing-state-as-empty initialization is not changed into a trusted recovery mechanism; lost established state remains a production admission blocker.

## Q shutdown compatibility

No lifespan order, deadline, task ownership, provider budget, Gaming cadence or Windows launcher changed. Q sees the PAPER latch before/after reconciliation, and forced marks/flush raise instead of falsely succeeding. Manual stop still drains its task then persists strictly; a prior required persistence failure remains the same original error.

The isolated sealed-report test demonstrates **INCOMPLETE**, retaining the original persistence exception while an independent cleanup completes. An earlier strengthened test expected INCOMPLETE with no completed cleanup steps; Q correctly returned UNKNOWN. That failed assertion is retained in `focused-verified.txt`; the fixture was corrected to provide an independent successful cleanup, without changing Q code or weakening outcome rules. Interrupted/insufficient evidence remains UNKNOWN. The report is still in-memory; authenticated durable manager acknowledgement and end-to-end drain acceptance remain blocked.

## Fault-injection evidence and validation

Tests execute copied source under a guard denying production `data`/`.env` access and external service connections. Production singletons in the new tests are omitted by AST; existing compatibility imports resolve into the isolated copied application. The test-only trusted-source `exec` has a local, explained S102 annotation; no runtime lint suppression or baseline waiver was added.

- Preserved original-source reproducer: **8 failed, 2 passed**, 17 cases deselected at that stage. These are expected original defects, not final unresolved test failures. Initial baseline also exposed a fixture lacking the BTC universe; corrected baseline is `original-confirmed-final.txt`.
- Final focused R/Q persistence and shutdown: **70 passed, 0 failed, 0 skipped** (`final-accepted.txt`).
- Final PAPER/manual/API/provider/cash/Gaming compatibility, 45 modules: **268 passed, 0 failed, 0 skipped**, two inherited dependency deprecations (`compatibility-final.txt`).
- Isolated Windows S/T/V ownership/lifecycle: **82 passed, 0 failed, 0 skipped** (`lifecycle.txt`).
- **Non-overlapping final total: 420 passed, 0 failed, 0 skipped, 0 expected failures.** Intermediate runs are not added. This is not the full canonical suite; E136 expected failures remain outstanding.
- Six changed/new Python files compile. Windows PowerShell 5.1 parser: **18 scripts/modules, 0 errors**. No script executed production lifecycle actions.
- Targeted correctness/security checks on the three runtime modules: **8 inherited findings before and after** (6 BLE001, 2 S110); new helper has zero. New R test/default Ruff checks pass. Full-tree comparison and exact final counts are in `ruff-summary-final.json`; lint gate remains BLOCKED, with no approved baseline.
- Git diff integrity and source/branch/worktree preservation are recorded in `result.json`.

Fault coverage includes write exceptions, full-disk ENOSPC, short writes, flush and fsync exceptions at intent and snapshot boundaries, replacement failure, directory-sync failure, interrupted publication, pending/legacy-temp restart refusal, concurrent cooperative publication refusal, corrupt JSON, successful replay, ambiguous close replay and manual action/refresh rollback. Metadata/identity review is isolated; no real database, Engine, power loss, production volume, backup or restore was tested.

Harness limitations are preserved: initial default temporary directory was inaccessible; initial Windows sandbox asyncio socket-pair creation stalled. Those test processes were interrupted without touching services. Guarded tests then ran with permission for Windows internal loopback support. The guard continued to deny external service connections and production data. No missing result was counted as PASS.

## Remaining required-record risks found during tracing

Inventory: `logs/diagnostics/r7e47r-20261019/persistence-path-inventory.txt`. This milestone does not silently relabel other stores as durable.

| Separate family | Evidence / disposition |
|---|---|
| Perpetual/equity pending-limit mirror journals | `_append_pending_event` / `_append` still suppress fsync errors. Cancellation can remove pending memory before append. Cross-store fill/pending transaction and retry accounting require a separate bounded correction. **BLOCKED**; no scanner eligibility or sizing changed here. |
| Prediction PAPER journal | `prediction/paper_engine.py::PredictionPaperJournal._append` suppresses fsync error. Its separate identity/replay contracts need scoped fault acceptance before a global durable-PAPER claim. Prediction Market Intelligence V2 restrictions remain intact. |
| PAPER risk-control snapshot | `paper_risk_controls.py::save` uses write/replace without strict fsync; in-memory controls and persisted confirmation need separate adjudication. **No risk limit or kill-switch policy was modified.** |
| Investment `PaperBook.save` | Direct JSON overwrite, no demonstrated atomic file/namespace commit. Separate engine remains unaccepted for a blanket durability guarantee. |
| Quality Dips journal | Flush/fsync exceptions already propagate; short-write, ambiguous retry and independent integrity acceptance are not proved by that fact. Existing cash C1–C4 scope remains untouched. |
| Observability/cohort/cache snapshots | Some are best-effort health telemetry; cohort boundaries can influence analysis and cannot automatically be treated as disposable. No execution/fill authority may be inferred from them. |

Consequently the global statement “every Atlas PAPER store is crash durable” remains **BLOCKED**. Other blockers include Windows namespace power-loss acceptance, independent backup/restoration, full disk-loss/rollback coverage, all-entry admission and real shutdown acceptance. No live or unattended authorization follows from the isolated tests.

## Files changed by this milestone

- `backend/app/core/durable_io.py` — new full-write/flush/fsync and platform-scoped directory-sync helpers.
- `backend/app/services/paper_journal.py` — strict append/flush, failure refusal and post-write state publication.
- `backend/app/trading_core/perp_manual_state_store.py` — exclusive intent/temporary publication and strict errors.
- `backend/app/services/perp_manual_service.py` — required acknowledgements and confirmed-state rollback/refusal.
- `tests/test_r7e47r_durable_acknowledgements.py` — new hermetic fault and restart tests.
- `tests/test_r7e47q_shutdown_outcomes.py` — three existing test contracts adapted to strict persistence/guards, retaining error-propagation assertions.
- `docs/R7E47R_DURABLE_PERSISTENCE_ACKNOWLEDGEMENTS.md` — this report.
- `docs/R7E47O_PHASE1_RELEASE_GATE_MATRIX.json` — only affected runtime/durability and isolated shutdown evidence, plus review label; all 21 identities/decisions preserved.
- `PROJECT_ATLAS_MASTER_ROADMAP.txt` — managed checkpoint through the verified updater; backup retained.

Diagnostics and isolated source/fixtures are retained under `logs/diagnostics/r7e47r-20261019`. No staging, commit, push, reset, service operation, shortcut/ACL/configuration change, real-volume inspection, backup/restoration, automatic Discord, Genesis access or trading-authority change occurred.

## Gate decision and next bounded work

All 21 gate statuses remain **5 scoped PASS, 13 BLOCKED, 3 NOT_TESTED**. Only `backend_current_runtime` and `complete_shutdown_contract` receive R evidence. Isolated durability does not pass real-runtime storage, container shutdown or backup acceptance. The full authoritative owner/dependency/acceptance matrix remains `R7E47O_PHASE1_RELEASE_GATE_MATRIX.json`.

Recommended next execution: **bounded pending-limit and prediction PAPER acknowledgement adjudication**, using the identified append suppression and cancellation-before-persist reproducers, preserving all risk/scanner/V2 policy. Risk-control and PaperBook snapshot corrections then require their own bounded acceptance. Do not begin runtime integration or another general recovery-security redesign.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.
