# R7E46W Stage A — gated cold backup and isolated recovery procedure

**DRAFT — NOT APPROVED, NOT EXECUTED. No data backup or restoration has been created.** This refines the preserved U plan; it does not authorize payload/secret reads, helper containers, directory/ACL changes, service startup or cleanup. Exact binding sheet: plan-bindings.json in the W evidence directory. Unknown required inputs block the first copy.

## Frozen source-to-archive mapping (revalidate before future approval)

| Source | Verified identity / path | Future output within a NEW operation directory |
|---|---|---|
| PG named volume | `projectatlas_atlas_pgdata`; container `c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1`; mounted `/var/lib/postgresql/data`; image `sha256:d8336a5c9cc49bdbf1e935234e8c87ab64b6d6d195fd2ecedff7b00185557631` | volumes/postgres.tar.enc |
| Redis named volume | `projectatlas_atlas_redis`; container `13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193`; mounted `/data`; image `sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99` | volumes/redis.tar.enc |
| Host evidence/state | D:\Work\Project Atlas\backend\data, entire tree; observed 2,736 files / 2,338,920,493 bytes | host/backend-data.tar.enc |
| Confidential configuration | Root .env and backend/.env separately identified, never swapped; any operator-approved secret overrides | host/configuration.tar.enc |
| Code/schema/dependencies | Exact dirty source/release manifest, Compose, models/db/session/main migration code, pinned image digests, observed dependencies and recovery docs | source/release-source.zip plus manifest |
| Recovery/audit identity | Master roadmap/checkpoint backups, logs/runtime history, any Complete receipt/CLI evidence and approved diagnostics selection | audit/recovery-evidence.tar.enc |

Preserve all host JSON/JSONL evidence, PAPER candidates/journals/risk state, investment state/history/observations/outcomes/plans, prediction PAPER evidence and research/raw inputs. Do not mix synthetic test outputs with production evidence. Optional cache/audit exclusions require an explicit list and acceptance; no silent exclusion to make capacity fit. A cold operation must not copy its own destination recursively into source archives.

If extended-hours journals exist later, include the exact journal plus its .commitment.sqlite3 and necessary SQLite sidecars coherently. If Discord stores are explicitly provisioned later, include consent, independent witness, subscriber persistence, recipient outbox, producer/watermark/source identity and applicable sidecars in one coherent operational window, preserving independent rollback evidence separately. Do not provision missing gated stores merely for backup.

## 1. Approval and source coverage — no payload copying yet

Record explicit operator approval of operation ID, exact source/target map, helper lifecycle, confidential payload reads, tool digest/options, resource limits, backup scope, maintenance window and final state. Neither production database nor API startup is needed or authorized. Both source containers must already be exited and Atlas stopped; abort rather than stop them under backup-only approval.

Under a separately approved metadata/configuration-only source review, establish actual PostgreSQL data_directory, pg_wal and pg_tblspc coverage and Redis directory/save/AOF configuration. Declared PGDATA, mounts and default command are insufficient to exclude overrides or external symlinks. Inspect link/config metadata without dereferencing unknown external resources; only positively identified Atlas storage may be added. Unknown/unowned targets remain BLOCKED; no Genesis access. No approved runnable backup command exists until this coverage and the tool/helper identity are concrete.

## 2. Destination, capacity and confidentiality

Use a NEW D:\Work\atlas-backup\atlas-cold-<UTC>-<UUID> operation path with CreateNew/no-overwrite semantics. Verify canonical paths, no reparse/junction substitution and separation from all live source roots/mounts before/after preparation. Creation and ACL changes require separate approval. Current directory is absent; parent ACLs are broad, not a confidential-backup policy.

Before copying, approve owner/SYSTEM/necessary-administrator access, encryption and independently recoverable key handling. Do not print secrets or assume machine-bound encryption alone is recoverable after loss. No cloud/VPS/upload. Do not inherit broad Users/Authenticated Users access blindly. Stage A performed no destination write test, key operation or permission change.

Capacity must account for measured uncompressed PG+Redis volumes, host evidence/config/source/audit scope, archive overhead, staging/verification copies, scratch restoration storage and an approved safety reserve. Free 751.3 GiB is an observation, not capacity acceptance: volume UsageData is unavailable and the complete budget is unknown. Recheck free space throughout the approved run; do not rely on compression estimates.

## 3. Enforce and maintain source quiescence

