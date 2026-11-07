# Quality Dips native read-only capability acceptance — 2026-10-24

Status: VERIFIED confined source/disposable read boundary only. B1/C1/D1/E1 BLOCKED. PAPER startup NO. Production NO-GO. All 21 governance decisions unchanged. Phase 2 HOLD; Phase 3 BLOCKED; AFI-1–AFI-10 PENDING, 0 accepted.

## Implemented boundary and exact files

- `backend/app/investment/quality_dips_read_capability.py`: injected enrollment, accepted authority read lease/current pins, trusted clock and existing-only native port; implements the existing router's reader/verifier protocol. No defaults, registration, issuer, provider, startup or financial writer.
- `scripts/volume_inspector/financial_read_port.py`: existing-only handle-bound source/projection/report verification. Reuses FS2 immutable load, FS3 immutable projection and archive lineage verifiers without constructing writer services or entering their recovery-capable guards.
- `tests/test_quality_dips_read_capability.py`: 27 pure/disposable authority and financial consistency cases.
- `tests/test_quality_dips_read_capability_native.py`: 15 confined native cases, 14 passed and one unavailable privilege. Fixture provisioners create only disposable synthetic records; no operational enrollment or credentials.
- This report, separate exact continuation, master managed checkpoint, autonomous state, execution queue, core readiness continuity and multi-strategy coverage addenda. Existing financial engine, native primitives, router, page, launchers, main.py, startup lock, historical records and goldens are unchanged.

## Findings and protocol

The existing FinancialRecordStore and ReportArchive guards can publish a recovery-required marker after abandonment; ReportService.history also uses these guards. They are unsuitable as unqualified read-only capabilities. The new reader calls only their immutable verification routines on restricted method surfaces; it does not construct those services, acquire their recovery mutexes or invoke latch/publish/execute/repair.

WindowsOutput's existing-only constructor opens read/attribute/security directory handles, verifies ancestors and exact protected root ACL/NTFS identity, and never creates a root. Bound payload reads verify file identity, ACL, single-link count and digest before trusting bytes; handles exclude write/delete during each individual file read. Outputs always close in finally. Directory enumeration supplies refusal checks only, not directory-wide exclusion.

The separate accepted authority must authenticate enrollment and return a coherent lease over source, projection and report resources, including independent current high-water/generation/acknowledged revision, source/report pins, freshness/expiry and unknown writer/rollback status. The lease must reject continuity loss both before and after reading. No implementation of independent custody, issuer, clock, enrollment or global writer exclusion is supplied. Injecting an arbitrary Python object or locally created pin does not create that authority. There is deliberately no operational composition root.

Selected V3 account/epoch, immutable manifest/policy/inception and native root identities must match enrolled scope. Every event must be durably acknowledged with required FS3 projection proof. Replay and independent financial audit derive exact state; current projection and source revisions must agree. Every retained report is independently audited against its exact historical source prefix; latest report must cover current source revision. Historical reports retain explicit cutoffs. Intraday INCOMPLETE is displayed as INCOMPLETE, never converted to COMPLETE. Report completeness is not lifecycle completion, liquidation or valuation; overnight holdings remain open. Missing reports refuse the financial read; UNKNOWN never becomes a successful snapshot. Unsupported aggregate fee/slippage breakdown and valuation remain unavailable.

Trusted observed_at comes from the authority snapshot, never from the act of rereading; revalidation cannot make old evidence fresh. Clock reversal, future evidence and expiration during reading refuse. The router verifier independently rereads/revalidates; a changing snapshot may conservatively refuse rather than return mixed revisions. No cache grants authority.

## Tests, original failures and exact counting

- Final focused selection: **41 passed, 0 failed, 1 skipped / NOT EXECUTED**, 6.73s. This comprises 27 non-native and 14 native passes plus one native symlink probe not executed.
- Combined FS1, selected policy/integration/frontend application, epoch/strategy/Q7–Q9 and production startup-lock selection: **311 passed, 0 failed, 1 skipped / NOT EXECUTED**, 25.24s. This predates one additional concurrent-writer native case; that disjoint case separately passed and is included in the final focused selection.
- Across these overlapping Python selections: **312 distinct passed cases, 0 final failures, 1 distinct NOT EXECUTED case** (313 selected cases). Do not add focused and combined totals. The prior 271-case compatibility selection is contained in combined, not extra.
- Separate frontend JavaScript selection: **25 passed, 0 failed/skipped**, unchanged DOM/fetch fixture assertions.
- Initial native run: 1 failed due to an incorrectly static-bound reused projection prefix method. Corrected to an instance method. Next sandbox run: 7 passed then hard-link setup denied with Windows error 5. Retained both failing JUnit artifacts. The explicitly authorized native rerun outside the sandbox executed hard-link and junction probes successfully and refused linked/reparse reads; no assertion weakened.
- True symlink creation failed with Windows privilege error 1314 even outside the sandbox: **NOT EXECUTED**, not proof of symlink resistance. No privileges or OS settings changed.
- Native tests verify missing/foreign roots, original-handle identity mismatch before ReadFile, byte tampering, identical-byte file replacement, projection/report corruption, missing ack, rolled-back report pin with retained newer evidence, hard links, junctions, incomplete source tail and a concurrent uncoordinated writer. Files remain byte-identical across reads/refusals; missing root remains absent. Patches forbid root creation, financial/report constructors and write_bound during valid reads.
- Pure cases verify absent authority, foreign enrollment, stale/expired/future/malformed pins, high-water/ack mismatches, generation/continuity changes, unknown writers, reverse clock, incomplete reports, legacy adoption refusal, source omission, altered cash and report/source mismatch.
- Targeted Ruff, in-memory Python compilation, unchanged checkpoint updater PowerShell parse and diff checks pass. No frontend build is claimed: frontend source is unchanged. Existing frontend regression tests remain passing.

