# R7E46W Stage A — cold backup quiescence, coverage and recovery preflight

**Read-only preflight complete; backup readiness BLOCKED; production NO-GO. No data backup, restoration or lifecycle operation executed.** October 18, 2026 America/Chicago (CDT UTC−05); exact UTC timestamps are in evidence. Branch chatgpt/atlas-rebuild-v1; HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0 unchanged. Read the full master roadmap/checkpoint, T ownership/recovery, U backup/restoration plan and V repair report.

## 1. Current ownership, state and writer evidence

Engine 29.8.1 accessible via verified local npipe:////./pipe/dockerDesktopLinuxEngine. Both containers were independently inspected by current names and frozen full IDs, with exact projectatlas/service/root/single docker-compose.yml/nononeoff labels, pinned image IDs, unchanged mounts and named-volume labels checked before use. No cached record alone established ownership.

| Dependency | Current full ID | Verified named volume / destination | State |
|---|---|---|---|
| PG | `c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1` | projectatlas_atlas_pgdata -> /var/lib/postgresql/data | exited, PID 0, exit 0 |
| Redis | `13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193` | projectatlas_atlas_redis -> /data | exited, PID 0, exit 0 |

The project root/config and images match prior accepted metadata; no unexpected identity/state drift occurred. Stored health is unhealthy on exited services, not certified running readiness. Current PGDATA metadata matches the PG mount; Redis default redis-server command/WorkingDir=/data matches its mount. No SQL/Redis query, container exec, payload/config-secret read or lifecycle action occurred.

Each exact-volume-filtered consumer query returned only its expected exited container ID. Unknown consumers would have blocked/aborted without inspection. No global container inventory, network-member inventory or Genesis resource was inspected. Docker State.Pid=0 supports absence of processes in those two stopped containers. Separate server-filtered metadata found no Python/Postgres/Redis executables rooted inside Atlas before or after tests; no command lines/unrelated processes were returned. The supported manager reports STOPPED/no run.

## 2. Quiescence and recovery fences — bounded conclusion

No active top-level owner/runtime/start/stop/recovery JSON/lock or Complete receipt was present. Archived stale-session/start-lock records remain preserved as history; they are not active fences and were not read/reset/moved. No pending Complete CLI intent was found in active records. No current SQLite/sidecar/journal-lock files were observed in the inventoried host data roots; this does not inspect payload-level pending intents or arbitrary external configured paths.

The metadata-only file set, sizes and nanosecond mtimes were unchanged at two observations for 2,761 host files (2,736 backend/data + 25 logs/runtime). No source payload was opened or hashed. These observations support current scoped quiescence, not a byte-integrity guarantee or continuous exclusive copy window. Privileged Docker/WSL/host actors and external-path writers cannot be ruled out by these scoped reads. No real mutex/journal lock was acquired or modified in Stage A. **Backup remains BLOCKED until an authorized operation can establish and maintain writer exclusion.** E136 independent witness/dual rollback/atomic recovery limitations remain unresolved.

## 3. Complete known persistence inventory, with coverage gaps

Detailed metadata: persistence-inventory.json, persistence-file-metadata.json, configuration-file-metadata.json and safe source references. All host inventory used stat/listing only, with no symlink/junction traversal; none were observed in the inventoried trees. This is the complete known/default map within scope, not certification that unreviewed effective overrides/external storage are covered.

| Recovery group | Known source and requirement |
|---|---|
| PostgreSQL | Entire exact named volume, actual database catalogs/extensions/WAL/config and any independently verified external tablespace/WAL/data_directory targets; exact compatible Timescale image required. External coverage not yet established. |
| Redis | Entire exact named volume and verified effective persistence settings/files; memory-only state cannot be recovered by a cold disk copy after exit. Save/AOF history/integrity unknown. |
| Core PAPER/evidence | Entire backend/data root files, including paper_journal.jsonl, paper_candidates.jsonl, manual/risk/session/checkpoint state and Alpha/funnel/shadow/evidence histories; preserve recorded results without rewriting. |
| Investment | Entire backend/data/investment: ledger/account/quality-dips journals/state, universe/plans/observations/opportunities/outcomes/history/snapshots/provider/valuation state. |
| Prediction | backend/data/prediction candidates/trades; preserve identities, policy/deadline/settlement/risk semantics; no live activation. |
| Research inputs | backend/data/research raw historical inputs/checksums/manifests and research results, needed for reproducibility. Optional cache exclusions require explicit acceptance. |
| Conditional gated stores | Extended-hours journal plus .commitment.sqlite3 and required SQLite sidecars; subscriber JSON and explicitly provisioned consent/witness/outbox/watermark/source-identity stores. No provisioning or activation for backup. |
| Configuration | Root .env and backend/.env metadata only; keep distinct, confidential and separately authorized for future reads. Include actual approved path/endpoint overrides, source examples and launch/runtime flags; do not treat examples as actual configuration. |
| Code/schema/migration | Exact dirty/untracked source release manifest, Compose/images, models, db/session/main schema/startup migration logic, recovery/migration docs and dependency versions. No standalone Alembic/migration directory was identified. create_all is not proof of migration equivalence. Actual schema version remains unqueried. |
| Recovery/audit provenance | Master roadmap/checkpoint backups (12 pre-existing roadmap backups observed), logs/runtime historical records, any future Complete receipt/CLI records and approved diagnostic/failure/artifact selection. Preserve as history; never reactivate old PIDs/locks or rebind IDs silently. |

