# R7E47M — writer exclusion and independent quiescence feasibility

**Overall feasibility: BLOCKED for recovery that clears uncertainty or permits startup. Production integration NO-GO. Production release NO-GO.** A narrower exact-file read-only lease is demonstrated on disposable NTFS fixtures; it is not an Atlas-wide barrier or Linux-helper exit proof.

2026-10-18, America/Chicago CDT UTC-05:00. Branch `chatgpt/atlas-rebuild-v1`, HEAD `f9df47b4cd80dd647d85043aba617cf00c4e6dc0`. Evidence: `logs/diagnostics/r7e47m-20261018-225823`. Latest master and G–L reports, snapshot/manual policy, H startup proposal, actual manager/worker, desktop-control, Compose and ownership source reviewed. D–L36source/report/fixture files and five lifecycle modules preserved by hash. No production integration or registry provisioning.

## Writer inventory — capability and resource, not a live process census

No production entry point currently imports the isolated inspection snapshot/fence policy. Existing production writers primarily modify lifecycle, research, PAPER, database and other runtime state. Future admission must cover their entry points before side effects; current process ownership checks alone are not inspection admission. Source AST scan records165candidate files in `writer-source-candidates.json`, with paths/line numbers/call kinds/hashes only. This is reproducible candidate discovery, not complete dynamic alias analysis or proof that all writers are running/stopped.

| Atlas-controlled component / exact source | Writer capability and resource | Inspection exclusion today |
|---|---|---|
| `scripts/windows/Atlas-Background.ps1` parent Start/Stop/Worker/StopWorker and status reconciliation | `logs/runtime` owner/start/stop/recovery locks, stop request, stale-session archives, stdout/stderr; can create worker/dependencies/API. Status can reconcile metadata, so it was not executed | Existing lifecycle identity/gates, no production inspection registry admission |
| Same manager `Invoke-BackgroundWorker`, dependencies and API launch | Rebinds run/PID/creation/executable/command identity, writes locks/owner, supplies desktop control directory/run, invokes Compose then uvicorn | Independent worker ownership checks exist; inspection admission before side effects is proposed |
| `backend/app/services/desktop_control.py` | Creates `runtime.json`, observes `stop.json`, removes matching-run manifest during shutdown | Run-bound lifecycle handshake, not inspection fencing |
| Direct `python -m uvicorn app.main:app`, debug/reload and `backend/app/main.py` imports/lifespan | Redis connection, schema creation, PAPER bootstrap, scanners/trackers/automation/accumulation/investment/extended-hours services, desktop control; shutdown persists PAPER marks/interruption evidence | Can bypass manager, no production inspection admission |
| `scripts/windows/Atlas-Background-Controls.ps1`, `Atlas-Background-Gaming.ps1`, `Atlas-Background-Ui.psm1` | GUI/wrapper delegates manager; creates temporary stdout/error diagnostics; Gaming sets child launch environment | GUI is not an authoritative fence; manager/worker must enforce |
| `ATLAS.bat`, `start-atlas.bat`, `scripts/windows/Atlas-Launch.ps1`, `Atlas-Stop.ps1`, `Atlas-Desktop-Smoke.ps1`, readiness/setup/pull/install scripts | Legacy API/dependency launch/stop/bootstrap/configuration or readiness workflows; possible write-capable imports/setup and desktop shortcut operations | Legacy bypass paths require reviewed migration; none executed/modified |
| `scripts/windows/Atlas-CompleteShutdown.ps1/.psm1`, `Atlas-ProcessOwnership.psm1`, `Atlas-ContainerOwnership.psm1` | Shutdown intent/receipts/ownership reconciliation and controlled dependency lifecycle when authorized | Positively pinned ownership protects target selection; does not establish all-writer exclusion |
| `scripts/investment_scan.py`, `investment_live_probe.py`, `investment_research_probe.py` | Standalone investment imports/bootstrap/scans, history directories, snapshots/opportunities and collector output | Must admit before imports/bootstrap; no production inspection guard |
| `scripts/atlas_watchdog.py`, `runtime_recovery_soak.py`, prediction PAPER smoke and diagnostic/release utilities | Local state/output files; API requests can trigger indirect writes; artifact builders and lint audits write selected destinations | Their selected output/API resource scopes need separate classification; read-like name is not proof of read-only behavior |
| `backend/app/services/paper_journal.py`, `paper_pipeline.py`, PAPER mirrors/risk/observability, prediction/investment/quality-dip services | PAPER journals/candidates/funnel/risk controls and strategy evidence; API routes and schedulers share these providers; main shutdown can also write | Existing trading restrictions remain, but not a storage-wide inspection barrier |
| `backend/app/services/discord_lifecycle_outbox.py`, consent generation/witness/coordinator/delivery/recovery, `paper_lifecycle_producer.py` | SQLite state/sidecars, consent/outbox/recovery receipts and synthetic producer journals at explicitly supplied paths | E136/producer integration remains isolated/gated; not authorized by M |
| `scripts/volume_inspector/shared_fence.py`, `snapshot_store.py`, `manual_handoff.py`, `native_recovery.py`, isolated adapter/output/proof/policy/barrier modules | Explicitly provisioned fixture SQLite/snapshots/witness/pins/intent/ack/approval/audit and lease files | Only disposable or proposed roots; no production provisioning/import. These are direct inspection-state writers in tests |
| `scripts/volume_inspector/helper.py` and approved pinned image plan | Linux metadata inspection/stdout; planned source mounts read-only, host protected publication performed by adapter | No real helper executed M. Read-only mount does not exclude independent writers or prove helper exit |
| Atlas PostgreSQL/Redis in `docker-compose.yml` | PostgreSQL data/WAL/checkpoint/background tasks and Redis persistence/cache state; direct DB clients can induce writes even without API | Ownership labels/EXITED observations are observations. No Windows file lease can fence Linux named-volume writers |
| Roadmap updater / build and diagnostic tooling | Master/checkpoint backups, release archives/manifests/logs | Documentation/artifact resources, separate from production inspection and DB resources |

