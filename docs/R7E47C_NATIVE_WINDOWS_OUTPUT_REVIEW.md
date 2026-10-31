# R7E47C — native Windows protected output and independent startup review

**Native NTFS protected-publication subset VERIFIED with explicit limitations. True symlink case NOT TESTED/BLOCKED by missing creation privilege. Production integration remains NOT ACTIVATED; production NO-GO.**

2026-10-18T07:51:22.811310-05:00, America/Chicago. Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Read latest checkpoint/permanent strategy/recovery, B implementation/report/plan and Y/Z/A reports/packages. Preserve historical failures, existing tracked/untracked changes and artifacts. Evidence: logs/diagnostics/r7e47c-20261018-072939.

## Files and implementation

New scripts/volume_inspector/windows_output.py and tests/test_r7e47c_windows_output.py; this report and STARTUP_INTEGRATION_CONTRACT document; mandatory roadmap/diagnostics. Existing adapter/ProtectedOutput, helper pin/image and production startup sources unchanged. No automatic Windows backend selection; caller must explicitly construct the new backend. Synthetic MockDocker adapter plus this actual filesystem backend passed an integration test.

Explicit local canonical drive path only; reject UNC/device namespace/ADS/traversal/reserved/trailing aliases. Root must exist with exact protected DACL unless explicit create_root creates a NEW synthetic root atomically with its security descriptor. Existing roots are never repaired or overwritten. Owner=current approved Windows process SID; exactly two allow full-control ACEs for that SID and SYSTEM, protected DACL, no inherited/extra/broad grants. Existing inherited/broad/wrong DACL fails closed. All new evidence/staging objects get explicit descriptors at native creation, not an unsafe create-then-tighten window. No production ACL was touched.

Drive root is opened once; every subsequent ancestor, root, staging/file lookup uses NtCreateFile relative to the previously verified directory HANDLE, no path re-resolution through mutable ancestors. OBJ_DONT_REPARSE and FILE_OPEN_REPARSE_POINT plus native attribute/type checks refuse reparse objects. Handles deny delete-sharing; directory write-sharing is necessary for link creation and is NOT writer exclusion. Native held-root rename rejection and mutable-path-string redirection refusal passed. Existing staging junction substitution on read fails without accessing its target metadata.

NTFS-only; other filesystems/platforms fail closed. Private files use exclusive FILE_CREATE, write-through/synchronous I/O, bounded65536byte data, checked complete writes and FlushFileBuffers. scalar filtering reused from B accepts actual helper schema but projects totals only, discarding filename/link/layout/path/SID strings. Raw exceptions are not written to output. Opaque names only; input image/source identifiers never appear in published metadata.

Publication layout: <operation>.json.pending/{metadata.json,audit.json,commit.json}, with <operation>.json.commit as a second native hard link to the already-flushed commit.json. NtSetInformationFile/FileLinkInformation creates the final root-relative link without replacement. Nothing is deleted or renamed for publication. The commit contains metadata/audit SHA256, audit contains byte count and metadata digest. All three files are fully flushed before publication; pending artifacts survive failure. No reader treats a pending directory as accepted output.

Reader pins marker/staging/file handles, rechecks DACL/reparse/type/link count and exact commit file identity, bounds reads, verifies hashes/audit and filters metadata again. Optional expected_digest checks independent fence commitment; future integration MUST supply it. Owner/SYSTEM can alter both data and hashes, so local hashes alone are not authentication/rollback resistance. No key, encryption or external authority is introduced.

## Native Windows acceptance (not mocked ACLs)

32 passed,1 skipped in the final native group. Combined with existing adapter/helper tests:187 passed,3 skipped,0 failed in4.66s. All Windows tests operate in new disposable diagnostics subdirectories, retained without cleanup.

Native tests cover explicit owner/SYSTEM DACL creation/verification; allowed current user and denied restricted-token write; inherited/broad/drifted/file-DACL refusal; actual write-permission failure; real root/ancestor junction rejection and staging-junction read refusal; pinned-root rename rejection; concurrent same-name writers; existing evidence collision; atomic visible marker boundary; metadata/audit/hash checks and independent expected digest; complete restart read; child-process exit23 after a flushed full/10byte partial metadata record; pending retention/refusal/no overwrite; unknown/malformed/secret output refusal; closed/missing roots; mock adapter orchestration with actual native publication.

Denied-principal evidence uses Windows CreateRestrictedToken with restricting Everyone SID and native impersonated CreateFile denial(error5), not a fake ACL callback or invented user account. This proves that security context denial; a separate normal user login and SYSTEM impersonation were not exercised. SYSTEM allowance is verified from native DACL entries, not an actual SYSTEM write. Same-owner/SYSTEM/administrator malicious modification is outside DACL isolation guarantees.

True symbolic-link fixture creation returned privilege-not-held1314; case skipped and NOT TESTED, no attempt to enable privilege. Actual junction fixtures and generic reparse checks do not waive that missing case. Other skips: B POSIX native publication and Y Linux descriptor on Windows; Z historical Linux evidence unchanged. B's historical skip text still mentions its legacy Windows-denied POSIX class; the separate explicit Windows backend is now tested, no global fallback enabled.