Hold the supported root lifecycle gate across the approved backup window and verify no owner/start/stop/recovery/uncertain-CLI state. Use relevant existing journal/commitment locks only under explicit backup authorization, without resetting them or pretending a new lock is honored by every writer. Establish operator-exclusive Docker/host/WSL writer control; no unsupported scripts or external mounts may write. Check exact volume consumers and Atlas process state before/during/after copying. If all writers cannot be fenced, do not copy.

Current observed stopped processes/consumers and stable metadata are point-in-time evidence; they do not provide an exclusive snapshot lock. Never create fake STOPPED records, reconstruct manifests, delete pending receipts or activate archived owner PIDs. A new helper may only mount positively owned source volumes/host paths READ-ONLY, with an exact output bind RW, no Docker socket/network/unrelated paths and a reviewed image already available by immutable digest. Its creation/start requires explicit approval. Helper UID/permissions/capabilities remain unvalidated; never fix access by source chmod/chown, broad privilege, database initialization or source writes.

## 4. Cold archive and integrity contract

After all gates pass, use the reviewed tool to preserve full volume file ownership/modes/symlinks and required metadata without blindly dereferencing external links. Keep source mounts RO and never invoke database startup, checkpoint/repair/CONFIG SET on source or Compose recreate/down/prune/rm. Apply an explicitly approved low-resource envelope; tool selection/performance remains untested rather than inferred from Gaming Mode.

Maintain the host journal/SQLite pair snapshot under verified writer exclusion, preserving database/WAL/SHM/journal sidecars where present. Do not independently copy a changing journal and witness. Hash each completed archive and any approved source consistency record; never display payloads. Verify encrypted archive readability and integrity only within the authorized confidentiality scope. State changes or copy/hash errors mean failure, not partial success.

## 5. Manifest, completion and partial failure

Operation states: DRAFT -> PREFLIGHT_VERIFIED -> WRITING -> SEALED_UNVALIDATED -> RESTORE_VALIDATED -> ACCEPTED. Any missing mandatory evidence, unknown writer, changed source/ID/mount, disk/ACL/encryption failure, hash mismatch or uncertain helper means BLOCKED/FAILED/QUARANTINED. No success flag from exit code 0 alone.

manifest.json must record schema/version; approval reference; UTC/CDT window; exact IDs/Compose/root/config hash/mounts/images; code/schema/dependency versions; source file counts/size/coverage and writer fences; tool digest/options; destination ACL/encryption contract without key material; output sizes/SHA256; exclusions; failures and completion state; journal/commitment and consent/witness identities where applicable. Canonical manifest hash belongs in manifest.sha256/independent evidence; never self-hash recursively. Keep independent witness/approval evidence outside the same rollbackable bundle. Existing E136 independent rollback/atomic snapshot gaps remain unclosed by archiving all stores together.

On interruption/disk-full/fence loss preserve partial files and errors under the operation ID. Never overwrite/reuse it as a new complete backup, restore it to production, retry uncertain work blindly or delete records to unblock startup. Stop only explicitly approved owned helpers through their approved controls; otherwise retain state and request evidence-preserving recovery. No automatic cleanup or deletion. A new attempt gets a new ID.

## 6. Separately approved isolated restoration validation

Authorize scratch-only volume/container creation/start and backup payload/validation access separately. Use unique Atlas restore-validation UUID/project, compatible pinned images, no network/host ports/production mounts/Docker socket and no production manager/API/collectors/Discord. Keep original containers/volumes and archives untouched. Missing images or unexpected permissions block rather than trigger pulls or production repair.

Verify manifest/provenance/hashes before restoring to NEW scratch storage only. Validate PostgreSQL startup/recovery/schema/extension compatibility and Redis persistence loading with separately approved scratch queries/credentials; emit non-secret summaries only. Validate journal+commitment and any SQLite recovery on scratch, never source. A create_all call is not a migration or proof of schema equivalence. Pinned code, actual restored catalogs and startup migration compatibility need evidence before API activation.

Compare approved continuity markers and archive hashes; document exactly what was and was not validated. Preserve old lifecycle/receipt evidence as history; never activate archived PIDs/locks or silently rewrite retained-ID fences for new scratch IDs. Data restoration is not consent, no-backfill, production delivery or trading authority. Keep PAPER_ONLY/MANUAL_ONLY and all notification/research production gates closed. E136 independent witness/dual rollback/atomic snapshot safeguards remain mandatory before notifications.

Scratch resources are disposable destinations in purpose, not permission to delete them. Scratch shutdown/cleanup and any production disaster recovery need explicit exact-resource approval. Do not use --rm, global cleanup, volume deletion or restore over real Atlas volumes. Only independent successful restoration evidence can advance a sealed backup toward usable/accepted status. No real lifecycle Stage B or shortcut change follows automatically.
