# R7E46M — extended-hours activation and rollback readiness

**Source/readiness validation GREEN: 99 focused tests passed. Production activation remains BLOCKED pending separate approval.**

Date: 2026-10-16 (America/Chicago, CDT, UTC−05:00).
Branch `chatgpt/atlas-rebuild-v1`; HEAD `f9df47b4cd80dd647d85043aba617cf00c4e6dc0`.
This milestone does not claim full-repository release acceptance, live collection,
production rollback acceptance, or sustained operation of the new contracts.

## Current runtime and source reconciliation

The supported `Atlas-Background.ps1 -Action Status -Json` independently verified
**running API PID 24804**, launcher PID **4836**, run
`f670a59a-e41b-450f-9371-38208c0fc88d`. The API's read-only gaming diagnostic matched
that PID/run; `/health` returned `ok`; actual Gaming Mode was **false**. Its recorded
API creation time is `2026-10-16T10:57:55.6552340Z`. These were verified, not assumed
from the historical identifiers in the request. Final re-verification is retained
with UTC timestamps in the evidence directory.

No Stop, Start, restart, recovery, Docker action, process signal, production
collection call, or test notification was issued. The existing backend continues
to run. Its command has no reload switch; editing source does not install the new
endpoint/contracts into that already loaded process. The production research journal
was absent at baseline. There was no matching extended-hours startup log in the
inspected current boot minute. Neither fact is treated as proof of a loaded feature
flag: current process-level feature activation telemetry is **not available** until
a separately approved startup loads the new diagnostic contract.

The master roadmap's managed checkpoint was R7E46L. Its permanent execution/recovery
contract and seven-phase Market Intelligence OS strategy were recovered and retained.
The working tree already contained substantial source changes, untracked prototypes,
backups, and test evidence. R7E46M preserves them; unrelated cash-session scanner and
calendar code were not edited. A future restart will load **all** pending applicable
source, so a complete working-tree release review is an activation prerequisite.

## Audit findings and exact changes

| File | R7E46M change |
|---|---|
| `scripts/windows/Atlas-Background.ps1` | Explicit Start-only `-EnableExtendedHoursResearch` switch. Before spawning its owned worker, supplies feature environment true only for this switch, otherwise false; restores the controller's prior environment on success/failure. Status/Stop do not toggle anything. |
| `scripts/windows/Atlas-Background-Gaming.ps1` | Optional explicit research switch forwarded to the encoded manager Start. Merely selecting Gaming Mode never supplies that opt-in. Gaming environment restoration remains intact. |
| `backend/app/services/extended_hours_research.py` | Corrects the stale claim that startup is unregistered; adds actual PID/run, environment versus latched activation, task state, cycle/error/commit counters and timestamps. Keeps errors isolated from other services. Production uses the post-fetch validation clock; explicit fixture clocks remain supported. |
| `backend/app/investment/extended_hours_collector.py` | Rejects boolean prices and missing source provenance; validates persisted research schema and duplicate identities before append. Moves bounded Windows locking/replay/fsync off the event loop and drains an in-flight commit when canceled, including repeated cancellation. No truncation/replacement/deletion recovery added. |
| `backend/app/api/diagnostics.py` | New read-only `GET /diagnostics/extended-hours`, reporting this API process's loaded service state. It cannot enable, stop, collect, repair, or delete anything. |
| `tests/test_r7e46m_activation_contracts.py` | Isolated flag, diagnostic, failure, timestamp, journal, cancellation and actual launcher-branch contracts, with fake senders/providers and fake managers. |
| `tests/test_r7e46m_roadmap_readiness.py` | Runs the real checkpoint updater against temporary roadmaps: initial/replacement write, historical preservation, backup creation and invalid input rejection. |
| `.r7e41-audit/run_tests.py` | Temporary test harness only: main-entry guard prevents spawned Windows workers from recursively executing pytest. Prior harness and failed-run evidence preserved. |
| This document and `PROJECT_ATLAS_MASTER_ROADMAP.txt` | Operational procedure and managed checkpoint, updated through the mandatory updater with backup/read-back verification. |

