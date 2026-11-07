# Native financial recovery and resource evidence — 2026-10-24

## Scope and result

FS_RECOVERY_ARCHIVE_V1 is an implemented, disposable **archival recovery** protocol. It preserves original immutable financial bytes and their original logical bindings, verifies separately created native destination identities, and independently replays financial and reporting evidence. It is not an FS2 writable-store transplant, operational enrollment, trusted issuer, migration, startup permission, or independent D1 acceptance. Original account records were not accessed. The alien-themed frontend is unchanged.

The root design gap is real: copying bytes changes NTFS identities while embedded predecessor, commit, projection and report references still name original resources. Rewriting those references would alter evidence. A copied ordinary pin must continue to fail normal FS2/FS3 admission. The new archive uses a separate physical-to-original mapping instead; it deliberately exposes no execute method and returns a distinct research-only view schema.

## Complete identity-binding trace

| Evidence | Existing binding | Recovery treatment |
|---|---|---|
| Enrollment/current custody | Account, epoch, manifest/policy digest, three native root IDs, inception; current generation/high-water/acknowledged revision and source/report pins | Original enrollment and cut retained in request; injected authority must authenticate complete current cut and exclusion lease |
| Inception | Source root ID and original inception file ID/digest | Byte-identical copy, original binding retained; separate creation-handle destination binding |
| FS2 intent/record | Revision, previous original record ID/digest and event head; intent commits canonical record digest | No rewriting; original pinned files verified before copying |
| FS2 commit | Original intent and record identities/digests | Same immutable bytes; copied bytes bound to new native IDs in separate manifest |
| FS2/FS3 acknowledgement | Original commit identity; required projection proof | Preserved; no manufactured acknowledgement for UNKNOWN or missing tails |
| FS3 projection | Original projection root, deterministic operation prefix, intent/view/ack file IDs/digests; context names original record/commit and state digest | All three files copied exactly; original proof remains historical evidence, never pretended to identify destination resources |
| FS3 report archive | Root, scope ID/digest, report revision and predecessor binding, report ID | Entire acknowledged archive copied; lineage retained |
| Daily report source | Original source root, inception/entry bindings, source head/revision and reporting cutoff | Historical source prefixes independently replayed and audited against original cut |
| Restored archive | New native root; intent binding; each role/name/original binding to exclusive destination creation-handle binding; commit binding | New separately authenticated recovery descriptor; never substituted into ordinary financial pins |

## Implemented protocol and trust contract

`scripts/volume_inspector/financial_recovery.py` injects an authority with `lease(request)`, `check()`, `accept(descriptor, commit_binding)` and `validate(descriptor, commit_binding)`. No authority implementation, credential, issuer, clock source, key enrollment or default financial path is supplied. Test custody is explicitly synthetic, in-memory and nonoperational.

1. Require a bounded stable recovery ID, distinct sources and a nonoverlapping new destination. Missing authority refuses before storage creation. The authority must reject stale/coherently rolled-back cuts, UNKNOWN, reused recovery identities, unsupported recovery scope and unavailable clock/exclusion evidence.
2. Verify existing source/projection/report resources through the existing-only native read port. Recompute financial state and independent arithmetic; verify historical report prefixes and require the latest report to match the acknowledged financial high-water. An INCOMPLETE intraday report may remain INCOMPLETE; this is not a clean shutdown claim.
3. Enumerate only the exact pinned namespaces. Read original files with expected native IDs **before payload access**, not merely hashes obtained from an untrusted path. Retain no-delete native handles during each read; reverify the complete original cut under the authority's writer-exclusion lease before publication.
4. Exclusively create a fresh native destination. Flush immutable intent, byte-identical copies and a versioned commit mapping. Each destination binding comes from its original creation handle. Re-read each published file against that binding. Bound count is 1,027 files; commit descriptor is limited to the native reader's 65,536-byte maximum. Larger histories refuse, never truncate or rotate.
5. Obtain the external durable acceptance/CAS acknowledgement for the exact new descriptor and commit binding. A commit-before-ack failure remains UNKNOWN. Retain incomplete destinations unchanged; same-destination retries refuse rather than overwrite or repeat financial operations. A separately reviewed new recovery attempt may use a new destination and new external authorization. There is no automatic resume/adoption of an uncertain archive.
6. Archive reads verify native destination root and every restored file identity/hash, original byte hashes, exact namespace, independent authority before/after reads, intent/commit consistency and financial/report recomputation. Source events, inception and report documents are compared back to the copied records. Reads cannot initialize, repair, execute, publish reports or grant startup permission.

The authority must enforce single-use durable recovery acceptance, independently retained current high-water, exact destination mapping approval, expiry/trusted clock and writer exclusion. An arbitrary Python object that always returns True is not independent acceptance. Local hashes alone cannot detect coherent rollback. Same-user/admin malicious code, unknown writers, complete namespace exclusion, durable external custody and physical power-loss protection remain outside demonstrated guarantees.

## C1 actual-source and native observation roster