Metadata totals under backend/data: 2,736 files, 2,338,920,493 bytes (~2.18 GiB): root 21 files / 880,068,536 bytes; investment 113 / 751,304,393; prediction 2 / 539,885,793; research 2,600 / 167,661,771. logs/runtime: 25 files / 21,395 bytes. Root data/,artifacts/,backend/artifacts/,backend/logs/ and logs/diagnostics/complete-shutdown do not currently exist. This does not authorize creating them.

Documented default discord_subscribers.json and extended-hours journal/commitment are absent. E133/E135/E136 classes are intentionally isolated/path-injected and not production-wired; no SQLite files were observed in host data. Absence is recorded rather than inventing a production store or subscriber history. Effective environment paths/connection endpoints remain unverified because secrets/live environment contents were not read. Any required configuration/data in container writable layers or external references also needs explicit coverage; a named-volume-only copy is not silently sufficient. Required coverage is therefore BLOCKED until sanitized effective configuration and all storage targets are independently established.

## 4. Destination readiness

Proposed D:\Work\atlas-backup does not exist; nearest existing parent D:\Work. D: is healthy NTFS with 806,697,721,856 free bytes (~751.3 GiB) at observation; source host data alone is ~2.18 GiB. D:\ and D:\Work are not reparse points, and the proposed sibling path is outside D:\Work\Project Atlas and its live host evidence roots. No destination directory/file or data archive was created.

Parent ACLs were inspected, owned by the current user, with broad inherited Users/Authenticated Users entries. This is not a confidential owner-only backup ACL. No write probe, final destination ACL, encryption/key recovery check or capacity reservation was performed. Access/readiness therefore remains conditional, not a verified write/confidentiality PASS.

Both named-volume UsageData fields are null; database volume sizes, selected audit/staging/restore footprint and safety reserve remain unknown. Free space alone cannot establish sufficient total capacity. Do not use global docker system df or unrelated project inspection to fill this gap. A separately approved Atlas-only helper/metadata method is required before capacity acceptance.

## 5. Exact future operation and restoration prerequisites

See docs/R7E46W_COLD_BACKUP_AND_ISOLATED_RESTORE_PROCEDURE.md and plan-bindings.json for exact source/archive mapping, NEW UTC/UUID destination, writer fences, read-only source mounts, approved helper/digest/permissions/resource envelope, archive/hash/manifest states, partial-failure quarantine and independent scratch-only restoration. The original U plan is unchanged. No runnable command can be approved until unresolved inputs are concrete.

Required separate authorizations:source metadata/config coverage; helper creation/start and payload/secret backup reads; protected destination creation/ACL/encryption/key handling; exclusive backup window/tool; and independent scratch creation/database validation access. Production API/DB startup, Stage B lifecycle and shortcut migration are never implicit. Helper access failure must not be repaired by source chmod/chown, privileged broad mounts or database startup. No cleanup/deletion is included by default.

A partial/corrupt/uncertain operation must remain FAILED/QUARANTINED with preserved evidence, never complete because copy exit0. Hash artifacts and canonical manifest independently; coherent journal/witness and consent rollback evidence require explicit validation. Restoration goes only to new isolated destinations, never production volumes, with no network/ports/production manager/collectors/Discord. Archived lifecycle records stay forensic; new IDs need an approved recovery contract. E136 consent atomicity/rollback, PAPER_ONLY/MANUAL_ONLY and PM-V2 safeguards remain gates after any data restoration.

## 6. Validation and safety

143 isolated tests passed, 1 expected E136 recovery-snapshot xfail, 0 unexpected failures, 2 dependency warnings in 43.86s. The selected expected failure documents two separate reads not being an atomic recovery snapshot; it is an unresolved gate, not success. Tests use temporary SQLite/journal data/fake lifecycle callbacks; no production payload copied. 18 Windows PS5.1 scripts parse with 0 errors; 7 selected Python modules compile; targeted Ruff and Git diff checks pass. Full suite/whole Ruff not rerun because no implementation changed; V's historical 2,370 pass / 3 xfail and 3,997 Ruff findings remain historical and unwaived.

