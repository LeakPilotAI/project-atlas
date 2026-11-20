# R7E46U Stage A retry — backup creation and restoration-validation proposal

**NOT APPROVED / NOT EXECUTED.** No backup payload, database contents or secrets were read in Stage A. Creating a backup necessarily reads payload bytes and is outside the current authorization. Restoring/validating requires separately approved scratch resources and potentially database-content/credential access. No new backup, container, volume, network or directory for backup storage was created by this proposal.

## Exact evidence gap

No usable backup was established at the four scoped locations recorded in backup-metadata.json. All were absent. Other locations were not searched. There is no attributable PG/Redis backup artifact, source identity/time/tool record, integrity manifest, retained compatible image/version or successful restoration report. Named volumes and exit code0 are not backups. O's journal/commitment recovery instructions and WINDOWS local-file-copy examples do not certify database/cache volume restoration.

## Source identity to freeze again before approval

- PG container: `c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1`
- PG volume: `projectatlas_atlas_pgdata` at `/var/lib/postgresql/data`
- PG image: `sha256:d8336a5c9cc49bdbf1e935234e8c87ab64b6d6d195fd2ecedff7b00185557631`
- Redis container: `13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193`
- Redis volume: `projectatlas_atlas_redis` at `/data`
- Redis image: `sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99`
- Compose project: projectatlas; root D:\Work\Project Atlas; single docker-compose.yml; non-oneoff; service labels postgres/redis. Both were exited with PID0 and exit0 during inspection.

These observations are not permission to stop a running service or assume it remains stopped. Abort if any ID/label/image/mount/state changes.

## Separate approval package A — backup creation only

1. Operator approves a bounded maintenance/ownership window, exact source IDs/volumes and a new protected local destination such as D:\Work\atlas-backup\<UTC-UUID>. No cloud/upload/VPS. Confirm capacity, owner ACLs, confidentiality/encryption, retention and recovery-key handling without printing secrets. Destination creation and payload reading need explicit approval.
2. Recheck Atlas STOPPED and both exact dependencies already exited, no writer or uncertain lifecycle request, and no external Compose controller modifying them. If running/ambiguous, stop and request separately scoped lifecycle permission; never treat backup approval as stop permission.
3. Verify, under separately approved configuration-only scope, that actual PostgreSQL data_directory/WAL/tablespaces and Redis storage directories are covered by the frozen source mounts. PGDATA metadata matches /var/lib/postgresql/data, but this alone does not rule out config overrides or external tablespaces. Unowned/external storage means BLOCKED until separately reviewed. Select a reviewed, digest-pinned local cold-volume backup tool. A helper container, if needed for Docker Desktop Linux volumes, requires explicit creation/start approval, a unique Atlas-backup project identity, no network, nonprivileged execution and production source mounts strictly READ-ONLY. No Docker socket, unrelated paths or volumes may be mounted. Do not use an unreviewed image or implicit pull. No source chown/chmod/repair, database init, CONFIG SET, prune/down/rm or volume deletion.
4. Produce PostgreSQL and Redis full-volume archives preserving file ownership/modes/symlinks and required extended metadata. Treat them as confidential; never echo payloads. No claim that an arbitrary copy of a running database is consistent. A cold copy is accepted only with verified stable stopped sources and no writers throughout the window.
5. Under O's approved independent journal/commitment fencing procedure, separately preserve the exact journal plus commitment and any necessary SQLite sidecar evidence coherently. Do not separately copy a changing journal and commitment, reconstruct evidence, migrate or edit live records. If an atomic/coherent snapshot cannot be established, fail closed.
6. Write an independent manifest: operation UUID; UTC/CDT window; operator approval; source container IDs, project/root/config hash, image digests, volume metadata, stopped-state evidence; tool digest/version/options; file/archive sizes and hashes; exclusion policy; confidentiality/ACL controls; journal/commitment identity; errors. Verify source state/metadata remained unchanged and archives are readable/integrity-checked without printing database contents. Store manifest and restoration contract independently from the payload; retain all failures.
7. Report BACKUP_CREATED_UNVALIDATED, not usable/accepted. Do not start production or Stage B.

## Separate approval package B — isolated restoration validation

1. Approve reading backup payloads and creating unique scratch-only volumes/containers under a dedicated Atlas restore-validation UUID/project. Preserve originals. Use no production mounts, ports, networks, aliases or Docker socket. Network isolation must prevent any Atlas/Genesis connection; never reuse projectatlas or the real container names. Required images must be reviewed/pinned; no unapproved pulls.
2. Verify archived hashes/provenance before extracting into NEW scratch storage only. Use production-compatible image versions and restore permissions into scratch only. Never overwrite the live PG/Redis volumes or any journal.
3. Start only the explicitly approved scratch database processes. Secure operator-provided validation credentials are separately authorized, never taken from logs or printed command arguments. Run only approved validation queries against scratch copies, including schema/row-count or integrity checks and Redis persistence loading; no application scanner, collectors, Discord, live-capital or external provider access. Non-secret summaries only. Any database-content access scope must be specified before queries.
4. Validate a coherent journal/commitment scratch pair using the O integrity verifier and independent manifest; no fabricated events/fills or production migration. Confirm expected continuity markers from an approved baseline. Missing baseline, version mismatch, load/recovery errors, corrupt archive, inconsistent pair or permission failure blocks acceptance.
5. Record restoration timings, exact scratch IDs and source hashes, verification results and limits. Source backups and production IDs/mounts remain unchanged. Scratch shutdown requires explicit authorization; retain all artifacts/resources unless a later exact-resource cleanup is approved. No global or implicit cleanup, no --rm/deletion default.
6. Mark backup usable only after independent provenance/hash/compatibility/restoration checks succeed. This does not approve production restoration or real lifecycle Stage B. Production restoration after a failure requires its own reviewed data-recovery plan and explicit approval.

## Redis persistence gap

Metadata confirms the default redis-server command and /data named volume, not effective previous save/AOF settings or file health. The container is stopped; no server CONFIG/INFO query or exec was performed. Before declaring preservation, approve a safe configuration-only review or infer configuration from verified scratch restoration under scope B, recording the distinction between persisted and volatile data. Never start production merely to obtain settings, read secrets, or silently enable persistence.

## Hold criteria

No operator approval, source drift, any active writer, insufficient disk/permissions, uncertain request, unreadable archive, missing provenance or failed restoration means BLOCKED. Keep production release NO-GO, preserve evidence and do not proceed to Stage B or shortcut installation.
