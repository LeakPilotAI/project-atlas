# Descendant ownership closure — November 5, 2026

**DESCENDANT OWNERSHIP SOURCE SLICE COMPLETE — NATIVE ACCEPTANCE PENDING.** Base `27d16d819e2d052b22875ed8647d1afb2d7dfcf2`. This supersedes the three pending descendant interfaces in the previous checkpoint below; it does not complete all AIP-06 source work or native acceptance. AIP-06 remains BLOCKED, completion 5/18, PAPER NO, production NO-GO.

## First-transfer admission

`Channel.receive` and the concrete pipe endpoints now separate original-peer identity capture from effect admission. Capture reads only the existing bounded/versioned private frame; it is not a Job-roster PASS. The first suspended-transfer frame must correlate with its precreation declaration, launch slot, complete prospective native manifest and exact original peer. Broker records INTENT before native duplication. Existing suspension fencing, image hash/native file identity, parent/child creation identity, leaf/ancestor/root Job membership and aggregate accounting must pass before RESULT/receipt. Any malformed/missing receipt latches the child; a failed staging/manifest transaction also poisons the parent graph. Ordinary requests cannot bypass full ownership admission.

The concrete session declares exactly one Job, one parent handle, one image, one thread and eight pipe handles, in addition to its reserved launch slot. Each parent duplicate is charged before duplication. Creator manifest handles are retained and matched to the independently staged original objects. No unknown PID is provisionally subtracted from a raw Job roster.

## Recursive roster and one ledger

The shared `AggregateJobBudget` holds per-original-birth descendant registries. `SuspendedDescendantGraph.rows` follows retained parent/launch edges recursively, reobserves each current native/CIM identity and checks every COMPLETE raw subtree Job. `RetainedLaunchBinding.verify` can use this retained graph; without it the old leaf-only refusal remains. `WorkerOwnership` refreshes the root receipt and verifies the complete union against its independent native Job query.

An intermediate process registers the exact original child channel before BIND, then forwards only that channel's ordered/revision-bound operations to the single root ledger. Registration binds nonce, full image/command/creation/ancestry identity and the original transferred Job handle; a guessed PID or matching executable name cannot register a child. The root retains the native handles, journals forwarded intents/results and verifies the graph before effects and receipts. Nested cursor heads advance to the actual returned snapshot cut, avoiding an extra intermediary ledger read or second writer. Correlated, timestamped root graph receipts supplement the inherited child's own native identity and raw Job observation; missing, stale, wrong-origin or conflicting proofs refuse. No PID-only adoption or independent intermediate authority was added.

## Final release

Release first proves the original normal exit, thread/Job drain and aggregate exit. Forwarded peer handle/deferred reservations are independently disposed while the original peer duplicates are still valid. Parent duplicates then close and release their own charges. The creator closes its original handles; each registered session handle is checked via duplication from the exact retained creator, accepting only ERROR_INVALID_HANDLE as closure and refusing live/reused integers or unknown probe results. Finalization requires all promised creator keys and every child-owned resource closed before the original process slot is closed. Aggregate usage is reconciled. Repeated confirmed finalization is idempotent; partial cleanup, an unknown outcome or a missing resource never receives credit.

## Offline evidence

