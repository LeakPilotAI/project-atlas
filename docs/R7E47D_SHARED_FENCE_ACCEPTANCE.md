# R7E47D — isolated protected SQLite and durable startup intent

**Isolated native contracts VERIFIED with remaining production security/integration gates. Production NO-GO.**

2026-10-18T08:25:06.807400-05:00 (America/Chicago). Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Read latest master/permanent contract, B/C reports and native output/startup contract. Existing source, untracked files, artifacts and failures preserved. Evidence: logs/diagnostics/r7e47d-20261018-075634.

## Implemented

New scripts/volume_inspector/shared_fence.py and tests/test_r7e47d_shared_fence.py; this report and R7E47D_INTEGRATION_READINESS.md. Existing B/C implementations, pinned helper/image lock and production lifecycle source unchanged. No new package dependency; Python ctypes/sqlite3/standard library only. Production logs/runtime/inspection-control was read-only checked absent; no production registry provisioned.

Registry.provision creates one new explicit native protected root, provision witness, native-exclusive main database, fixed SQLite schema, initial audit/revision receipt and ready witness. Current owner/SYSTEM only, no broad inherited rights or existing ACL repair. Expected instance UUID, native root/database identities, no-reparse/type/single-link checks and fresh path bindings refuse substitution. Concurrent child initializers produce exactly one winner. Existing/missing/partial/corrupt initialization is never silently reset.

Native global coordinator mutex is keyed to verified root identity and has independently checked owner/SYSTEM kernel DACL. Acquisition500ms, SQLite busy timeout0.5s and BEGIN IMMEDIATE serialize cooperating processes. Durable PENDING startup intent precedes worker creation; worker binding/admission checks exact operation, nonce, PID/creation/image/command hashes and30s window. Independent worker admission changes to STARTING; expiration, delay, crash or process disappearance never resets intent. All real launch paths remain unconnected.

Native self-only identity uses actual process/module APIs, hashes command/image without persisting raw path/command; no unrelated process enumeration. This is not a production independent worker/process proof collector. Parent/worker handoff integration and completion/shutdown reconciliation remain separate.

## Actual SQLite storage evidence

| Surface | Native observation |
|---|---|
| fence.sqlite3 | Explicit protected owner/SYSTEM DACL,2grants, no inherited broad rights; frozen native file identity |
| fence.sqlite3-journal | Actually created in PERSIST transaction;2owner/SYSTEM inherited grants verified independently |
| fence.sqlite3-wal | Actually created in WAL write;2owner/SYSTEM inherited grants verified independently |
| fence.sqlite3-shm | Actually created in WAL/concurrent connections;2owner/SYSTEM inherited grants verified independently |
| Coordinator mutex | Actual kernel DACL mapped to MUTEX_ALL_ACCESS0x1f0001; no unexpected principal/grant |

Exact per-file booleans are retained in final-native/test_native_complete_sidecar_s0/surface-evidence.json and s1. No SID strings, credentials or application records are published in these metadata files. Native restricted-token READ and WRITE opens are denied for the main file AND every present sidecar, plus mutex modification denial. The test uses Windows token enforcement, not mocked ACL callbacks. A separate ordinary login/SYSTEM write and hostile administrator were not exercised.

PERSIST/WAL use FULL synchronous and memory temps. Attachment limit0 and SQL authorizer refuse ATTACH, temp tables, journaling/sync/temp-store drift and extensions. Model SQL is bounded and fixed; not arbitrary query support or a sandbox against code holding same privileges. Ordinary SQLite close/recovery naturally cleans its own disposable sidecars; no explicit file/volume/data deletion or destructive cleanup was performed.

Every state transition and audit commit gets a unique native-flushed revision receipt. DB-only rollback, missing audit rows and DB-commit/receipt gaps refuse admission. All-files privileged rollback is not solved. Sidecar ACL/identity rejection persists a recovery latch BEFORE close can remove WAL/SHM. Abandoned coordinator also latches; future opens remain blocked, even when an independent fixture SQLite recovery proves transaction rollback. No automatic latch/uncertainty clearing exists.

## Startup races, crashes and recovery

Native cross-process provisioning and startup races, competing inspection/startup threads, concurrent WAL connections and bounded mutex contention passed. Exactly one competing admission wins. Replaced PID/creation/executable/command, nonce/op mismatch, pre-intent worker, rebind, replay and30s delay are rejected; durable intent remains blocking.

Actual child exits23 after committed parent intent: interpreter native identity and PENDING state survive, inspection remains refused. Actual child exits24 inside an uncommitted PERSIST or WAL transaction: Windows reports abandoned mutex to retained parent, persistent recovery latch remains; independent fixture-only SQLite read confirms prior revision0 rollback, without authorizing startup. Partial JSON/corrupt file, missing ready/root, main-file replacement, junction sidecar and missing receipt fail closed with evidence retained. No orphan or real service was started/stopped.

