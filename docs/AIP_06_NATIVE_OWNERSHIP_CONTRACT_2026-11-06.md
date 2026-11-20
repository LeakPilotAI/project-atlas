# AIP-06 native case-host and reader ownership contract

**Status: engineering contract for review; not native authorization.** This
contract reconciles the current source behavior with documented Win32
semantics. It does not qualify a Windows adapter, approve a handle-rights
profile, enable `CaseContext.require_execution`, or change any B1/C1/D1/E1 or
21-decision gate. Native execution, PAPER operation, and production remain
blocked.

## 1. Current composition and ownership boundaries

The original controller is the only process-creation authority. Its
`NativeController` binds the original process, file, CIM, allocation, and
process ports. `FixtureGuard._spawn` reserves ledger entries, prepares an
exact launch, calls `WindowsSessionPort.create_suspended`, verifies the
suspended Job, resumes the primary thread, binds a `WorkerOwnership` record,
installs the child guard, and only then releases the pinned target.

`WindowsSessionPort` owns the original process, primary-thread, per-launch Job,
and pipe handles returned or created by the original launch. It does not reopen
a process by PID. `RetainedLaunchBinding` binds the retained parent and launch
handles to image/file identity, source hash, command line, parent birth, nonce,
role, and the complete bounded Job roster. `WorkerOwnership` owns the normal
exit and distinct case-host abort transitions. `GuardedProcess` owns wrapper
closure. `CaseHostCoordinator` binds an existing released host and sends one
data-only INPUT; it is not a launcher or executor.

The reader is a separately guarded **sibling** process under the original
controller, not code running inside the case host. Its `ReaderExecutionContext`
accepts explicitly injected exact provider classes, checks its own retained
identity and bounded cuts, and marks results `native_acceptance: false`.
`aip06_reader_context_entry.main()` still refuses because a concrete native
provider-host binding is not qualified. No production call site currently
assembles controller, case host, reader, Stop, and terminal release into one
physical workflow. `CaseContext.require_execution()` and coordinator
`execute()` remain unconditional refusals.

Primary source locations:

- `scripts/observation_runtime/aip06_native_controller.py`
- `scripts/observation_runtime/aip06_native_session.py`
- `scripts/observation_runtime/aip06_case_host_coordinator.py`
- `scripts/observation_runtime/aip06_scoped_context.py`
- `scripts/observation_runtime/aip06_remote_handles.py`
- `scripts/observation_runtime/aip06_windows_process.py`
- `scripts/observation_runtime/aip06_windows_acceptance_adapters.py`
- `scripts/observation_runtime/aip06_reader_context_entry.py`
- `scripts/observation_runtime/aip06_owned_stop.py`
- `scripts/observation_runtime/aip06_harness.py`

## 2. Documented Windows behavior versus Atlas assumptions

The following are Windows API facts, not Atlas qualification:

1. `DuplicateHandle` requires `PROCESS_DUP_HANDLE` on both the source-process
   and target-process handles. `DUPLICATE_SAME_ACCESS` ignores
   `dwDesiredAccess` and gives the new handle the source handle's access mask;
   the duplicate refers to the same kernel object. `bInheritHandle = FALSE`
   makes the duplicate non-inheritable.
2. `AssignProcessToJobObject` requires `JOB_OBJECT_ASSIGN_PROCESS` on the Job
   handle and `PROCESS_SET_QUOTA | PROCESS_TERMINATE` on the process handle.
   Job assignment cannot be undone. Windows 8/Server 2012 and later support
   nested Jobs; older supported systems do not.
3. Job members' children normally join the Job. Breakaway limit flags can
   change that behavior. `TerminateJobObject` requires
   `JOB_OBJECT_TERMINATE`; it requests termination of all current members but
   is not an exit wait or a complete-roster receipt.
4. `WaitForSingleObject` requires `SYNCHRONIZE`. A signaled process handle
   establishes that the process object is signaled, not its Atlas identity,
   ancestry, Job drainage, or ledger closure.
