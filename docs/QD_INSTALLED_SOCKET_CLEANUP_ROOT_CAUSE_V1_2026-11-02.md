# Installed socket cleanup investigation — offline correction complete, native cause BLOCKED

Starting commit **b3602eeae17f3b56809cec560a4f4faefec8f0c4**, branch `chatgpt/atlas-rebuild-v1`. Scope: source correction, retained evidence inspection, mocked regressions and one disposable ephemeral socket diagnostic. **No installed Atlas application launch or operational selection/mutation occurred.**

**Confirmed and corrected:** the orchestration retained READY after an acknowledged Stop, causing duplicate Stop dispatch and skipped process reaping before handle disposal. **Unresolved:** why Windows reported the historical listener with owner PID 0. A disposable native diagnostic also exposed an unsupported CIM state value. Full native cleanup qualification and another installed acceptance attempt remain **BLOCKED**; no historical failure is relabelled passed.

## Recovered evidence and exact findings

The preceding installed session stopped successfully in **0.591364 seconds** (outer observer **0.6167427 seconds**) after the timely **27.3332249-second** browser acknowledgement under the unchanged 45-second deadline. Its immediate socket audit queried `MSFT_NetTCPConnection` by local port, then counted State=2 rows; it retained states/counts but omitted full endpoints and owners for that first snapshot.

The exact retained endpoint was **TCP / IPv4 / 127.0.0.1:60840**. The later read-only diagnostic at **2026-11-02T12:56:25.3875228Z** retained 33 raw CIM rows and 33 named-wrapper rows, all at that exact local address/port and all with `OwningProcess: 0`. Each array contained one State=2 row. The independent retained native `netstat` output included an exact local endpoint `LISTENING` row ending in PID **0**, alongside TIME_WAIT/CLOSED rows. The immediate audit had counted two State=2 rows; these different observations are not assumed simultaneous.

| Possible explanation | Evidence-supported classification |
|---|---|
| Atlas replaced missing ownership with zero | **Not supported.** The original audit did not parse owners; the later CIM property and raw netstat text explicitly contained zero. No Atlas fallback or conversion manufactured it. |
| Windows reported zero in the owner field | **Established.** This does not identify a safe-to-terminate process or prove the listener harmless. |
| Zero means unavailable attribution rather than an actual owner | **Unresolved.** The retained outputs cannot establish that provider/kernel meaning. |
| Different endpoint counted by the original audit | Initial audit was under-instrumented and matched port only. However, the later full CIM/netstat evidence includes the exact IPv4 loopback endpoint, so a wrong-address match does not explain away the entire finding. |
| Stale enumeration or normal transition | Possible, **not proven**. The original audit lacked collection start/end timestamps; later rows changed states between observations. |
| A leaked Atlas process is proved | **No.** The retained owned Job was empty and the closing Atlas process roster was zero. That does not establish port release. |
| Kernel/provider state-reporting defect | **Not established as the historical root cause.** The new disposable observation adds a discrepancy, described below. |

