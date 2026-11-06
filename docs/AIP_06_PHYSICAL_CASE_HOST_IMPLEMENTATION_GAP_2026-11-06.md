# AIP-06 independent case-host: verified integration gap (2026-11-06)

Status: **BLOCKED / NO NATIVE ACCEPTANCE**. This is an implementation audit, not permission to launch. All B1/C1/D1/E1 approvals, 21 decisions, original owner, Job, Stop, and source pins remain in force. No production or financial execution.

## Code-path findings

1. `aip06_case_host_entry.py` is a guarded target, not a launcher. It reads `ChildServices.read_input` after inherited bootstrap and always refuses native case execution. Its preflight reports `execution_authorized=False`.
2. `aip06_child_entry.py:435-512` owns inherited `ChildRuntime.run`: `InheritedChannel.open`, pinned-source checks, `ChildBootstrap.prepare`, original `RELEASE`, guard installation, then target execution. `main` requires six distinct inherited handles and a 32-character session nonce. Do not substitute `subprocess.run`.
3. `aip06_child_bootstrap.py:149-280` verifies all pinned sources before HELLO/BIND and the RELEASE receipt before guarded execution. Existing injected tests do not prove a separate physical case host.
4. `aip06_windows_process.py:313` provides original suspended creation with explicit inherited-handle list and restoration readback. Its failure retains original created handles for bounded abort. It does not independently authorize a case-host launch.
5. `aip06_native_controller.py` has original owner lifecycle and native ownership probes, but no reviewed case-host-specific binding that combines original reservation, separate process identity, original Job membership, authenticated handoff and independent reader evidence.
6. `aip06_scoped_context.py` provides reservation and handoff data verification. The packet's digest is not independent attestation. `CaseContext.require_execution` always refuses; `aip06_host_preflight.require_execution` also always refuses.
7. `aip06_native_scenario_bindings.py` refuses reviewed source-case execution in-process. Missing fault producers and physical reader cannot be inferred from the existing tests.

## Required assembly order (no unqualified native experiment)

1. **Owner-bound launch intent:** tie exact `HOST_ENTRY` command, pinned source bytes, one case reservation, original parent, Job, stop escrow, six inherited handles, and one-shot nonce to an original native controller-owned launch transaction. Reject if any capacity/ACL/identity prerequisite is absent.
2. **Suspended child and failure escrow:** use the original `Win32ProcessCalls.create_suspended` and retained original process/thread/Job handles. Confirm assignment to the original Job before resume, then independently read process image, creation time, ancestry, token and membership. Any failure must abort using retained handles, not reopen by PID.
3. **Authenticated private input:** send the reserved handoff on the original bounded session channel only after BIND/ACK/RELEASE, with one receive owner, exact sequence, deadline and no competing Stop receiver. Verify the receiving child and original reservation ledger in its own guard.
4. **Independent reader:** create an independently guarded reader host with original native read handles and source pins, complete descendant roster, ledger reconciliation and ACL/query-charge evidence. A same-process injected provider is not sufficient.
5. **Stop and cleanup:** test original owner-held Job termination, escrowed Stop, timeout, unknown child refusal, closed original handles, no leftover descendant, bounded cleanup and durable evidence on Windows under an explicitly authorized native acceptance session.
6. **Admission:** only after independent native evidence is reviewed, define a narrowly scoped, once-only host execution gate. Never modify the unconditional `require_execution` refusal based solely on a packet, test, or self-attested flag.

## Current integration checkpoint (2026-11-06)

The owner-side launch-intent validator, original guarded case-host plan, suspended Job/observer checks, original session registration, and exact target-release checks now exist and have injected regression coverage (latest nine-suite run: 340 passed). They are **not** a physical acceptance result. The entry additionally checks closed native source receipts for itself and preflight.

