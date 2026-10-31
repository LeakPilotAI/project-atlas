# One-click lifecycle and durability contract

Date: 2026-10-19, America/Chicago. Decision: **production NO-GO; design delivered, production integration not authorized**.

This contract defines the desired operator experience and bounded acceptance work. It does not activate startup, recovery, Docker, research, PAPER automation or notifications. No lifecycle commands were executed for this review. Runtime observations below are explicitly historical.

## Current implementation and evidence

| Component | Implemented behavior | Boundary / blocker |
|---|---|---|
| Project Atlas desktop icon | Repaired target opens Windows PowerShell with `-NoProfile -ExecutionPolicy Bypass -STA -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background-Controls.ps1"`; working directory is the repository. Original icon preserved and shortcut backed up. | Opens a passive control panel, not the entire application. Status must be checked before Start becomes available. No auto-start implemented. |
| Atlas Background icon | Same approved control-panel delegation; unchanged. | Not a separate admission authority. |
| Stop Atlas icon | Still invokes `ATLAS-STOP.bat` and the blocked legacy stopper. | **Do not use**. Batch success text is not shutdown evidence. Migration needs separate approval. |
| Background manager and worker | Root lifecycle coordination, exact process creation/identity checks, worker handoff, dependency identity checks and retained failure evidence. No forced backend kill. | Shared inspection admission protocol is isolated, not integrated across production entry points. Status can reconcile stale records; it was not invoked for this source-only review. |
| Docker availability | Manager requires the intended local Engine already available; refuses otherwise. | Automatic Docker Desktop launch is not implemented or approved. No context switching or Engine repair permitted implicitly. |
| Dependencies | Validates exact Compose/container identities and waits for healthy dependencies. Existing-pair restoration and an absent-pair creation branch exist. | Creation branch uses explicit project `atlas`, while retained production identities use `projectatlas`. Never silently reinterpret ownership, create empty replacement databases or use this branch to recover missing production data. Reconcile first-install versus restore policy before integration. |
| Complete Shutdown | Opt-in exact-ID contract: backend exit before dependencies, durable pending intent, reinspection before/after stops, no automatic uncertain replay; graceful container stop without force escalation. | S/T/V isolated acceptance only. Real-container acceptance pending. Backend process exit alone does not prove application cleanup COMPLETE. |
| R7E47Q application shutdown | Four outcomes, aggregated cleanup errors, retained unresolved work, one 20-second application budget and strict shutdown checks. | In-memory report is not an authenticated durable manager acknowledgement. Uvicorn pre-lifespan drain can add another 20 seconds; manager observes 30 seconds. These are not an accepted end-to-end deadline. |
| Recovery storage and admission | Snapshot, pin, native approval, bridge and non-clearing verification prototypes exist. | No production registry provisioned; full uncertain-state recovery remains blocked. Quarantine/read-only verification grants no startup permission. |
| Research integrity | Extended-hours JSONL has an independent commitment database, pending-intent protocol, hashes and fail-closed truncation checks. | Feature disabled by default. Witness protects this journal, not every PAPER store; same-host coordinated rollback remains possible. |
| PAPER and manual state | PAPER append uses flush/fsync, with Q latching first fsync failure for shutdown. Manual state uses temporary file plus replace. | Normal PAPER append may still return after fsync failure. Manual state suppresses fsync errors, uses a fixed `.tmp` name and defaults missing state to empty. Atomic replacement alone is not proven power-loss durability or evidence that missing prior state is safe. |

Historical runtime evidence: `desktop-launcher-repair-20261019` observed Atlas stopped/no listener at 2026-10-19 09:27:05Z (04:27 CDT). At approximately 09:26:10Z, `desktop-linux` Engine 29.8.1 was available. PostgreSQL ID `c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1` and Redis ID `13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193` had verified `projectatlas` ownership and were EXITED, PID 0, exit code 0. Retained health labels were unhealthy, not fresh readiness. These are not fresh observations or authorization to use cached identities.

## Future one-click startup contract

One intentional click may execute an already approved policy. It must not silently manufacture new recovery, provider, unattended PAPER or container-creation approval.