5. Access masks are object-type-specific. API requirements must be derived
   from every operation actually performed on the duplicated handle, not from
   a general label such as “read-only”.

Atlas-specific assumptions that still require evidence or review:

- The retained `CreateProcess` process handle is the original handle used for
  Job assignment, observation, abort, and exit verification; no PID reopening
  or discovery adoption is allowed.
- The native session's per-launch Job is the case host's controlling Job.
  Assignment and exact membership are checked while the primary thread remains
  suspended. The existing limit readback permits the configured finite limits
  and kill-on-close setting but not breakaway flags.
- The parent's `RetainedPeerHandles` path duplicates a *child-context* handle
  into the original parent for observation. It is not a reader-provider
  transfer. Current code uses `DUPLICATE_SAME_ACCESS`, so the parent duplicate
  may retain more rights than the observation methods need.
- `ReaderIntent.access` is a checked declaration, not an OS access-mask
  enforcement mechanism. The code does not yet show that the reader's actual
  handles have exactly those rights.
- Injected Windows responses test Atlas control flow only. They do not prove
  real OS handle rights, ACLs, Job nesting, process ancestry, or closure.

Official references:

- [DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle)
- [Process Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights)
- [AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject)
- [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [Job Object Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/job-object-security-and-access-rights)
- [TerminateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject)
- [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)
- [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)

## 3. Contract requirements

In the matrix, “tests” names current offline/injected coverage. None of those
tests is physical Windows acceptance.

| # | Requirement and responsible component | Preconditions | Required postconditions | Failure behavior | Existing coverage / gap |
|---|---|---|---|---|---|
| 1 | **Original-handle ownership and identity** — `NativeController`, `FixtureGuard._spawn`, `WindowsSessionPort`, `WorkerOwnership`, `RetainedLaunchBinding` | Exact pinned executable/target and launch command; original controller and ledger are current; resource/process-slot reservations are durable before native allocation; one direct `case_host` nonce and role; the process and primary-thread handles returned by suspended creation remain retained by the original controller. | The original process handle, primary-thread handle, and original per-launch Job handle remain paired with their ledger tickets. `RetainedLaunchBinding` proves parent, child birth (`PID` plus creation time), image/file ID/hash, exact command and nonce. The exact bounded Job roster contains the suspended process before resume; the owned roster and child guard are bound before target release. The reader is a distinct, separately guarded sibling process. | Do not reopen/adopt by PID, compare equal-value foreign wrappers, or replace lost original handles. A failed or conflicting bind latches refusal and retains unresolved tickets. | `test_aip06_case_host_suspended_plan.py`, `test_aip06_case_host_guarded_process_handoff.py`, `test_aip06_case_host_identity_spoof.py`, `test_aip06_native_session_stop.py`, `test_launch_ownership.py`. Still no physical binding/ancestry evidence. |
| 2 | **Peer-handle duplication and rights** — `RetainedPeerHandles`, original `WindowsSessionPort`, `Win32ProcessCalls`, authenticated `Channel`/`Broker` | Authenticated current peer and nonce; exact resource key is already reserved to that peer; source handle belongs to the peer process; original process handles with `PROCESS_DUP_HANDLE` are retained; target is the original owner process; `bInheritHandle` must be false. | A type-specific, non-inheritable duplicate remains in the original owner only for the minimum rights needed by its registered observer; object type and identity are checked against the exact peer and reservation. Reader providers do not receive the controller's broad duplicates. `PROCESS_TERMINATE`, `PROCESS_CREATE_THREAD`, write/adjust rights, and Job assignment/termination rights are not granted to a reader. | Any unknown handle, object type, rights, or identity fails closed. Do not retry a possibly partial duplication, close the source as an incidental effect, or accept a PID/name-only match. Keep the reservation and duplicate ticket unresolved until reviewed terminal evidence. | `test_aip06_descendant_closure.py`, `test_aip06_native_session_stop.py`, `test_aip06_physical_native_proofs.py` verify injected continuity, wrong type, and closure. **Rights are not constrained today:** `Win32ProcessCalls.duplicate` selects `DUPLICATE_SAME_ACCESS` when `access=0`; type-specific rights are a human security-review decision. |
| 3 | **Reader-provider boundary** — `CaseContext.reader`, `ReaderContext`, `ReaderExecutionContext`, `WindowsReaderSet`, `PinnedWindowsRead`, `aip06_reader_context_entry` | Separately launched pinned reader entry; reader's own retained parent/process/Job and shared reservation are current; bounded private packet, exact case/reader manifest, source pins, nonce and request; concrete provider set is injected inside the reader child. | Reader has no controller or case-host Python object/capability. Its process evidence identifies the reader itself; file reads are pinned by path, file ID, hash, byte cap, ACL observation, and before/after identity. The fixed provider set returns complete fresh raw cuts and explicitly labels them non-acceptance. | Missing provider, unknown reader/source, stale or partial cut, provider error, changed identity, or timeout latches failure. No implicit loader, fallback provider, summary flag, or successful-looking default is allowed. | `test_aip06_scoped_context.py`, `test_aip06_reader_input_bytes.py`, `test_aip06_reader_source_receipt.py`, `test_aip06_reader_identity_spoof.py`. **Blocked:** `main()` refuses; no authorized native provider host or verified per-handle access masks. |
| 4 | **Failed-open and duplicate escrow** — `BootstrapBudget`, `NativeAllocations`, `PinnedWindowsRead`, `RetainedPeerHandles`, `WindowsSessionPort` | Reserve each prospective allocation before the OS call. Keep the exact original peer/Job alive while resolving the operation. Only the typed `NativeOpenFailed` path currently certifies that a pinned file open failed before returning a handle. | Success: retain exact handle and ticket until independent close proof. Known pre-acquisition refusal: release only under a reviewed, typed proof that no handle was acquired. Unknown outcome: retain an explicit unresolved ticket; no ledger credit. | Duplicate failure now records `DUPLICATE_OUTCOME_UNRESOLVED`, latches the peer, blocks replay, and prevents `dispose_after_exit()` from claiming complete release. The duplicate ticket and child resource stay open. No restart adopts the ticket. | `test_aip06_native_session_stop.py` covers the new unresolved-duplicate regression; `test_aip06_bootstrap_objects.py`, `test_aip06_native_allocation_identity.py`, and `test_aip06_case_host_abort_cleanup.py` cover other reserve-before-effect/cleanup paths. **Review required:** whether and how a concrete `DuplicateHandle` failure can be proved to have created no target handle so escrow can ever be safely released. |
| 5 | **Process and Job termination ownership** — original `WindowsSessionPort.abort`, `WorkerOwnership.abort_exit`, original `GuardedProcess` | Exact retained case-host session/binding and Job handle; binding's observer uses that same Job; if the host is still live, its retained process handle must still be a member of that exact Job. Child began suspended and was assigned/read back before resume. | Only the original controller may call `TerminateJobObject` on the exact retained Job. After the call, wait on the original process handle and independently re-read exit identity and the complete Job roster; the Job must be empty. Case-host abort may not fall back to `TerminateProcess` on the root alone. The terminal abort transition remains distinct from normal exit. | If membership is absent/unknown, refuse without terminating only the root. On timeout, nonempty Job, wrong identity, or failed Job query, retain all handles and ledger entries; no wrapper or case release. | This checkpoint adds the live-host membership guard and adversarial test. `test_aip06_case_host_abort_cleanup.py`, `test_aip06_native_abort_identity.py`, `test_aip06_native_abort_postwait.py`, `test_aip06_descendant_closure.py`. Physical Job hierarchy and descendants remain untested. |
| 6 | **Stop delivery and acknowledgment** — financial worker: `FixtureGuard.begin_stop`, `OwnedStopAssembly`, `GuardedStopCollector`, `StopVerification`; case host: not implemented | Financial path: one durable request bound to worker identity, one original authenticated channel, monotonic deadline, reserved Stop capacity, and independent reader. Case-host graceful Stop has no qualified message/ACK contract. | Financial Stop requires exact ACK correlation, complete zero-pending/zero-order/non-unknown drain, independently verified reader/financial readback, process/Job completion, and complete resource release. A case-host abort by Job termination is an abort only; it is not a graceful Stop ACK or a PASS. | Missing/mismatched ACK, incomplete drain, unknown state, or timeout latches failure and invokes only the already-owned cleanup path. Do not infer ACK from exit, EOF, or an exit code. For a case host, do not claim a graceful Stop until its protocol is reviewed and implemented. | `test_aip06_native_session_stop.py`, `test_aip06_case_host_abort_cleanup.py`, and Stop tests exercise distinct paths. **Human decision:** whether the host needs an explicit graceful STOP/ACK/DRAIN protocol before owner-controlled Job abort, and what complete drain means for case work. |
| 7 | **Independent exit verification** — `Win32ProcessCalls.wait/lifecycle`, `NativeProcessObserver`, `RetainedLaunchBinding`, `WorkerOwnership` | Keep original process handle open; use one absolute monotonic deadline; capture identity/ancestry while live; no PID reopen. Normal exit and abort have separate state transitions. | A bounded wait returns signaled; `GetExitCodeProcess` and retained-handle PID/creation time match the original launch; the independent original Job query is complete and empty; `WorkerOwnership.abort_exit` commits an abort as `normal_exit: false`. Normal `verify_exit()` still requires its exact configured success code. | Wait timeout, STILL_ACTIVE/unsignaled conflict, malformed receipt, reused PID/birth, missing capture, incomplete roster, or normal exit-code mismatch refuses. Do not close the process handle before all post-wait checks. | `test_aip06_native_abort_postwait.py`, `test_aip06_native_abort_identity.py`, `test_aip06_case_host_abort_cleanup.py`, `test_launch_ownership.py`. Injected only. |
| 8 | **Resource-ledger terminal reconciliation** — `WindowsSessionPort`, `RetainedPeerHandles`, `WorkerOwnership`, `GuardedProcess`, `CaseContext._close` | Every native resource and process slot is reserved under its exact owner before allocation. Keep the initial case resource baseline and exact host key set. Independent observers must be retained for each close. | Close the channel and exact native handles only after verified exit/Job drainage. Close native process slots only after the owner terminal transition. The ledger observer must agree with the exact complete resource set. Then close the original `GuardedProcess` wrapper, run `CaseContext.abort/_close`, and verify original scope release. Each close is idempotent only after its original proof. | A ledger conflict, missing key, failed observer, unknown duplicate, incomplete close, or changed wrapper leaves the ledger open and scope unreleased. Never set `closed` flags or refund charges from a receipt or child declaration alone. | `test_aip06_case_host_abort_cleanup.py`, `test_aip06_case_host_coordinator.py`, `test_aip06_native_close_identity.py`, `test_aip06_native_close_proof_identity.py`, `test_aip06_descendant_closure.py`. Physical ledger/OS agreement remains unverified. |
| 9 | **Timeout, crash, replay, and partial failure** — all owner-side phases above | One-shot nonce and phase transitions; deadline is monotonic and capped by the active session; original owner retains process/Job/resource capabilities; every side effect has a preceding ledger reservation. | Each phase moves monotonically from reserved to acquired/bound to verified terminal. Retried requests are refused. On partial cleanup, already proved closures may be recorded, but unresolved capabilities remain charged and block complete release. Parent crash/owner loss is not converted into a receipt or restart adoption. | Timeout or process crash means `UNKNOWN` until original-handle/Job evidence proves a terminal outcome. Keep unresolved reservations and latch failure. A killed process does not substitute for reader evidence, Stop acknowledgment, or a complete ledger cut. | Adversarial replay/partial-close cases across case-host, descendant, reader, and native-abort tests; new duplicate-failure case verifies the unresolved state. No power-loss/Windows crash-injection result exists. |
| 10 | **Physical acceptance evidence** — future separately authorized acceptance owner plus independent reviewer | Fresh explicit, bounded, single-use authorization scoped to exact source pins, Windows build/session, targets, roots, test matrix, resource/time budgets, and allowed cleanup; independent reader/provider binding and Stop plan reviewed first. This specification is not authorization. | Retain independently captured pre/post process identity and ancestry, pinned executable identity, exact Job limits and full roster, actual handle rights/inheritance, reader/provider process identity and all fresh source cuts, Stop ACK/DRAIN (when required), original exit code, empty Job, full resource-ledger terminal state/head, wrapper closure, timeout/replay/fault evidence, and post-run host inventory. Review receipts against actual OS observations and source pins. | Any missing, changed, late, malformed, replayed, provider-self-authored, or contradictory evidence means BLOCKED/FAIL; do not retry under the same authorization or infer qualification from injected tests. | Current suite has no independent physical Windows evidence. Required package and actual acceptance execution remain blocked by fresh authorization and security review. |

## 4. Handle-rights matrix and proposal validation (not approved)

Requirements below apply to the **object handle passed to the listed API**,
not the process handles used to call `DuplicateHandle`. Microsoft documents
limited query rights on current Windows and stricter requirements on some
legacy versions. Atlas has not qualified a supported Windows-version range.

| Handle / component | Source operations | Documented requirements | Reader proposal and exclusions | Transfer / close status |
|---|---|---|---|---|
| Process — `WindowsProcessCalls`, `WindowsObjectCalls`, `WindowsProcessEvidence` | `GetProcessId`, `GetProcessTimes`, `QueryFullProcessImageNameW`, `GetExitCodeProcess`, `IsProcessInJob`, `GetProcessMemoryInfo`, `WaitForSingleObject` | Query calls accept `PROCESS_QUERY_LIMITED_INFORMATION` or `PROCESS_QUERY_INFORMATION` on current Windows; `WaitForSingleObject` requires `SYNCHRONIZE`. `GetProcessMemoryInfo` accepts query-limited on modern Windows; XP/Server 2003 additionally require query-information and `PROCESS_VM_READ`. | Candidate for modern Windows observation: `PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE`. Exclude `PROCESS_DUP_HANDLE`, `PROCESS_TERMINATE`, `PROCESS_SET_QUOTA`, `PROCESS_SET_INFORMATION`, `PROCESS_SUSPEND_RESUME`, `PROCESS_VM_OPERATION`, and `PROCESS_VM_WRITE` from the reader. Legacy memory observation is blocked pending platform and least-rights review. | `PROCESS_DUP_HANDLE` is required on the source-process and target-process handles passed to `DuplicateHandle`; it is not a right on the duplicated process object. Current duplication uses `DUPLICATE_SAME_ACCESS`, so the proposal is not enforced. Original process close stays with its original owner. |
| Thread — `WindowsObjectCalls.observe` | `GetProcessIdOfThread`, `GetThreadId`, `GetThreadTimes`, `WaitForSingleObject` | Query calls accept `THREAD_QUERY_LIMITED_INFORMATION` or `THREAD_QUERY_INFORMATION` on current Windows; waiting requires `SYNCHRONIZE`. Older versions may require the full query right. | Candidate: `THREAD_QUERY_LIMITED_INFORMATION | SYNCHRONIZE`. Exclude `THREAD_TERMINATE`, `THREAD_SUSPEND_RESUME`, `THREAD_SET_CONTEXT`, `THREAD_SET_INFORMATION`, token-setting, and impersonation rights. | Peer duplicates preserve source access today. No reader-specific thread duplicate is authorized or qualified; terminal closure needs original-owner proof. |
| Job — `WindowsProcessCalls`, `WindowsJobEvidence` | `QueryInformationJobObject` for process list, limits, and accounting | `JOB_OBJECT_QUERY`. Assignment, setting limits, and termination separately require `JOB_OBJECT_ASSIGN_PROCESS`, `JOB_OBJECT_SET_ATTRIBUTES`, and `JOB_OBJECT_TERMINATE`. | Candidate observation right: `JOB_OBJECT_QUERY` only. Exclude assign, set-attributes, set-security-attributes, and terminate rights from the reader. | Original controller retains assignment/configuration/termination authority. Reader access is not assembled; no query-only duplicate is actually established. |
| Access token — `WindowsFileCalls.token_identity`, `WindowsObjectCalls.observe` | `GetTokenInformation` for user SID and token type | `TOKEN_QUERY` for querying token information. | Candidate only if token identity remains in reviewed reader scope: `TOKEN_QUERY`. Exclude `TOKEN_ADJUST_*`, `TOKEN_DUPLICATE`, `TOKEN_ASSIGN_PRIMARY`, and impersonation rights. | Token duplication/opening and reader provisioning are unqualified; no token rights are transferred by the current reader entry. |
| Pinned file/directory — `WindowsFileCalls`, `PinnedWindowsRead` | Read contents and metadata, inspect final path and ACL, close the opened handle | The source requests generic read plus `READ_CONTROL` and file attributes for pinned images; relative opens use operation-dependent NT access flags. Exact generic mapping, ACL-query needs, and directory operations must be audited per path and API. | Do not publish a single approved mask. `FILE_READ_DATA`, `FILE_READ_ATTRIBUTES`, `READ_CONTROL`, and `SYNCHRONIZE` are candidates only where the exact provider call requires them. Exclude write/append/EA/attribute, delete, DACL/owner mutation, and execute rights. | `PinnedWindowsRead` opens a separate pinned read handle; this is not peer-handle transfer. Its original owner accounts and closes it. A reader must not receive a handle to an output or writable endpoint. |
| Pipe / event / mutant / semaphore / timer — `WindowsObjectCalls`, `WindowsChildEndpoints` | `GetFileType`, `GetNamedPipeInfo`, `NtQueryObject(ObjectTypeInformation)`, `CompareObjectHandles`, and pipe reads/writes on owner-side channels | No complete documented minimal mask has been established for the exact combined operations. Pipe endpoint direction matters; `NtQueryObject` is not a basis for a portable least-rights grant. | Blocked: no general reader mask. Exclude unused read/write direction, signal/modify, and all mutation rights. `DUPLICATE_CLOSE_SOURCE` is not an ordinary transfer mechanism. | Never use `DUPLICATE_SAME_ACCESS` as proof of least privilege. Exact endpoint rights and close ownership require review. Unknown object types remain refused. |
| Process handles used to duplicate peer handles — `Win32ProcessCalls.duplicate` | `DuplicateHandle(source_process, source_handle, target_process, ...)` | `PROCESS_DUP_HANDLE` is required on both process handles passed as source and target. `bInheritHandle=False` makes the new handle non-inheritable. `DUPLICATE_SAME_ACCESS` ignores `dwDesiredAccess` and copies the source object's access. | Keep this capability solely in the original controller boundary; do not give it to the reader. Do not treat it as a right on the child process-object duplicate itself. | Current code passes `access=0`, selecting `DUPLICATE_SAME_ACCESS`; it does not enforce the proposed masks. No `DUPLICATE_CLOSE_SOURCE` transfer. A raised duplicate failure is unresolved escrow and cannot be replayed. |

`scripts/observation_runtime/aip06_handle_rights.py` adds a pure proposal
validator for documented process, thread, Job, and token query operations. It
rejects missing operation rights, mutation/transfer rights, unknown types, and
unknown operations. Its result is always labeled
`UNAPPROVED_REVIEW_CANDIDATE`, with `native_handle_verified`,
`security_approved`, and `execution_authorized` all false. File and IPC object
masks are deliberately rejected as unreviewed.

The reader input also checks its symbolic access declaration against a closed
read-only label set and rejects mutation, duplication, inheritance, or write
labels. This checks only the declaration; it does **not** inspect an OS handle,
enforce an access mask, or qualify the provider host. The reviewed
`ReaderIntent.access` remains a declaration, not an OS grant receipt.

Microsoft API references used for this matrix:

- [DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle)
- [Process Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights)
- [GetProcessId](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocessid)
- [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes)
- [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo)
- [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)
- [Thread Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/thread-security-and-access-rights)
- [GetThreadTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes)
- [Job Object Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/job-object-security-and-access-rights)
- [QueryInformationJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject)
- [Access Rights for Access-Token Objects](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-rights-for-access-token-objects)
- [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)

## 5. Safe source changes in this checkpoint

Three fail-closed/source-only changes are implemented and covered by injected tests:

1. An owned case-host abort now proves the binding's original Job handle is the
   exact session Job. If the host is still live, it must still be a member of
   that Job before `TerminateJobObject` is allowed. The owner-scoped case-host
   path cannot fall back to terminating only the root process when Job
   membership is absent. This prevents a false subtree-cleanup claim.
2. If peer-handle allocation reservation fails, the retained peer is latched.
   If `DuplicateHandle` raises after its ticket is reserved, the peer records
   an explicit `DUPLICATE_OUTCOME_UNRESOLVED` escrow and is latched against
   retry. `dispose_after_exit()` can close other independently known resources
   but refuses complete release while that unknown outcome remains. It does
   not refund the ticket, close the child's resource slot, or manufacture a
   successful receipt.
3. `aip06_handle_rights.py` adds an offline proposal validator for documented
   process, thread, Job, and token query operations. Reader-context construction
   rejects symbolic declarations containing mutation, transfer, inheritance,
   or write labels. The proposal result always remains unapproved and
   unauthorized; it neither observes nor grants a Windows access mask, and
   file/IPC masks remain blocked. An adversarial scoped-context test exercises
   the rejection at the reader boundary.

No actual Windows API was invoked by these tests. The candidate rights are not
connected to `DuplicateHandle`, and the symbolic reader labels do not establish
provider identity or OS rights. The unresolved duplicate escrow intentionally
remains a blocker pending review of a trustworthy no-target-handle proof or an
independently qualified reconciliation method.

## 6. Human security-review decisions and next executable milestone

Required decisions before any physical assembly:

1. Approve an object-type-specific access-mask table and the exact boundary
   holding `PROCESS_DUP_HANDLE`; verify that the reader cannot terminate,
   mutate, or inherit any controller capability.
2. Confirm supported Windows build, nested Job behavior, Job handle identity,
   per-launch versus aggregate Job containment, and proof that no breakaway
   route exists on the target.
3. Decide whether case-host Stop requires a distinct graceful STOP/ACK/DRAIN
   protocol, and review its owner, receiver, timeout, and failure-to-Job-abort
   ordering. Existing financial Stop receipts are not reusable as host ACKs.
4. Decide how an indeterminate `DuplicateHandle` failure is reconciled without
   releasing a possibly live local duplicate or adopting handles after restart.
5. Qualify how exact native providers are created and pinned in the independent
   reader, including actual handle rights, ACL provenance, and freshness.
6. Approve the exact independent acceptance evidence package and the separately
   scoped one-time Windows authorization. Source tests cannot supply it.

**Next executable engineering milestone:** implement the reviewed,
type-specific peer-handle rights and qualified reader-provider binding behind
the unchanged execution refusals, then add injected tests for each access mask,
forbidden right, partial duplicate, reader isolation, and replay. Until the
review decisions are made, the only next action is source review; no physical
case-host or reader execution is authorized.

Roadmap remains **5/18 (27.8%)**. AIP-06 physical acceptance is blocked. Daily
PAPER is not operational. Production remains **NO-GO**. B1/C1/D1/E1, all 21
safety decisions, and Genesis isolation remain unchanged.