Recovery uses explicit fixture authority authorization bound by HMAC to instance/revision/state/proof and fresh exact helper exit. Forged/foreign keys, stale/future proofs, changed helper/state, boolean PID, no identity or replay are refused. Successful fixture recovery records failure/verified exit and leaves operation used, never retry/success. Production authority/key handling/trusted witness is not supplied or approved. Storage-latch and failed-start recovery deliberately have no automatic reset path.

## Results

- New D native tests:62 passed,0 failed,0 skipped.
- Existing C native:32 passed,1true-symlink privilege skip.
- Existing B adapter:105 passed,1POSIX skip.
- Existing Y helper:50 passed,1Linux skip.
- Combined final:249 passed,3 skipped,0 failed in10.91s.
- Guarded S/T/V lifecycle:82 passed,0 failed in45.81s.5tested lifecycle files match current source byte-for-byte.
- Targeted Ruff PASS;11Pythonmodules compile;18Windows scripts parse0errors; pinned helper and B/C source hashes unchanged; diff and roadmap preservation verified in final evidence. No full canonical suite/whole-Ruff waiver or Docker/native Linux rerun.

Original failures retained: initial probe rejected mutex because file-rights mask was incorrectly expected; native mutex ACL showed object-specific0x1f0001 and verifier corrected. First expanded run43pass3fail: two real WAL/SHM failure-latch defects after SQLite cleaned sidecars, fixed with persistent recovery marker; third was a wrong test assumption equating venv launcher Popen PID with interpreter PID. Native GetProcessTimes/GetModuleFileName identity is now tested without weakening equality. Earlier30pass/46pass/244pass runs retained; final249pass. No failure artifact discarded.

## Gate matrix and boundaries

| Gate | Status / evidence |
|---|---|
| Isolated provisioning/DACL/main and sidecars |PASS in native fixture scope |
| Cooperating concurrency/startup handoff/crash persistence |PASS |
| Signature-bound explicit fixture recovery |PASS as synthetic contract only |
| Real production independent authority / rollback witness |BLOCKED |
| True symlink, cross-session, alternate-user/SYSTEM execution, power-loss |NOT TESTED; inherited symlink case not waived |
| Win32 SQLite VFS hostile path/sidecar mutation TOCTOU |BLOCKED for stronger real-operation guarantee; before/after binding is not a relative-handle VFS |
| Production fixed-root provisioning/startup integration |NOT PERFORMED / BLOCKED pending approval and bridge acceptance |
| Real helper/image/ownership/writer exclusion |Not verified here; no Docker calls or dependence |
| Overall release |NO-GO; all previous cash/provider/Ruff/runtime/E136/Discord/PM-V2 gates retained |

Native registry mutex protects only cooperating clients, not external Docker clients, same-owner/SYSTEM code bypassing the API, or privileged writers. SQLite Win32 VFS still takes absolute paths; native no-follow inspections and root leases do not prove absence of an adversarial race inside its I/O. A handle-relative VFS/broker or independently justified exclusion policy is required before real use. Resource/time limits bound lock acquisition, not uninterruptible disk operations. OS flushes/receipts are not full-machine power-loss or all-files rollback protection. No such guarantee is silently accepted.

Runtime was not queried D; last A verified STOPPED/Engine unavailable remains historical, not current DB/image evidence. No Atlas/Docker lifecycle, real helper/volume, Genesis, production database/payload/secret read, real backup/restore, production ACL/shortcut, trading/Discord, Git stage/commit/push/reset, cleanup or VPS operation. Synthetic rollback/corruption fixtures contain only generated control records. PAPER_ONLY/MANUAL_ONLY, permanent gaming objective/normal PAPER cadence and separation preserved.

## Integration and remaining seven-phase roadmap

See R7E47D_INTEGRATION_READINESS.md for exact entry-point matrix, fixed-root/lock order, startup intent, authority and recovery prerequisites. All actual manager/worker/Gaming/legacy/API/standalone paths remain unprotected by the new registry today. Manual Compose/Desktop/Engine restart remains outside application exclusion.

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.


Current core: independent native VFS/security/authority review; protect fixed registry/sidecars under reviewed deployment; isolated parent-worker lifecycle bridge and failed-start/owned-stop reconciliation; all-path admission; fresh Docker ownership/image and independent exit witness; operator-exclusive writer window; separately approved real metadata/coverage/capacity/destination/key recovery/backup/scratch restore. No automatic production provision or integration follows from these tests.

Next safest proposed milestone: R7E47E independent shared-fence/VFS/security review and isolated lifecycle-bridge acceptance with mocked process/Docker actions. No production wiring, registry provisioning or lifecycle action without separate authorization.

Primary SQLite references: https://www.sqlite.org/tempfiles.html ; https://www.sqlite.org/wal.html ; https://www.sqlite.org/pragma.html#pragma_synchronous . Tested native observations determine acceptance; documentation is not substitute evidence.