Microsoft documents CIM TCP State **2 as Listen**, **1 as Closed** and **11 as TimeWait**. The native IPv4 TCP-row contract also states that remote endpoint fields have no meaning for LISTEN rows; a nonzero remote port therefore does not justify discarding a listener. See [MSFT_NetTCPConnection](https://learn.microsoft.com/en-us/windows/win32/fwp/wmi/nettcpipprov/msft-nettcpconnection) and [MIB_TCPROW_OWNER_PID](https://learn.microsoft.com/en-us/windows/win32/api/tcpmib/ns-tcpmib-mib_tcprow_owner_pid). PID 0 is never treated as automatic clearance.

## Exact cleanup-harness defect

The executed private worker did the following:

1. Sent Stop and verified its successful acknowledgement.
2. Ran the independent socket audit **before** clearing `ready` and recording the completed cycle.
3. The audit raised. The `finally` branch still saw `ready`, sent another Stop, and tried to read a second acknowledgement.
4. The PowerShell orchestration was already waiting for `NEXT`; the second Stop was not `NEXT`, so it exited. The extra read failed with `INSTALLED_READINESS_PIPE_REFUSED`.
5. The same exception skipped `communicate()`. The unconditional `_handle.Close()` then disposed the outer process handle while `Popen.returncode` was still unknown. Its destructor later polled that closed handle and reported WinError 6.

This is an orchestration state/ordering defect, not evidence that the previously acknowledged application Stop failed. The original outer controller exit code remains unavailable. The reviewed installed PowerShell adapter already reaps its actual application controller, validates the exit/Stop result and disposes it; that frozen installed code was not changed. The historical supervisor's zero-process Job observation and no-forced-termination result remain preserved, not substituted for socket proof.

## Source corrections

`scripts/observation_runtime/installed_acceptance_cleanup.py` provides a narrowly scoped observer for the existing test harness. It starts no process, selects no release and supplies no financial authority.

- Retains the exact native PID, creation FILETIME and image checks through the existing `observe_pid` / `observe_handle` primitives.
- Marks Stop attempted **before** pipe effects and caches an accepted Stop **before** independent auditing. Later cleanup cannot resend an accepted or ambiguous Stop. The eight-second adapter and outer Stop limits remain enforced.
- Allows a second cycle only after fresh, complete socket evidence and the original strict process roster pass. Any unresolved cleanup latches refusal; a later empty observation cannot silently reset that refusal.
- EOF/drain runs separately from the Stop/audit error path. It collects the process exit code while the retained handle is valid, closes streams, then disposes the handle. A timeout retains ownership; it never kills or terminates a process. Repeated finalization does not poll or close an already disposed handle.
- Distinguishes a confirmed remaining listener from incomplete/failed enumeration. Complete rows retain protocol, family, local/remote addresses and ports, state, owner-field presence and owner value. Missing ownership stays null rather than becoming zero.
- Requires the exact loopback endpoint/query binding and post-Stop monotonic collection timestamps. Concrete IPv4/IPv6 endpoints remain distinct; wildcard or mapped listeners that could overlap refuse. LISTEN always refuses regardless of owner. Unsupported states, active connections, stale/pre-Stop/slow snapshots, missing fields and nonzero/unknown process counts also refuse. CLOSED/TIME_WAIT are retained as terminal socket evidence, not called listeners or used to erase trades.

The observer's additional collection bounds are conservative test-harness checks: at most five seconds to collect, at most two seconds since collection, at most 1,024 rows. They are not changes to the clock validator, eight-second Stop, 45-second browser deadline, host/request limits or financial policy.

`scripts/windows/Atlas-Acceptance-Resource-Audit.ps1` retains the original strict scalar helper PID/creation/image comparison block, with complete socket capture and explicit error/timing information. It performs read-only queries and emits private JSON; it contains no application launch, Stop, selection, service or networking mutation. All query failures remain failures, never empty successful tables.

`docs/QD_INSTALLED_ACCEPTANCE_CLEANUP_CORRECTION_V1_2026-11-02.patch` records the exact focused integration into a **future copy** of the retained worker: instantiate the observer, store Stop before audit, gate NEXT on the complete assessment, and always reap before handle disposal. The corrected private copy parses. The executed worker/auditor/controller/supervisor and raw results were not edited. **The patch is not an executable authorization or a new deployment handoff**: its retained checkpoint/baseline pins are consumed historical pins. A future separately approved worker must be reviewed against the actual revision-4 baseline and current exact source identities.

No frozen application, installed support, its nine pinned sources, installation receipt, selector implementation or operational journal was modified.

## Validation — exact counts and limits of proof

- Final focused and relevant fixture regressions: **248 passed / 0 failed / 0 skipped, 13.88 seconds**. This is 86 new observer/PowerShell-mock cases plus 162 existing support/selector/launcher cases.
- The new cases cover remaining listeners after process exit, PID 0, null/missing owners, both address families, concrete/wildcard/mapped endpoints, stale/pre-Stop evidence, transitions/unknown states, unrelated port reuse, complete/partial/exceptional enumeration, post-ACK audit failure, ambiguous Stop/no retry, native identity changes, eight-second outer timing, drain timeout/handle retention, pipe-close errors, failed exit verification and second-Open refusal.
- Six tests exercise the real Windows PowerShell parsing/JSON path with **all CIM calls mocked**. They perform no native socket or process enumeration and cannot supply operational authority.
- Ruff check and format check passed for the four new Python files; Python candidate parsing and the PowerShell parser passed. No lint cache was enabled.
- Early offline development findings are retained privately: initially **74 passed / 7 failed**, then **78 passed / 3 failed**, plus one focused diagnostic failure. These were test-fixture construction/PowerShell mock-binding errors, corrected without relaxing acceptance assertions. An intermediate 81-pass result and the final 86-case focused result are preserved.

### Separate genuine disposable native diagnostic — FAILED, not hidden

One opt-in test created a standalone Python child with **one OS-assigned ephemeral IPv4 loopback socket**. It used neither the installed Control Center nor the former Atlas test ports. The parent retained its actual native creation identity and handle; no provider or financial code ran. The child had a 20-second natural maximum lifetime, with a 30-second test ceiling and 64-entry / 8-MiB fixture limits.

While the child's `listen()` had returned and the child was still alive, the genuine CIM capture returned the correct positive owner PID and exact endpoint but **State 0**. The documented TCP enumeration does not assign that state to a valid listener. The new observer refused it as **SOCKET_ACTIVE_OR_UNKNOWN_STATE**; the native test's expected State=2 witness assertion failed. **Result: 0 passed / 1 failed / 0 skipped, 1.91 seconds.** No second native run was attempted and State 0 was not normalized to force a pass.

The test's `finally` closed the original stdin, collected `closed:true`, zero exit status and empty stderr, then closed the retained process handle. Its fixture contained **four entries / 828 logical bytes**. A post-exit socket snapshot was **not reached** after the failed initial witness assertion, so no independent post-exit port-clearance result is claimed. The child closure/exit evidence is preserved separately from the missing socket readback.

This demonstrates fail-closed behavior on a genuine unsupported observation. It does **not** establish why the earlier, different installed endpoint had a PID-0 listener. A cross-checked native socket observation is still needed to qualify the enumeration path. Microsoft provides the read-only [GetExtendedTcpTable](https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getextendedtcptable) interface as a candidate independent comparison; it was researched, **not implemented or executed** here. No network-policy correction is justified by the current evidence.

## Readiness, preservation and next boundary

**Offline harness correction: implemented and regression-verified. Native enumeration qualification and historical socket root cause: BLOCKED / unresolved. Corrected full harness: not yet certified ready for another installed acceptance attempt.**

Next technical work is a bounded disposable-only comparison of CIM raw fields/types, native IP Helper rows and native textual output while an exactly owned listener is open and after its exit. Retain conflicting values and timings rather than selecting the passing reader. No installed launch, Windows setting change or administrator permission is presently justified. No further installed acceptance may run without a fresh explicit grant, fresh clock and all original checks.

Recovered baseline remains **UNSELECTED revision 4**, head **bdfe3b9a58605667dbf3a1b74b035236c196445697759cc82cd9124e22f7a419**. This milestone performed no operational selector readback/publication, rollback, reinstallation, journal reset, frozen-payload/shortcut change, provider connection, financial enrollment, account inception, PAPER/live trading, clock/networking configuration change or Genesis access. The unrelated research edit, prior failure reports and private evidence remain preserved. All B1/C1/D1/E1 requirements, 21 decisions and seven phases remain unchanged.

Raw evidence, original-file hashes, mocked/native logs and source-candidate proof remain private under `D:\Work\Project Atlas\logs\diagnostics\qd-socket-cleanup-root-cause-v1-20261102`. The full canonical roadmap archives its preceding checkpoint, and the recovery state retains prior evidence. **Stop after this source/validation checkpoint. PAPER NO. Production NO-GO.**
