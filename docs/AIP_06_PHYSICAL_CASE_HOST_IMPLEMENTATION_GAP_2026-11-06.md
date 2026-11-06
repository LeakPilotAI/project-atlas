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

The next missing integration is **owner-to-child handoff delivery**. `CaseContext.physical_host_handoff` produces a data-only packet; `inspect_launch_intent` returns it to the owner; `aip06_case_host_entry.inspect_inherited_handoff` awaits an authenticated `ChildServices.read_input` INPUT frame. There is no reviewed owner-side case-host sender in this path connecting those ends. The original `ChildRuntime.run` executes the pinned entry after guarded RELEASE, but the entry has no qualifying handoff unless the original owner delivers it on that child's private channel. Do not substitute environment variables, stdout, a second process, or a synthetic frame.

## Next engineering slice

Implement a bounded, once-only **original-owner case-host INPUT delivery** on the retained authenticated session channel, after exact BIND/RELEASE, using the original reservation and nonce. Prove the sender cannot race Stop, send to a foreign child, replay a packet, or exceed the channel's byte/deadline limits. Test via injected original transport first; retain the unconditional host refusal and production NO-GO. Physical reader, independent Stop/cleanup evidence, and native authorization remain separate later gates.

Roadmap: 5/18 (27.8%); daily PAPER BLOCKED; production NO-GO. Project Genesis out of scope.
