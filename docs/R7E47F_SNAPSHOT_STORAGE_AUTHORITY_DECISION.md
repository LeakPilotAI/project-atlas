# R7E47F — handle-bound snapshot storage and recovery authority

**Isolated storage contract PASS within a caller-trusted current-pin threat model. Architecture decision BLOCKED for a production-integration proposal. Overall production NO-GO.**

Completed 2026-10-18T10:35:06.998845-05:00, America/Chicago (CDT, UTC-05:00). Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Evidence: logs/diagnostics/r7e47f-20261018-102420. Latest master checkpoint/permanent contract, D/E reports, SQLite attack reproductions, complete shared-fence implementation, bridge tests and readiness matrix reviewed. Their source/report hashes remain unchanged. Existing working tree, untracked inputs and original failures preserved. Architecture review is a source-based adversarial assessment, not third-party certification.

## Exact security requirement

A control-state admission may use only bytes from the exact approved native file identity and committed revision, reached through a verified root/ancestor chain. Before reading state bytes, obtain and validate the same handle's volume/file identity, object type, single-link status and protected DACL against an independently trusted current commitment. Hold a sharing lease denying write/delete access through that read. Verify the bounded bytes' committed digest BEFORE decoding or trusting fields. Reject absent, malformed, inconsistent, corrupt, substituted or obsolete commitments. A post-open/post-SQLite check is insufficient; opening a no-follow handle for identity metadata is distinct from consuming payload or authorizing startup.

Coverage must include the main database and every rollback journal/WAL/SHM file if SQLite is used. A design eliminating SQLite file access must not accidentally fall back to it. Reparse/junction and hard-link attacks must fail before reading state; concurrent changes must be denied during read or cause refusal before admission. Revision reservation/commit gaps and parent/worker crashes must preserve startup prohibition. Recovery must require explicit, fresh authenticated exact-helper exit and revision-bound authorization, never elapsed time or Docker disconnect.

Threat assumptions: unapproved restricted tokens are denied by native owner/SYSTEM ACLs; cooperating authorized programs obey the same coordinator and trusted current pin. Same-owner malicious code, SYSTEM/administrators/kernel actors, compromised caller pins/keys, mapped-file/physical-disk attacks and external Docker writers are NOT proven excluded. Local ACLs and immutable-by-API filenames alone cannot provide independent anti-rollback authority. No narrower production threat model was silently approved.

## Selected isolated architecture

New scripts/volume_inspector/snapshot_store.py and tests/test_r7e47f_snapshot_store.py. No production imports or startup integration. Bounded canonical JSON snapshots replace the initially considered serialized SQLite approach: fixed control-state records do not require SQL. This is a smaller storage prototype, not a replacement SQLite VFS. D/E source is preserved for comparison and regression. The module reuses D's native Windows helpers/coordinator construction; it transitively imports sqlite3 but never opens a SQLite connection or uses its path-based I/O.

Two explicitly created disposable protected NTFS roots hold (1) snapshot-N.json state and (2) intent-N.json / commit-N.json witness records. Native exclusive creation and flush, no overwrite/reset/delete. A caller-supplied pin binds instance UUID, both directory identities, revision, snapshot file ID/digest and witness commit ID/digest. No latest-file discovery or initialize-on-missing. The synthetic revision cap is128, with64KiB per record. This bound is a prototype acceptance limit, not a production retention policy.

read_bound uses handle-relative no-follow NtCreateFile, native owner/SYSTEM protected DACL verification, single-link/type/size checks and expected file ID BEFORE ReadFile. That same native handle has read-only sharing, preventing ordinary conflicting write/delete/rename opens during its lifetime. SHA-256 verifies bytes before JSON decoding. Main and witness identity mismatches have explicit tests showing the substitute's handle is never passed to ReadFile. Native conflicting write/rename calls return ERROR_SHARING_VIOLATION32. These are native Windows tests, not mocked identity decisions. Microsoft's [file-sharing contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew) supports the design; measured local results determine acceptance.

There is no journal/WAL/SHM in this storage engine. Known legacy fence.sqlite3/main/journal/WAL/SHM and current-snapshot sidecar names cause immediate refusal without payload reads. A sidecar created after that check is never opened by this design; it cannot redirect snapshot reads. This is sidecar elimination, not a claim that old SQLite sidecars are secured. E's two SQLite attack reproductions were rerun and remain successful demonstrations of the old boundary.

### Publication and restart semantics

Under the native root-identity coordinator (500ms acquisition; no network/process waits): read and authenticate current state, build a bounded new control snapshot, flush an exclusive next-revision intent in witness storage, flush the snapshot, verify exact intended bytes through a native handle, then flush an exclusive commit binding snapshot identity/digest. Only then return the new caller pin/state. Snapshots embed the prior snapshot digest and fixed transition event. Witness intent records embed the complete prior pin and intended next hash. All artifacts remain on failure.

