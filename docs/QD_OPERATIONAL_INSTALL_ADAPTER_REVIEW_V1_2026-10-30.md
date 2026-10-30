# Operational install adapter review — October 30, 2026

Base: `26387e821bc928656b64953daa1bb5873f473f80`. Scope: source-only adapter engineering, disposable delta fixtures and browser attribution. **Source review complete; no operational installation, selection, activation or provider connection occurred.** B1/C1/D1/E1 technical gates, all 21 historical decisions, original UI, protected financial records/journals and Genesis isolation remain unchanged.

## Implementation reviewed and corrected

The historical `qd-install-coordination-release-20261028.py` is a retained commit-specific installer: it broadly enumerates Git files, records native copy identities and probes D:-resident Python. It must not be rerun as the current exact selected-package installer. The existing `install_synthetic_candidate` only permits new diagnostic candidate/interrupted children and cannot authorize operational installation. There was no accepted operational version-selector implementation to certify.

The narrow unselected-code adapter is now implemented in **`scripts/install_verified_release.py`**, reusing the existing physical copier through **`scripts/native_install_candidate.py`** and shared pure preflight **`scripts/native_install_plan.py`**. It has no selector, shortcut writer, financial resource path, account initializer, provider or service launcher. Default invocation refuses. Actual execution requires a separate operator grant and explicit `--execute-approved-unselected` invocation, a pinned proposal, exact three adapter-source hashes, exact archive/selection/dependency pins and a genuine runtime-bound `LocalWindowsClock`. That invocation flag and local hashes are not financial authority or an independent trust root.

| Review item | Result / correction |
|---|---|
| Source-to-target copy | Frozen, verified ZIP bytes plus only the pinned D-runtime dependency subset; original native creation handles, ACL/link/identity checks, flush and independent readback retained |
| Explicit manifest | Operational entry requires the exact selected inventory digest and tracked source entries; duplicate, malformed or contradictory proposal fields refuse |
| Dependency namespace | Fixed silent dictionary collapse of duplicate/case/slash aliases; validate file/directory row shape, native ID integers, unique physical IDs, hashes, sizes, required parent mappings and file/directory conflicts before creation |
| Module/runtime readback | Exact retained child identity; isolated new D interpreter/base/stdlib/import paths; existing installed `NativePersonalReleaseIdentity` checks native receipt and module cohort; parent verifies digest, counts, process identity, layout and zero retained verification handles |
| Receipt generation | Durable create-new intent journal before copy; separate create-new final receipt only after copy, layout/native readback and clock checks. New creation identities, never historical fixture IDs. Code inventory is not financial enrollment |
| Observer boundary | Progress callback receives deep snapshots, retaining the public synthetic schema for compatibility; it cannot mutate returned copy facts, schema or verification inventory |
| Handle cleanup | Removed unconditional zero-handle reporting. File/directory closes check native return values; remaining owned handles are counted and close uncertainty refuses. No financial native primitive was changed |
| Limits | Preflight included in 600-second copy bound; 40,000-entry/1-GiB plan ceiling; existing per-file/chunk bounds and no provider/service side effects |
| Selection / rollback | **No operational selector is installed or changed.** The adapter always leaves code unselected. Existing staging interruption/marker-preservation tests remain evidence, not a claimed real atomic selector |
| Interrupted copy | Prior release/marker never written; preserve partial destination and pending journal. Any existing destination, receipt or pending journal blocks a blind retry. No repair/adoption/deletion |
| Windows paths / ACLs | Exact new `D:\AtlasRuntime\releases\<source-sha>` only; ancestor/reparse refusal; native owner/SYSTEM policy reused. Existing project/root/financial permissions are never altered |
| Financial / Genesis / unrelated files | No financial resource or Genesis process/root is an input; no global termination; no migration, current-pin rollback, autostart or broad source enumeration |

