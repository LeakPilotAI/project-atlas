# Native-copy acceptance closure — October 30, 2026

Base: 5da418094ea58544b2abcb03f539a468519135a0. Branch: chatgpt/atlas-rebuild-v1. **Source repairs and disposable validation complete. No new full native copy, operational installation, selection, provider, financial activation, Windows Time change or PAPER startup occurred.** Original native failures and the cache variance remain historical findings, not retroactively green acceptance.

## Corrections

**Refusal diagnostics.** scripts/install_verified_release.py now raises a typed InstalledReadbackRefusal with QD_CHILD_DIAGNOSTIC_V1: raw byte count/SHA-256, truncation flag, first/last 2,048 characters, child return code and stdout byte count. The terminal refusal is retained rather than lost after 250 characters. Failed, oversized and inconsistent readback still refuses. No verifier, identity, ACL, financial, clock or authority requirement changed. These are bounded exposed diagnostics, not a memory sandbox for arbitrary child output.

**Expected negative fixtures.** scripts/native_copy_test_scope.py and an opt-in pytest plugin declare the existing hardlink-negative fixture before execution. Create-only declarations bind the exact test owner, actual generated fixture directory/identity and two expected relative paths. Accounting requires the complete same-identity alias pair and matching link counts. Unknown owners, undeclared paths, substituted parents, malformed/duplicate records, links in candidate/interrupted namespaces, missing/outside aliases, contradictory identities and reparse points refuse. No bare path whitelist or post-hoc promotion is used. Local declarations are test bookkeeping, not independent financial custody.

Worker, progress budget, final accounting and supervisor share the declaration-aware accounting. Entries/bytes include both aliases; allocation is conservatively overcounted. Accounting refusal is recorded alongside the original failure instead of masking it or claiming success. Consumed native authorization explicitly refuses reexecution; worker deadlines must match the original authorization timestamp. No old target is reset, repaired or reused.

The physical copier and source-plan implementation remain byte-identical. No financial engine, codec, store, dashboard, startup lock, historical decision or strategy changed.

## Containment

New artifacts stayed under logs/diagnostics/qd-native-copy-closure-v1-* workspaces. TEMP, TMP, potential bytecode, Ruff and XDG cache paths point inside the workspace. Bytecode and pytest caches are disabled. Ruff uses --no-cache and RUFF_NO_CACHE=1, with explicit import classification so a temporary directory named pytest cannot change lint grouping. Existing repository caches were only snapshotted; none was deleted or repaired.

The Python test process audits ordinary writable opens, directory creation, deletion, rename, linking and related path mutations. A deliberate outside write was denied before creation. The final run recorded only that expected denial. Pipes and the exact Windows null device are distinguished from filesystem outputs, with no general device-prefix exemption. Newly created adversarial-unit aliases were removed only from their own test directories; original-session artifacts and unrelated files were not deleted.

This is Python-level instrumentation plus known-tool flags and snapshots, **not a system-wide filesystem monitor or sandbox against arbitrary native/subprocess code**. Ruff is additionally checked by unchanged repository-cache snapshots. No new ACL/owner modification, elevation, symlink privilege experiment or native financial publisher ran.

## Final validation

Final fixture: D:\Work\Project Atlas\logs\diagnostics\qd-native-copy-closure-v1-6be275cc068b.

- **223 passed, 0 failed, 0 skipped, 11.66 seconds.** Existing adapter/plan/archive/namespace/source/module/resource/clock-boundary coverage remains. Thirty new cases replace three earlier bare-whitelist cases: net increase 27 over the historical 196-case selection. Prior results are not added to this total.
- New cases cover bounded long/malformed stderr, actual readback error branches with mocked processes, dynamic registrations, outside/contradictory aliases, manifest/parent substitution, forbidden namespaces, cache environment, primary-error preservation, consumed-grant refusal, duplicate receipt refusal and SHA-bound ACK integrity.
- Shared copy algorithm tests use explicit **fake Windows I/O/ACL ports** and ordinary files: success, bad input hash, corrupt readback, interruption and uncertain-close refusal. These are source regressions, not new native ACL acceptance.
- A **genuine read-only Windows child** used the retained disposable candidate's Python through the repaired adapter. The original disposable receipt schema was preserved. The real installed verifier refused with PERSONAL_RELEASE_VERIFIED_INVENTORY_REQUIRED, now visible in the bounded diagnostic. No fixture was relabelled operational. Existing owned-child exit/handle cleanup remained in the readback path. Without an explicit fixture environment, this one probe skips honestly; it executed in the final run.
- Ruff passed for all eight changed/new Python source/test files. Pytest/Ruff and the retained interpreter probe exited. No listener/port opened.
- Exact final accounting, including the result itself: **2,458 entries = 1,190 files + 1,268 directories; 3,243,965 logical bytes; 13,311,933 conservative allocation bytes**. Final validation took **15.907 seconds**, below 300 seconds/8,192 entries/128 MiB. Filesystem counts were measured again after durable result creation and matched exactly.
- Existing .ruff_cache/.pytest_cache snapshots, original native-test evidence hashes and every retained candidate metadata row were unchanged in the final run. No current-task lint-cache variance was observed.