A newer intent with an old pin is ambiguous even if a commit exists: refuse, never fall back. Restart must receive the independently retained latest pin and validate its exact files. Storage identity/content/integrity rejection or abandoned coordinator writes a persistent recovery-required marker when storage permits, and the in-memory store is poisoned. Repairing bytes alone does not clear the marker. No automatic reset, retry, migration, garbage collection or storage-latch recovery API exists. If storage cannot accept the marker, durable new failure evidence cannot be promised; the call still refuses. OS flush/process-exit tests are not physical power-loss acceptance.

The latest pin is NOT independently durable or authenticated by this prototype. It lives in the synthetic caller, with fixture files used to carry it across child exits. The separate witness root has the same user/SYSTEM trust, not a distinct security principal. An interrupted caller after commit but before independently recording the new pin requires explicit reconciliation; it cannot safely auto-discover/recover. This remaining external-authority contract prevents production approval.

### Synthetic admission scope

reserve_start records PENDING before any future worker; admit_worker records STARTING, and inspection refuses either phase. Concurrent startup/inspection has one winner. Inspection records UNCERTAIN and consumes operation ID; helper identity is explicitly synthetic. Parent and worker child-process exits leave PENDING/STARTING committed and continue to block inspection. No fake dependency actually starts. This minimal state model is a storage acceptance harness, not a replacement for E's nonce/window/independent worker-verification lifecycle bridge. Real manager/worker identity and trusted handoff remain unimplemented. Private mutation primitives assume trusted program code and are not a Python sandbox against same-owner callers.

## Recovery-authority decision

SyntheticAuthority demonstrates TWO cryptographic roles: exit-witness attestation and operator approval. Exit facts bind exact helper, operation, exited state, integer PID0 and fresh timestamp within5s/nonfuture. Operator approval binds instance, revision, complete state hash, exact signed evidence and nonce, and requires approved=True. Verification checks both signatures and exact retained inspection/helper; a valid operator signature over forged witness evidence remains insufficient. Recovery records EXIT_PROVEN_FAILED, consumes the operation and increments revision; old grants cannot replay. No timeout/disconnect/missing helper inference clears uncertainty. No recovery method starts services; production_admission ALWAYS refuses fixture proof.

Both keys are ephemeral test keys in one Python process. This is NOT independent production evidence, authenticated operator identity, separate-principal key storage, durable high-water mark or real Docker/process witness collection. Real proof collection remains deliberately unimplemented. Production requires an explicitly approved independent principal/trust anchor, durable non-rollbackable instance/revision authority, authenticated approval channel, exact image/container/operation exit collector and key rotation/revocation/audit/recovery policy. E136 anti-rollback/consent obligations are not solved by this prototype.

A native boundary reproduction deliberately hides the newer local intent (retained by rename) and supplies an old genuine pin. The old genuine snapshot is then accepted in the synthetic model, demonstrating that local files cannot discover a rolled-back external authority. Production admission still refuses. This is an expected unresolved trust-boundary result, NOT a successful anti-rollback acceptance or permission to clear real uncertainty.

## Adversarial acceptance evidence

| Case | Result and meaning |
|---|---|
| Pre-open main-equivalent snapshot / witness replacement |PASS: native IDs refuse before substitute ReadFile or JSON decode, no new startup intent |
| Same-identity corrupt/incomplete snapshot |PASS: digest refusal before decoding/admission; persistent latch survives byte repair |
| Journal/WAL/SHM/main legacy and snapshot sidecar insertion |PASS:7 forbidden surfaces refused without state decode; no SQLite access path |
| Concurrent write/rename during native read |PASS: actual write-handle and rename blocked with32; original committed state read intact |
| Hard link / junction |PASS: native link/no-follow checks refuse before decode |
| True symlink |NOT TESTED: native creation privilege1314 unavailable; no waiver |
| Stale pin with retained newer reservation |PASS: refuse and retain fence, no old-state fallback |
| Local witness AND trusted-pin rollback |BLOCKED for stronger guarantee: expected limitation reproduction; independent durable authority missing |
| Interrupted snapshot/commit publication |PASS: durable intent retained; old startup/inspection forbidden |
| Actual process exit after publication reservation |PASS: child exits24; parent sees abandoned coordination, durable intent/latch |
| Actual parent and worker fixture exits |PASS: children exit23; latest fixture pin reopens PENDING/STARTING, inspection blocked |
| Concurrent startup/inspection |PASS: exactly one committed admission |
| Forged evidence/grants, missing authority, stale/future/wrong helper/running/boolPID/revision mismatch/replay |PASS: uncertainty remains; valid two-role fixture recovery separately passes |
| Native restricted token |PASS: real token READ/WRITE denial for snapshot AND witness |
| Malformed/missing/changed-root pins |PASS: refuse, no automatic provision |

## Architecture comparison and decision