1. Acquire Atlas operation coordination; allocate a unique operation ID. Recheck current owner PID, creation time, executable, command line and run ID. A duplicate click attaches to the same operation or reports existing state. Conflicting Stop/Start is refused or serialized before side effects. An unused port is not proof of STOPPED.
2. Validate protected admission state before starting Docker dependencies or research. Missing, corrupt, substituted, unfinished or UNCERTAIN recovery evidence refuses admission. Distinguish explicitly provisioned first installation from lost existing state. Manager durable startup intent must precede worker creation; worker independently verifies exact intent and identity. Cover supported GUI/manager/worker, legacy launchers, direct API and standalone Atlas writers before claiming exclusion. External Docker writers and administrators remain outside Atlas's lock boundary.
3. Query only the approved Docker Desktop Linux context with bounded responses. An unavailable Engine is UNKNOWN, not proof that Docker is stopped. Never switch context silently.
4. Future Desktop auto-launch requires an explicit operator-approved shared-Engine policy. Launching Docker can reactivate other projects through restart policies; absence of an Atlas command against another project does not prove no effect. Do not inspect Genesis to establish this policy. If safety cannot be established without doing so, require the operator to make Docker available independently. If Desktop is already present but Engine unavailable, bounded wait then refusal; no restart, service repair, termination or settings change.
5. Freshly validate the complete PostgreSQL/Redis pair: immutable container IDs, image identities, Compose project/service/configuration/work-directory labels, expected mounts and volume ownership. Container names alone never authorize an action. Missing or replaced production resources require explicit reconciliation; never recreate empty stores as recovery.
6. Only an approved dependency-start policy may restore the verified pair. Revalidate before every action and after completion. Start databases before clients; readiness requires current exact-container health and database connectivity, without logging credentials. Partial availability is not full readiness. Migration/schema compatibility requires separate validation; `create_all` is not a migration plan.
7. Start the exact admitted worker/backend; bind its actual process and runtime configuration to the operation. Confirm API and dashboard responsiveness, owned workers, database connections, journal consistency and PAPER reconciliation. Do not infer effective environment from a parent shell or configuration file alone.
8. Confirm PAPER_ONLY/MANUAL_ONLY, live-capital denial, risk stops and both central automated Discord sender denials. MANUAL_ONLY does not mean every simulation lane is manual: existing auto-PAPER lanes need an explicit documented operator policy. Prediction unattended/new opens remain disabled unless separately approved; pre-event and one-position restrictions remain intact.
9. Verify each permitted feed's actual timestamp, freshness, session coverage, provider budget and rights. HTTP 200 is service liveness, not market-data freshness. Premarket quotes do not establish continuous premarket scanning. Extended-hours opt-in and cash C1–C4 scope remain unapproved; do not activate them through normal or Gaming launch.
10. Report **READY** only for the independently verified coverage. Otherwise show STARTING, DEGRADED, FAILED or UNKNOWN with specific failed checks. Do not display full-market READY when only crypto or service health passes. Preserve operation evidence and use only verified Atlas-owned rollback controls; retain ambiguous ownership rather than force cleanup.

Normal and Gaming launches must explicitly select their effective mode rather than inherit an accidental shell value. Gaming discovery cadence and normal PAPER management cadence require actual-process verification and benchmarks, not source-only assertions.

Docker restart policy implications: [Docker restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/). The existing Compose source uses `unless-stopped`; no restart-policy changes are authorized here.

## Future one-click shutdown contract

The future safe Stop Atlas icon must delegate to the verified manager, with an explicitly selected complete-stop policy and a separate developer backend-only mode. Do not repoint or execute the legacy icon in this milestone.

1. Bind Stop to an exact owned run and durable operation identity; prevent new startup admission. Close ingress for new scans, PAPER opens and provider requests. Define handling of existing simulated positions during drain; do not invent exits or silently flatten results.
2. Quiesce every Atlas-controlled writer, cancel cooperative jobs and drain bounded queues. Track queued, running and off-loop operations individually. Cancellation is not proof a blocking third-party call ended. Late results must not write after final shutdown confirmation.
3. Flush committed research and PAPER state, reconcile unknown acknowledgements using event identities, close client connections and verify producer/sampler/provider exit. Continue independent cleanup where safe; preserve original and subsequent errors. Never close storage underneath a writer whose exit is uncertain.
4. Publish a protected, durable, run-bound application outcome with cleanup results, pending work and commit evidence. The manager must verify this acknowledgement **and** exact backend exit. Logging success, PID disappearance, a stop request or an old manifest is insufficient. A crash without valid acknowledgement yields UNKNOWN, not COMPLETE.
5. Only after verified required cleanup and backend exit, revalidate the exact dependency pair. Backend-only stop leaves dependencies intact. Complete stop requests graceful shutdown by verified immutable IDs; stop independent databases only after all Atlas clients release them. Do not invent a database ordering dependency where none is proven.
6. Preserve pending request receipts before Docker calls. No force kill, broad name matching, `down -v`, prune, global termination or deletion. Bound observation; if graceful shutdown does not finish, retain unresolved receipt and report it. Never auto-replay uncertain stop requests.
7. Reinspect the entire pair and backend to detect replacement/restart; record actual final states. Leave Docker Desktop, Engine, networks, containers, images, volumes, journals and unrelated resources intact. External clients can still race; this limitation must remain visible.

