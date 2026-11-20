# V6 concurrent worker-log access correction

**READY FOR V6 APPROVAL-PACKAGE PREPARATION. Source and disposable validation only.** Starting commit `e672bd52c53fce2e82da812936f2a384f16b1c01`, branch `chatgpt/atlas-rebuild-v1`. No installed Atlas launch, selection, grant retry or V6 approval package occurred.

## Proven V5 failure mechanism

V5 remains **FAIL**, its single-use grant **consumed**: supervisor `ReadAllText(worker-stdout.log)` failed at 2.997116 seconds while Python held the log open for writing. The original observer/worker were source Python, not the installed application. The retained verifier exited zero; the recorded parent/worker launch handles existed, but clock collection and complete worker ownership admission were not reached. Reviewed exact-owned Job containment was required; final Job zero, worker exit unrecorded. Nothing selected; no installed Open/browser/Stop measurement. All original raw files and 155 source pins are preserved unchanged.

The new genuine Windows fixture reproduces the **same live-writer/ReadAllText sharing exception** and then separately tests the corrected read-only/shared reader on that same writer. It passes without ACL repair, writer termination or filesystem fallback. This establishes the immediate V5 cause as incompatible concurrent file sharing. It is not evidence of a financial, clock, provider or installed-payload failure. Separate negative tests produce actual access denial and exclusive-sharing errors and keep them distinct from missing files, EOF and worker exit.

## Implementation and attribution

V5 source and consumed execution copies remain immutable. New source fork:

- `scripts/acceptance_harness_v6/WorkerLog.psm1`: explicit `FileAccess.Read` / `FileShare.ReadWrite`, without delete sharing. Native directory/ancestor leases and file IDs, single-link/no-reparse checks, strict receipt types and retained worker PID/native creation handle binding. Errors latch refusal; a later readable file cannot clear it.
- `scripts/acceptance_harness_v6/worker_log.py`: the actual Python stdout/stderr file descriptors publish a flushed, no-replace log declaration bound to the original launch nonce/PID/FILETIME, root native ID, file IDs and creation times. A producer-completion marker is created after declaration rename returns. The reader holds the declaration read-only, excluding later writes/deletes. A declaration is evidence, never an execution or ownership capability.
- `scripts/acceptance_harness_v6/supervise.ps1`: retains the V5 original suspended launch handles, parent handoff, sole Job ownership, native Job queries, source verification, watchdog and exact-owned cleanup. Only the log reader integration and V6 namespace change. It reads complete attributable records during the worker lifetime and drains bounded final records after exit. It records worker exit before final log checks. Handle-close errors cannot report success or skip owned cleanup.
- `scripts/acceptance_harness_v6/worker.py`: same acceptance lifecycle and V5 ownership implementation, with a V6 source bootstrap, explicit UTF-8 stdout/stderr and native log declaration. AST comparison confirms its entire existing acceptance/Stop/socket/browser/rollback body remains unchanged.
- New tests: `tests/test_worker_log_v6.py`, `tests/v6_log_writer_fixture.py`, `tests/run_v6_worker_log_native.ps1`, `tests/v6_regression_context.py`.

Attribution requires the original retained process handle, PID and native creation time; exact approved directory/native root; actual worker-published log file identities; native file identity/creation/link/reparse checks at open and every read; and immutable append-only prefix verification. Mere file presence or command resemblance does not qualify. These log checks supplement the complete V5 image/hash/command/ancestry/Job roster, which remains mandatory. Missing declarations while a live worker starts are an explicit WAITING state, never accepted evidence. Missing declarations/files at exit refuse.

Reads are bounded at **1 MiB per log, 64 KiB per line, 4,096 total records, 128 records per polling cut and 32 final-drain cuts**. UTF-8 is strict. Complete lines alone are forwarded; partial UTF-8/lines stay in the bounded raw snapshot until complete. Length decrease, any previous-prefix rewrite, wrong native identity, aliases, unexpected short read, unreadable file, invalid declaration, nonzero writer exit, empty exit log or incomplete final line refuses. A live file's current end is not a completed writer. Final well-formed backlog drains without loss/duplication, under the same outer time/resource limits.

All file/declaration/directory leases receive deterministic close attempts, including when another close fails. Incomplete closure remains a refusal. No blanket I/O suppression, automatic retry into acceptance, unbounded tailing or financial-engine change was introduced.

## Genuine native evidence

Both final runs use the exact current source hashes and existing source Python only:

| Evidence root under `logs/diagnostics` | Cases | Seconds | Final entries | Accounted bytes, including result |
| --- | ---: | ---: | ---: | ---: |
| `qd-v6-worker-log-native-verified-a-20261103` | 33/33 | 8.3738940 | 457 | 4,167,819 |
| `qd-v6-worker-log-native-verified-b-20261103` | 33/33 | 8.3418669 | 457 | 4,167,827 |

**66/66 final native case executions passed**, with 33 distinct scenarios and five additional normal timing repetitions in each run. Every case ended with an empty owned Job and closed reader/declaration/directory/owner/thread/Job handles; rename round-trips confirmed file-handle release. No emergency cleanup occurred in either final run. Each run deliberately terminates **one exact owned synthetic worker** for the required negative test; that termination is recorded separately and never called a graceful exit or installed Stop.