`main.py` and both existing cash-session scanner/calendar files remain byte-identical
to their R7E46M baselines. `Atlas-Background-Controls.ps1` is unchanged: its normal
and Gaming starts do not supply the new switch and therefore disable this feature
in the child. No new GUI toggle or desktop shortcut modification was made.

### Environment inheritance and default behavior

The service reads `os.environ[ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED]`, not a Pydantic
setting. Writing this name into `.env` alone does **not** configure this service;
Pydantic reading a dotenv file does not export it into the process environment.
Previously a true flag inherited from a controller could also accompany a Gaming
launch. The supported manager now explicitly masks such an inherited flag unless
the operator supplies its Start-only research switch. Its worker inherits that
temporary controller value, and the venv launcher/API child inherit the worker's
environment. No source change mutates an already running API environment.

Accepted service flag strings remain `true`, `1`, `yes`, `on` (case/whitespace
normalized); missing, false and malformed values fail closed. Start eligibility and
latched activation are separate status fields. Editing `.env`, changing another
shell's environment, or closing the GUI is **not a hot enable/disable mechanism**.
Direct manual uvicorn launching is outside this supported activation procedure.

### Integration, data and failure contract

- Application lifespan invokes extended-hours Start after investment-scanner Start,
  and Stop after investment-scanner Stop. The feature independently checks its flag;
  disabled Start creates no task, file, provider request or lock. There is no change
  to cash-session scanner timing, rate limits, strategies or authority.
- Collector is research-only, using the existing active equity universe and shared
  read-only RH/Yahoo quote service. Default service interval is **180 seconds**;
  constructor minimum is 30 seconds. There is no new public cadence-setting API.
  It collects only calendar-permitted premarket/postmarket windows, not regular cash
  hours, weekends, holidays or dates outside the existing supported calendar.
- Durable output is
  `D:\Work\Project Atlas\backend\data\investment\extended_hours_observations.jsonl`.
  Its sibling `.jsonl.lock` is a persistent file containing a Windows byte-range lock;
  file existence alone does not mean the lock is currently held. Do not delete it
  to bypass a live writer. Non-Windows operation fails closed rather than silently
  dropping the cross-process lock.
- Valid records require positive finite non-boolean prices, aware nonfuture source
  timestamps, at most 900 seconds' age, matching extended session and LIVE/FRESH quote
  quality. This is research freshness, not a 120-second trading SLA. Previous-close,
  reference, missing, stale and future observations are rejected. No prices are invented.
- An earlier cycle-start clock could misclassify a newly fetched quote as future.
  Production now validates after retrieval. Explicit `now` remains a deterministic
  fixture/manual utility; it is not an HTTP production collection endpoint.
- Identity is canonical uppercase symbol plus normalized UTC effective timestamp.
  The committed journal is re-read under the exclusive Windows lock before appending;
  restart and independent-worker duplicate prevention rely on durable history, not
  the in-memory seen set. Writes are flushed and fsynced.
- Malformed/truncated JSON, invalid persisted research contracts or duplicate
  persisted identities block append and preserve the original journal. Disk/lock
  failures remain visible through cycle errors. No automatic repair, rewrite,
  historical backfill, journal reset, unsafe process termination or trade action exists.
- File locking/replay/fsync run in a worker thread. Graceful cancellation waits for
  an already-started commit to finish and release its lock; it may legitimately finish
  that commit before Stop returns. Cancellation before commit starts causes no append.
  A blocked disk/filesystem cannot be forcibly made safe; preserve evidence and report
  timeout rather than kill a process or delete a lock. A provider's blocking worker
  may finish its network work after cancellation, but cannot start a later collector
  commit through the canceled collection coroutine.
- `last_completed_at` means a cycle completed, including zero new records. It is
  **not proof of provider freshness**. `last_commit_at` and committed record content
  are needed for actual collection acceptance. Historical journals may exist while
  the service is disabled. Error text in the public status is reduced to exception
  class; no credentials/subscriber IDs or generic configuration dump is exposed.
- Both central automated Discord senders remain restricted and unchanged. Research
  observation collection provides no order authority, PAPER entry authority or
  automatic notification permission. Current policy remains PAPER_ONLY/MANUAL_ONLY.

## Validation and failure evidence

