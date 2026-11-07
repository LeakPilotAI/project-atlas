# V5 verified launch ownership binding

**READY FOR V5 APPROVAL-PACKAGE PREPARATION.** Source and disposable Windows validation only. Installed acceptance has **not** passed. V4 remains FAIL and its single-use authorization remains consumed. Starting checkpoint: `220efd0a7f0ef1827101ccb93bb76fa06756070a`, branch `chatgpt/atlas-rebuild-v1`.

## What was established

The existing source virtual-environment executable is a Windows Python redirector in the tested environment. Genuine disposable launches independently observed two distinct Python processes: the retained D-venv launch process and the base interpreter running the requested command. The base interpreter's parent was the launch process; both native creation times, image paths, native image-file identities, SHA-256 values and exact command lines were recorded while native process handles remained open. The redirector rewrites the first command-line token to a quoted base-interpreter path; it does not preserve the venv executable token. This was measured, not inferred from filenames. Python documents Windows venv redirectors in its [venv documentation](https://docs.python.org/3.12/library/venv.html).

That reproduces the mechanism capable of producing V4's unclaimed outer PID. It does **not** reconstruct PID 19940's missing parent/handle evidence or retrospectively grant ownership. The original strict refusal was correct. No V4 result, claim, proposal, reviewed template or source pin was changed.

Direct detached interpreter launches required one owned Python process. The tested venv redirector additionally created `C:\Windows\System32\conhost.exe` as a child of the inner interpreter, even when the outer launch was detached. A preliminary `CREATE_NO_WINDOW` direct launch also created a console host. All unrequested processes were refused; none was hidden by an executable-name exclusion. The final venv test explicitly requested and pinned that console-host role before launch.

## Exact implementation

| File | Behavior |
| --- | --- |
| `scripts/observation_runtime/launch_ownership.py` | Immutable role/nonce/topology/image/command request; original parent and launch handles; exact live ancestry and lifetime checks; retained runtime/optional explicit auxiliary handle; complete native Job roster; latched refusal; exact retained exit checks. No process creation, killing, PID adoption or operational authority. |
| `scripts/observation_runtime/launch_ownership_windows.py` | Read-only native PID/FILETIME/image observations cross-checked with independent exact-PID CIM command/parent/image/creation observations; before/after lifetime checks, five-second freshness bound, bounded Job enumeration and cleanup-time reserve. Image read leases bind native file identity and SHA-256 while excluding writes/deletes. |
| `tests/run_launch_ownership_native.py` | Confined fixture-only launch owner: original `CreateProcess` handle, suspended launch, Job assignment before resume, explicit inherited-pipe handle list, independent READY checks, repeated binding verification, EOF shutdown, exact exit/readback and handle closure. Records source hashes, not an installed-acceptance ticket. |
| `tests/launch_ownership_child.py` | No Atlas imports, ports, provider/account access or application start; bounded READY/nonce/role fixture, stdin-EOF lifecycle and controlled unexpected-child negative fixture. |
| `tests/test_launch_ownership.py` | 67 new offline cases for direct/redirected ownership, missing/contradictory evidence, lifecycle, PID reuse, orphaned/missing parents, explicit auxiliary identity and read-lease boundaries. |

The launch owner retains the actual `CreateProcess` handle for the launch process. A redirected runtime is opened only as a candidate inside that exact owned Job; it becomes bound only after independent native/CIM creation, image, command, parent, nonce and full-roster checks. A matching command alone never supplies ownership. The parent handle remains retained and is freshly reverified throughout; parent PID reuse or changed creation time refuses. Missing handles, unsupported topology, wrong roles, unexpected Job members, incomplete observations or any disagreement fail closed and latch refusal. JSON claims are output from the verified in-memory binding, not sufficient input for creating one.

The exact console-host executable is separately pinned by native file identity/hash and exact command `\??\C:\WINDOWS\system32\conhost.exe 0x4`; parent must be the verified runtime and creation must follow its parent. Windows component-store hardlinks are allowed **only** for a separately requested read lease on that exact SystemRoot console image. The file-object read lease denies write/delete sharing through aliases. Project image hardlink/reparse refusals remain unchanged; financial custody code and namespace rules are untouched.

The Python launch/runtime must both exit **0**. The measured console-host terminal code was **109**, after verified Python exit and pipe closure. Microsoft labels 109 as [ERROR_BROKEN_PIPE](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-). The request must explicitly pin the auxiliary's exact expected terminal code; it is never translated into Python success, accepted as an unknown error, or used to excuse a remaining Job member. Its original handle, exact creation time, signalled exit and empty Job are mandatory. Future approval must review this explicit console-host dependency and terminal behavior; it is not an operational policy change.

The adapter records native identity while suspended, then requires full independent command/ancestry evidence after genuine fixture READY because WMI did not expose usable command evidence for the suspended process. Native image queries may fail after process exit; exit verification therefore uses the **retained original handle's** PID, FILETIME, signalled state and exit code, without reopening or replaying a PID. Windows documents retained creation handles in [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw) and inherited Job membership in [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

## Final genuine native validation

Evidence: `logs/diagnostics/qd-v5-launch-ownership-native-verified-20261103`. All four recorded source SHA-256 values still match current files. Total **54.9442281 seconds**, six cases passed:

