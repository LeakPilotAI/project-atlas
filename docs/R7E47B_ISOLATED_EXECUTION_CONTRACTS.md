# R7E47B — isolated adapter, fence, output and recovery contracts

**Isolated core contracts VERIFIED. Native Windows protected output and production startup enforcement BLOCKED. Overall production NO-GO. No real-operation acceptance claimed.**

Time: 2026-10-18T07:17:40.799469-05:00 (America/Chicago). Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. Read latest managed checkpoint and permanent contract, Y implementation/package, Z acceptance/addendum, A preflight/authorization. All pre-existing changes and failures retained. Evidence: logs/diagnostics/r7e47b-20261018-070650.

## Implemented files

- scripts/volume_inspector/isolated_adapter.py: no Docker import/client/subprocess/lifecycle API. Adapter accepts exactly the included MockDocker transport; real transport injection is rejected. It is an orchestration contract, not an approved production executor.
- tests/test_r7e47b_isolated_adapter.py: synthetic ownership/control/output fixtures, SQLite state, mocked Docker replies and a disposable child-process crash test. No production state or Docker socket access.
- This report, docs/R7E47B_STARTUP_INTEGRATION_PLAN.md, required roadmap checkpoint and diagnostics. Existing pinned helper, policy, image lock and production launchers unchanged.

## Admission and bounded adapter

Derives trusted launch specification through existing pinned policy.plan (fresh ordered <=5s before/after snapshots, exact frozen container IDs/project/service/root/config, source volume identity/CreatedAt/mounts/consumers/stopped backend, immutable image pin and helper source hash). Explicit one-time approval binds operation/source/volume/image, <=300s validity and an asserted exclusive window. Synthetic extension requires private PID/IPC namespaces, default seccomp, empty extra env/devices/binds and synthetic_only=true. Canonical entire-spec comparison rejects missing/extra/mistyped controls (including bool/integer substitutions). Created helper exact ID/operation/full normalized specification must match before start. Sources are rechecked after create and after exit. Actual native Docker-to-normalized-spec collector remains a separate gate.

Per-request timeout <=5s and65536byte response cap; monotonic40s total observation budget with wall-clock approval expiry checks and late-result refusal. Mock transport has no workers, background threads or connection and accepts no callback transport. This demonstrates deterministic timeout/quarantine contracts, not enforcement against a real blocking Docker API or D-state. Production bounded streaming, cancellation/worker lifetime and daemon behavior remain unimplemented/unvalidated.

Malformed create/start/inspect/exit responses, identity replacement, source drift, timeout, disconnect, output errors and cancellation fail closed. Error messages/raw stdout/stderr never enter evidence; static audit failure codes do. No stop/kill/remove/retry/restart method exists.

## Durable cooperating-writer fence

States: NOT_AUTHORIZED -> PRECONDITIONS_VERIFIED -> UNCERTAIN (persisted BEFORE create) -> IN_PROGRESS -> COMPLETE; failures/interruptions retain UNCERTAIN; independently verified recovery transitions to FAILED, never success or retry. Terminal states consume the one-time authorization; a fresh run cannot reauthorize it. Unknown helper ID after interrupted create remains UNCERTAIN and requires separately designed operation-label discovery, never guessed absence.

SQLite synchronous=FULL, bounded busy timeout and BEGIN IMMEDIATE compare-and-swap serialize authorizations/transitions and append audit in the same transaction. Explicit O_EXCL initialization only; missing/corrupt/partially initialized state is not reconstructed or silently reset. Reopened IN_PROGRESS/UNCERTAIN/PRECONDITIONS_VERIFIED state blocks startup. startup_guard holds a write transaction through cooperating startup admission to prevent check/start authorization races. Connections close deterministically. Actual disposable child exits17 after committing IN_PROGRESS; reopening retains startup prohibition.

This is an application-level coordination mechanism, not a lock against external Docker/host writers, administrator state replacement/rollback or power/storage loss. Operator-exclusive window remains an assertion needing independent evidence. All real startup paths remain unchanged and currently do NOT enforce this new fence. See integration plan. A trustworthy single shared fence location, access controls, approved initialization/migration and live startup integration are unresolved gates.

## Protected output

safe_metadata enforces bounded byte input, unique JSON keys, strict schema/scalar types, service/status/config/payload flags, rejects unexpected fields/incomplete reports/external links and projects helper metadata down to totals only. Known helper filename/link/layout strings are discarded, never persisted. Raw errors and forbidden output are not stored; audit retains fixed failure status. Actual helper.inspect synthetic response is accepted and projected without filenames. Every finalized record has an integrity digest in fence audit/state.

ProtectedOutput implements POSIX owner-only0700 directory and0600 exclusive/no-follow files; rejects symlink/noncanonical paths/changed directory identity or permissions, path traversal, overwrite and oversize data. Data fsync precedes a unique pending digest file; hard-link publication of .commit is atomic/no-replace; directory fsync follows. Pending/data files remain on failure. Consumers MUST treat data as unpublished until a complete64hex .commit digest matches the data; these reader/recovery rules still require integration/native acceptance. Exclusive directory ownership is an assumption against same-user privileged races, not an OS sandbox.