- Final focused: **31 passed, 0 failed/errors/skipped**, 61.26 seconds, `logs/diagnostics/aip06-closure-focused-final.xml`. These cases are all included in the final broader selection.
- Final relevant synchronous regressions: **703 distinct passed, 0 assertion failures/errors/skips in the two completed runs, 5 deliberately deselected**, 14 modules (all ten AIP-06 modules, launch ownership, native budget, PAPER epoch and Quality Dips autonomous model), 0 warnings. This is **not one combined passing suite**: 669 passes in `core13.xml` plus 34 disjoint passes in `source-isolated.xml`. The focused cases are a subset; no overlaps or partial-run counts are added. Evidence/commands/source hashes: `logs/diagnostics/aip06-descendant-closure-20261105/`. No Node run: no Node/JS implementation changed.
- New cases: 26 descendant closure tests plus one child-bootstrap missing-identity refusal. Original forwarding tests and leaf-only negative checks remain. Tests exercise real Channel framing and Broker/RemoteResources through injected native responses, including a two-generation recursive path and reverse-order recursive release, not a second simulated implementation.
- Negative coverage: missing/changed first-transfer receipt, absent predeclaration, wrong ancestry/birth, missing Job membership, incomplete manifest, stale/missing-parent/duplicate graph evidence, unregistered/replayed/wrong-Job channel, running child, creator-handle leak, ledger/child-resource leak, interrupted duplicate closure, wrong release owner, and repeated finalization.
- Historical failures retained: first exploratory 5-failure run; early new-test fixture mismatches; wider focused 404 passes/3 failures (factory fixture omitted inherited identity), then 53 passes/3 failures (missing `body` import), all corrected and superseded by final validation. No late result is relabeled as native acceptance.
- Full 73-module run: **BLOCKED, not PASS**. File-list collection stalled; a diagnostic stack showed pytest conftest metadata lookup, and its interruption reported an interpreter access violation. A public-hook runner traversed the directory once, verified all 73 modules and collected 1,804 eligible IDs with the five launch exclusions. A later timed execution stack identified Windows asyncio blocked in `socket.accept` / `_fallback_socketpair` / `ProactorEventLoop._make_self_pipe`, inside pytest-asyncio setup before an async test body. The partial alphabetical and retained-order runs and diagnostic stacks are preserved. No shared cause, Windows OS defect or verified networking correction is claimed. No networking, event-loop implementation, dependency or acceptance contract was changed. Final broader validation is explicitly restricted to the 14 synchronous affected modules, with all **666** prior distinct identities in that scope compared and preserved. Tests outside that scope remain unverified on this final source; partial counts are not added to the final totals.
- Combined 14-module attempt: **FAILED, not PASS**, process exit -1073741819 (access violation) during `test_parent_only_releases_bootstrap_reservations_after_original_exit_or_no_creation`, with stack frames in the fixture audit/deepcopy path. Its timed traceback hook was active. The cause is unresolved; no claim that the hook, Atlas, CPython or Windows alone caused the fault. Preserve `broader-core-process-fault.txt`. The source-closure module and other 13 synchronous modules were then run separately with ordinary pytest diagnostics and unchanged assertions/fixtures/source. Their completed results are reported independently above and do not retroactively accept the failed combined session. Combined-run and async environment qualification remain blockers before any larger acceptance claim.

## Boundaries and exact next prerequisite

No native acceptance or financial worker, installed application, selection, provider/account, Discord, PAPER/live operation, Windows configuration or Genesis change occurred. Financial fixture process/Job/object responses were injected; the separate test-runner asyncio socket-pair setup was the environmental blocker described above. No actual eight-second Stop timing, capacity, native IPC or full inherited-path acceptance is claimed. Existing thresholds, Stop and browser deadlines, B1/C1/D1/E1 and all 21 decisions remain unchanged. The five financial-child launch cases were excluded by the retained exact selection expression. The unrelated research-test edit remains byte-identical and is excluded from staging; private evidence and backups remain.

Next, in a separate source-only scope: resolve combined/async test-runner qualification, supervisor/unexpected-child probe wiring and full inherited-path qualification. Neither probe implementation nor full inherited qualification was started here. Native acceptance remains a later independently authorized gate; current installed/provider/research/clock/financial custody and V6 browser/listener blockers are not cleared. Stop after this descendant slice and verified Git checkpoint.

Commit/push is verified separately after documentation checkpointing; this report does not assert an unverified SHA.

---

# Current ownership-forwarding checkpoint — November 5, 2026

**SOURCE INTEGRATION BLOCKED — validated partial source checkpoint.** Base `652cc467ce00503e6e62e64e5c4740592d367fac`. Existing edits and earlier recovery history below preserved.

Implemented: persistent receipt-failure latching under the RPC lock; typed stage/bootstrap-release/release/global-graph RPC routes; parent retained-registry delegation; concrete `DescendantGateway` constructed for actual child RemoteResources; guarded session hooks before creation, after Job assignment, before bootstrap resume and before release. Explicit native-object backends now construct the existing parent descendant registry. Registered staged nodes use complete raw parent/leaf Job checks and aggregate native verification rather than PID filtering.

Validation: first focused selection 115 passes; final affected-interface selection 211 passes; 9 overlapping cases; **317 distinct passes**, zero failures/skips. New forwarding module has ten cases. Tests cover changed receipts and uncertainty latch, stale retained identity, missing registry, failed release, gateway ordering/replay and existing staging/bootstrap/physical-provider/session protections. Raw XML/text: `logs/diagnostics/aip06-forwarding-focused.*` and `logs/diagnostics/aip06-forwarding-final.*`. Ruff F checks pass without cache. No full broader, Node, probe or inherited full-path validation run. The five native-launch cases were not selected. Injected source tests establish contracts only; no native processes or financial workers were launched.