Private records retain regressions.txt, lint.txt, python-write-audit.json, full candidate before/after metadata rows, zero-difference report, fixture declarations and result.json. Private identifiers stay out of Git.

## Preserved failures

The **two original native harness failures and original two-cache-entry variance remain unchanged**, including raw records and original reports. This closure neither waives the variance nor changes the original scope-compliance result.

Earlier current-task roots remain:

1. 008998d661e2: guard refused pytest's Windows null-device logging before tests ran; Ruff's temporary-root import grouping also differed. Exact null-device handling and explicit import classification fixed setup. No outside file was created.
2. 567b5e29a3aa: **220 passed, 1 failed, 2 setup/teardown errors**. A huge generated parameter ID exceeded Windows' environment-variable length; a helper retained its original default root. Compact IDs and dynamic root resolution corrected these test/harness defects without weakening assertions.
3. cdf126399fce: tests passed, but an early digest-only retained-metadata comparison refused. Individual baseline rows were not saved then, so the exact difference remains **unattributed**. A subsequent read-only audit verified all **10,204 original hashes/sizes**, exact file namespace, recorded NTFS file-ID components and one-link counts unchanged. Consecutive metadata snapshots had zero differences. Full row snapshots were added and the issue did not recur in two subsequent complete runs. The original exception/diagnostic remain.
4. c735362ffb94: **223 passed** and full metadata preservation passed. Accounting was then tightened to include after-metadata/difference reports and the result itself. These were authorized workspace writes, not escapes. The final run above verifies corrected exact accounting.

No historical failure was erased and no cache cleanup occurred. No current provider, financial journal, operational account or Genesis path was accessed. Financial admission/UNKNOWN/refusal regressions remain; unrelated full accounting suites were not repeated because financial code did not change.

## Pins and remaining boundary

Historical QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V1_2026-10-30.json is byte-identical, canonical SHA-256 **888c645b055b016b165c2133a4f9bf69dabbe6f3d5c259a516a863586b7539f2**. Its native-copy provenance remains valid for the unchanged copier/source plan and original copied bytes; it is not current installation authority.

The **unapproved V2 proposal** retains the same 638-source archive, dependencies, destination, limits and false activation flags. It pins the updated adapter and is the CLI's exact current proposal path. The contract schema remains V1 because fields/meaning did not change. V2 canonical SHA-256: **09e899b09916300aec70b69d743d4c7e2383f43ecb58cea4a032f4070988917e**. It is a review artifact, not an installation request/grant. QD_NATIVE_COPY_CLOSURE_SOURCE_MANIFEST_V1_2026-10-30.json separately pins ten exact SDK/controller/test sources. The application archive is unchanged; no broad/untracked packaging occurred.

**A full native copy need not be repeated to validate these source repairs:** fixture regressions, unchanged copier identity, historical native evidence and the real read-only diagnostic probe establish those results. **A fresh bounded authorization/full run would be required to claim an uninterrupted native end-to-end/scope-compliance PASS for the revised full harness.** That claim is not made. No full native run occurred; the old grant remains consumed. Any fresh-run proposal needs its own new root, pins and limits.

No operational-install authorization is requested or consumed here. Before an actual unselected code copy, the sole operator must review V2 pins/findings and separately authorize exact paths/evidence writes. Actual-path readback, fresh qualifying clock and real resource/release binding still apply. Active selection/Control Center promotion, current research/rank custody, executable IEX, financial custody/inception, actual financial Stop within eight seconds/dashboard/restart and bounded PAPER operation remain separately gated. No external committee is introduced.

**PAPER startup: NO. Production: NO-GO.**
