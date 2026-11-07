# AIP-06 native session and Stop integration

2026-11-04. Branch `chatgpt/atlas-rebuild-v1`.
Starting checkpoint: `0a4eb3f4fcdfadbb574d13fa56f1f59c0e4bfd92`.

**SOURCE INTEGRATION BLOCKED — physical endpoint/child-entry binding, non-file/descendant proofs, aggregate Job budgeting and legacy probe integration remain incomplete.** The implemented source connections below pass offline validation. This report does not mark the requested full source integration complete. AIP-06 remains BLOCKED; overall completion remains **5/18**. PAPER: NO. Production: NO-GO.

## Scope and implementation

Recovered the canonical roadmap/state, integrated audit, native readiness review, fixture-guard integration report and Windows adapter report. Existing source changes and private evidence were preserved. This increment does not create a native fixture, run a native backend loader/controller, launch a native financial worker, select/launch installed Atlas or connect any provider. Tests inject Windows responses into the actual new source classes; a passing mock is not native evidence.

### Concrete process-session factory

`aip06_native_session.NativeSessionFactory` now constructs `WindowsSessionPort` from the controller's actual filesystem, CIM, allocation and process interfaces. `FixtureGuard.spawn` drives that port through planning, reservations, suspended creation, finite Job-limit readback, assignment before resume, native/CIM READY verification, retained ownership binding, child guard receipt and target release. There is no Popen or PID-discovery fallback.

The port verifies the current parent against its registered full identity, retains the parent/process/thread/Job/image handles and checks the immutable image through its original handle. Process/thread slots precede creation. Inheritance is restricted to the exact owned allocation map; the working directory is the workspace; old native/installed grants are refused. Command plans retain their history but bind only the current nonce, so a later identical reader command cannot accidentally match an old plan. Existing ledger, charges, nonces and session history survive the timing sampler's roster rotation.

Guarded launch refusals and communication failures now invoke bounded cleanup of known sessions. Assignment failure uses the original creation handle and captured birth identity, not OpenProcess(PID). Abort checks that birth again. A failed/refused session remains failed after cleanup; unproved reservations are not refunded or relabeled released. Incomplete/ambiguous native cleanup retains unresolved state. These source tests do not establish real Windows cleanup timing.

### Child-side resource and transport connections

`aip06_remote_handles` connects child file-handle registration to `RemoteResources`/the parent broker. The parent duplicates only from the original retained peer process, verifies file/directory identity/path/link information and retains a charged duplicate. A close declaration triggers an independent duplicate attempt against that original peer handle. A still-valid or reused integer refuses. Enumeration errors do not become closure. Parent-held duplicates can be disposed after independently verified original peer exit; that proof explicitly says `financial_ack=False`.

`ParentFrames` services actual resource RPC frames while awaiting child evidence and records OUTPUT before returning it. It does not reinterpret text as ACK. It preserves received phase frames and timestamps for later readback, bounds output and refuses surprising frames. Child resources now share a bounded mailbox so STOP arriving during a resource reply is preserved. Cached frames recheck age and peer identity before use; stale queued STOP refuses.

`ChildSessionIO` supplies authenticated input, correlated Stop acceptance, bounded stdout/stderr, structured output and reader receipt handling. `ChildBootstrap.run` uses the output context when bound and closes IO caches before EXIT. Failed text delivery retains the pending bytes and refuses automatic retransmission. Raw descriptors are unavailable. The physical cross-process endpoint/context construction remains unbound, as detailed below; `ChildBootstrap.main()` still explicitly refuses.

### Financial Stop, cold readback and outputs

The actual owned timing entry can now use the session port's `owned_stop_spec`, `financial_ready`, `send_stop` and `collect_stop` connections. `OwnedStopAssembly` reuses the original in-memory fixture parameter definition; it does not invent a manifest or native resource identity. Native identity starts absent and is filled only from matching READY account/epoch/manifest/process evidence and independent resource-directory readback. The original pipeline READY observer now exports its actual enrollment, manifest and acknowledged source revision rather than an empty value.

`ChildStopEndpoint` checks the durable parent Stop request, actual worker identity, nonce, revision and account scope before emitting its acceptance ACK. The original pipeline's READBACK callback occurs only after its existing complete financial Stop, flat-position, acknowledged readback and zero-pending assertions; that callback enables the drain message. A raw stdout line is not a drain or financial ACK.

`GuardedStopCollector` preserves the original `started + 8 seconds` deadline. It receives exact ACK/drain frames, requires verified worker exit, launches a separately retained reader through the same guard, binds the reader response, closes owned resources, collects three-reader socket evidence first and strict process evidence last, and passes the evidence to the unchanged financial `StopVerification.finish` replay/audit checks. Failure latches the collector/guard, records FAILED or UNKNOWN and cleans only known sessions. No deadline is extended and later cleanup cannot turn failure into success.

