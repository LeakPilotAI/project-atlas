# R7E46W Stage A2 — effective storage, capacity and protected tooling

Status: production inspection and isolated acceptance preparation only. Backup prerequisites BLOCKED; production NO-GO. No data backup, restoration, helper/database startup or production change authorized or executed. October 18, 2026 America/Chicago CDT (UTC-05); exact observations in evidence.

## Verified current state

Branch chatgpt/atlas-rebuild-v1, HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0. No active top-level lifecycle JSON/lock/temporary record found before supported Status. Status confirmed STOPPED. Sandbox CIM and Docker-pipe access initially failed; narrowly scoped read-only checks outside sandbox succeeded. This was access restriction, not evidence of a service failure. Initial failures retained. Final checks must confirm no drift.

Fresh name and full-ID inspections agree. Exact projectatlas, service, Atlas root, single docker-compose.yml and nononeoff labels verified. PG c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1; Redis 13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193. Both exited, Running=false, PID0, exit0. Exact volume-filtered consumers are only their expected exited IDs. No unrelated container or Genesis resource inspected.

## Effective PostgreSQL coverage

PASS declared storage: one local named volume projectatlas_atlas_pgdata mounted /var/lib/postgresql/data, no additional bind/config mounts. Image ID sha256:d8336a5c9cc49bdbf1e935234e8c87ab64b6d6d195fd2ecedff7b00185557631 and declared image volume verified. Standard postgres command, docker-entrypoint.sh path, one process argument and standard PGDATA observed; no command-line -c or alternate config argument in this recorded invocation. Compose has no command/entrypoint/config override. Volume driver local, options null. Image metadata is not verification of entrypoint filesystem contents.

BLOCKED effective coverage: PostgreSQL configuration and ALTER SYSTEM can redirect data/config; pg_tblspc/pg_wal can reference external storage. Neither the lack of extra mounts nor PGDATA excludes container-layer targets or prior initialization choices. No volume directory/link/config contents or database catalogs were read. No claim that tablespaces or external WAL are absent. Complete cluster/storage and actual schema/extension version remain unproved.

Minimal next authorization: stopped-volume directory/stat/link metadata and specifically allowlisted storage settings from postgresql.conf, postgresql.auto.conf and includes, with no general config dump, credentials or relation/WAL payload reads; exact approved read-only helper/tool required. Unknown targets must be blocked without dereferencing them. SQL is not the first step and remains unauthorized. If metadata cannot resolve effective paths, request separate scratch-only restoration/catalog validation or a separately scoped database-query approval; do not start production to fill this gap automatically.

## Effective Redis coverage

PASS declared storage: image sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99, standard redis-server command, standard entrypoint, WorkingDir=/data, one exact named volume projectatlas_atlas_redis at /data. No recorded config-file argument, AOF option or extra bind mount. Missing optional StopSignal is not an ownership failure.

Expected upstream default intent is RDB snapshot persistence; AOF is not explicitly enabled by Compose. This is an expectation, not certification of defaults compiled into this exact image or last-session effective configuration. CONFIG SET can change runtime behavior without a persisted configuration, and memory-only data is unrecoverable from a cold volume after exit. Actual RDB/AOF presence, rewrite/load state, persistence success and recovery coverage remain BLOCKED/NOT TESTED. Do not equate a mounted /data with a usable backup or require turning AOF on as part of this audit.

Minimal next step: separately authorized filename/stat metadata and reviewed image-default/config provenance; no RDB/AOF payload reads. Actual loading/checking requires separate scratch-container approval. No CONFIG GET, SAVE, BGSAVE, CONFIG REWRITE or Redis connection performed.

Primary reference context (not proof of local effective settings): https://www.postgresql.org/docs/current/backup-file.html ; https://www.postgresql.org/docs/17/storage-file-layout.html ; https://redis.io/docs/latest/management/persistence/ . PostgreSQL file copies need a consistent full cluster and all storage; Redis documents snapshot/AOF distinctions. These general facts do not establish local completeness.

## Measured capacity and uncertainty

