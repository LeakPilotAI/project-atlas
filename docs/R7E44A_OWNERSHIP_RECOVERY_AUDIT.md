# R7E44A — ownership recovery audit, 2026-10-16

**Audit complete. Retained ownership is stale; recovery and startup were not performed.**
R7E44 remains blocked until a separately approved recovery establishes a clean
stopped state. No production Status, Start, Stop, recovery, process signal, Docker
operation, Genesis inspection, staging, commit or push was invoked.

Branch: `chatgpt/atlas-rebuild-v1`; unchanged HEAD:
`f9df47b4cd80dd647d85043aba617cf00c4e6dc0`.
Observation: 2026-10-16 08:00:36–08:04:56 UTC / 03:00:36–03:04:56 CDT (UTC−05:00).

## Records and identity reconciliation

All paths below are relative to `D:\Work\Project Atlas`.

| Evidence | Finding |
|---|---|
| `logs/runtime/atlas-background-owner.json` | Schema 1, root matches Atlas, `stop_timeout`, run `867a9b46-e377-4018-b42f-010a71332caa` |
| Recorded API | PID 31552; created `2026-10-14T07:41:51.2012980Z`; base Python 3.12 executable; Uvicorn `app.main:app`, port 8000, Atlas logging config |
| Recorded launcher | PID 24880; created `2026-10-14T07:41:51.1660240Z`; Atlas venv Python; same Uvicorn arguments |
| Actual Windows identity | Both PIDs absent. There is no current creation time, executable or command line to compare; neither identity survives |
| Windows boot | `2026-10-16T03:10:08.5000000Z` / Oct 15 22:10:08.5 CDT, later than both recorded process creations |
| `logs/runtime/runtime.json` | Absent |
| `logs/runtime/stop.json` | Valid GUID `9a2b6955-04ca-4dbe-a48a-d045ed11417e`, different from owner; last written `2026-10-16T02:51:01.2985291Z` |
| Start / stop / recovery locks | All absent |
| Atlas-root process inspection | PID 10304 is VS Code mypy `lsp_server.py`, not Uvicorn; left untouched. No Atlas API/lifecycle worker found by the scoped query |
| API port | Independent Windows TCP listener enumeration found zero listeners on 8000 |

The owner file's error says the earlier identity check failed and **no process was
signalled**. Its last write was Oct 14 07:41:55.9881849 UTC. Historical roadmap
observations later verified this same API/launcher run active; consequently this
retained error was never reliable proof of a completed shutdown or a true graceful
timeout. Current PID absence and the subsequent Windows boot establish that these
recorded identities are now stale. Port absence is corroboration, not the proof.

Protected SHA-256 values match the R7E44 baseline:

- Owner: `c5a5fd075de43bbdfecb16e9116b45c39ee586d51ccffd77e8b63fe604c0967d`
- Stop request: `0927329d7b309367e554fece68cc39fb768c1ca7bc77cd227d232aae6bb19ad7`

## Exact blocker and provenance limits

`Get-VerifiedState` in `scripts/windows/Atlas-Background.ps1` validates the owner,
then requires a runtime manifest with matching run ID and a valid PID. With this
manifest absent, it returns `AMBIGUOUS` before querying API/listener state or
entering its confirmed-dead-session recovery branch. `Assert-CleanStart` therefore
refuses startup. The mismatched stop request is additional historical evidence;
it is **not** the immediate branch that blocks Start.

`Test-AtlasDeadSession` requires both owner and runtime records with matching run
IDs. `Move-AtlasDeadSessionMetadata` uses that predicate and archives both files,
with rollback protections. Neither supports an owner-only/missing-runtime case.
Do not manufacture a runtime record or substitute the unrelated stop GUID to pass
those checks. The refusal is deliberate fail-closed behavior.

`DesktopControl.start()` writes `runtime.json`; its `stop()` removes only a manifest
whose run ID matches that control instance, but does not remove the background
owner or stop request. The older interactive launcher body generates independent
run IDs in the same control directory without maintaining the background owner;
its legacy path is now explicitly blocked and must remain unused.