Native ACL/junction/hard-link operations were restricted by sandbox in early attempts. Authorized unsandboxed tests were limited to new synthetic roots; no production path or service access. First23-case run:20pass3fail (junction fixture sandbox denials plus missing directory-data access for no-delete pinning); later sandbox and sharing/rename failures preserved. Initial relative Win32 rename rejected(error87), missing NUL buffer produced an incorrect synthetic name, and no-write-sharing conflicted with publication(error32). Retained roots/logs/source snapshots show each failure. Final code uses handle-relative NT component opens and hard-link publication with directory READ/WRITE sharing but no DELETE sharing; all final runnable cases pass. No failed artifacts removed.

## Durability and recovery limits

Actual write-through and successful native FlushFileBuffers calls establish OS-acknowledged file flushes, not device honesty or tested sudden-power-loss survival of the new directory entry. Atomic visibility was observed at the marker boundary; not a blanket guarantee across network/ReFS/drivers/power failure. No full-machine crash, resource exhaustion, hostile administrator or simultaneous actual reparse mutation stress was performed. A pending/no-marker/invalid-hash record is INCOMPLETE; retain it and refuse same-name retry. No automatic reconstruction, copying, permission repair or cleanup. In the adapter, output failure retains UNCERTAIN; any real helper-exit/fence release requires independent proof. No actual helper was created.

## Startup review and coverage

Full matrix and contract: docs/R7E47C_STARTUP_INTEGRATION_CONTRACT.md. Parent manager Start791 uses global mutex but releases it837 after child spawn; worker starts dependencies616/API626 after that. Guarding only parent leaves a handoff race. Require durable startup intent plus worker-side re-admission under fixed global-mutex -> fence-transaction -> ownership-record order. Never wait for a child while holding its required mutex or acquire mutex while holding SQLite. Existing B fence alone lacks this bidirectional startup-intent protocol.

Supported manager/worker, Gaming wrapper/GUI, legacy ATLAS.bat/Atlas-Launch, smoke harness, direct API/import/lifespan and standalone writers all require admission changes under future approval. Lifespan currently contacts Redis and performs schema writes, so guard before them; launcher dependencies need earlier guard. Manual Compose/Desktop/Engine restart and administrator clients remain external bypasses; Compose restart=unless-stopped requires maintenance-window control. No production entry point consults the new fence today. No current enforcement claim.

Proposed fixed fence directory: D:\Work\Project Atlas\logs\runtime\inspection-control; dedicated protected registry with approved one-time initialization, no missing-state recreation, trusted owner/SYSTEM writers, guarded sidecars and independent recovery witness. NOT CREATED. Path/ACL/native SQLite sidecar handling, startup intent, lock order, rollback/corruption authority, real transport/proof and source writer exclusion remain implementation/acceptance gates.

## Validation and release matrix

| Gate | Result |
|---|---|
| Native protected root/DACL/metadata publication and reader | PASS within tested local NTFS scope |
| Actual denied restricted-token context / junctions / races / process interruption | PASS |
| True symlink fixture | NOT TESTED/BLOCKED — privilege unavailable |
| Native power-loss/hostile-admin/cross-machine behavior | NOT TESTED |
| Combined helper/adapter/native tests |187pass3skip0fail |
| Guarded S/T/V lifecycle regressions |82pass0fail45.02s;5 tested production modules match retained snapshot byte-for-byte |
| Targeted Ruff / compilation / PowerShell parsing / diff |PASS;9Pythonmodules;18Windows scripts0errors; final checkpoint evidence |
| Startup integration / fixed protected registry |BLOCKED / not activated |
| Real Docker transport, independent proof, writer window, hard D-state exit |BLOCKED |
| Fresh Docker/container/image verification |Not attempted C; last A Engine unavailable, historical Z not current proof |
| Real-volume coverage/capacity/backup/restore/lifecycle |Not performed / separately authorized |
| Overall production |NO-GO; all previous gates retained |

No Atlas/Docker lifecycle, production helper/mount, Genesis access, DB payload/secret reads, real backup/restore, production ACL or shortcut change, trading/Discord activation, Git stage/commit/push/reset or destructive cleanup. Runtime not queried C; last A STOPPED evidence remains historical, not a fresh health claim. PAPER_ONLY/MANUAL_ONLY, gaming low-resource objective and normal PAPER management cadence preserved.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.


Current core: close true-symlink/native portability review; independently review native ctypes security boundary/durability limits; implement and isolate-test protected fixed fence/SQLite sidecars/startup-intent handoff and all admission paths only with separate approval; real Docker adapter/proof/writer window; fresh ownership/image; then separately approved real-volume metadata, effective coverage/capacity/destination/key recovery, backup and scratch restoration. Complete Shutdown/shortcut and Gaming runtime acceptance remain separately gated.

Recommended next milestone: R7E47D isolated shared-fence provisioning, SQLite sidecar permissions and parent/worker startup-intent protocol acceptance, with an independent native security review; no production wiring or lifecycle actions. Separate authorization required.

## Primary design references

Microsoft [NtCreateFile](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile), [FILE_LINK_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_link_information), [file security descriptors](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights), [restricted tokens](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken) and [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers). Native observations above, not documentation alone, determine acceptance.