The owner-to-child data-only handoff path is now implemented: `CaseContext.deliver_physical_host_handoff` checks the retained pinned launch intent and original guarded process, `GuardedProcess.send_case_host_handoff` delegates to the original `WindowsSessionPort.deliver_case_host_input`, and `ChannelSessionProtocol.send_case_host_input` sends once on the original authenticated INPUT channel after guarded RELEASE. Both context and port now require exact retained child object identity, not equal-value copies. The child entry still reads through `ChildServices.read_input` and unconditionally refuses native execution. Offline adversarial tests cover replay, owner/nonce/Stop reservation checks, transport errors, retained-handle abort, identity drift, incomplete Job termination, and unverifiable handle/channel closure. These are injected tests, **not independent native evidence**. Do not substitute environment variables, stdout, a second process, or a synthetic frame.

## Verified regression checkpoint (2026-11-06)

The broad offline/injected AIP-06 suite completed successfully: **1,191 passed, 0 failed, exit code 0**, in **573.41 seconds (9m33s)**. This run preceded the dedicated reader identity-spoof test added in commit `63b430f4`; that new test and its companion focused identity/context tests separately passed **10/10**. The separately launched joined-lifecycle regression also completed **5 passed, 0 failed, exit code 0** in **425.74 seconds (7m05s)**, including the intentional account-scope refusal and bounded cleanup tests. Later focused case-host INPUT checks passed **46/46** (commit `d08efddc`), and malformed UTF-8 refusal checks passed **45/45** (commit `aa557c7b`); the 1,191-test full run predates these additions. These are source-level regressions only, **not physical Windows native acceptance**, and do not satisfy the B1/C1/D1/E1 or 21-decision gates.

## Next engineering slice

The broad AIP-06 regression is verified GREEN. Next, verify **independent child-side reservation and authenticated INPUT receipt**, complete original-owner Stop/cleanup and descendant evidence, and implement the independently guarded native reader behind existing approval gates. Current sender, replay, timeout, and retained-handle cleanup checks are injected source-level evidence only; they do not qualify physical acceptance. Keep the unconditional host execution refusal and production NO-GO until separately authorized native acceptance evidence is reviewed.

Roadmap: 5/18 (27.8%); daily PAPER BLOCKED; production NO-GO. Project Genesis out of scope.

## Updated regression checkpoint (2026-11-06, post-219bb68c)

The clean AIP-06 pytest selection excluding `test_aip06_joined_lifecycle.py` completed with **1,244 passed, 0 failed, exit code 0**, in **157.51 seconds**. This run includes the strict final-process evidence freshness regression (commit `536321d9`) and corrected injected post-wait process-exit fixture (commit `219bb68c`). The earlier pre-fix run reported three fixture failures and was superseded; those cases separately passed in the corrected targeted run (**8 passed** including post-wait verification). The separately launched joined-lifecycle suite is still pending at this checkpoint; do not claim a new full combined GREEN result until it finishes. All of these tests are injected/offline evidence, not native Windows acceptance. B1/C1/D1/E1, all 21 safety decisions, daily PAPER BLOCKED, and production NO-GO remain unchanged. Genesis untouched.

## Latest independent regression checkpoint (2026-11-06)

The separately executed joined-lifecycle suite completed **5 passed, 0 failed**, exit code 0, in **379.49 seconds (6m19s)**. The current independent-reader/abort focused regression completed **102 passed, 0 failed** after commit `fab4793e`. The prior broad AIP-06 suite completed **1,244 passed, 0 failed**, before that reader-deadline change. These are offline/injected source regressions, not native Windows acceptance. AIP-06 remains incomplete; daily PAPER and production are not authorized. Preserve B1/C1/D1/E1 and all 21 safety decisions.

## Full regression checkpoint (2026-11-06; latest)

The complete 47-module offline/injected AIP-06 regression (excluding the separately tested joined-lifecycle module) completed with **1,264 passed, 0 failed, exit code 0**, in **163.22 seconds**. The separate joined-lifecycle module previously passed **5 tests** in 379.49 seconds.