| Final outcome | Required meaning |
|---|---|
| COMPLETE | Every required cleanup succeeded, exact processes exited, and every selected dependency is verified stopped; no required evidence missing. Backend-only COMPLETE explicitly excludes container shutdown. |
| INCOMPLETE | A required step is known to have failed; preserve all errors and actual resource states. |
| TIMED_OUT | The declared observation/drain deadline expired; pending work may remain. No force escalation or false COMPLETE. |
| UNKNOWN | Identity, acknowledgement, storage or Engine evidence is insufficient/contradictory. Retain refusal and evidence. |

Use an absolute monotonic deadline per operation, with explicit reserved time for persistence and reporting. Do not merely raise timeouts to pass tests. Current 20/20/30-second layering requires isolated adjudication and subsequent runtime acceptance. A full disk or reporting failure must leave a truthful failure, not erase earlier errors. No new work or journal writes are allowed after **final COMPLETE**; a timeout is not final cleanup confirmation.

## Durability and recovery contract

### Acknowledgement boundary

Distinguish RECEIVED, IN_FLIGHT, DURABLY_COMMITTED, UNKNOWN_COMMIT and RECONCILED. Only acknowledge durability after the required storage commit/flush and integrity commitment succeed. An interrupted operation can be absent, pending or committed with its acknowledgement lost. Use stable source/event/action identities and a unique durable deduplication constraint; reconcile unknown commits before replay. Do not fabricate fills or assume exactly-once behavior from a source identity alone. Cross-store PAPER/journal/database updates are not one atomic transaction unless demonstrated.

Current PAPER fsync suppression and manual snapshot fsync suppression are **confirmed source-level gaps** for a strict durable-acknowledgement promise. Q improves shutdown reporting but does not fix ordinary caller acknowledgement or make its in-memory error latch survive power loss. Missing manual state returning an empty default must not be reused as permission to erase an established session. These findings are recorded, not repaired in this documentation milestone.

### Files and integrity

Atomic replace prevents some partial visibility; it does not alone establish power-loss persistence, correct Windows identity-before-access, independent rollback detection or complete multi-file publication. Require exclusive temporary publication, bounded validated contents, verified identities, actual flush errors propagated, and native publication/reopen/crash evidence. Preserve interrupted artifacts; never auto-truncate a corrupt journal or reset a witness. Verify database/journal/WAL/SHM sidecars together where applicable.

The extended-hours journal commitment detects missing committed records in its demonstrated scope. It does not make all `backend/data` files durable, exclude external writers, or defeat coordinated rollback of both journal and witness. Snapshot/pin prototypes and non-clearing verification remain isolated. An actual UNCERTAIN record cannot be bypassed by relabeling a launch normal operation.

### PostgreSQL and Redis