Final focused run: **99 passed, 0 failed in 80.38 seconds**, 15 selected files.
Includes prior R7E46F/G/H collector/persistence/concurrency/crash/Windows-lock/lifespan
tests, Gaming launcher/inheritance/GUI/passive-opening regressions, actual API
diagnostic contracts and new activation/roadmap tests. Providers, journals and
launches are isolated; launcher tests use fake managers or stub Start-Process and
never invoke a real Atlas Start/Stop. Windows child processes are temporary fixtures.

Initial run: **91 passed, 2 failed in 112.24 seconds**. The temporary test runner had
no main-entry guard, so Windows spawn re-entered pytest instead of only executing the
test worker. Failure output and old harness are retained. An Atlas-scoped read-only
process check found zero remaining test workers; no process was killed. After the
guard repair, the targeted process-lock rerun passed **3 tests in 5.96 seconds**,
then the complete final selection passed. No failed test was silently excluded.

Focused Ruff passed on collector, service and both new tests. Initial lint output is
preserved; compatibility-preserving style changes use Python 3.12 UTC/ISO support.
Diagnostics retains **20 existing Ruff findings**, with identical rule counts at
HEAD/current; no full-file lint-clean claim is made. Four PowerShell files parsed;
five isolated Python copies compiled; Git diff integrity passed. Full canonical
repository testing was not performed; existing unrelated working-tree/E136 work is
not certified by these 99 tests. No new seven-minute soak or gaming benchmark ran.

Evidence: `logs/diagnostics/r7e46m-20261016/`, including verified runtime identity,
API observations, source/protected baselines, source-before copies, initial/final
test logs, fixed-harness process tests, parser/Ruff comparisons, roadmap checkpoint
input/update output/backup verification and final result. Existing logs/backups and
all untracked work remain intact. Historical R7E46I's 420-second/105-observation/
36-symbol soak is roadmap evidence, not a new production result in R7E46M.

## Operator-approved activation — procedure only, NOT executed

1. **Release/go-no-go review first.** Review/freeze the entire pending working tree;
   a restart loads more than this feature. Resolve unrelated release blockers and
   run broader regressions as needed. Approve a named maintenance window that
   explicitly permits stopping the current verified session, one opt-in Gaming Mode
   startup, bounded feature observation and, if needed, rollback Stop/Start. Approve
   normal PAPER shutdown/reconciliation effects. No such authorization exists here.
2. Preserve the current roadmap, configuration hashes, owner/runtime identities,
   journal prefixes and diagnostic logs. Use supported Status and independently
   verify actual PID, creation time, executable, command, parent and run. An unknown
   session, mismatched owner, port conflict or ambiguous lock is an immediate abort.
   Do not stop or replace a different session. Never inspect or touch Genesis.
3. Under that separate approval, use the normal verified manager Stop; wait for owned
   processes to exit and lifecycle records to clear. Reconcile PAPER before proceeding.
   Do not force recovery or terminate processes on timeout. Do not change `.env`,
   machine/user environment variables, risk limits or the desktop shortcut.
