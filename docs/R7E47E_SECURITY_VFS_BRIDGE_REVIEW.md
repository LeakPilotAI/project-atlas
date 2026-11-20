# R7E47E — independent security/VFS review and isolated lifecycle bridge

**Isolated bridge acceptance PASS. Required SQLite/VFS security acceptance BLOCKED. Future production startup integration BLOCKED. Production NO-GO.**

Review completed 2026-10-18T08:40:49.401472-05:00, America/Chicago (CDT, UTC-05:00). Branch chatgpt/atlas-rebuild-v1, HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Evidence: logs/diagnostics/r7e47e-20261018-083029. Latest master checkpoint/permanent recovery contract, B–D reports, complete shared_fence.py and tests, and integration matrix reviewed. Input SHA-256 manifest retained. This is a fresh source-based assessment; no claim of an external human penetration test.

## Independent threat model

Assets: startup exclusion, exact inspection/helper/operation identities, durable uncertainty, consent to recovery, registry/audit/receipt integrity, protected metadata and preserved evidence. Trust roots: approved fixed registry instance and location, native Windows security implementation, intended owner/SYSTEM, approved program/identity collector and independent recovery authority. Production instances, authority and binding are NOT provisioned.

| Attacker/failure capability | Actual mitigation and evidence | Residual risk / disposition |
|---|---|---|
| Unapproved/restricted token opens main or sidecars | Native protected owner/SYSTEM directory plus independently verified main/journal/WAL/SHM ACLs; D restricted-token READ/WRITE and mutex denial rerun | PASS within this local token/NTFS scope; ordinary alternate login/cross-session SYSTEM not tested |
| Preexisting junction/reparse, hard link, wrong instance/main file | Native no-follow relative checks, root leases, single-link check, pinned root/main ID, expected UUID; D junction/replacement tests and E main hard-link refusal pass | True symlink creation lacks privilege1314; cannot waive. Path checks are not SQLite VFS interception |
| Malicious same-owner or privileged file substitution between checks | Later main-ID mismatch latches recovery; native E reproduction confirms this happens AFTER SQLite opened and queried a substituted synthetic DB | BLOCKED for identity-before-access guarantee; owner can modify registry files/ACLs, code and witnesses. No admin/SYSTEM threat exclusion claimed |
| Sidecar replacement with correct restrictive DACL | Type/link/ACL checked whenever present | E native test substitutes an empty journal with a different file ID and surface() accepts it. Sidecar continuity is NOT enforced, and legitimate SQLite sidecar recreation means simple permanent-ID pinning is insufficient |
| Cooperative concurrent start/inspection/create | Global native coordinator, BEGIN IMMEDIATE, durable PENDING/UNCERTAIN, exclusive used IDs and revision receipts; E simultaneous admission and duplicate-create tests pass | Only clients using fixed same registry and code cooperate; external Docker/SQL/manual writers bypass |
| Missing, malformed, partial, corrupt, rollback or unavailable registry | Exclusive initialization, expected instance/receipts/audit chain, fail-closed reads and persistent failure latch; D/E corruption/ACL/identity/crash rerun | No initialize-on-missing/reset. If storage cannot accept latch, no durable new failure evidence can be promised; startup still refuses |
| Parent crash, worker replacement, stale/replayed intent | Durable intent before spawn; one-use create claim; independently observed synthetic identity, nonce/operation/30s bounds; exact worker admission before effects | No actual process ownership proof, trusted handoff IPC, startup completion or owned-stop/failed-start recovery contract supplied |
| Forged/replayed recovery or altered proof/revision | Fixture HMAC binds instance, revision, complete state and fresh exact helper proof; E missing/forged/replaced/running/stale cases refuse | Ephemeral fixture key is in same process, not independent production authority; all-files rollback and privileged key theft outside guarantee |
| Interrupted SQLite transaction/coordinator | Native child-crash PERSIST/WAL recovery and abandoned-mutex persistent latch rerun; receipt gap refuses | OS flush/crash evidence is not physical power-loss acceptance. Missing last mutex handle may erase kernel abandonment evidence; durable records remain essential |
| Lock inversion/unbounded external call | Registry lock500ms and SQL busy0.5s; bridge returns from transaction before synthetic spawn/dependency effects, tested | Actual outer lifecycle lock not connected; native disk I/O can block. No hard I/O deadline or external writer exclusion |

## SQLite/VFS decision — NO for the stronger required guarantee

The present standard Win32 path-based connection cannot demonstrate that every SQLite open uses the native file identity that was checked. E test test_native_main_substitution_open_precedes_rejection injects the adversarial interval at sqlite3.connect, performs real NTFS rename/copy of disposable generated databases, queries a fixture-only marker through the actual SQLite connection, and then observes main-ID refusal and a persistent recovery marker. The original main file is retained. No production database or payload is read. This is a deterministic attack reproduction, not a mocked identity verdict and not an assertion of successful exploitation under an unrelated restricted token.