Metadata-only logical byte counts: backend/data 2,338,920,493; runtime history 21,395; root/backend .env combined 9,316 (sizes only, no content); existing 914 release-source files 9,497,966; master roadmap and existing backups 20,881,275. Known subtotal 2,369,330,445 bytes (~2.21 GiB), not complete source size. No links/reparse targets traversed in host evidence inventory. Existing data file count2736 unchanged from Stage A.

Both exact volume UsageData fields are null. No measured volume size can be obtained from these allowed Docker metadata replies. Do not use global docker system df, inspect WSL disks or launch a helper without approval. Additional selected audit artifacts/effective external state, sparse/allocated expansion and restore overhead are unknown. Current D free 806,681,903,104 bytes (~751.3 GiB). This does not establish sufficient space.

Proposed capacity envelope: S = measured PG + Redis + complete host/config/source/audit/external state. Reserve at least ceil(3.3*S) + max(ceil(0.2*S),10GiB) on a shared destination/scratch disk: archive + verification copy + scratch restoration, ten-percent aggregate allowance and safety reserve. No compression credit; account for database scratch working growth, allocation expansion and any additional copies explicitly. This is an illustrative conservative approval policy, not a measured requirement or guarantee. Unknown S blocks evaluation; rerun free-space checks before/during a future authorized operation. Independent disk/key failure domains require an explicit future policy, not a silent cloud/VPS copy.

## Protected destination policy

D:\Work\atlas-backup absent; parent D:\Work has broad inherited Users/Authenticated Users access and is not a confidential backup destination. Parent and drive were not reparse points. Proposed destination is outside live host-source roots, but on the same D drive: path separation is not disaster-independent storage. No creation, write probe, ACL/encryption changes or keys accessed.

Future approved creation: bind current operator SID explicitly; create a NEW operation directory with restrictive security descriptor from creation, inheritance disabled, only operator data access and approved SYSTEM/recovery administrators. Do not create broadly readable files then restrict them later. Deny/allow semantics and the resulting ACL must be independently checked; administrators can take ownership, so ACLs alone are not an encryption boundary. Recheck canonical paths/reparse status and CreateNew/no-overwrite semantics before and after creation. Test access only under separately authorized synthetic probe; do not alter D:\Work ACL.

Prefer reviewed authenticated portable archive encryption for exported contents/manifest confidentiality with an independently recoverable key, plus owner-only local access. Whole-drive encryption addresses some offline theft but does not protect from other logged-in principals; machine-bound protection alone is not proven off-machine recovery. Tool/version/digest, algorithm, manifest authenticity, key custody and independent recovery rehearsal remain NOT TESTED. No key generation/display/access or encryption implementation occurred. Explicit approval must define encryption/recovery policy and avoid secrets in process arguments/logs/manifests.

## Tooling acceptance and restoration design

See docs/R7E46W_A2_BACKUP_TOOLING_ACCEPTANCE.md. No production backup implementation or pinned helper/tool has been accepted. The isolated prototype is an acceptance-policy experiment only: exact synthetic sources, hashes, unknown capacity rejection, fence loss, no restored-evidence false success, atomic no-overwrite marker and retained partial failure. It does not implement encryption, source acquisition, all-writer fencing, archive metadata fidelity, complete effective storage discovery or restart-safe operations. Passing it cannot authorize backup.

Fresh source-to-target mapping from Stage A remains binding only after revalidation. No automatic code-based traversal of real sources was implemented. Tests used generated bytes only. Real tooling must preserve UID/GID/mode/symlinks without following unowned targets, coherent journal/witness pairs, independent rollback witness, output hashes and canonical manifest, fail closed on ID/ACL/disk/fence drift, and publish completion only after all required verification. SEALED_UNVALIDATED is not RESTORE_VALIDATED or ACCEPTED. Atomic directory entry publication is not evidence of power-loss durability of the entire archive/directory; a crash/power-loss contract needs separate testing.

Capacity-aware scratch design: verify provenance/manifest/authenticated archive and capacity before NEW unique disposable storage. Offline archive/metadata/journal validation requires explicit backup-payload access. PostgreSQL checks require a separately approved isolated pinned-image container: production-compatible major/extensions, no production mounts, no host ports, no external network/API/collectors/Discord; validate startup recovery, schema/extensions and scoped continuity/integrity summaries. Redis requires separately approved pinned isolated startup/load and non-secret persistence summaries; do not run repair/fix on original backup. Optional check tools operate on scratch only. No scratch create/start/restore/query/shutdown/deletion is currently authorized; future approval must enumerate exact resources and retention/cleanup boundaries. Restored lifecycle PIDs/locks stay historical, never active. Consent and trading authority do not follow from restored data.

