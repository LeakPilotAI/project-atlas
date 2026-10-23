# R7E44C — controlled Gaming Mode runtime acceptance

**BLOCKED: startup ownership defect. Graceful cleanup succeeded; final state STOPPED.**
One supported Gaming Mode start and one normal manager Stop were performed. No
startup retry, extended benchmark or optimization was attempted.

Branch `chatgpt/atlas-rebuild-v1`; HEAD unchanged:
`f9df47b4cd80dd647d85043aba617cf00c4e6dc0`. Test run:
`689b6423-8620-441b-bc6f-0b1e98527440`; API PID **15876**, launcher **27960**.
Dates below are 2026-10-16; CDT is UTC−05:00.

## Actual results

| Check | Observed result |
|---|---|
| Fresh preflight | STOPPED, no owner/manifest/locks or conflicting session; port 8000 unused |
| Gaming start requested | 08:28:26.7119577 UTC / 03:28:26.7119577 CDT |
| API startup complete | 08:28:53.978 UTC, **27.266 seconds** after request |
| Manager acceptance | **Failed** ownership check; retained `stop_timeout`, no signal sent |
| API health | HTTP 200, `status=ok`, expected scanner/PAPER services running |
| Perp dashboard | HTTP 200, 67,190 bytes |
| Actual API environment/settings | PID/run matched test; `ATLAS_GAMING_MODE="true"`, loaded gaming flag true |
| Discovery | Configured normal 60s, effective gaming **180s**, discovery task active |
| PAPER management | Enabled, task active, independently configured **8s** |
| Risk snapshot | Reliable, `PAPER_ONLY`, live execution/capital/automatic real-money execution false |
| Pre-stop reconciliation | One manual-auto PAPER open, zero duplicate fills, reconciliation true |
| Graceful stop request | 08:32:09.8653785 UTC / 03:32:09.8653785 CDT |
| API exit | Application shutdown complete and PID exit at 08:32:16.948 UTC; **7.083 seconds** after stop request |
| Final verification | STOPPED; both owned PIDs absent, port clear, no API/worker or lifecycle-record orphan |
| Post-stop manual-auto reconstruction | 351 opens / 351 closes; zero currently open, zero duplicate fills or malformed rows |

The API startup duration is not a successful manager-readiness duration. The worker
failed before its normal HTTP/readiness stabilization gates. No claim of complete
runtime acceptance or sustained feed freshness follows from a responsive API.
The live policy snapshot confirmed PAPER-only/live-capital restrictions; MANUAL_ONLY
policy source was unchanged. No real-money order, permission change or test DM was
requested. Normal PAPER activity and administrative shutdown appended journal rows;
the complete prior journal prefix, both environment files and frozen membership
were preserved. The latter three files remained byte-identical.

## Confirmed startup defect

`Invoke-BackgroundWorker` builds `$owner` as a hashtable. The existing
`Test-AtlasApiProcessOwnership` examines
`$Owner.PSObject.Properties["launcher_pid"]`. Dictionary entries do not appear there
as object properties. For the Windows base-Python child, that misses the verified
venv-launcher relationship and returns false. The worker's attempted startup-error
cleanup also refuses to signal because of this failed ownership result.

Once the exact same owner is persisted and read by Windows PowerShell 5.1, it is a
PSCustomObject: the real verifier returns **true**. Creation times, executables,
command lines, run IDs, API parent relationship, sole port listener and API-reported
PID/run all matched. This established conclusive ownership for the specifically
approved graceful cleanup. The existing manager Stop path then succeeded without
changing ownership code or weakening its checks.

A fixture-only reproducer using the recorded identities confirms:

| Valid owner representation | Verifier result | Desired |
|---|---|---|
| PSCustomObject | true | true |
| Hashtable used during startup | **false** | true |

Its desired-behavior assertion fails, exit 1, and is preserved as defect evidence.
No fix or second startup was attempted. An initial PowerShell 7 inspection also
normalized JSON timestamp strings and was not used to authorize cleanup; the
conclusive proof and reproducer use the manager's actual Windows PowerShell 5.1.

## Basic resource observation — no extended benchmark

Two passive samples, 08:32:00.3868772–08:32:02.4973021 UTC (2.110425 seconds):

- API working set: **666.17 MiB**; private bytes: **987.78 MiB**; 24 threads.
- Launcher working set: **4.07 MiB**; private bytes: **0.75 MiB**.
- API CPU counter: 65.734375 total seconds at both samples; no measurable increment
  in this short interval. Launcher CPU counter also unchanged.

Private bytes are a memory-allocation observation, not resident RAM. No normal-mode
comparison, sustained-load measurement or resource-saving conclusion is justified.
R7E45/R7E46 remain unapproved. Atlas Postgres/Redis started through the normal manager
dependency path and remain healthy/running under its normal retention policy; they
were not stopped as cleanup and are not orphan API processes.

## Diagnostic and validation changes

Added `GET /diagnostics/gaming-runtime` in `backend/app/api/diagnostics.py`, a bounded,
read-only allowlist of this API process's PID/run, gaming flag/environment, discovery
and management settings, and task state. It exposes no credentials, generic settings
dump or mutation/control action. Tests: `tests/test_r7e44c_gaming_runtime.py`.

- Pre-start diagnostic/launcher/ownership regressions: **52 passed**, 62.07 seconds.
- Final diagnostic tests after a nonbehavioral annotation correction: **4 passed**,
  0.81 seconds. Compilation passed; new test module Ruff passed.
- Diagnostic module has **20 pre-existing Ruff findings**, identical rule counts
  at HEAD and after the addition with Python 3.12 target; no finding added.
- Ownership reproducer: **one unresolved failing acceptance assertion**, intentionally
  preserved in diagnostic evidence rather than waived or called GREEN.
- Full suite not rerun for this operational acceptance. Its earlier 2,033 passed /
  3 expected E136 failures remain historical evidence only.

## Evidence, preservation and next execution

`logs/diagnostics/r7e44c-20261016/` retains preflight, prior lifecycle files/logs,
start/stop timestamps and responses, manager/API logs, actual API observations,
Windows identity proof, resource samples, shutdown/final-state proof, protected-file
hash checks, post-stop reconstruction, test output, reproducer and `result.json`.
Earlier R7E44A/B archives and source changes remain intact. No desktop shortcut,
trading authority, Genesis, unrelated process, staging, commit or push was changed.

Next: a separately scoped ownership fix must support dictionary and object owners
equally while preserving root/run/PID/executable/command/time/parent checks. Add
positive and negative tests of the actual startup path and startup-error cleanup.
Only after that source validation and separate approval should one new controlled
runtime acceptance run be attempted. Atlas remains STOPPED. Preserve the permanent
gaming objective and Prediction Market Intelligence V2 phase without implementing
further features, benchmarks or optimizations in this execution.