4. Start the reviewed source once with the supported explicit opt-in:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background-Gaming.ps1" -Action Start -EnableExtendedHoursResearch
   ```

   A non-gaming approved start may use `Atlas-Background.ps1 -Action Start
   -EnableExtendedHoursResearch` instead. Selecting Gaming Mode alone never enables
   the feature. Do not issue a duplicate start or silently retry a failed start.
5. Verify manager `running`, normal startup/readiness, and actual API identity using
   `/diagnostics/gaming-runtime`. Read `/diagnostics/extended-hours`; require contract
   `R7E46M_V1`, same actual PID/run, environment_enabled=true,
   activation_enabled=true, running=true and task_active=true. Require research-only,
   no execution authority and no automatic Discord delivery. A missing endpoint,
   wrong contract, false field or different PID/run is **not activation acceptance**.
6. During an actual supported extended session, verify bounded provider activity,
   completed cycles and fresh journal commits: check canonical identities, symbol
   membership, source/effective/retrieval timestamps, price/quality/session/age,
   absence of duplicates, and unchanged pre-existing byte prefix. A zero-record cycle
   or outside-session idle task proves neither data freshness nor journal health.
   Record per-cycle errors/provider load and API responsiveness. Do not claim live
   collection GREEN without valid newly committed observations. No automatic alerts.
7. Independently confirm the cash scanner configuration/cadence and normal PAPER
   management/risk/reconciliation remain unchanged. Gaming still preserves the normal
   management cadence. Do not convert this functional check into an unapproved
   resource benchmark or longer unattended soak.

## Rollback and failure recovery — procedure only, NOT executed

- **Before activation:** leave the current backend alone. No rollback is required
  merely because source or documentation changed; no production flag was installed.
- **After a future approved activation:** capture diagnostics and preserve the
  journal/prefix/lock evidence. With explicit rollback-window approval, reverify that
  exact owned run, gracefully Stop through supported controls and reconcile PAPER.
  Then Start without the research switch (Gaming Mode may still be chosen). The
  manager explicitly passes false even if the operator's parent environment had true.
- Verify a new PID/run, normal readiness, the actual intended gaming setting,
  feature environment=false, activation=false and no active feature task. The retained
  historical journal must remain intact and receive no collector append after rollback.
  Do not delete/rename/reset it or the lock file, and do not restore unrelated source.
- A corruption/disk/permission/lock error must leave evidence intact. Capture the
  error class and file hashes without exposing credentials. Pause feature operation
  through the approved rollback lifecycle; do not repair a live journal. A persistent
  lock-file pathname alone is not a reason for recovery. Any eventual repair needs a
  separate plan, verified writer absence, immutable original backup and explicit scope.
- If graceful shutdown, ownership or rollback verification is ambiguous, **abort**
  further actions and report the evidence. Do not kill, force startup, bypass locks,
  operate Docker globally, or interfere with unrelated processes/projects.

## Remaining roadmap and single safest next execution

Completed in the managed history: R7E46F collector, G persistence/locking, H lifespan,
I isolated soak, K recovery contract and L checkpoint updater. R7E46M completes
isolated activation/rollback readiness; production enablement and rollback remain
untested and blocked. R7E46J's activation follow-up remains pending approval.

| Phase | Remaining work |
|---|---|
| 1 — Core reliability and operations | Whole-worktree release review; approved feature activation/rollback and sustained collection/recovery; gaming CPU/RAM/data-continuity benchmarks; safe Windows launcher modernization and operational diagnostics. |
| 2 — Research Evidence Engine | Immutable evidence and hypotheses/outcomes, historical replay, precision/recall/calibration, realistic PAPER costs, leakage controls, reproducible reports, Research Memory/analogues. |
| 3 — 15-minute crypto PAPER research | Eligible contracts/rules/jurisdiction/fees/settlement checks, timestamped depth, spot/perp/context joins, independent probabilities, executable pricing, cost/depth-aware PAPER fills and settlement, sustained out-of-sample regimes before any separately approved live proposal. |
| 4 — Cross-Market Intelligence | Unified evidence, liquidity/positioning, anomalies, explainable opportunity scores and cautious suspicious-activity hypotheses, confidence/uncertainty/invalidation validation. |
| 5 — Professional SaaS | Demand/pilots, tiers, authentication/tenant isolation, billing/entitlements, versioned research APIs, dashboards/exports/alerts, support/onboarding/analytics, data licensing and validated unit economics. |
| 6 — Institutional platform | Roles/audit logs, security/incident response, reproducible workspaces and governance, stable APIs/metrics, requirements/licensing/compliance review and enterprise pilots. No hosted/VPS implementation authorized here. |
| 7 — Commercial expansion | Product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led market expansion, revenue/margin/cost/churn measurement and reinvestment. Pricing remains unvalidated hypotheses. |

All legacy evidence/consent/Discord safety gates and incomplete working-tree work
remain open unless individually verified elsewhere. Preserve the permanent gaming
objective, Atlas/Genesis separation, PAPER_ONLY/MANUAL_ONLY and historical Prediction
Market Intelligence V2 phase; do not silently replace its historical gates with a
new execution permission. No subscription/activation watermark/real-capital authority
was created. No staging, commit or push occurred.

**Single safest next execution: R7E46N whole-working-tree release and activation
go/no-go review, without restart or activation.** Only after that review and separate
explicit operator approval should the maintenance-window procedure above be attempted.