## Gate matrix

| Gate | Status | Required evidence / decision |
|---|---|---|
| Current exact ownership and exited state | PASS | Fresh container/image/mount/label/consumer checks |
| Declared PG and Redis storage | PASS | One exact named volume each; standard recorded commands |
| Complete effective PG coverage | BLOCKED | Allowlisted stopped-volume settings/link metadata; unknown target handling |
| Redis effective persistence/recoverability | BLOCKED | Persistence evidence and separately approved scratch validation |
| Point-in-time Atlas quiescence | PASS | STOPPED, no active record, exact exited consumers |
| Continuous writer exclusion | BLOCKED | Approved maintained lifecycle/journal/operator fences; external actors covered |
| Volume sizing/full capacity | BLOCKED | Exact volume metadata sizing plus complete approved scope |
| Protected destination policy | PASS (design only) | No real directory/ACL/security acceptance |
| Protected destination/encryption/key recovery | NOT TESTED | Separate creation/probe/encryption policy and recovery approval |
| Synthetic acceptance-policy tests | See validation evidence | Not production tool acceptance |
| Pinned backup tool/archive fidelity/crash contract | BLOCKED | Implementation/tool-specific review and isolated acceptance |
| Usable backup and isolated restoration | NOT TESTED | Separate explicit approvals; no production writes |
| Cash/provider budgets/stuck workers/Ruff/clean-machine/runtime/Gaming/shortcut/E136/Discord/PM-V2 | BLOCKED or NOT TESTED, unchanged | Prior release gate matrix retained without waiver |

Recovery caveat from source review: the manager starts existing positively verified IDs, but its both-absent creation branch uses Compose project atlas whereas current volumes belong to projectatlas. A future recovery must bind the actual restored storage/project explicitly; never assume names or silently create an empty alternate project. No change or lifecycle experiment made. This is not a new claim that the existing-ID path is broken.

## Safety and final validation

No production source/volume payload copy, database connection, secret/key read, destination/ACL change, helper/Atlas/Docker lifecycle, Genesis access, shortcut edit, trading/Discord activation, Git stage/commit/push/reset or destructive cleanup. Only new reports/synthetic evidence plus the mandatory roadmap checkpoint and its previous-version backup. Existing implementation bytes must remain unchanged.

Exact test/static/preservation outcomes are appended after completion and in result.json. Full-suite/Ruff inheritance remains unwaived, not silently passed by focused tests.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

Current backup work: effective storage metadata/sizing, protected destination and concrete tool/fence acceptance, then separately authorized backup creation and independent restoration. No automatic Stage B.

Next safest execution: separately approve A3 stopped-volume metadata-only sizing/config/link review with a concretely reviewed helper/tool and exact RO Atlas mounts, or supply equivalent sanitized authoritative evidence. Production databases remain stopped. No payload backup/restore, helper activation or destination creation is implicit in this recommendation.

## Completed validation results

22 synthetic tests passed (0.13s); initial sandbox run21pass/1hard-link AccessDenied retained. Focused regressions143pass/1known E136 atomic-recovery xfail/2warnings,41.18s; initial sandbox run stalled/cancelled, no worker remained, exact cause unverified. Three new evidence Python scripts compile; targeted Ruff final passes after one evidence-only I001 correction. Final ownership/container/mount/state identical and supported Status STOPPED. All914 prior release-source bytes unchanged before mandatory checkpoint. Windows parser and diff outcomes in evidence; mandatory roadmap verification recorded separately. No source implementation edit.

Final verification:18 Windows PowerShell5.1 scripts parsed,0errors;Git diff check PASS. Checkpoint updater succeeded, previous-version backup matches raw pre-update roadmap, read-back successful and outside-managed-checkpoint bytes identical. Permanent strategy/recovery/PM-V2 preserved. Only roadmap changed among914prior release files;2761host data/runtime file sizes/mtimes unchanged. See checkpoint-verification.json.
