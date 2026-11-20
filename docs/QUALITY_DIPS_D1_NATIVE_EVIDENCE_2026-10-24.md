# Quality Dips D1 — disposable native Windows evidence

Base `0a8ebd71a1292f33b0cc7e022f51f06ec96bcb0a`; branch `chatgpt/atlas-rebuild-v1`.
Authorization: explicit **P-D1-DISPOSABLE-NATIVE**. **B1/C1/D1/E1 BLOCKED; all 21 decisions unchanged; PAPER startup NO; production NO-GO.**

## Scope and confinement

One exclusive run directory was created under the authorized `logs/diagnostics/qd-d1-native-acceptance-<unique-run>` prefix. Its exact path, native identities, Windows/Python versions, source hashes, helper commands/creation times, per-case outcomes, API return codes, originals and cleanup evidence remain private locally. No raw native evidence, machine/account identity, security descriptor, generated database or test log is included in Git. The operator receives the exact local location separately.

`scripts/volume_inspector/native_acceptance_runner.py` requires that explicit pre-created root, validates the fixed parent/prefix, rejects traversal/reparse ancestors, pins the root identity and refuses replacement, reused attempt directories and unexpected marker links. Each attempt has new confined pytest temporary storage; TEMP/TMP/TMPDIR point inside it, bytecode generation and pytest cache/autoload are disabled. There is no default production destination or application entry import. The native primitives open their own disposable protected roots through verified ancestor handles. Test source/remediation and the mandatory roadmap/publication files are repository changes expressly permitted by the directive; all generated test resources are inside the single run root.

Reviewed test code imports the existing snapshot/native modules and selected earlier native test functions; it does not launch an arbitrary related suite. A pure fixture SQLite writer-control module is loaded only for the expressly requested admission-closure interruption cases; no operational financial services, callbacks or original records are initialized. All values are generated synthetic data. No provider/network access, service startup, Genesis access, production financial record, protected provisioning, account creation, privilege grant, registry/key/TPM change or parent-directory ACL mutation occurred. Git publication is a separate expressly authorized action.

Helpers were only fixed harness-created junction commands and reviewed Python children that call `os._exit(24)` at specified publication boundaries. Exact retained child handles supplied PID/creation-time observations. There was no live process census, C1 ownership claim or unrelated process action. Helpers either completed their command or self-exited; none was force-killed. A timeout path records UNKNOWN and does not kill. Final selection used four helper executions; fourteen across overlapping iterations, all recorded EXITED. Artifacts, including attack junctions/hard links, remain retained inside the run; there was no destructive cleanup.

## Final exact results

| Measure | Result |
|---|---|
| Final collected Windows-harness cases | 46 |
| Executed and passed | **45** |
| Failed assertions | **0** |
| Harness cases BLOCKED | **0** |
| NOT EXECUTED / pytest skipped | **1** — native true-symlink creation privilege unavailable, Windows error1314; no elevation or waiver |
| Duration | 2.01s |
| Targeted Ruff / in-memory compilation / CRLF-aware diff | PASS |
| Unresolved recorded helpers | 0 |

This is a Windows-specific selection mixing real native enforcement, actual SQLite behavior and explicitly injected/synthetic publication failures. It is **not** 45 independently accepted security guarantees. Attack-reproduction cases PASS when the unsafe path is demonstrated; the affected design remains BLOCKED. Original/earlier overlapping runs are not added to the final count. Prior Q9 224 tests were not rerun or added. No protected runtime, browser, provider or power-loss acceptance is claimed.

## Observed findings and their meaning

| Surface / experiment | Actual result | Evidence class / limit |
|---|---|---|
| Valid native file/root identity and restart | Expected committed revision read; durable startup reservation prevents conflicting inspection/replay | Native handle-bound control-state primitive, not a trusted runtime issuer |
| Replaced snapshot/commit, identity mismatch, corruption/incomplete bytes | Refusal before substitute payload ReadFile/JSON trust; no new startup intent | Native file identity/link checks plus application digest/lineage validation |
| Hard links and relative traversal | Unexpected snapshot or pinned probe links refused before payload read; traversal rejected | Native link count and application component validation; sidecar hard-link probes are generated namespace records, not a SQLite VFS |
| Root mismatch / directory rename | Wrong pinned root refused; held-directory rename denied by OS5/32 | Retained ancestor/root handles; does not exclude privileged actors |
| Junction substitution | Handle-bound snapshot read refused; separately, raw path-based SQLite followed a substituted parent junction and read the alternate generated database | Native safe-reader rejection AND positive reproduction of unsafe path-based access; both targets stayed inside the run |
| Concurrent write/delete while trusted read handle active | Write and rename denied with Windows32 | Actual OS sharing enforcement during that handle lifetime, not permanent directory-wide writer exclusion |
| Owner/protected ACL | Reviewed native create/read succeeds with exact owner/SYSTEM protected DACL; inherited or changed/unprotected file DACL rejected | Actual native ACL validation. ACL change test removed protection only on a test file; it did not grant broad access |
| Restricted token | Snapshot/witness read/write denied5; snapshot deletion and new journal/WAL/SHM creation denied5 | Real temporary restricted token, restored in finally; no account or privilege provisioning |
| Actual SQLite DELETE and WAL surfaces | Main/rollback-journal and main/WAL/SHM created and observed; every tested SQLite-created file failed the exact protected-DACL policy because of inherited/unprotected descriptors | Parent protection is not proof that each file/sidecar satisfies the accepted descriptor contract. No ACL was silently repaired to obtain PASS |
| Active SQLite writers/sidecars | Concurrent INSERT refused by SQLite transaction locking; active journal/WAL/SHM rename denied5/32 | Locks while active, not identity continuity before open or after close |
| Main checked then replaced before SQLite open | Alternate generated database payload read successfully | **Path-based identity-before-access guarantee NOT established**; expected unsafe-design reproduction |
| Journal/WAL/SHM replaced after main identity | Sidecar file identities changed independently; same main identity does not bind them | Controlled generated sidecar namespace probe, not proof that SQLite safely consumes substituted sidecars |
| Before/after durable intent, commit before caller acknowledgement | Failed publication now poisons the object; retained intent/stale pin or durable failure marker refuses restart | Native files plus application state protocol; unavailable storage cannot promise a newly durable failure marker |
| Actual child exit after intent and after commit | Child exits24; parent sees abandoned/unresolved publication and persistent recovery refusal | Real subprocess termination with committed storage evidence, **not power loss** |
| Projection/report staging interruption | Pending metadata retained; no readable published commitment | Injected failure using actual protected metadata publisher; not native financial projection/report runtime integration |
| Admission closure before/after commit | Disposable SQLite closure rolls back or commits as appropriate; pending operation remains and restarted close returns INCOMPLETE/no authority | Existing fixture control contract, not C1 actual writer or protected financial storage acceptance |
| UNKNOWN inspection / stale revision | Startup remains refused; absent recovery authority cannot clear uncertainty | Synthetic helper identity, real native control storage; no real Docker proof |

