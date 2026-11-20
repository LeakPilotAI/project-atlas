# Atlas manually controlled gaming workflow

Gaming mode is opt-in. It raises Perp micro discovery's interval to at least
180 seconds; a configured slower interval stays slower. PAPER position management
keeps its independently configured interval (8 seconds by default). Other collectors
and services are not throttled by this setting. CPU and RAM savings have not been
measured, and lower discovery frequency can delay discovery of new opportunities.
PAPER_ONLY / MANUAL_ONLY and existing trading-authority restrictions still apply.

## Normal operator workflow

1. Open **Atlas Background Controls**. Opening the window makes no manager request.
   Both Start buttons and Stop are disabled until an explicit status check.
2. Click **Atlas Status**. Only a valid `STOPPED` response enables **Start Atlas
   Background** and **Start Atlas Gaming Mode**. Ambiguous ownership, starting,
   stopping, and timeout states do not permit another start. Do not delete locks or
   ownership records to make the buttons available.
3. Click **Start Atlas Gaming Mode** once. The hidden child sets
   `ATLAS_GAMING_MODE=true` and invokes the existing manager's `Start` action.
   The GUI's internal `GamingStart` label is translated before invocation and
   completion handling. Normal Start, Status, and Stop inherit the existing
   environment without the GUI setting this flag.
4. After the request completes, click **Atlas Status** again. A Start acknowledgement
   is only a request acknowledgement. Wait for verified `running` ownership and
   successful API/readiness checks before treating Atlas as ready. A later click
   of Status is required; the GUI does not automatically poll status or start Atlas.
5. Play games while Atlas runs. Closing the controls does not stop Atlas. The UI's
   lightweight timer checks only an explicitly requested active child; it launches
   no manager process while idle.
6. When finished, check **Atlas Status**, then click **Stop Atlas Background** only
   when it reports a verified running owner. This uses the existing graceful manager
   path. Do not use the blocked legacy launcher/stopper or terminate Python manually.
7. After completion, click **Atlas Status** again and require `STOPPED`. Confirm the
   graceful-shutdown log and PAPER reconciliation before starting another run.
   `stop_timeout`, unconfirmed worker creation, missing evidence, or ambiguous
   ownership requires review; it is never proof of a successful stop.

The GUI disables lifecycle controls during a request and after lifecycle completion
or failure. Only an explicit subsequent valid status response can re-enable them.
Errors do not trigger automatic retry, startup, recovery, or shutdown.

## Controlled acceptance plan — explicit permission required

No real Start/Stop is authorized by isolated tests. Before acceptance, agree on a
maintenance window, review current Atlas ownership and PAPER state without altering
them, and preserve protected environment, journal, and runtime evidence. Status can
perform existing stale-session metadata recovery; do not invoke it casually to
resolve unverified stale ownership. Genesis must not be inspected or operated.

During an approved run:

1. Establish an unambiguous stopped state with no conflicting Atlas owner/lock or
   port ownership. Do not force recovery, delete evidence, or operate shared services.
2. Explicitly start through the gaming GUI. Verify the unique run ID, launcher,
   worker, owned API relationship, and readiness. Confirm the **actual API settings**
   have gaming enabled, discovery >=180 seconds, and unchanged management cadence.
   An isolated settings probe is not live API certification. If no approved runtime
   settings observation is available, leave that acceptance item open.
3. Check API health, market timestamps, PAPER reconciliation/duplicate fills, and
   risk restrictions read-only. No production test orders or Discord messages.
4. Sample only the verified Atlas process family at a modest interval over a
   representative period. Record timestamp, CPU-time deltas, working/private memory,
   thread counts, and scan/manage activity. Compare normal and gaming runs only
   with separate lifecycle permission and comparable market/load windows. Never
   inspect unrelated processes. A discovery interval change alone proves no savings.
5. Request graceful stop through the background GUI, verify process exit under the
   same run identity, retained journal integrity and reconciliation. Do not force a
   timeout or fall back to a legacy stopper. A failure ends acceptance for review.

Resource optimizations beyond discovery cadence are deferred until measurements
identify a safe target. PAPER management, alert correctness, evidence integrity,
and graceful shutdown must retain their existing contracts.

## Validation scope

R7E41 repairs button initialization/state adjacency and manager action translation.
R7E42 executes the real GUI functions and encoded child against inert temporary
managers, including success, errors, environment inheritance, status gating, idle
behavior and duplicate-request exclusion. The actual initialization creates and
disposes controls without showing a window or starting its timer.

R7E43 executes the manager's real Start branch and API launch statement with isolated
ownership/dependency fixtures. The hidden worker substitutes a Python settings probe
for Uvicorn; it never imports `app.main`, starts collectors, accesses production
credentials/data, or starts Docker. This proves process inheritance and configuration
behavior. Production worker ownership, live startup/shutdown, and sustained readiness
remain controlled acceptance items.

The standalone gaming launcher now uses a hidden encoded manager child for Start,
so its start-lock command line can satisfy the unchanged `Test-StartCommandLine`
verifier. Isolated tests inspect only that mock child PID and execute the real
verifier against its actual command line. They verify opt-in inheritance and parent
environment restoration after success and failure. Status and Stop retain their
existing delegation. Production CLI lifecycle acceptance remains gated alongside GUI
acceptance; these tests do not authorize it or relax ownership verification.

No staging, commit, push, production lifecycle action, Genesis operation, or Discord
activation is part of this execution. Protected untracked E136 work remains separate.

## Checkpoint results — 2026-10-16

| Milestone | Result | Evidence / remaining gate |
|---|---|---|
| R7E41 | PASS | Original 20 focused regressions; button and action fixes |
| R7E42 | PASS | 18 behavioral GUI cases |
| R7E43 | PASS, isolated contracts | 6 inheritance/ownership cases; actual runtime settings require R7E44 |
| R7E44 | GATED | Explicit permission and controlled lifecycle acceptance required |
| R7E45 | GATED | No verified running session benchmarked; resource benefit unknown |
| R7E46 | DEFERRED | No measured basis for additional optimization |
| R7E47 | PASS | Final 44 focused passed; full suite 2,033 passed, 3 existing xfailed, 0 unexpected failures |
| R7E48 | Documentation complete | Actual operator workflow acceptance follows R7E44 |

Final canonical test time: 159.27 seconds; focused: 55.11 seconds. Two existing
dependency warnings remain. PowerShell parsing, Ruff, compilation and diff checks
pass. The three E136 expected failures remain production consent/recovery gates.
No staging, commit or push occurred. The full canonical roadmap retains its prior
history and records the complete remaining inventory and exact next execution.