Exact pending implementation:
1. `WindowsChildEndpoints.channel.verify` and `InheritedIdentity.verify` still require an exact leaf roster before the FIRST staged-transfer frame. The new RPC cannot cross that physical boundary once the created child appears in its inherited parent Job. No provisional unknown member was accepted to bypass it.
2. `WorkerOwnership` global bind/verify and recursive descendant forwarding still need the complete retained graph integrated. The new graph RPC verifies already registered nodes, not an otherwise unowned process.
3. `RemoteResources.close` / `Broker._operation` still reject closing a descendant-owned process slot from its creator. Release forwarding proves parent duplicate closure only; creator-handle and process-slot ledger reconciliation still require an independently verified final-release transaction. No reservation is silently refunded.

Supervisor/unexpected probes and full inherited qualification were deliberately not started under this narrowed directive. Native acceptance remains unexecuted. AIP-06 BLOCKED;5/18;PAPER NO;production NO-GO. B1/C1/D1/E1 and21 decisions unchanged. No provider/account/Discord/installed/Windows/Genesis actions. Unrelated research edit retained at SHA256 `4836c60e65a9b48b36e08b3df824e4bdf0dde7e0667ffd835a742ca43b602ffb` and excluded from staging.

Commit/push verification is recorded by the execution result after checkpointing; no unverified remote success is asserted in this document.

---

# AIP-06 ownership graph and probe closure — interrupted recovery

Starting and verified HEAD: `652cc467ce00503e6e62e64e5c4740592d367fac`.
Branch: `chatgpt/atlas-rebuild-v1`.

**SOURCE INTEGRATION BLOCKED — implementation not started in this execution.**

Recovered the canonical roadmap/recovery state, integrated audit, previous physical-path report and current source references. Execution response budget ended after recovery. This is an interruption note, not an implementation or validation milestone.

Exact remaining interfaces:
- `aip06_child_entry.ChildServices.descendant_gateway` remains `None`.
- `aip06_ipc.Broker` / `RemoteResources` lack precreation declaration, suspended original-handle transfer and bootstrap-release forwarding.
- Endpoint/inherited-identity/global ownership readers still require their original leaf rosters; full forwarded recursive graph is not connected.
- `aip06_legacy_probe.CASES` supports only `direct-worker`; supervisor formal-role and unexpected-child paths remain unsupported.
- Complete inherited physical-path qualification remains unproved.

No source files changed, tests run, commit or push occurred in this execution. Prior results remain historical: 1,765 broader and 529 focused passes with overlap; 1,767 distinct cases; five native-launch cases deselected. They are not new test results.

The unrelated tracked edit `tests/test_free_research_pipeline.py` remains present. Private evidence and historical authorizations were preserved. Canonical roadmap/recovery files remain at their verified checkpoint; this note was left uncommitted for continuity.

Resume at the concrete descendant IPC/gateway implementation using existing suspended registry primitives. Do not repeat completed query/staging work or treat this recovery as closure. No native/installed/provider/financial/PAPER execution occurred. AIP-06 BLOCKED; 5/18; PAPER NO; production NO-GO. B1/C1/D1/E1 and all 21 decisions unchanged.

## Continuation implementation checkpoint

HEAD remains `652cc467ce00503e6e62e64e5c4740592d367fac`; branch verified. Implemented precreation declaration forwarding in `RemoteResources.declare_descendant`, `Broker._operation` and `RetainedPeerHandles.declare_descendant`. The parent reconstructs and validates the exact LaunchRequest and delegates to the existing retained descendant registry. Declaration receipts explicitly confer no financial ACK.

Focused validation: `tests/test_aip06_descendant_forwarding.py`: 2 passed, 0 failed/skipped (1.23 seconds), offline only. Broader regressions and adversarial validation of the new parent decoder remain pending. The conflicting-receipt case verifies rejection; it does not yet prove a persistent uncertainty latch after the RPC completes.

Execution response limit interrupted implementation. Source edits and new tests are preserved uncommitted. No commit/push or canonical-state promotion is claimed. Pending: complete receipt-failure latching, suspended-transfer/bootstrap-release forwarding, concrete ChildServices gateway, full global graph verification, remaining probes and inherited integration tests. No native workers or operational actions occurred. Overall source integration remains BLOCKED;5/18;PAPER NO;production NO-GO.