The second native reproduction, test_native_sidecar_identity_continuity_not_enforced, retains the original and previous empty synthetic journals, creates a new protected empty journal and confirms different native file identities pass the current ACL surface check. The test documents a missing guarantee; it does not approve it. Configuration PRAGMAs in database() also precede its post-connect surface check, so eventual refusal must not be described as proof of no foreign file access or effects. Shared-fence D source is preserved unchanged: no quick permissive fix or stronger security claim.

SQLite documents that the VFS mediates file opens and other OS I/O, and that Windows normally uses win32. Native checks outside that VFS are not an atomic substitute. [SQLite VFS](https://www.sqlite.org/vfs.html). WAL adds a shared-memory sidecar; a main-file handle alone cannot cover the full surface. [SQLite WAL](https://www.sqlite.org/wal.html). These sources support architecture only; local native tests determine the decision.

## Narrow alternatives and minimum acceptable contract

1. Ordinary Win32 SQLite under an explicitly trusted, cooperative owner and exclusive maintenance policy: simplest, but DOES NOT satisfy the stronger hostile same-owner/substitution guarantee. Would require an explicit narrower threat-model decision, independent fixed-root authority and external-writer operational exclusion. Not silently accepted here.
2. Hold independently checked native main-file handles denying write/delete sharing: helpful to prevent replacement, but ordinary SQLite needs compatible writes and manages its own journal/WAL/SHM opens. A main-file lease does not cover sidecars or same-identity content writes; cannot declare this sufficient without a tested compatible open policy.
3. Recommended smallest prototype: native handle-relative verified immutable generation files, read bounded serialized SQLite bytes through the verified handle into an in-memory engine, write a new immutable serialized generation and no-replace commit witness through existing native publication, plus single shared coordinator and independently bound revision/head authority. This removes live path-based SQLite/sidecar I/O from the control store, but requires crash/commit/rollback and same-owner threat acceptance; design only, NOT implemented or selected for production in E.
4. Separate-principal broker or custom handle-relative VFS could provide a stronger boundary. Both are larger changes; no extensive replacement VFS/broker implemented or approved.

Minimum before integration: independently protected fixed root/instance, explicit trusted-writer threat model, demonstrated identity continuity before every relevant read/write, no-follow/single-link controls across the complete storage surface, atomic durable state/audit commitment with crash refusal, independent anti-rollback/recovery authority, reviewed lock order, authenticated real process/handoff/helper proof, all-entry admission, and explicit failed-start/owned-stop reconciliation. If one is unverified, integration remains BLOCKED. No application fence controls privileged administrators or external Docker writers.

## Isolated bridge implementation

New scripts/volume_inspector/lifecycle_bridge.py and tests/test_r7e47e_lifecycle_bridge.py only; no production module imports them. IsolatedBridge accepts exact fixture Registry and FixtureWorld types, not a real transport/subprocess/Docker interface. Its identity table is synthetic independent observation, not actual Windows process proof. Generated identities/callback effects contain no application evidence or telemetry.

Manager admission commits PENDING/receipt before any synthetic create. Before creation a second transaction validates parent/op/nonce/window and commits an immutable used-table namespace claim bridge-worker-create:<operation>. Concurrent or restarted callers cannot duplicate that create. Spawn/bind interruption retains PENDING and used claim; there is no automatic retry. Bind checks independently observed exact worker identity, followed by independent worker admission to STARTING before the synthetic dependency effect. No dependency or API actually starts. Child replacement, delay, replay, missing/corrupt registry, ACL/identity change and uncertainty refuse effects.

Inspection admission serializes against startup, records UNCERTAIN before any simulated helper binding, and refuses a synthetic active writer. Missing/unreachable/changed/running helper never clears state. Recovery independently obtains fixture exit facts and requires a revision-bound fixture grant; successful recovery records failed-inspection exit proof, consumes operation and never starts/replays an inspection. The bridge uses Registry._change for its narrow immutable create claim and fixed audit event; this private API coupling must be reviewed/versioned before any future implementation reuse.

No synchronous child wait/external call occurs under registry guard; tests assert lock depth zero at synthetic create/dependency effects. Production outer lifecycle-gate ordering remains unimplemented. Parent restart test is a close/reopen with removed fixture parent; actual process-crash and interrupted transactions are separately provided by rerun D native children.

## Acceptance results

| Suite/check | Exact result |
|---|---|
| New E bridge/native adversarial tests |33 passed,0 failed,0 skipped |
| Existing D registry |62 passed |
| Existing C native output |32 passed,1 skipped |
| Existing B adapter |105 passed,1 skipped |
| Existing Y helper |50 passed,1 skipped |
| Combined accepted-native.txt |282 passed,3 skipped,0 failed;14.01s |
| Guarded S/T/V lifecycle |82 passed,0 failed,0 skipped;45.66s |
| Total final tests |364 passed,3 skipped,0 failed |
| Targeted Ruff |PASS across helper directory and five test modules |
| Compilation / Windows parsing |13 Python files compile in memory;18 PowerShell scripts parse,0 errors |
| Current lifecycle vs guarded snapshot |5 exact source hashes match; D source/tests/reports unchanged |
| Git diff |PASS; final evidence verifies checkpoint and preservation |

Skips: native true-symlink creation privilege unavailable; POSIX publisher native case on Windows; helper Linux descriptor case on Windows. Historical Z Linux acceptance is preserved, not rerun. No full canonical suite or whole-tree 3,997-findings lint waiver. Existing inherited lint/release gates remain.

Original first-native.txt has27 passed/1 failed: PERSIST had already retained a journal, so an exclusive fixture create correctly refused collision. Test corrected to preserve/rename that initial journal, not overwrite it. First Ruff reported one blind Exception assertion; narrowed to OSError/ValueError/sqlite3.Error. Intermediate final-native.txt281passed3skipped preceded the added durable create-claim regression; final accepted-native.txt282passed3skipped is authoritative. All originals retained; no failures hidden.

## Integration/release-gate decision

| Gate | Decision / exact next need |
|---|---|
| DI synthetic lifecycle bridge, single-use create, races/refusal/recovery |PASS in fixture scope |
| Native protected DACL/restricted token, hardlinks/junction and fail-closed crash evidence |PASS within tested scope; true symlink/cross-session remain NOT TESTED |
| Identity-before-SQLite-access and sidecar continuity |BLOCKED by two passing attack reproductions |
| Fixed trusted deployment, independent anti-rollback/key/recovery/process/helper authority |BLOCKED; fixture authority is insufficient |
| Failed-start and normal owned-stop intent reconciliation |BLOCKED; intentionally no automatic reset API |
| All actual startup paths and outer lock order |NOT INTEGRATED; approval prohibited in E |
| Real Docker/writer exclusion, volume metadata/coverage/capacity/backup/restore/lifecycle |NOT TESTED / separately approved gates |
| Future controlled production startup integration |BLOCKED; security contract has not passed |
| Overall production release |NO-GO |

If security gates later pass, minimum modifications would cover scripts/windows/Atlas-Background.ps1 parent Start and worker before dependencies/API, common lifecycle admission/ownership module, Gaming/Controls delegation, guarded legacy Atlas-Launch.ps1/ATLAS.bat paths, Desktop smoke launcher, backend/app/main.py/direct API pre-import admission and standalone writer/migration entry points. Add independent proof/config/recovery modules and cloned tests first. GUI checks alone or lifespan-only checks are insufficient. No production file in that list changed E. Shortcut migration remains a separate approval. Manual Compose/Desktop/Engine writers remain outside Atlas control.

Safest next proposal: **R7E47F isolated handle-bound snapshot-store proof and independent authority decision**, testing the narrow alternative without production wiring/provisioning or an extensive replacement VFS. First accept the explicit minimum threat contract; then prototype only the bounded storage primitive, native substitution/sidecar elimination, crash commitments and rollback/refusal. Separate approval is required; E stops here.

## Runtime, safety and preservation

No Atlas/Docker status command or lifecycle action was invoked E. User reports STOPPED; last independently queried A status/Engine-unavailable evidence is historical, not fresh database/image/process proof. Production inspection-control path remains absent at final source check. No production registry, ACL, volume mount/helper, backup/restore, shortcut, trading/Discord, Genesis, Git stage/commit/push/reset or destructive cleanup. PAPER_ONLY/MANUAL_ONLY, permanent gaming efficiency/normal PAPER cadence, project separation and PM-V2 preserved.

Existing tracked/untracked work and original failure evidence preserved. Read-back/backup/outside-marker-byte verification is recorded in result.json after the required updater. Updated full master remains the authoritative downloadable TXT; do not interpret historical GREEN sections as current release approval.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.


Current phase1 security/recovery additions: resolve native identity-before-I/O/sidecar continuity via a reviewed narrow storage design; independent fixed-root/rollback/key/process/helper authority; failed-start/owned-stop reconciliation; all startup entry admission and outer lock order. True symlink/cross-session/alternate-user/SYSTEM and power-loss acceptance remain unverified. Real ownership/image/exclusive writer window, metadata inspection, effective configuration coverage/capacity, destination/encryption/key recovery, backup and scratch restore require distinct authorizations. Complete Shutdown real-container acceptance and desktop migration remain blocked. All previous cash-scanner, provider rights/HTTP/stuck-worker, Ruff, clean-machine/runtime/Gaming, E136/Discord and Prediction Market Intelligence V2 gates unchanged.