External Docker Desktop/CLI/API clients, direct database clients and privileged/same-account processes are not collectively owned by Atlas merely because they can access Atlas resources. No external/Genesis process or resource was inspected. Broad arbitrary source execution outside supported paths cannot be excluded by cooperative Python/PowerShell checks.

## Protected resource inventory and authority boundaries

| Resource | Exact declared location/surface | What a separate barrier must cover |
|---|---|---|
| Proposed production inspection registry | `logs/runtime/inspection-control` in the prior integration proposal; still unprovisioned | Initialization, all admissions, uncertainty, recovery intent/commit and replacements; not interchangeable with existing runtime ownership |
| Snapshot state | Explicit F fixture root, `snapshot-NNNNNNNN.json` | Current file identity/hash plus future publication names and directory ancestry; locking one existing revision does not fence the next |
| Witness/commit | Separate fixture witness root, `intent-*`, `commit-*`, `recovery-required.json` | Independent root, complete revision chain and poison evidence; not protected merely by snapshot-file lock |
| Durable revision pin/handoff | G explicit handoff root, `ack-*`, `intent-*`, `manual-review-required.json`, caller-bound root/file identities | Cross-root consistent progression, no rollback/replay or unexplained interrupted reservation; local pins not independent whole-machine anchors |
| Approval/proof/audit/recovery records | Explicit H/K/L fixture output roots; challenge/decision/consumption/audit/digest/attempt files | Exclusive publication, native permissions, flush/commit and interrupted-record refusal; future new files are distinct resources |
| Existing lifecycle records | `logs/runtime/atlas-background-owner.json`, start/stop/recovery locks, `runtime.json`, `stop.json`, Complete Shutdown receipts and stale archives | Manager/worker/desktop-control coordination, process identity and run binding; separate from inspection state |
| PostgreSQL named volume | Compose logical `atlas_pgdata` -> `/var/lib/postgresql/data`; historical U/W actual `projectatlas_atlas_pgdata` | Linux filesystem/database writers and external clients; possible effective external paths remain storage-coverage gates. No live volume inspection M |
| Redis named volume | Compose logical `atlas_redis` -> `/data`; historical U/W actual `projectatlas_atlas_redis` | Linux Redis/persistence writers, actual configuration/consumers; not inferred from a Windows barrier or source filenames |
| Other Atlas evidence/runtime | `backend/data/paper_journal.jsonl`, `paper_candidates.jsonl`, `pipeline_funnel.jsonl`, risk/mirror controls, investment DATA_DIR/history, extended-hours observation/commit evidence, subscriptions/outbox/consent SQLite surfaces, diagnostic logs | Exact configured roots/sidecars/new files, service-specific drain and data authority. Not all are inspection-control state |
| Configuration/migrations/release state | Reviewed sources and configuration references, schema/migration metadata, release artifacts/master roadmap | Preserve separately; no credentials/configuration payloads read or changed by M |

Historical DB volume names and previous EXITED state are not fresh ownership/state claims. Source Compose currently permits restart-unless-stopped and declares only the data mounts; effective Redis persistence/storage layout is not re-established by source review. Manager/ownership source permits project names atlas/projectatlas in particular paths; preserve policy and bind exact approved identity later, never infer ownership from names alone.

## Mechanism comparison and independent evidence