`QUALITY_DIPS_C1_SOURCE_ROSTER_2026-10-24.json` records exact paths, sizes and SHA256 for 18 actual source files. Read-only native handles also captured their volume/file identities locally in the retained diagnostic roster. Only the current observer's own process was observed using supported .NET APIs for PID, creation time and image. It was not represented as an Atlas worker or as proof of ownership. No unrelated/Genesis processes were enumerated; no operational process was started or stopped.

| Writer/reader boundary | Actual files and resources | Required accepted ownership/drain evidence |
|---|---|---|
| Parent/direct worker/function | Atlas-Background.ps1; StartupAdmission.psm1 guards before dependency/API startup | Named retained process handles, image/command/parent/creation/SID/incarnation and accepted exact writer roster; currently unavailable |
| GUI/Gaming delegates | Atlas-Background-Controls.ps1; Atlas-Background-Gaming.ps1 | Delegation is not financial authority; guards remain refusal-only |
| Python lifespan | backend/app/main.py; core/production_startup_lock.py | Startup remains disabled; no process observation here supplies approval |
| Research and legacy mutation | api/investment_board.py; investment/quality_dips_paper.py, marking/terminal, v3_state, prospective_evidence and v3_forward_store | Existing legacy/research writers must be independently excluded from any future selected roots; a GET on the legacy board can mutate state and must not be used as the financial read path |
| Selected prospective writer | investment/quality_dips_selected_account.py -> injected FS2 publisher/projection | Unregistered, no operational roots; require durable admission close, pending/UNKNOWN barriers, full financial/projection/report drain and independent process ownership |
| Selected read-only route | api/quality_dips_selected_paper.py -> selected read capability -> financial_read_port.py | Explicit enrolled identities/current custody; never initialize/repair or refresh providers |
| Canonical/projection/report writers | financial_record_store.py and financial_reporting.py | Exact source/projection/report physical roots, writer/incarnation/resource roster and quiescence not operationally enrolled or accepted |
| Other Atlas accounts and tools | Shared PAPER journal, manual perps/setup/equity/adaptive, investment PaperBook/engine, prediction, crypto/shadow utilities | Remain distinct legacy/strategy accounts. No account adoption, consolidation or implicit exclusion; independently verify they cannot reach selected resources before C1 promotion |

This is concrete source/file evidence, not a complete operational C1 ownership certification. No accepted operational PID, selected root, issuer or all-writer drain receipt exists in this execution. Source hashes cannot prove runtime ownership, directory-wide exclusion or the absence of a child writer. The native mutex and owner/SYSTEM ACL do not exclude all same-user/admin writers.

## Validation and remaining permissions

Exact final results and diagnostic filenames are recorded in the companion continuation after execution. Original failures are retained: sandbox hard-link and junction setup denied access; unsandboxed confined native execution preserves the same assertions. A temporary roadmap-capacity fixture initially exercised first-insertion newline trimming; it was corrected to test the actual existing managed-section path with exact prefix/suffix and backup checks. No financial assertion was weakened.

The existing managed roadmap had 29,969 characters against a 30,000 limit. The updater's finite cap is now 60,000, with positive 31,000-character and rejecting 60,001-character disposable tests. Existing managed bytes are retained verbatim inside the new checkpoint; no historical rotation, deletion or silent archival replacement.

**Next exact permission/evidence:** a named independent custodian/security reviewer must accept the recovery mapping threat model, complete original source cut/high-water and new destination mapping, external durable single-use acknowledgement, trusted clock, rollback custody, abandoned-writer policy, exclusion and retention/capacity rules. Then separately authorize a confined recovery acceptance using that genuine custody. Operational writable restored-store admission requires a further explicit design/integration authorization; it is not implemented or authorized here. Actual C1 process observations require a named Atlas process/resource roster and explicit read-only scope. No generic process enumeration, protected provisioning or financial routing follows.

B1 account/exclusions/capital/rules, C1 ownership/all-writer exclusion/drain, D1 enrollment/current-pin/issuer/clock/rollback/recovery and E1 rights/executable prices/corporate actions/backup/supervised release remain BLOCKED. All 21 decisions unchanged. Phase 1 incomplete; Phase 2 Evidence Engine/AFI HOLD (AFI-1–10 PENDING, 0 accepted); Phase 3 BLOCKED; Phase 4 Cross-Market pending; Phase 5 SaaS deferred/pending; Phase 6 institutional pending; Phase 7 commercial pending. PAPER startup NO; production NO-GO.

Final combined validation: **147 passed, 0 failed, 1 skipped/NOT EXECUTED**, 25.46s. Includes 21 new recovery cases, 15 existing native-read cases (14 passed/1 symlink privilege unavailable), 29 pure read-capability cases, 74 selected integration cases, 3 production-lock cases and 6 updater cases (2 new capacity cases). Focused/intermediate runs overlap and are not added. Ruff clean for new recovery module/tests and updater tests; four Python files compile; updater PowerShell syntax and final diff checks pass. No new browser, provider, operational or physical power-loss tests. Native source roster: 18 read-only observed files. The restoration protocol currently requires the original verified source cut to remain available during copying; recovery from unavailable originals/offline backup media and writable restored-store admission need separate accepted custody and integration.