The existing `personal_readonly_restart_child` can export raw financial rows/snapshot/head plus hash inventories and stage cuts through `personal_financial_reply`. It reuses the original `PersonalRuntimeCurrent._capture`, native source/projection/report checks and selected-reader verification. Missing projections, UNKNOWN publication, stale/conflicting revisions, source/hash changes, currency mismatch or missing writer-rebind refusal reject the reply. The original Stop verifier still independently replays and audits these rows; fixtures do not become operational authority.

A review found that a self-exiting reader could print its response and exit before the parent observed its live retained identity. The reader now waits for an exact request/financial-digest/reader-bound **transport receipt** after printing. The parent binds the live reader identity before issuing it. This receipt explicitly has `financial_verified=False`; financial acceptance still occurs in the original verifier after exit. Missing, wrong, replayed or falsely financial receipts refuse.

`aip06_test_driver` provides an explicit six-module native-fixture selection, guarded temporary paths and bounded create-new JUnit publication. It disables plugin autoload requirements, cache, raw FD capture and faulthandler output; temporary paths and XML remain under fixed fixture roots. Setup/call/teardown, skipped/failed/incomplete test outcomes retain their actual meaning. Tests invoke a fake pytest entry to exercise this adapter; no selected native test module was executed here. The installed application, dashboard and notification system were not activated.

### Bootstrap accounting qualification and its limit

`IntrinsicJournalIO` now lives on the same `SharedResources` instance and prospectively accounts the journal's own ephemeral handle lifetimes, without recursively writing a journal event to reserve the handle needed to read that journal. The existing 16-handle batch bound is retained, counters/hash continuity never reset within the instance, failed opens are distinguished from released handles, close proof is required and every batch must be quiescent. The first real ledger still imports the copied bounded bootstrap reservation; ordinary file/storage charges remain in its original journal. Stop checks the intrinsic meter as well as ordinary resource release.

An integration test exercises actual `NativeJournalIO`/`CreateNewJournal`/`SharedResources` algorithms against fake Windows files, proving nonrecursive accounting and closed native lifetimes at the source boundary. This meter is process-local native IO accounting, not a second financial journal, durable antirollback authority or proof of a real kernel handle lifetime.

Failed Stop resolution now retains STOP mode for bounded cleanup rather than returning to WORK mode. This preserves the existing 540-second work cut and 600-second cleanup ceiling; it does not extend the eight-second Stop deadline. Offline cases cover failure after the work cut and refusal of further work.

**The full resource requirement is not yet proved.** Existing prospective charges and per-session finite Job limits are enforced by the new source port, but a common native aggregate Job budget covering controller plus all workers is not constructed. Per-Job memory/CPU ceilings alone do not establish the canonical aggregate private-memory/CPU cap. Declared descendant Jobs and the controller's own resource envelope need an explicit composed implementation; do not infer compliance from independent per-process ceilings or fake usage samples. The fixed 4096-byte accounting assumption also still needs a mandatory observed-volume compatibility gate before a real run.

## Completeness audit

The companion `docs/AIP_06_NATIVE_SESSION_STOP_BOUNDARIES_2026-11-04.json` indexes current call sites, working-byte source pins and the following entry-point decisions. Static indexing is not dynamic coverage or a general Python security sandbox.