This checkpoint includes retained native cleanup preflight checks and inherited independent-reader command/source-receipt validation. These are regression results only; **physical Windows native acceptance is unverified**, daily PAPER is incomplete, and production remains NO-GO. All existing approval gates and unconditional native execution refusals remain in place.

## Post-reader-role verification regression (2026-11-06)

The 47-module AIP-06 offline/injected regression excluding the separately verified joined-lifecycle module completed **1,275 passed, 0 failed**, exit code 0, in **117.65 seconds** after commits `4d40df4e` and `1ad8b42b`. This verifies source-level reader digest and inherited role-target checks, not physical native acceptance. AIP-06 remains incomplete; B1/C1/D1/E1, all 21 decisions, daily PAPER BLOCKED and production NO-GO remain unchanged. Genesis untouched.

## Retained resource closure regression (2026-11-06)

The 47-module offline/injected AIP-06 regression (excluding separately verified joined-lifecycle) completed **1,281 passed, 0 failed**, exit code 0, in **124.74 seconds** following commit `82caee8a`. Original retained-session resource closure proof now requires the exact complete resource and process-slot key set; six new adversarial/success cases were added. This is not physical Windows native acceptance. AIP-06 remains incomplete, daily PAPER BLOCKED, production NO-GO; B1/C1/D1/E1 and all 21 decisions unchanged. Genesis untouched.

## Inherited case-host source digest regression (2026-11-06)

The 47-module offline/injected AIP-06 regression (excluding separately verified joined-lifecycle) completed **1,291 passed, 0 failed**, exit code 0, in **120.12 seconds** following commit `226b2cdc`. Ten additional adversarial cases verify malformed case-host and preflight source digests are rejected before source receipts or private input. This is not physical native Windows acceptance. AIP-06 remains incomplete; daily PAPER BLOCKED and production NO-GO. B1/C1/D1/E1 and all 21 decisions unchanged. Genesis untouched.

## Exact cleanup resource-set regression (2026-11-06)

The 47-module offline/injected AIP-06 regression excluding separately tested joined-lifecycle completed **1,293 passed, 0 failed**, exit code 0, in **122.46 seconds** after commit `47368631`. Two additional adversarial cases require exact retained native-resource and process-slot keys before cleanup side effects. Physical Windows native acceptance remains unverified. AIP-06 incomplete, daily PAPER BLOCKED, production NO-GO; B1/C1/D1/E1 and all 21 decisions unchanged. Genesis untouched.

## Original-session identity regression (2026-11-06)

The 47-module AIP-06 offline/injected regression excluding separately tested joined-lifecycle completed **1,300 passed, 0 failed**, exit code 0, in **132.84 seconds** after commits `3c0e888f`, `cea40850`, and `4fb0cfe0`. Suspended case-host argv validation is type-checked, and pre-resume retained-session membership uses object identity with an adversarial equal-but-unretained session regression. These checks do not constitute physical Windows native acceptance. AIP-06 incomplete, daily PAPER BLOCKED, production NO-GO; B1/C1/D1/E1 and all 21 decisions unchanged. Genesis untouched.

## Owner source-pin and typed pre-resume receipt regression (2026-11-06)

The 47-module offline/injected AIP-06 regression excluding the separately verified joined-lifecycle module completed **1,305 passed, 0 failed**, exit code 0, in **132.50 seconds** after commits `b36417e1` and `300b0a74`. Five additional adversarial tests reject malformed original owner case-host source digests and missing/malformed pre-resume session/Job receipts. These are source-level regressions, **not independent physical Windows native acceptance**. AIP-06 incomplete, daily PAPER BLOCKED, production NO-GO; B1/C1/D1/E1 and all 21 safety decisions unchanged. Genesis untouched.

## Post-release original session identity regression (2026-11-06)