Server logs record PID 31552 exiting after application shutdown on Oct 14. Later
server processes appear in the shared log; the last is PID 28968, with application
shutdown complete and process exit logged at Oct 15 21:51:01.890 local time
(Oct 16 02:51:01.890 UTC). That aligns with the stop-file modification time and
precedes the reboot. This is consistent with a later desktop run cleaning up its
manifest while the older background owner remained.

**Not established:** the exact writer of the `9a2b...` request, that GUID's binding
to PID 28968, or the exact deletion time/actor for `runtime.json`. The available
logs do not record that correlation. `stop-latest.json` reports
`requested_graceful=false`, `forced_process_trees=0`, finished
`2026-10-16T02:51:03.6380162Z`; it does not prove the stop request caused the preceding
shutdown. Windows reboot alone does not explain deletion of a persistent file.
Normal `DesktopControl.stop()` cleanup is a supported explanation, not a proven
file-deletion audit trail. No PAPER reconciliation claim follows from these logs.

## Proposed recovery — NOT EXECUTED

Safe recovery is possible in principle because the retained process identities
are stale. The existing automatic two-record procedure cannot execute it as-is.
A narrow owner-only archival action must first be separately approved and reviewed.
It must retain the existing fail-closed identity, locking and preservation rules:

1. Recheck branch/root and exact owner/stop bytes, absent runtime and lifecycle
   locks. Recheck recorded API/launcher PID absence, boot chronology, no Atlas
   API/start/stop worker and no listener. Abort on any change, query failure,
   concurrent worker, reused recorded PID or ambiguity; never signal anything.
2. Acquire the existing exclusive Atlas recovery lock using its current-process
   identity and run-scoped evidence. Recheck everything after acquiring it, as the
   manager does. Do not dot-source the whole manager: its default action is Status.
3. Preserve original owner bytes, hash, timestamps and a recovery receipt in a new,
   unique Atlas-local archive. Explicitly record that the manifest was absent.
   Archive **only** the stale owner with an exact-path, no-overwrite operation.
   Do not recreate a manifest or call the two-file archive helper with fabricated
   evidence. Leave `stop.json` byte-for-byte in place: its well-formed unrelated
   GUID cannot stop a newly generated run under `DesktopControl.requested()`.
4. Verify archival bytes and absence of the original owner/runtime, no new worker,
   no listener, unchanged stop request, and the same lock identity. On failure,
   preserve the lock and artifacts for manual review; do not erase evidence or
   declare STOPPED. The filesystem operation is not a distributed transaction;
   a hard interruption must remain fail closed behind the recovery lock.
5. Release only the recovery lock owned by this exact recovery process after
   successful verification. Then a separately invoked manager Status can establish
   STOPPED. Any unexpected state ends the procedure. No implicit startup follows.
6. Only after that gate may the approved R7E44 gaming lifecycle acceptance be
   rescheduled. Its fresh Start/Stop operations must use the verified new run ID;
   they must not reuse either historical GUID. R7E45/R7E46 remain unapproved.

This is a plan, not an executable recovery script. No lock, owner, stop request,
manifest or archive under `logs/runtime` was created, changed, moved or removed.

## Validation and evidence

- **52 passed, 0 failed**, 47.94 seconds: two new R7E44A forensic tests plus E128,
  A23 recovery-hardening and desktop-operator regressions.
- New tests execute the actual manager functions only against temporary records.
  They prove missing-manifest refusal occurs before recovery/process queries,
  startup remains blocked, record contents stay unchanged, and the archive helper
  rejects missing/conflicting runtime, live PID/API/listener and lifecycle locks.
- Ruff, isolated compilation and diff whitespace checks passed. Application
  ownership/recovery implementation was not changed. The prior full-suite result
  remains 2,033 passed / 3 expected E136 failures; no full-suite rerun was needed
  for this audit-only change, and the new two cases are reported separately.
- Evidence: `logs/diagnostics/r7e44a-20261016/` contains `pid-presence.json`,
  `current-forensics.json`, `lifecycle-log-events.json`, isolated `tests.log`, and
  final integrity/checkpoint records. No secrets or raw environment exported.

**R7E44 cannot resume yet.** A safe recovery procedure is now specified; recovery
execution remains pending separate approval and fresh verification. All previous
source changes, untracked E136 work and live-data boundaries remain preserved.