| Mechanism | Real effect | Missing guarantee |
|---|---|---|
| Durable cooperative admission / snapshot coordinator | Serializes participating Atlas operations; intents survive crashes and refuse unexplained replay | Production paths not integrated; independent Docker/DB clients do not participate |
| Native exclusive NTFS handle on one exact file | Kernel rejects conflicting ordinary opens/replacement while handle is held; acquisition conflict can reveal a current accessor | Not every file/sidecar/new publication; not Linux volumes; no privileged access guarantee |
| Held ancestry handles / protected owner-SYSTEM directories | Prevent particular path substitution and restricted-other-user access; native identity-before-read | Same trusted owner may create another permitted file; ACL is not a process-specific lease |
| Verified Windows process identity + observed exit | Distinguishes exact PID/creation/executable/run; kernel releases that process's handles on exit | Does not establish absence of another writer, inherited/shared handles or a Linux helper behind a Windows proxy |
| Exact container/image/ownership observations | Supports target identity and bounded current observations | K still cannot prove daemon generation/cache-independent computation or all holder absence; MISSING is not exit |
| Operator-controlled maintenance window | Operational coordination and explicit action approval | Promise/click is not enforced exclusion or independent helper quiescence |

An exact NTFS lease is independent of Docker for its **own file**: it can reject an ordinary active writer without trusting Docker's state. It cannot prove a Linux helper is no longer accessing another resource. Kernel-backed file-handle/identity evidence and Windows child-process exit are therefore useful scoped facts, not an Atlas-wide quiescence witness.

After daemon restart or missing/replaced helper evidence, protected state and durable lineage can identify what is unresolved; they cannot manufacture an exit observation. A lease on a host audit JSON does not prove that a helper stopped reading a Linux volume. No fresh Engine/helper state collected here. External writer unknown always preserves refusal for all-writer recovery.

## Minimal native prototype and actual outcomes

New `scripts/volume_inspector/resource_barrier.py`, `tests/test_r7e47m_resource_barrier.py`. No production imports. Explicit synthetic source/helper/writer facts are required and never treated as production authority. The prototype opens one relative `resource.json` with native no-follow semantics and **ShareAccess=0**, validates protected DACL, file identity/link/type/content commitment, and keeps the same handle. Parent ancestry handles remain held. It has no Docker interface or recovery permission.

Single-use native exclusive flushed `barrier-intent.json` is created before acquisition. Interrupted acquisition or process death leaves that intent and refuses cooperative replay; no timeout/reset clears it. Lease token binds actual self PID/creation/executable/command, random nonce, phase and expected file/root identities. Wrong/released tokens refuse. Release intent precedes handle close, then separate released evidence; release interruption never grants startup. Records are preserved, not deleted. This is a fixed fixture, not a general new security service.

Demonstrated on actual disposable NTFS fixtures:

- INSPECTION and RECOVERY phases deny ordinary file write opens and replacement while held.
- Four concurrent acquisitions yield exactly one kernel/file-intent winner; others refuse.
- Existing write handle prevents acquisition; retained intent blocks replay after it closes.
- Existing writable mapping also prevented acquisition on this workstation (`mapping-result.json`: KERNEL_REFUSED_LEASE). This is a tested instance, not a universal claim about every mapping/kernel writer class.
- Replaced file identity is refused even when replacement bytes and DACL are valid.
- Two synthetic child-process crash cases (parent/worker roles, actual OS exit23) release their file handles but **do not clear the durable fence**. These are fixture Python processes, not Atlas services or container helpers.
- Helper RUNNING/MISSING/UNKNOWN/replaced, unavailable Docker, active/unknown external writer and stale/replayed lease facts refuse. Synthetic facts are inputs to refusal testing, not collected real-world evidence.
- Interrupted release keeps ordinary write exclusion until fixture close, and the durable intent still refuses later admission.
- **Scope counterexample:** another file `uncovered.json` was successfully created in the protected directory while the exact file remained leased. The barrier demonstrably does not fence a whole directory, future revision or journal.

No claim that this prototype makes the whole protected state consistent or safe to mutate. Releasing the fixture handle lets ordinary opens resume, while one-use intent prevents its own cooperative reuse; that asymmetry is intentional and does not control external writers.

## Hard feasibility decision and narrower safe operation

**BLOCKED** for the requested all-resource recovery. Missing guarantees are an independently authenticated exact Linux-helper quiescence witness and an enforced Atlas-scoped boundary covering every relevant writer/resource through recovery publication, including dynamic files and external Docker/restart paths. Windows one-file leases cannot supply either Linux guarantee. A larger collection of local flags/keys/leases does not make them true.

Smallest corrective action: decide an explicitly narrower resource/action scope **before** another framework. Read-only identity/content verification of a finite set of host control files under held native handles is feasible within documented limits. A quarantine-only incident record in separate protected host output can be proposed while retaining all uncertainty/startup prohibitions. This does not clear a fence, certify helper exit, restore data, permit startup or authorize production publication. No real quarantine record was published M.