Current release source bytes and desktop shortcut hashes are unchanged except mandatory master checkpoint update/new reports/evidence. No live lock/journal/state/container metadata/volume was modified. No data backup/restoration/helper creation, Atlas/Docker lifecycle, Engine/Desktop termination, Genesis access, credential/database/backup payload read, shortcut change, live trading/Discord activation, staging/commit/push/reset/deletion or VPS work occurred. The only new backup is the explicitly required roadmap updater's previous-version .bak, not a data backup.

## 7. Gate decision and next safest milestone

Current scoped ownership/stopped writer observations:PASS. Exclusive copy window, complete effective coverage, database sizing/capacity budget, protected writable destination, reviewed helper/tool and usable backup/restoration:BLOCKED/NOT TESTED. Production NO-GO. All cash/provider/HTTP-budget/stuck-worker/Ruff/clean-machine/runtime/Gaming/desktop/E136/Discord/PM-V2 gates remain unchanged.

Safest next milestone: separately approved Atlas-only storage-coverage/sizing and protected-destination/tooling validation, without production DB startup. Any helper launch/config read/write probe requires explicit narrowly scoped permission. Only after those gates and writer fencing are satisfied should data backup creation be approved; restoration validation remains separate. STOP at Stage A.

## Complete remaining seven-phase roadmap

1. Core reliability and operations: obtain cash-scanner combined-release scope acceptance; retain provider pacing/ownership/drain regressions; verify provider terms and Yahoo internal request behavior, resolve nonterminating-worker operational acceptance and controlled workload thresholds; resolve release-quality/Ruff policy; independently validate final artifacts, dependency portability and license companions; separately authorize live-data acceptance, disabled rollback and sustained recovery. Preserve normal PAPER cadence and permanent low-resource Gaming Mode objective. Extended benchmarking/optimization requires separate approval.
2. Evidence Engine: immutable timestamped hypotheses and outcomes, replay, precision/recall/calibration, false positives, realistic PAPER fees/slippage/funding, leakage/look-ahead controls, reproducible reports and Research Memory/analogues. E29 baseline/challenger remains NOT_READY; Alpha/cadence/corroboration remains context-only.
3. Fifteen-minute crypto PAPER: eligibility/jurisdiction/market rules, fees and settlement; timestamped price/depth and spot/perpetual volatility/funding/liquidity joins; independent probability calibration and executable edge; realistic depth/cost fills, actual settlement and out-of-sample regime evidence before any separate live-capital proposal.
4. Cross-market intelligence: unified equity/ETF/crypto/derivatives evidence, liquidity/positioning/anomalies, explainable scores, uncertainty/invalidation and reproducibility; suspicious-activity outputs remain cautious hypotheses.
5. SaaS: demand validation/pilots, tiers/auth/tenant boundaries/billing/entitlements, APIs/dashboards/exports/alerts, onboarding/support/analytics, licensing and unit economics. Pricing remains unvalidated.
6. Institutional readiness: RBAC, audit/security/incident processes, reproducible governed workspaces, API stability, evidence metrics, licensing/compliance and enterprise pilots. No VPS/hosted dependency is authorized.
7. Commercial scale: product-market fit/retention, partnerships/integrations, white-label/API licensing, evidence-led expansion, revenue/margin/cost/churn measurement and disciplined reinvestment.

Cross-phase unfinished obligations: E136 independent rollback witness, dual-database rollback/consent resurrection and atomic recovery snapshot gates; recovery fencing, recipient-specific transport/render/storage, uncertainty/dead-letter handling. Discord requires explicit approval and durable no-backfill activation watermark; never automatically retry uncertain sends. Prediction PAPER requires exactly-once identities, pre-deadline protection and auto-flat. Portfolio-versus-strategy risk policy remains undecided. Preserve Prediction Market Intelligence V2 PM-V2.1 through PM-V2.6: discovery, probability/calibration, executable edge, pre-event PAPER, evidence/backtests and dashboard. One position per market; no combos/stacking/averaging/opposing YES+NO; settlement research does not override pre-event gates. Atlas/Genesis separation and PAPER_ONLY/MANUAL_ONLY are permanent. No production activation, live trading or automatic Discord is authorized.

Current core prerequisites: preserve W metadata inventory/known IDs, close effective coverage/sizing/confidential destination/tool/fence gates, then obtain explicit backup and separate isolated restoration approvals; no automatic Stage B.