The 47-module offline/injected AIP-06 suite, excluding the separately verified joined-lifecycle module, completed **1,313 passed, 0 failed**, exit code 0, in **130.25 seconds**, following commits `5a79c802`, `ad1bacb1`, and `3d7f3715`. Eight additional adversarial cases cover guarded handoff argument typing, exact retained host identity at release, and post-release original session identity/state. These are source-level tests, **not independent native Windows acceptance**. Roadmap remains 5/18; daily PAPER BLOCKED; production NO-GO; B1/C1/D1/E1 and all 21 decisions unchanged. Genesis untouched.

## Missing case-host orchestration call site (2026-11-06)

Static call-site audit across `scripts/**/*.py` finds **no caller** of `CaseContext.deliver_physical_host_handoff` beyond its definition. `CaseContext.admit` invokes `inspect_launch_intent` during guarded spawn preallocation, and `FixtureGuard.spawn` verifies suspended creation, Job membership, binding and release, but neither currently sequences the original guarded case-host spawn with `deliver_physical_host_handoff` and the independent reader and Stop evidence. These are independently tested building blocks, **not a complete physical workflow**.

Next implementation slice: define one owner-scoped, once-only case-host coordinator that (1) consumes the existing original held case reservation and exact pinned HOST_ENTRY command, (2) obtains the original GuardedProcess via the existing guarded spawn path, (3) invokes `case.deliver_physical_host_handoff` only after guarded release, (4) retains original process/Job and Stop ownership for bounded abort/cleanup, and (5) records independent native reader and descendant evidence. Do not invoke it or lift unconditional execution refusal until B1/C1/D1/E1 and explicit native acceptance authorization are satisfied. Add integration tests for ordering, failure/cleanup and one-shot semantics; no synthetic native acceptance claims.

The 1,313-test broad regression is GREEN, but milestone status remains 5/18 (27.8%), daily PAPER BLOCKED and production NO-GO. Genesis untouched.

## Coordinator integration checkpoint (2026-11-06, after e7fc33e5)

`aip06_case_host_coordinator.py` now provides once-only original reservation preparation, retained guarded host binding, original private INPUT delegation, bounded original-native-owner abort, native closure observation, complete guarded-wrapper cleanup verification, and original `ReaderContext` evidence attachment/reverification. It retains the original native child/resource key identity and reader/session/child/result digest. A caller cannot mutate its retained launch intent through the returned preparation object. Adversarial offline tests cover replay, abort-then-INPUT refusal, native-vs-wrapper closure distinction, and substituted reader result/session/child.

**Still missing:** a reviewed native controller call site that actually assembles this coordinator with the original guarded spawn, authenticated host INPUT, independently spawned reader and descendant roster; bounded native Stop escrow and durable independent Windows evidence; successful physical acceptance. The existing coordinator `execute()` and case-host entry remain unconditionally disabled. An offline fake-port abort test is not proof of Windows Job termination. The original guarded wrapper may remain open after native abort, and complete case cleanup must not be inferred from native resource closure alone.

**Engineering priority:** implement an owner-scoped end-to-end orchestrator with independently verifiable native descendant/Stop receipts, only behind the existing explicit authorization gates; add successful original-reader integration and physical cleanup evidence tests. No independent process/PID adoption, automatic startup, live orders, or Genesis changes. Roadmap 5/18; daily PAPER BLOCKED; production NO-GO; B1/C1/D1/E1 and all 21 decisions unchanged.

## Broad coordinator regression checkpoint (2026-11-06)

The current AIP-06 offline/injected pytest selection, excluding the independently verified joined-lifecycle module, completed **1,331 passed, 0 failed, exit code 0, 128.81 seconds** after coordinator integration and adversarial reader/abort lifecycle tests. The joined-lifecycle module was not rerun in this checkpoint (previously 5 passed). These results are not physical native Windows acceptance. No changes to B1/C1/D1/E1, 21 decisions, daily PAPER BLOCKED, production NO-GO or Genesis isolation.

## Post-cleanup-scope hardening regression (2026-11-06)