### SQLite decision

**Do not promote path-based fixture SQLite to trusted operational storage.** Main-file inspection, directory protection and active SQLite locking do not demonstrate complete main/journal/WAL/SHM identity-before-access. The experiments confirm the previously documented VFS/sidecar boundary; they do not authorize a replacement VFS or storage engine. F's handle-bound immutable snapshots remain a tested *control-state* candidate, not an automatically suitable financial ledger. The independent reviewer must select/accept the minimum financial persistence contract before implementation/provisioning. No original financial store was read.

## Demonstrated source defect and bounded repair

The first new before-intent fault test failed: `SnapshotStore._transition` propagated a witness intent-write error but left the in-memory store usable. A failed storage operation could therefore be followed by reuse without an explicit failure latch. This is a reusable isolated control-storage defect, not protected runtime behavior.

`scripts/volume_inspector/snapshot_store.py` now catches publication failure, poisons that object and attempts an exclusive persistent `recovery-required.json` marker while preserving the original error. A targeted regression proves restart refusal when the failure marker is writable. The existing pre-intent failure assertion was retained and now passes. If storage cannot write any failure evidence, only in-memory refusal is established; independent caller/operator failure evidence and trusted admission remain required. No marker auto-clear/reset/recovery API or successful production admission was added.

The initial full attempt was **22 passed,7 failed,1 skipped** and is retained privately. One failure exposed the latch defect. Six were harness setup errors: three supplied invalid metadata before reaching the planned publication fault; two tried a read-sharing lease against SQLite's active write handle; one left a context-managed SQLite connection open (transaction context does not close the connection). Corrections supply valid narrow metadata, use explicitly observation-only share-compatible handles, and close fixture connections. These fixes do not weaken trusted-reader identity/ACL assertions or remove evidence. Final 45/0/1 is authoritative; all earlier overlap retained, not summed.

Files changed: new confined runner, new focused test module, minimal snapshot publication latch, sanitized report and mandatory roadmap/state/queue/coverage evidence. Existing native ACL/read primitives, startup locks, operational financial dispatch, deadlines and governance decisions remain unchanged. No second security framework or operational authority was created.

## Independent reviewer questions and next boundary

1. Accept or reject the measured native control-state identity/DACL/sharing/interruption evidence **within the selected trusted-workstation Phase 1 threat model**. Same-owner compromise, administrators and coherent full-machine rollback are not excluded.
2. Review the publication-failure latch and original preserved failure. Is its memory/durable-evidence distinction adequate for the intended accepted caller, including unavailable storage?
3. Confirm path-based SQLite financial storage remains unaccepted; specify the narrow approved financial identity/sidecar/publication contract and exact next development scope. No extensive VFS/replacement-engine approval is inferred.
4. Disposition the missing true-symlink capability without granting privileges or calling the absent test PASS. Native junction/hard-link results do not silently waive it.
5. Identify issuer/operator enrollment, trusted clock/current pin/known-rollback handling and explicit UNKNOWN recovery evidence still required. This run creates no operational issuer or acceptance signature.

**Exact continuation:** BLOCKED_WAIT after all authorized confined tests/remediation. Submit this sanitized package and locally retained native evidence to the designated independent storage/security reviewer. Obtain the accepted financial-storage contract/next file-level scope before operational provisioning or financial dispatch. No additional broad C1 process census, E1 provider/backup test, private evidence access or startup permission is requested or implied. B1/C1/D1/E1 and all 21 decisions remain unchanged. All seven phases and multi-strategy separation are retained.


Approved roadmap checkpoint verification: backup byte equality,exact managed-section read-back and historical outside-section equality against pre-update/base all PASS. Canonical21decisions/startup-lock hashes unchanged. Exact backup/roadmap verification details remain in the private run evidence.