| Entry point | Guard/ownership/accounting/release | Offline evidence | Remaining requirement |
|---|---|---|---|
| `NativeController.initialize` | Original identity/image/token; bootstrap import; intrinsic meter; factory binding | Existing adapter tests plus shared native-journal injection | Init failure closure, runtime/volume compatibility and aggregate controller/worker budget remain unqualified/incomplete. |
| `FixtureGuard.spawn -> WindowsSessionPort` | Prospective exact slots; retained native/CIM image/ancestry; suspended Job; receipt before release | Actual guard/factory/roster exercised, including assignment/create/ownership/receipt/termination failures | Physical transport provider is still required. No native execution was performed. |
| `ChannelSessionProtocol.ready/bind/release` | Versioned Channel, exact identity/nonce/snapshot receipt; no early release | Existing Channel/bootstrap tests; new session/protocol tests | `endpoints.command/prepare/channel/receive_guard_receipt/communicate/close` have no concrete complete Windows endpoint/context provider. |
| `ChildBootstrap.main / prepare / run` | Fenced parent-ledger bootstrap and output/cache hooks | Prior bootstrap cases preserved; new child output/receipt validation | `main` still refuses `AIP06_NATIVE_CHILD_LAUNCH_PORT_NOT_BOUND`. Inherited descriptor loading and concrete child guard/root bindings are not complete. |
| `RemoteResources -> RetainedPeerHandles` | Original peer handle; prospective parent duplicates; independent close/exit evidence | Register/close/reuse/wrong-owner/dead-peer cases | Files/directories only. Native token/event/thread/mutex proofs and no-allocation/effect-capacity releases remain incomplete. |
| `RemoteHandleProofs.child / RetainedPeerHandles.child_binding` | Explicit refusal, no PID-only adoption | Missing/foreign proof refusal retained | Both descendant transfer functions remain unbound. The present exact per-process Job roster also needs declared transitive ownership for financial crash/race children; do not silently accept extra members. |
| `run_owned_stop_sample -> OwnedStopAssembly` | Exact S1–S3 roots/nonces; original parameters; genuine READY-derived native IDs/revision | READY mismatch cases and original three-slot guard tests | Needs physical endpoint/child services and complete native cleanup providers before executable eligibility. |
| Worker Stop/READBACK callbacks | Durable request identity; acceptance ACK; drain only after original financial checks | Correlation/drain negatives and real source function wiring | No actual native worker or native financial ACK was observed. Child watchdog/native-object services remain to be bound. |
| `GuardedStopCollector -> StopVerification.finish` | Actual guard/roster, separate reader, raw replay/audit, socket then process, eight seconds | End-to-end injected worker/reader lifetimes and financial replay; missing/conflicting/late evidence fails | Concrete bounded CIM/IP Helper/netstat/process collection composition is not supplied. All three readers remain mandatory. |
| Cold reader `main / personal_financial_reply` | Existing native custody checks; stable hashes; live identity receipt then exit | Raw financial/changed hash/revision/currency/projection/rebind and reader receipt tests | Genuine root/handle binding, native readback and whole-window timing await complete source plumbing and later authorization. |
| `ParentFrames / ChildText / run_reviewed_tests` | Broker servicing, received output records, capacity/no raw descriptor, guarded tmp/XML | Output/queued-frame/JUnit/driver/capture refusal tests | Must be selected by the concrete child/endpoint construction; no unbound output path receives an exception. |
| Legacy probe `run_launch_ownership_native.main` | Existing missing-binding refusal preserved | Earlier unsupported-probe tests retained | `WindowsSessionPort.legacy_probe`, `NativeController.probe_case` and independent probe release verifier remain unimplemented. Supervisor/unexpected-child cases cannot be declared passed by weakening the financial-worker roster. Raw legacy body remains unreachable. |

All remaining work above corresponds directly to this milestone's process, child, Stop/probe/output or bootstrap-budget requirements and the native readiness contract. No strategy, provider, infrastructure or acceptance-contract expansion is proposed. These are **technical source gaps**, not a demand for routine engineering permission. Do not request a native grant to execute the incomplete assembly.

## Validation and preservation

Final results and exact hashes are recorded in the recovery state and the retained diagnostic result index. Final Python: **1,576 passed, 0 failed/errors/skipped; 5 financial-child cases deliberately deselected**. Focused selection: **421 passed** (overlaps broader tests). **61 new cases**; all **1,515 prior case identities** were independently verified present in the final XML. Node: **42 passed, 0 failed/skipped/cancelled**. Standalone polling/transport/render contract: PASS, counted separately. The existing Starlette/httpx and Discord `audioop` warnings remain.

Final JUnit: `logs/diagnostics/aip-06-session-stop-20261104/verified-budget-final.xml`.
SHA-256: `07689da477fee486167ae0adb5ceda7dd2d7617c236caff1bb37a7d690147dae`.

The three epoch-crash and two autonomous-QD abrupt-child cases remain excluded; original assertions are unchanged. All tests here use ordinary offline fixtures/injected Windows responses. New JUnit/output-driver tests do not execute the native pytest selections. Raw logs, intermediate XML, source/case-ID evidence and private fixtures are preserved under `logs/diagnostics/aip-06-session-stop-20261104`. Initial 106 focused cases passed; an expanded run retained one tuple/list owner-fixture failure (389 passed/1 failed) before correction. Later focused 408, 412, 417 and 419 runs and the 1,567/1,574 broader runs are retained; final evidence supersedes overlapping results. No failure or late evidence is relabeled PASS.

The unrelated `tests/test_free_research_pipeline.py` edit retains SHA-256 `4836c60e65a9b48b36e08b3df824e4bdf0dde7e0667ffd835a742ca43b602ffb` and is excluded from this commit. Existing native records, backups, historical failures and consumed authorizations are preserved. The proposed native roots remain absent; no native cleanup PASS or actual Stop duration is claimed from fake interfaces. Cache/bytecode outputs were disabled and offline TEMP/TMP were confined to the diagnostic directory.

## Checkpoint and next action

Finish the physical endpoint/inherited child context and root/handle services, compose the aggregate/descendant Job budget and strict native cleanup/probe providers, then rerun source completeness and offline validation. Only after all source connections pass should an exact executable native proposal be prepared and separately authorized. Do not start AIP-07 or retry V6.

No installed release, selection, support receipt/ACK/journal, desktop shortcut, Windows Time/network configuration, provider, operational account or Genesis state was modified. Historical UNSELECTED revision 6 was not reread or changed. B1/C1/D1/E1, all 21 commissioning decisions, USD/USDC separation, original strategy/funding/maker semantics, the 45-second browser requirement, three-reader agreement and eight-second Stop remain unchanged. **PAPER: NO. Production: NO-GO.**