| Dimension | D/E path-based SQLite | F handle-bound snapshot prototype |
|---|---|---|
| Identity before state read |Native pre/post checks do not intercept SQLite opens; E attack reproduced |Native expected file ID checked on same read-leased handle before ReadFile; digest before decode |
| Sidecar surface |Journal/WAL/SHM paths, identity continuity unresolved |No SQLite sidecars; reject known legacy/snapshot sidecar presence |
| Crash consistency |SQLite transactions plus independent local receipts; gaps latch |Flush intent -> snapshot -> witness commit; gaps/stale pins refuse; external pin handoff still unresolved |
| Rollback authority |Local receipts insufficient against all-files privileged rollback |Same limitation if local witness and caller pin can both roll back; independent authority still needed |
| Complexity |Mature SQL engine but difficult VFS/sidecar identity enforcement |Smaller fixed JSON control model; native reader/mutex and explicit pin/publication contracts |
| Migration |Existing isolated schema only; no production registry |No automatic migration/backfill; future stopped, independently witnessed migration would require approval |
| Operations |Known SQL tooling and recovery semantics |More small append-only-by-API files,128revision prototype bound, explicit stuck-publication reconciliation; no cleanup policy approved |

**Decision: BLOCKED for even a narrowly scoped production-integration proposal.** Local identity-before-read is demonstrated for the tested unprivileged/cooperative NTFS model, but the independently durable/authenticated revision and recovery authority is unimplemented; native true-symlink/cross-session/SYSTEM/alternate-user and power-loss acceptance is incomplete. A malicious same-owner/admin changing both keys/pins and files is not excluded. No production registry/proof collector/startup path was created or changed.

Smallest corrective milestone proposed: **R7E47G independent authority/trust-boundary contract and isolated durable-pin handoff acceptance**. Choose and explicitly approve the trusted principals/threat model; prototype authenticated external current-revision/commit acknowledgment and interrupted-handoff refusal using disposable fixtures, separate evidence/operator roles and rollback attacks. Do not broaden into a replacement VFS or production broker deployment. Real keys/principals/process/Docker collector/provisioning/integration need separate explicit authorization. No next milestone executed here.

Before future integration also retain E's authenticated manager/worker binding, durable single-use spawn, all startup/legacy/API/standalone entry admission and lock-order review, failed-start/owned-stop reconciliation, independent helper exit, external writer maintenance window, approved migration/rollback and separately controlled runtime acceptance. GUI-only checks or direct API lifespan checks do not cover dependency launch. All prior release gates remain.

## Validation counts and original failures

- New F:43 passed,1 skipped,0 failed.
- Existing E/D/C/B/Y:282 passed,3 skipped,0 failed.
- Combined verified-native.txt:325 passed,4 skipped,0 failed in15.49s.
- Guarded S/T/V lifecycle:82 passed,0 skipped,0 failed in48.10s.
- Final total:407 passed,4 skipped,0 failed. No full canonical suite or broad lint-policy waiver.
- Targeted Ruff PASS;15Python files compiled in memory;18Windows scripts parse,0errors. Five lifecycle sources match guarded snapshot byte-for-byte. All D/E reviewed sources/reports unchanged. No added package dependency.

Four skips: F true-symlink and inherited C true-symlink cases (privilege1314), POSIX publication on Windows, Linux helper descriptor on Windows. Historical Z Linux acceptance preserved, not rerun.

Failures preserved: first-native31pass/1fail/1skip: Python's denied write open lacked winerror, while test expected32; replaced that assertion with actual native CreateFileW denial32 plus rename denial32. Expanded-native323pass/4skip. Accepted-native323pass/2fail/4skip: identity-only replacement fixture inherited a DACL and correctly failed earlier at protected-ACL validation; corrected fixtures to use native protected exclusive creation so ID-before-ReadFile is directly exercised. Final verified-native325pass/4skip. No product safeguard was loosened to pass tests; original logs retained.

## Runtime and preservation

No Atlas/Docker status or lifecycle operation invoked; user-reported STOPPED remains inherited, not independently reverified here. Last A independent STOPPED/Engine-unavailable evidence is historical; no current database/image claim. Production inspection-control path remains absent. No real volume/helper, Genesis, production DB/payload/credential, real backup/restore, production ACL/shortcut, trading/Discord, Git stage/commit/push/reset or destructive cleanup. Only new isolated source/tests/report, diagnostic artifacts and required master checkpoint changed in F. Existing broad working-tree modifications remain pre-existing.

PAPER_ONLY/MANUAL_ONLY, permanent gaming efficiency and normal PAPER management cadence, Atlas/Genesis separation and Prediction Market Intelligence V2 retained. Required updater backup/readback/outside-managed-byte verification is recorded in result.json at finalization; historical source/report sections remain intact.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.


Phase1 additions: independent durable/current revision and recovery principal/key/proof authority, crash-safe pin handoff and external rollback witness; native true-symlink/cross-session/alternate-user/SYSTEM scope; all startup/worker/legacy/API/migration admission and failed-start/owned-stop recovery; approved fixed-root/migration policy, real ownership/image/exclusive writer window, metadata/effective storage coverage/capacity/destination/encryption/key recovery/backup/scratch restoration; Complete Shutdown real-container and shortcut migration acceptance. All cash-scope/provider rights-HTTP-budget/stuck-worker/Ruff/portability/clean-machine-runtime/Gaming/E136/Discord/PM-V2 gates remain unchanged.