| Case | Launch → runtime PID | Result | Total case seconds |
| --- | --- | --- | ---: |
| Direct supervisor | 18644 → 18644 | Verified live binding, Python exit 0, empty Job, handles closed | 10.2982392 |
| Venv supervisor | 24116 → 20952 | Both Python identities plus console 31916 verified; exits 0/0/109; empty Job | 13.1530886 |
| Direct worker | 17324 → 17324 | Verified live binding, Python exit 0, empty Job, handles closed | 10.3180135 |
| Venv worker | 32724 → 6536 | Both Python identities plus console 31260 verified; exits 0/0/109; empty Job | 12.8536965 |
| Direct unexpected child | 6436 → 6436 | Strict `UNEXPECTED_OR_MISSING_JOB_PROCESS` refusal; normal fixture cleanup | 3.5831643 |
| Venv unexpected child | 1828 → 20532 | Same strict refusal despite otherwise matching requested chain; normal cleanup | 4.7162196 |

Each positive case also ran five negative checks against actual live native observations: wrong exact command, wrong executable hash, wrong retained parent, missing original handle and closed parent handle. **20/20 native negative checks refused.** All four positive cases also refused a live claim for the now-exited retained runtime. These are native evidence checks, not additional installed cycles or an operating-system PID-reuse experiment. Deterministic PID-reuse, missing-ancestry and orphan/missing-parent cases use offline injected observations; no attempt was made to force Windows to recycle a PID or orphan an unrelated process.

Every final fixture Job ended empty; all retained process, primary-thread, Job, image, pipe and reader-thread resources closed normally. **No forced cleanup occurred in the final six-case run.** No ports were bound. Independent query helpers completed synchronously. Final native resource accounting before result serialization was **21 entries and 87,617 logical bytes**, under the fixture's 180-second / 1,024-entry / 16-MiB bounds; final reporting totals are recorded separately. These case durations include many independent identity queries: **they are not installed Stop timings** and do not alter the eight-second installed Stop requirement.

The existing D-source venv and its existing C-resident base interpreter were used; nothing was installed. No installed Atlas interpreter or Control Center ran. Actual frozen installed-runtime/dependency origins remain a future, separately authorized acceptance requirement.

## Regressions and preserved failures

**217 passed, 0 failed, 0 skipped**: 67 new ownership/image-lease cases plus all 150 previously verified ownership/resource-audit/cleanup/sequencing cases. Final log: `logs/diagnostics/qd-v5-launch-ownership-20261103/final-regression.log` (17.39 seconds). No-cache lint passed for all five new source/test files. Existing browser ACK 45 s, Stop 8 s, three-reader agreement, fresh process snapshot and rollback requirements were not modified; their relevant regression cases passed.

All preliminary native failures are preserved in distinct `qd-v5-launch-ownership-*` roots. They include confined CIM denial; missing suspended command evidence; an unrequested native console host; post-exit image-query refusal; explicit SystemRoot image hardlink refusal; and console exit 109 being rejected by the prototype's all-zero exit check. The last prototype exit failure independently recorded both Python exits 0 and console exit 109 before the exact auxiliary terminal contract was added. These failures are not retroactive passes.

One earlier prototype recorded a console PID still in its Job immediately before Job closure even though its `forced_cleanup` flag was false. That flag did not establish graceful descendant cleanup: the Job was kill-on-close. The final fixture owner checks the **whole Job**, records/contains residual descendants on any failure, and never counts forced cleanup as success. The final six cases demonstrated empty Jobs before closure without using that fallback. Original V4 failure evidence and all historical 21 decisions remain unchanged.

## Next prerequisite and remaining limits

The binding is ready to be incorporated into a **new V5 approval package**, including the exact outer-launch entry point, parent/launch/runtime/console role pins, source inventory, dependency/library paths, capability retention and revalidation at each orchestration boundary. That package must wire the retained binding into the actual helper roster; merely copying its JSON output or rerunning the unchanged V4 entry point is insufficient. A direct detached, wrapper-free launch has fewer dependencies and should be evaluated first when preparing that package. No operational entry point, V4 proposal, support installation or frozen application was changed by this milestone.

Then obtain a fresh explicit single-use installed-acceptance authorization, new unused evidence root and full current native/receipt/ACL/clock/socket/process/rollback preflight. V4 authorization cannot be reused. Installed two-cycle browser/Stop/restart acceptance is still missing. The last independently verified selector remains **UNSELECTED revision 6**, head `c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc`; no fresh operational selector read or mutation occurred here. The historical 704-ms clock capability remains revoked, not current clearance.

Accepted current research, executable IEX/calendar/rights evidence, financial custody/authority, separately authorized once-only inception and PAPER execution remain financial commissioning prerequisites. No provider, account, financial writer, browser/desktop launcher, Windows Time setting, shortcut, autostart, frozen application or Genesis resource was touched. B1/C1/D1/E1, all 21 decisions, seven phases, original UI and unrelated workspace changes remain preserved. **PAPER: NO. Production: NO-GO.** Stop after this source/disposable milestone, reporting and verified Git synchronization.