If recovery must release inspection exclusion or allow writers/startup, a separately authorized investigation must demonstrate actual per-Atlas Linux writer custody and independent holder evidence, or the path stays blocked. Global Engine/VM shutdown or interference with unrelated projects is not an acceptable substitute under this contract. No broad security framework or production integration is recommended from the current evidence.

Recommend **R7E47N — Resource-Scoped Recovery Decision Package**: select quarantine-only/non-clearing host evidence closeout versus retaining the full Linux-custody blocker, with exact permitted resources/actions and acceptance criteria. No production change or scope relaxation is implicit; stop at M's feasibility gate.

## Validation, preservation and runtime

Focused18passed,0failed,0skipped;0.61s. Combined M/L/K/J/I/H/G/F/E/D/C/B/Y **529passed,0failed,4skipped;32.71s**. Guarded S/T/V lifecycle **82passed,0failed,0skipped;47.21s**. Non-overlapping final total **611passed,0failed,4skipped**. RuffPASS;29Python compile;18PowerShell scripts parse0errors; Git diff integrityPASS. Source candidate scan165files; not runtime census.

Original focused17passed/1failed preserved: replacement test created an inherited-DACL replacement, which the unchanged verifier correctly rejected earlier than the expected identity exception. Fixture now creates a valid protected replacement and confirms identity refusal. Two new test-only Ruff findings (nested context/check argument) corrected. No guard weakened or pre-existing source changed. Four inherited F/C symlink1314/POSIX/Linux-descriptor skips unwaived; historical Z Linux evidence retained, no container rerun/full canonical-suite claim. Existing native I approval hash unchanged; no new human approval dialog.

Atlas remains operator-reported STOPPED. No new production process census or Docker/container/volume inspection; no Atlas/Docker lifecycle, real helper launch, database payloads, Genesis, backups/restoration, production ACL/configuration/shortcut/registry/startup changes, live trading/Discord, Git staging/commits/push/reset/deletion or VPS. Process review was source architecture plus self/fixture identities only. Existing untracked files, failures, logs and recovery instructions preserved.

Master update uses only `scripts/windows/Atlas-Roadmap-Checkpoint.ps1`. Final result verifies original backup equality, exact read-back, byte-identical history outside managed markers and permanent strategy/recovery/PM-V2 anchors.

## Complete remaining seven-phase roadmap

1. Core reliability/operations: resource/action scope decision; actual source/helper/all-writer quiescence and recovery/admission gates; cash-scanner scope; provider rights/HTTP/Yahoo budgets/pacing/stuck-worker/drain; Ruff disposition; complete artifact/licenses/dependency/clean-machine portability; live-data/runtime/rollback/Gaming resource/cadence. Separate storage coverage/capacity, destination/encryption/key recovery, backup/disposable restoration, Complete Shutdown/shortcut approvals. Extended benchmarking/optimization separately authorized.
2. Evidence Engine: immutable hypotheses/outcomes, replay, precision/recall/calibration/false positives, realistic PAPER fees/slippage/funding, bias controls, Research Memory. E29 NOT_READY; corroboration context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/rules/fees/settlement, timestamped spot/perp/depth/volatility/funding/liquidity, calibrated probability/executable edge, realistic fills and out-of-sample evidence before live proposal.
4. Cross-market intelligence: equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable uncertainty/invalidation/reproducibility; cautious hypotheses.
5. SaaS: demand/pilots, tenancy/auth/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics/licensing/unit economics; pricing unvalidated.
6. Institutional readiness: RBAC/audit/security/incidents, governed research/workspaces/API/compliance/pilots; stronger principal/TPM/off-machine authority separately scoped; no VPS dependency.
7. Commercial scale: product-market fit/retention, partnerships/integrations/white-label/API licensing, evidence-led expansion and measured economics/reinvestment.

Cross-phase gates: E136 independent rollback witness, dual-database consent resurrection/atomic recovery/fencing, recipient delivery/render/storage and uncertainty/dead letters. Discord explicit approval/durable no-backfill/no automatic uncertain retry. Prediction exactly-once/pre-deadline/auto-flat; portfolio-versus-strategy risk undecided. Preserve PM-V2.1–PM-V2.6 discovery/calibration/edge/pre-event PAPER/evidence/dashboard; one position per market, no combos/stacking/averaging/opposing YES+NO; settlement research never overrides pre-event safeguards. PAPER_ONLY/MANUAL_ONLY, Gaming efficiency/normal PAPER cadence and Atlas/Genesis separation permanent. Production integration and release remain NO-GO.