After commit `048bfbed`, the 47-module AIP-06 offline/injected selection excluding the separately verified joined-lifecycle module completed **1,332 passed, 0 failed, exit code 0, 130.56 seconds**. The latest coordinator requires both original factory pending-case and native port scoped-case references to be exactly `None` before case-scope release verification succeeds; replacement objects are rejected. This is source-level/injected regression, not physical native Windows acceptance. Static search still finds no production `CaseHostCoordinator` construction call site. The descendant gateway exists and should be reused by a future authorized owner-scoped orchestrator. Roadmap 5/18, daily PAPER BLOCKED, production NO-GO; B1/C1/D1/E1 and all 21 decisions unchanged; Genesis untouched.

## Guarded wrapper and case-scope cleanup ownership audit (2026-11-06)

Reviewed `GuardedProcess.close()` and `CaseContext._close()/abort()`. The coordinator's `abort_original_host()` delegates to `port.abort(original_child)` and can prove native child resources closed, but that alone does **not** set `GuardedProcess.closed`; wrapper closure is owned by `GuardedProcess.close()`, which also validates the retained ownership binding and exit state. Separately, `CaseContext._close()` only releases the case scope after the complete ledger resource delta is already closed; `CaseContext.abort()` marks the case/factory failed and then calls that same strict cleanup. Therefore the coordinator must not infer wrapper closure or call case-scope release based only on native abort. A real orchestration design needs a reviewed original-owner terminal-state API that reconciles abort exit status, ownership-roster transition, exact Job/resource closure, wrapper closure, and then `CaseContext.abort/_close` in order. Do not mutate `GuardedProcess.closed` directly or add a PID-based fallback.

Static inspection confirms `FixtureGuard.spawn()` returns the retained `GuardedProcess`, `CaseFactory.reader()` creates the independent reader, and `CaseContext.deliver_physical_host_handoff()` is the guarded INPUT boundary. No production call site assembles these into the coordinator. No native Stop receipt API was found in the AIP-06 modules searched; existing Stop/escrow acceptance references are elsewhere and require an explicit reviewed adapter. This is a genuine integration blocker, not a reason to weaken current gates.

The 47-module offline/injected regression after `048bfbed` remains **1,332 passed, 0 failed**. No source changes made in this audit. Roadmap 5/18, daily PAPER BLOCKED, production NO-GO, B1/C1/D1/E1 and all 21 decisions unchanged; Genesis untouched.


## Post-coordinator full offline regression (2026-11-06)

The 47-module AIP-06 selection excluding `test_aip06_joined_lifecycle.py` completed **1,360 passed, 0 failed**, exit code **0**, in **147.59 seconds**. This includes the retained-original-host binding, once-only handoff, abort owner checks, native closure proof, independent ledger cleanup checks, and final case-release revalidation through commit `076ac1c3`. This is injected/offline regression evidence, **not physical Windows acceptance**. The joined-lifecycle module was excluded and is not represented by this result.

Remaining blocker: native abort closes native session handles but does not reconcile `GuardedProcess.closed`, the `WorkerOwnership` terminal binding, and the ledger. `RetainedLaunchBinding.verify_exit()` requires exact normal exit; arbitrary nonzero termination must not be admitted. A separate original-owner, independently observed abort terminal state is required before resource and case closure can be certified. B1/C1/D1/E1, all 21 decisions, daily PAPER BLOCKED, production NO-GO, and Genesis isolation remain unchanged. Roadmap 5/18 (27.8%).


## Independent joined-lifecycle regression (2026-11-06)

The previously excluded `tests/test_aip06_joined_lifecycle.py` completed **5 passed, 0 failed**, exit code **0**, in **322.37 seconds**. Together with the separately executed 47-module offline regression (1,360 passed), this is **1,365 passing cases across two independent invocations**; it is not a single unified run and does not constitute native physical Windows acceptance. The original-owner abort terminal-state reconciliation and physical case-host assembly remain unimplemented. No gate is lifted: roadmap 5/18; daily PAPER incomplete; production NO-GO; B1/C1/D1/E1 and 21 decisions preserved; Genesis untouched.