## Security limitations and unaccepted evidence

Fixture authority is explicitly in-memory/test-owned, not independent high-water custody or operational enrollment. Coherent rollback of all files plus a forged/local authority snapshot is not solved by hashes or this reader. Accepted independent current pins/issuer/clock/recovery and complete namespace/nonparticipating writer exclusion are still mandatory. Each-file handle exclusion does not prove whole-directory quiescence. No power-loss durability, malicious same-user/admin resistance, complete symlink coverage, backup/restoration acceptance or operational D1 acceptance is claimed. Test-owned synthetic accounts are not authenticated financial history. The capability cannot sandbox a malicious injected port/authority callable; only independently accepted implementations may be bound in a future composition root.

## Supervised disposable HTTP/browser acceptance plan — NOT EXECUTED

1. Obtain explicit permission for a new uniquely confined synthetic source/projection/report bundle and a dedicated loopback-only test host. Retain exact process handle, PID/creation identity, executable/command and host instance ID; refuse a foreign port, ownership mismatch or duplicate host. No main.py lifespan or normal backend import/startup.
2. Bind this reader to the existing unregistered create_router with commands=None and an explicitly labeled fixture authority. Serve only the existing quality_dips.html/common approved static assets and selected script at versioned/hash-pinned paths. Add no operational financial sources, providers, legacy research endpoint or command dispatcher. Default command POST must remain 403.
3. Check actual HTTP readiness and host ID, exact Host/loopback origin, no-store and approved path allowlist. Open quality_dips.html?mode=selected-paper. Verify exact synthetic inception/cash/remaining quantity, costs unavailable where unsupported, report cutoff/INCOMPLETE, overnight positions, refused/stale/UNKNOWN states and escaped text. Inspect actual network requests: selected GET only, no legacy mutating GET, provider/POST/worker calls or duplicated polling. Run network refusal and slow-response replacement checks.
4. Verify every source file hash before/after; browser/HTTP failures cannot initialize, repair, publish or clear UNKNOWN. Observe graceful owned-host-only exit, retained ownership on timeout, released port and safe restart. Never kill by port/name or terminate unrelated processes. Retain errors and genuine browser/network evidence.

No HTTP server, network listener, real browser, screenshot, operational enrollment or Control Center launch ran in this milestone. DOM/fetch fixtures are not native browser acceptance.

## Exact future registration/Control Center changes (separate authorization)

Current scripts/observation_runtime/readonly_dashboard.py is a fixed Workspace V2 static bundle host with five allowed files; it imports no backend and has no selected route. Atlas-ReadOnly-Dashboard.psm1 launches that fixed bundle on loopback, checks exact host ID and retains its child. Atlas-Background-Controls.ps1 delegates Open/Close to that module. It cannot currently serve this new account merely because a router factory exists.

Smallest next development scope: a dedicated disposable test host/composition in scripts/observation_runtime (proposed selected_account_readonly_host.py), plus tests for exact assets, router GET/POST refusal, ownership and HTTP/browser readiness. Reuse backend/app/api/quality_dips_selected_paper.py factory and this capability; do not register in backend/app/main.py or import its operational lifespan. Any later operational composition requires accepted immutable enrollment/current-pin/clock/exclusion services, an exact read-only process/resource roster and explicit route-registration permission. Only after that acceptance should the Windows module/controls offer a separately identified selected-account host with verified instance ownership and safe graceful close, preserving existing deadlines and protected Start/Stop behavior. Do not widen the historical static bundle allowlist or overwrite retained artifacts silently.

B1: independent isolated account/capital/instrument/risk/legacy exclusions review. C1: actual all-writer/resource ownership, exclusion, drain and read-service lifetime acceptance. D1: protected enrollment, authority, current high-water custody, trusted clock/rollback/recovery and namespace acceptance. E1: provider rights, usable authorized price evidence, backup/isolated restoration, native lifecycle/browser and supervised release. None supplied by these tests. Trade commands and any operational PAPER startup remain separately gated.

## Full roadmap and continuation

1. Core reliability/Windows Daily PAPER incomplete; read-only capability implemented and confined-native tested, not operationally bound.
2. Research Evidence Engine/AFI HOLD; AFI-1 through AFI-10 PENDING, 0/10 accepted.
3. 15-minute crypto/prediction research BLOCKED pending Phase 2; optional scope deferred.
4. Cross-Market Intelligence pending; original evidence/provenance requirements retained.
5. Professional SaaS pending/deferred; licensing/tenant/revenue acceptance retained.
6. Institutional platform pending; independent security/enterprise acceptance retained.
7. Commercial expansion pending; original customer/revenue acceptance retained.

All 21 gate identities/decisions remain byte-identical. Next executable scope is the explicitly disposable isolated host/real browser acceptance above, subject to its named host/resource permission. No operational enrollment, registration or startup follows automatically. Exact recovery pointers and validation diagnostics are retained locally in this run's unique diagnostics directory; those logs, synthetic records, pins and private data are excluded from publication.