PostgreSQL committed-transaction survival depends on effective WAL/flush configuration and honest OS/storage flush behavior. Verify actual `fsync`, `synchronous_commit`, `full_page_writes`, storage mapping and crash recovery in separately authorized acceptance; configuration defaults are not observations. Lost commit acknowledgements require transaction identity reconciliation. See [PostgreSQL WAL configuration](https://www.postgresql.org/docs/16/runtime-config-wal.html) and [storage reliability](https://www.postgresql.org/docs/16/wal-reliability.html).

Redis must first be classified as disposable cache or required durable state per consumer. RDB and AOF have different loss windows and replay properties; actual persistence policy and paths have not been verified here. A named `/data` volume does not prove required state was persisted. Measure accepted RPO/RTO using isolated recovery. See [Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).

Do not promise zero loss across power failure, device failure or full-machine rollback. Separate acknowledged commits from unacknowledged in-flight operations and state the tested fault model. Process termination tests are not physical power-loss tests.

### Backups and restoration

No usable independent data backup and isolated restoration acceptance has been established by the retained gates. Source archives are not database backups. Planned scope includes exact PostgreSQL/Redis volumes, complete host evidence and PAPER state, journal commitments/sidecars, schema/migration/code/image metadata, and separately protected configuration needed for restoration. Secrets must never enter ordinary diagnostic output.

Account for effective PostgreSQL data/WAL/tablespace locations, Redis RDB/AOF configuration, symlinks and host state before asserting complete coverage. Read-only mounts alone do not prove writer exclusion or snapshot consistency. A cold copy requires proven quiescence; an online backup needs a database-supported consistent procedure. Neither is authorized here.

Require independently recoverable backups, capacity/headroom, integrity manifest, known provenance, retention and protected key recovery. Same-disk copies do not protect against disk loss. Measure and obtain operator acceptance of RPO and RTO; do not invent targets. Restoration must use isolated destinations and verify records, commitments, deduplication, schema and restart behavior before any production recovery proposal. Never restore stale PIDs, grants or live authority as startup permission. Failed/interrupted backups or restores retain evidence and cannot replace the last verified backup.

### Unclean recovery

Detect unfinished operation intents, pending commitments, incomplete shutdown receipts and inconsistent snapshot/pin revisions. Permit bounded read-only verification and non-clearing quarantine only within demonstrated scope. Missing helper evidence, Docker EXITED, timeout or an operator click alone cannot clear uncertainty. Independent exact-helper exit, valid revision-bound authority and required writer exclusion remain separate full-recovery gates. Freeze further broad security redesign; pursue normal-operation reliability independently, without bypassing any actual uncertain state. Privileged administrators, external Docker clients and full-machine compromise are outside the proven local boundary.

## Failure acceptance matrix — specification, not executed results

All new fault tests start with disposable synthetic stores/processes. Real Engine/container/VM fault tests require separate bounded approval and verified ownership. No production power cutting, disk filling, database crash or Engine interruption is authorized.

| Case | Required evidence and refusal behavior |
|---|---|
| Normal startup/shutdown | Exact operation/process/container identities, DB readiness, actual mode, fresh market coverage, durable outcome and no owned orphan writers. |
| Power loss during collection | Disposable VM/storage fault harness; distinguish acknowledged commits from in-flight loss; replay/deduplication and corruption evidence. Child-process kill alone cannot pass power-loss durability. |
| Process crash during journal publication | Kill fixture before intent/after intent/during append/after fsync/before acknowledgement; never grant false commit or silently repair pending state. |
| Database crash | Disposable database transaction/WAL recovery with lost-ack replay and unique-action enforcement; no missing acknowledged transactions within declared configuration/hardware assumptions. |
| Engine interruption | Isolated Engine test, exact helper/daemon ambiguity retained, no inferred exit or automatic uncertainty clearing. |
| Network outage | Bounded retries/queue, stale feed shown, no fresh marks invented or pending send blindly retried. |
| Duplicate launcher activation | One durable intent, one admitted worker, no duplicate PAPER action or dependency creation. |
| Concurrent Stop and Start | Serialized admission; no new writer after quiescence; interrupted operation retains refusal. |
| Partial database availability | Full READY refused; safe independent cleanup; no automatic empty-store recreation. |
| Corrupt/missing recovery records | Fail closed before side effects; distinguish authorized first provisioning from lost established state. |
| Full disk | Small disposable quota/fault injection; append/fsync/commit/audit errors propagate; previous committed state preserved; no false COMPLETE. |
| Failed backup | Invalid manifest/provenance prevents acceptance; prior verified backup untouched; no startup authority inferred. |
| Interrupted restoration | Isolated target remains incomplete/quarantined; source untouched; no activation until independent validation. |
| Blocking worker / deadline | Retained worker ownership, bounded observer, TIMED_OUT/UNKNOWN; no late final-confirmed writes and no claim cancellation terminated native I/O. |
| Logging/acknowledgement failure | Original error survives secondary reporting failure; missing durable report never becomes COMPLETE. |
| Container replacement / shared Engine | Recheck exact IDs before and after actions; abort on change; Atlas-only action evidence cannot prove external-writer exclusion. |

Each test report must record commit point, injected fault, initial/final hashes and revisions, expected and observed outcome, elapsed budget, unresolved processes and repeatability. Native Windows acceptance cannot be replaced by mocked ACL assertions. Fresh runtime tests must not be inferred from historical isolated passes.

## Separate future live-money certification

No trading authority is added by this contract. Before any separately proposed live use: reconcile broker/exchange orders, fills, partial fills, balances and positions against external truth; use durable client order IDs and resolve UNKNOWN submission before retry. Validate fees/funding, rejected/canceled orders, disconnect and rate-limit behavior. Establish independently operable kill switches, maximum loss and gross/net exposure limits, stale-data refusal and auditable manual intervention. Emergency flattening can fail, partially fill or be unavailable; it is not a guaranteed escape. Require independent security/audit and strategy/risk certification with measured evidence. PAPER success is not live execution certification. Keep all Prediction Market Intelligence V2 pre-event, one-position and no-combination safeguards; no stacking, averaging or opposing YES+NO authority.

## Bounded execution sequence and exact blockers

| Priority / next bounded work | Allowed offline deliverable | Separate runtime/operator gate |
|---|---|---|
| 1. Strict durable acknowledgement | Audit PAPER/manual commit boundaries; minimal error propagation, unique publication and synthetic crash/full-disk/replay tests. No storage-engine redesign. | Native disposable filesystem crash acceptance; no production data migration implied. |
| 2. Shutdown completion handshake | Design/test durable run-bound app acknowledgement, queue admission closure and one end-to-end drain budget; preserve exact ownership and all failures. | Explicit production lifecycle integration approval, then one controlled runtime trial. |
| 3. Storage/backup acceptance | Reconcile documented storage coverage, backup scope, capacity and isolated restore criteria; retain existing helper restrictions. | Separately authorize exact read-only volume helper, backup creation and isolated restoration as distinct actions. |
| 4. One-click admission and Docker policy | Minimal manager/worker/GUI integration proposal and mocked tests; resolve `atlas` versus `projectatlas`, first-install versus restore, normal/Gaming environment selection and shared-Engine auto-launch policy. | Production admission provisioning/integration and Desktop launch require explicit approval. No uncertainty bypass. |
| 5. Stop icon and dependencies | Prepare verified complete/backend-only UI and shortcut migration package; identity/partial-failure tests. | Operator approves shortcut change and exact-container stop/restore acceptance; leave Desktop/Engine running. |
| 6. Release and data rights | Resolve bounded Ruff disposition, regenerate current release artifact, dependency licenses, cash C1–C4 decision package, provider actual HTTP budgets/rights and stuck-worker criteria. | Provider use and cash scope require explicit acceptance; no silent waiver or activation. |
| 7. Runtime and gaming | Prepare bounded market freshness/PAPER reconciliation and CPU/RAM/discovery/management cadence test plans. | Separately approved runtime session and sustained gaming benchmark; current controlled-trial history is not blanket unattended permission. |
| 8. Optional notifications / live capital | Keep E136 consent/recovery, no-backfill and uncertain-delivery gates separate. Live certification remains future. | No automatic Discord or real-money activation without their own explicit evidence and authorization. |

**Single recommended next execution:** offline strict PAPER/manual durable-acknowledgement adjudication and fault tests, bounded to the identified fsync/publication defects. Do not start another general recovery-security redesign. This milestone itself stops at the contract decision.

The authoritative 21 gates retain their identities, ownership, evidence and decisions in `R7E47O_PHASE1_RELEASE_GATE_MATRIX.json`: 5 scoped PASS, 13 BLOCKED, 3 NOT_TESTED. This document grants no gate PASS. Exact blockers: production admission, full recovery, current-candidate backend acceptance, real Complete Shutdown, safe Stop workflow, backup/restore, actual HTTP budgets, provider rights, cash scope, stuck-worker acceptance, lint disposition, clean-machine acceptance, gaming performance, E136 recovery, Discord activation and extended-hours activation. Source artifact PASS remains historical, not acceptance of the current dirty candidate.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

## Review evidence and validation

Source review: approved Windows manager/controls/Complete Shutdown module; R7E46T, R7E46O migration, R7E46W backup, R7E46Y approval package, R7E47N and Q reports; application shutdown, database session and manual state store. Historical Q acceptance: 187 focused + 40 PAPER + 82 lifecycle = 309 passed, zero failed/skipped; historical Ruff 3,977 remains unresolved. These tests were not rerun for this documentation-only contract. Current validation is documentation coverage, source/shortcut preservation, 21-gate equality, Git integrity and roadmap checkpoint verification. See `logs/diagnostics/one-click-lifecycle-contract-20261019/result.json`. Initial system Python alias was unavailable; repository virtual-environment Python was used successfully. No product failure inferred.