The public [exact code-install proposal](QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V1_2026-10-30.json) pins the three reviewed source files and existing 638-file package. Canonical UTF-8/LF proposal SHA-256: **`888c645b055b016b165c2133a4f9bf69dabbe6f3d5c259a516a863586b7539f2`**. It is a proposal with all activation/selection flags false, not permission. Adapter tools sit outside the frozen application selection; the 638 application files were not changed by this engineering increment.

The eventual, separately authorized invocation is `scripts.install_verified_release` with `--execute-approved-unselected`, the exact proposal path and its `--proposal-sha256`. Its parent must run from the reviewed D source/interpreter environment; it constructs/revokes the existing native clock, checks source pins and invokes only the unselected-copy API. The destination remains `D:\AtlasRuntime\releases\2c039af29dfefd1df77e0caa3db3fdf5ed188118`. Private evidence would be `logs\diagnostics\qd-unselected-release-2c039af29dfefd1df77e0caa3db3fdf5ed188118.pending.jsonl` and the matching final `.json`. Neither exists from this task. Neither path is an active selected-version marker. No receipt from the old disposable candidate is relabelled operational.

**Important limit:** the new operational path and changed native copier have not executed a real new native installation in this task. Unit doubles exercise protocol/refusal logic; their fake inventories cannot verify a real D release or authorize a financial runtime. An actual Windows copy/readback acceptance remains required before using the new adapter operationally. True symlink/privilege-dependent native probes are not claimed executed from these unit tests.

## Two runtime deltas

The unchanged 638-source ZIP (`0e65fae1891fc8d406f086a6aa711781053aa7d9a6b3cf1c9c7963f709c87677`) was safely copied into one new disposable **source stage** under `logs/diagnostics/qd-install-adapter-review-v1`. Exact namespace, file sizes and hashes were verified before and after testing. It contains 640 files including the two archive companions, not a new native installation receipt.

The verified candidate's D Python ran **54 tests, 0 failures/skips, 4.03 seconds**, against this stage. Actual origins of both target modules were asserted inside the stage, preventing workspace or old-candidate fallback:

- `scripts/observation_runtime/personal_research_archive.py`: native-image protocol with **in-memory Windows I/O**, source/native revision and ACK binding, CAS/idempotence, partial publication/UNKNOWN, rollback/current custody, capacity, read preservation and source-producer roundtrip.
- `backend/app/services/quality_dips_iex_input.py`: offline IEX cache/reference and admission, exact physical clock boundary, source/identity/session/freshness refusal and no entry/shutdown observation issuance on inadequate evidence.

No provider was contacted; no financial service started. Any ledger used by the original source-producer test is a confined synthetic fixture, not operational custody. Fixture authorities stay synthetic. **This establishes the two packaged versions' offline compatibility, not native installed delta acceptance, current research publication or executable market evidence.** The source stage remained byte-identical; the owned child exited and its process handle closed. Delta stage/test work took 13.993 seconds and initially retained 676 entries / 8,237,581 bytes, within 300 seconds / 4,096 entries / 128 MiB. Later browser evidence is separate below.

## MutationObserver attribution

A new bounded observation-only host served the old candidate's original pages plus minimal controls. A **first-head-script** error/rejection listener recorded source/line/stack into visible DOM trace elements; it never called preventDefault or suppressed errors. This was fixture response instrumentation only; no candidate/frontend file was edited. No journal or financial source was supplied.

Genuine in-app browser sequence:

1. Minimal non-Atlas page: no console error; page trace `[]`.
2. Minimal page with **six same-origin minimal iframes**, before any Atlas application/dependency loaded: the same `MutationObserver.observe` TypeError appeared in browser logs; page traces remained `[]`.
3. Traced original Atlas hub/Perp page: another identical browser-log error; first-head page and loaded-frame traces remained `[]`.

**The error is reproducible in the browser/automation environment without Atlas application or third-party Atlas dependency code. Atlas code is not necessary to cause it.** The API exposes no source URL/stack for these console entries, so the exact extension/automation/browser component is still **unresolved**. No extension was disabled, no browser internals/credentials were accessed and no app error was hidden. This is stronger attribution than the earlier unexplained result, not a claim that every future UI is error-free.

