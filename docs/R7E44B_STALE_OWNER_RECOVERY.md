# R7E44B — controlled stale-owner recovery

**PASS: verified STOPPED. Atlas was not started.**

Executed 2026-10-16 at **08:19:51 UTC / 03:19:51 CDT (UTC−05:00)**,
on `chatgpt/atlas-rebuild-v1`, unchanged HEAD
`f9df47b4cd80dd647d85043aba617cf00c4e6dc0`.

## Recovery performed

1. Rechecked the exact approved owner/stop hashes, owner schema/root/run/PIDs,
   missing manifest, absent lifecycle locks and repository checkpoint.
2. Verified API PID **31552** and launcher PID **24880** were both absent. Windows
   boot at `2026-10-16T03:10:08.5000000Z` followed their Oct 14 creation times.
   Scoped Atlas-root queries found only known VS Code mypy tooling PID **10304**;
   no API, conflicting session or lifecycle worker. Port 8000 had no listener.
3. Acquired the existing exclusive `atlas-background-recovery.lock` with the
   manager's `New-ExclusiveJsonFile` helper, exact recovery-process identity and
   unique recovery ID `49f6d05d-bc9f-4153-8999-df3557435ba8`.
4. Repeated record, process, boot and listener checks under that lock. Preserved a
   prepared receipt containing identity proofs, hashes, timestamps and explicit
   evidence that the runtime manifest was absent.
5. Moved **only** the approved stale owner to a unique Atlas archive using a
   no-overwrite file operation. Verified its hash, stop-file preservation, absent
   original owner/manifest, process absence and exact lock identity again.
6. Released only this recovery process's lock through the manager's normal
   `Remove-OwnedFile` cleanup helper after successful verification.
7. Repeated the no-session proof and evaluated the existing manager
   `Get-VerifiedState` function with Atlas-scoped read-only process/listener
   providers. It returned `STOPPED: No Atlas background run is recorded.` The
   whole manager entrypoint/default Status action was not invoked.

No ownership check was relaxed, and the two-record archive helper was not supplied
with fabricated runtime evidence. On any failed locked check, the script would
retain the lock and evidence; that failure path was not needed in this execution.

## Original and final state

| Record | Before | After |
|---|---|---|
| Owner run `867a9b46-e377-4018-b42f-010a71332caa` | Retained `stop_timeout` | Archived; original runtime path absent |
| API / launcher PIDs | Both absent | Both absent |
| `runtime.json` | Absent | Absent; never reconstructed |
| Stop run `9a2b6955-04ca-4dbe-a48a-d045ed11417e` | Present | Same bytes and last-write timestamp |
| Start / stop locks | Absent | Absent |
| Recovery lock | Absent | Acquired exclusively, verified, then released |
| Lifecycle projection | `AMBIGUOUS` | `STOPPED` |
| Atlas startup / shutdown | Not performed | Not performed |

Owner SHA-256 remains
`c5a5fd075de43bbdfecb16e9116b45c39ee586d51ccffd77e8b63fe604c0967d`.
Its original last-write timestamp remains `2026-10-14T07:41:55.9881849Z`.
Stop SHA-256 remains
`0927329d7b309367e554fece68cc39fb768c1ca7bc77cd227d232aae6bb19ad7`;
its last-write time remains `2026-10-16T02:51:01.2985291Z`.

## Preserved evidence

Archive directory, relative to `D:\Work\Project Atlas`:

`logs/runtime/stale-sessions/867a9b46-e377-4018-b42f-010a71332caa-owner-only-r7e44b-20261016T081951026Z-49f6d05d-bc9f-4153-8999-df3557435ba8/`

It contains the original `atlas-background-owner.json`, immutable
`prepared-receipt.json`, and verified `recovery-receipt.json`.
Execution evidence is in `logs/diagnostics/r7e44b-20261016/`: the exact recovery
script, preflight, result, independent integrity checks and test log. Existing
archives and R7E44/R7E44A evidence were preserved.

## Validation

**60 passed, 0 failed, 64.51 seconds** before live execution: eight new temporary
owner-only recovery cases plus the R7E44A, E128, A23 recovery and desktop-operator
regressions. Coverage includes changed owner/stop, unexpected manifest/start lock,
out-of-scope destination, existing destination, changed lock, and successful
owner-only preservation. Fixtures never invoke real lifecycle actions.

PowerShell parsing, Ruff, isolated compilation, tested-script byte comparison,
independent archival/stop integrity checks and diff whitespace checks passed.
Application ownership code was unchanged; the full suite was not rerun for this
controlled operational recovery. Prior full-suite evidence remains 2,033 passed /
3 expected E136 failures, separately from these 60 focused tests.

## Remaining acceptance gates

The ownership blocker is cleared. **R7E44 can be scheduled after separate startup
approval and a fresh preflight; it has not been executed or certified.** Actual
Gaming Mode settings inside the API, normal PAPER management cadence, readiness,
basic CPU/RAM observations, graceful shutdown and orphan/reconciliation checks
remain outstanding. No performance benefit is claimed.

R7E45 benchmarking and R7E46 optimization remain unapproved. The permanent gaming
objective, Atlas/Genesis separation and Prediction Market Intelligence V2 phase
remain intact. No other project was inspected, no process was signalled, and no
Docker, PAPER, trading-authority, live-trading or Discord activation action occurred.
Nothing was staged, committed or pushed; existing repository work was preserved.