Coverage includes original failure reproduction, reader before first entry, writer before reader, partial lines/CRLF, delayed flush, 200 concurrent lines without loss/duplicates, 300-line final backlog, real access-denied/exclusive-sharing failures, missing declaration/file, unexpected exit, incomplete/empty EOF, truncation, same-length overwrite, replacement, wrong file/process/root/nonce, malformed declaration, log/line/record caps, invalid UTF-8, stale retained creation identity and worker termination. Each failure remains latched; repaired access or later content never retroactively passes it.

Each final native fixture enforces **180 seconds including cleanup, 2,048 entries and 32 MiB accounted storage**, with 150-second/2,000-entry/30-MiB reserves, bounded commands and child lifetime. Only fresh confined diagnostic roots and their synthetic children are used. One access-denial test changes and restores the DACL of its newly created synthetic log only; no installed ACL, global permission, service or system setting changes.

These are log-mechanism/process fixtures, **not full installed V6 Control Center acceptance**. They invoke actual source launch primitives, publisher and reader, while the operational supervisor entry is never authorized or launched.

## Regressions and preserved preliminary failures

Final relevant suite: **520 passed, 0 failed, 0 skipped, 32.49 seconds**. It includes **22 new offline cases**, all prior 353 ownership/package/ACK/EOF/cleanup/sequence protections, and relevant clock/IEX admission, socket/capture cases. No-cache lint, formatting and PowerShell parsing passed. Full source hashes, exact commands/XML/logs and final native result hashes are retained in `logs/diagnostics/qd-v6-log-correction-20261103` and the named test roots.

One historical preparation-only test asserted that V5's real root was unused. The first broad run recorded **519 passed / 1 failed** because the approved V5 run had consumed it. Deleting its claim or modifying that pinned test would be wrong. `tests/v6_regression_context.py` now applies **only to that one case**: it creates a labeled disposable pre-execution copy, verifies the operational validator refuses its synthetic root, executes the original copy/hash/unclaimed invariants unchanged, then checks the real consumed V5 directory and every original file hash are unchanged. All other tests run normally; no test is skipped or deselected. The first fixture adapter itself omitted a yield on unrelated tests and recorded **1 passed / 519 setup errors**; that test-adapter defect was fixed and its log is retained. It did not modify an acceptance gate.

Earlier native failures remain in their separate roots: raw `DirectoryInfo` lacked `PSIsContainer` under strict mode (corrected to the actual directory type); the test initially expected LF instead of genuine Windows CRLF (reader bytes unchanged); the exclusive-handle fixture exposed an integer stream name (fixture now gives the same real native FD its explicit pathname); and a synthetic command transiently refused open. The latter's exact Win32 subcause was not captured. Explicit producer-completion markers now order command/declaration reads after publication returns; **failed reads are never retried into success**. Final repeated tests pass. All preliminary result files remain failed, including their recorded exact-owned emergency containment where applicable.

## Preservation and current baseline

A fresh standard-token native read-only metadata check verified **UNSELECTED revision 6**, head `c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc`, six record pairs / 12 names, native root `[4004218753, 65536, 1532785]`. Existing support receipt/ACK/native identity/ACL binding and **17 original metadata names/hashes** passed. All read handles/mutexes closed. No selector publication or rollback was performed.

V5 FAIL/consumed evidence and all 155 source pins, V4 historical findings, unrelated research-test modification and private files are unchanged. No clock sample/capability was issued and historical accepted clock readings remain historical. B1/C1/D1/E1, all 21 decisions, seven phases, financial isolation and original UI remain intact.

## Next prerequisite and remaining uncertainty

The correction is ready for **V6 approval-package preparation**. That separate milestone must build exact V6 gate/module/publisher/source pins, copy into a fresh unused evidence root, review the additional owned log declaration/marker files and confirm full current baseline/dependencies/limits. **No such proposal, grant or execution root was created here.** A later installed run still needs fresh explicit single-use operator authorization and full fresh native/ACL/receipt/selector/rollback/clock/socket/process preflight.

The unchanged requirements remain browser acknowledgement <=45 seconds, complete Stop <=8 seconds, peer EOF/client closure, unanimous three-reader evidence, pre-selection evidence, strict CIM last, exact process/image/parent/original handle/Job membership, clock uncertainty <=1,000 ms / age <=120 seconds and all financial restrictions. PID-0 LISTENING, State 0, unexpected processes and missing evidence still refuse. No actual installed V6 browser/Stop/restart/module-origin/current-clock acceptance is claimed. The historical transient synthetic command-open subcause remains unproven; final producer ordering addresses the observed publication boundary conservatively without suppressing access errors.

No installed Atlas launch or selection, reused V5 grant, support reinstall, journal reset, Windows Time/network change/resync, shortcut/autostart change, provider connection, account/writer activation, PAPER/live trading, real order, Genesis access or destructive Git. The sole personal operator remains release authority. **PAPER: NO. Production: NO-GO. STOP after reporting, archival checkpoint, commit/push and remote verification.**