Private evidence: `qd-install-adapter-review-v1/browser/attribution.json`, traced screenshot and owned-host result. One loopback host, **38 attempts / 33 admitted / 5 refused / 0 pending**, 67.078 seconds including cleanup, below 90 seconds / 96 attempts. Owned child exited, server thread drained, port and parent handle released. Test tab closed. No real Chrome or Windows Control Center GUI execution is claimed.

## Exact validation and retained failures

- **187 focused/broader cases passed, 0 failed, 0 skipped, 7.48 seconds**: new plan/adapter lifecycle/readback/proposal tests plus archive, selected inventory, source identity, Windows namespace, installer refusal, release module binding and refusal/resource regressions.
- **54 disjoint staged-delta cases passed**, above. **Total: 241 distinct final cases, 0 failed, 0 skipped; 71 new source-only cases.** Earlier 148/102/295-case evidence remains preserved rather than added to these counts.
- Ruff passed for all five changed/new Python source/test files. Static PAPER audit remains zero issues. Read-only plan preparation against the genuine retained package/dependency metadata produced **10,204 planned files / 903 directories / 260,369,081 bytes**; no destination was created.
- An initial new plan test used an old fixture's non-SHA `fixture-head`; strict source-commit validation correctly refused. The fixture was corrected to the existing SHA-pinned selected-builder helper. Original **1 failed / 49 passed** output remains retained.
- A restricted-context broad run could not create its confined hard link (**1 failed / 168 passed**). Standard-user rerun executed the unchanged hard-link assertion and passed; the original permission failure is not erased or called PASS.
- Final old candidate read-only native audit: **10,203 files / 903 directories unchanged**, identities/ACL/hashes/namespace verified, zero retained verification handles. No new protected child ACL, operational release, selected marker, credentials, clock setting or financial record was created or altered.

Private unit outputs are `qd-install-adapter-unit-v1/v2.txt` and `qd-install-adapter-regressions-v3/v4/v5/final/final-compat.txt`. The stage, failure fixtures, original browser finding and new traces remain retained. Public documents exclude machine/process IDs and private financial evidence. The unrelated modified research test and all historical roadmap content are preserved.

## Readiness and exact next boundary

**Source-only unselected adapter: implemented/reviewed. Actual native adapter acceptance: NOT EXECUTED. Operational installation/promotion: NOT AUTHORIZED.** Atomic active selection remains deliberately outside this adapter and requires its own reviewed mechanism and explicit authority; preserving an old marker in a fixture is not operational selector acceptance.

The smallest next permission is **one bounded disposable native code-copy acceptance** of this reviewed copier, using exactly one new fixture parent:

- `D:\Work\Project Atlas\logs\diagnostics\qd-native-install-adapter-v1`, with only `candidate`, `interrupted` and owned audit/test children.
- Exact frozen 638-file source ZIP and original 9,566-file D dependency inventory from the public proposal. No broad Git enumeration or source substitution.
- **600 seconds total including interruption/readback/cleanup verification, 40,000 entries, 1 GiB**, programmatically enforced. Owner/SYSTEM ACL changes only on newly created fixture children; original handles, hashes, namespace, interrupted-copy refusal and closed-handle counts checked. Preserve partial/failure evidence rather than deleting/recreating it.
- Only exact retained test children using the verified D Python; no UAC/system change, provider, protected account/journal, financial publication/service, active selection, Genesis or PAPER operation. Unsupported native privileges remain NOT EXECUTED.

**That native permission is not granted by this report and was not used.** After native acceptance, the operator can separately approve the pinned **unselected operational code copy** and its exact two audit files; still no promotion, financial enrollment, provider or PAPER authority. Then real local resources/current research and entitled executable IEX, fresh native clock, actual Control Center financial Stop <=8 seconds/dashboard/restart, and the separately gated inception/pilot remain. No external committee is required under the personal policy; technical and authorization boundaries remain intact.

**PAPER startup: NO. Production: NO-GO.**