**Windows deliberately raises PermissionError before creating output. No Windows ACL changes or unsupported chmod claims.** The native POSIX permissions/fsync/hardlink test is skipped on this Windows host. Successful native protected publication is therefore NOT independently verified here; Windows DACL/handle-based enforcement, reader implementation, interrupted-publication recovery and output-path deployment remain BLOCKED. The mocked publisher exercises orchestration/error propagation only, not filesystem permissions or atomicity. No metadata is published to a real inspection/backup destination.

## Uncertain-helper recovery

Fresh independent proof must identify the exact retained helper and operation, exited state and integer PID0, timestamp within5s/not future, plus explicit operator approval. Changed/stale/running/unreachable/unknown-helper evidence cannot clear the fence. A verified exit changes UNCERTAIN/IN_PROGRESS to FAILED and permits only the modeled cooperating startup guard; it never accepts metadata as successful, replays the inspection or starts anything. Trusted proof acquisition/approval authority is not implemented: callers provide synthetic proof only. Real Docker independent witness, full image/control identity reconciliation and recovery integration remain BLOCKED.

If fence storage/audit itself becomes unavailable, no code can promise durable new failure evidence. The reader/guard fails closed; do not reconstruct state. Preserve prior artifacts and obtain independent recovery review. No state garbage collection, automatic expiry reset or destructive cleanup exists.

## Validation

- New adapter tests:105 passed,1 skipped.
- Existing helper/policy regressions:50 passed,1 skipped.
- Combined final:155 passed,2 skipped,0 failed in5.56s. New skip is native POSIX protected output; existing skip is Linux helper descriptor on Windows (Z historical Linux evidence unchanged).
- Existing guarded S/T/V lifecycle regressions:82 passed,0 failed in49.10s. Runner uses retained isolated-source snapshot and blocks production data/.env/network; no live services.
- Targeted Ruff over helper directory and both test modules PASS. Seven Python modules compiled in memory.18 Windows scripts parsed,0 errors. Original helper source pin unchanged. Git diff/checkpoint preservation verified at finalization.
- Initial114passed1skip2errors: pytest oversized parameter IDs exceeded Windows32767 environment limit; short IDs repaired test harness, original log retained. Adversarial schema-bool test found a real acceptance defect (142pass/2skip/1fail), fixed strict type comparison. An intermediate broad edit produced an IndentationError at collection, corrected and retained. Local new-file lint findings repaired without unrelated churn. Subsequent passing runs retained; no full canonical/whole-Ruff waiver or Linux container rerun.

## Gate matrix

| Gate | Status | Scope/remaining requirement |
|---|---|---|
| Mocked pinned admission/full-spec/identity controls | PASS | Synthetic normalized model only |
| Persistent state/concurrent authorization/child crash | PASS | Isolated SQLite/cooperating callers |
| Timeout/disconnect/late result/uncertainty | PASS | Controlled clocks/mock responses, no real I/O workers |
| Metadata projection/rejection/audit | PASS | Scalar allowlist, no raw secrets |
| Windows protected-output enforcement | BLOCKED | Native DACL/handle implementation and acceptance |
| POSIX durable protected publication | NOT TESTED natively | Implemented; Windows platform skip |
| Production startup-fence integration | BLOCKED | No launcher/API/Docker integration approved |
| External writer/container-replacement exclusion | BLOCKED | Cannot be guaranteed by application fence |
| Real Docker transport/proof collector/output streaming | BLOCKED | Mock-only; requires independent acceptance |
| Fresh Docker ownership/imported image | BLOCKED | A last observed unavailable Engine; no Docker inspection attempted B |
| Real-volume coverage/backups/restore/lifecycle | NOT TESTED/separate | No authorization or execution |
| Production release | NO-GO | All existing release blockers preserved |

Runtime status is inherited from A's fresh STOPPED evidence; B made no real runtime/Engine query or lifecycle action. Production PostgreSQL/Redis/current image state remains unverified while Engine unavailable. Historical Z identities and synthetic Linux results are not relabeled current.

No production source/startup, Docker lifecycle, real mount/helper, Genesis access, secret/payload read, backup/restore, ACL/shortcut changes, trading/Discord, Git stage/commit/push/reset or cleanup. PAPER_ONLY/MANUAL_ONLY, low-resource Gaming and normal PAPER management cadence preserved.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.


Current core additions: independently accept native Windows protected output and reader/recovery; reviewed fixed fence location/permissions/initialization; separately approve startup integration and exact Docker transport/normalized control proof; fresh ownership/image; exclusive window/uncertain helper authority; then separate one-time real metadata attempt, coverage/capacity, backup and scratch restoration. No real-operation permission follows from mocked passes.

Next safest proposed milestone: R7E47C native Windows protected-output implementation/isolated acceptance and independent startup-integration design review, without activating production paths or using real volumes. Separate authorization required.
