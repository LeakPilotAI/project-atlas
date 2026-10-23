# R7E46W Stage A2 — backup tooling acceptance and restore authorization contract

DRAFT, NOT APPROVED FOR REAL DATA. Companion to R7E46W Stage A procedure; original U/W documents remain unchanged. No runnable production backup tool or helper is accepted by this document.

## Exact source scope and fail-closed admission

Revalidate current full IDs, projectatlas/service/root/config/nononeoff/image/mount bindings and exact-volume consumers. Sources are the two positively owned named volumes, entire backend/data, separate root/backend confidential configuration, exact dirty source/schema/dependency artifact, and explicitly enumerated recovery/audit history. Unknown effective storage, external paths or credentials block instead of expanding scope automatically. No names-only ownership, arbitrary path/env discovery, all-Docker/WSL scan, Compose config secret expansion or Genesis access.

A future helper must be approved by local immutable image/tool digest, reviewed entrypoint/arguments/UID/capabilities, read-only root, no network/socket/host PID namespace, only exact source mounts RO and exact NEW destination RW, bounded CPU/RAM/I/O/process limits. No source chmod/chown/checkpoint/repair/init, database start, broad privilege, image pull, --rm or destructive cleanup. Permission failures preserve evidence and block. This is a required review contract, not a tested helper configuration.

## Continuous writer exclusion

Point-in-time stopped state and unchanged metadata are insufficient. Future operation must maintain actual supported Atlas lifecycle gate, relevant journal/commitment writer locks and operator-exclusive host/WSL/Docker control for all source writers. A private backup mutex alone cannot fence programs that ignore it. No resetting stale fences, fake manifests or silent recovery. Abort before copying if complete fencing cannot be established; lost fencing means FAILED/QUARANTINED even when hashes or copy return success. Periodic checks supplement maintained locks; before/after booleans in synthetic tests do not implement continuous exclusion.

## Archive/manifest/confidentiality

Preserve file modes/UID/GID/symlinks and required metadata; never follow unapproved targets. Measure logical/allocated expansion and count all source, verification and scratch footprints. Do not infer volume sizes from null UsageData or compressibility. Maintain journal/commitment/sidecar coherence and retain independent rollback witness separately. No claiming E136 recovery atomicity merely because files share an archive.

Canonical versioned manifest: approval/operation ID, UTC/CDT window, source ownership and versions, exact coverage/exclusions, writer-fence evidence, tool digest/options/resource envelope, archive sizes/hashes, approved encryption identity WITHOUT keys, destination path/security verification, verification and restoration state, errors. Do not store confidential file contents, connection strings, encryption key material or command-line secrets in reports. Public inventory metadata itself can be confidential. Authenticate/encrypt manifest as appropriate, keep independent hash/approval witness outside same rollbackable bundle; do not self-hash recursively.

State machine DRAFT -> PREFLIGHT_VERIFIED -> WRITING -> SEALED_UNVALIDATED -> RESTORE_VALIDATED -> ACCEPTED. Successful archive creation is not usability. Completion marker must be new-operation/no-overwrite, atomic after all mandatory verifications, with archive/manifest/marker flush and platform crash guarantees independently reviewed. The synthetic hard-link experiment tests one same-volume NTFS publication mechanism only; no directory/power-loss durability, encryption or full archive implementation is certified. Never apply synthetic ACCEPTED markers to actual backup evidence.

Interruption/full disk/identity drift/ACL/encryption/fence/hash failure preserves all partial artifacts and logs; no success marker, no automatic deletion, no reusing old operation ID. Future cleanup/helper shutdown requires exact-resource authorization. No uncertain replay, blind retry, production restore or forced process termination.

## Isolated tests actually performed

New evidence-only synthetic_contract.py/test_synthetic_contract.py use generated synthetic bytes. Coverage: six exact source keys, each missing/tampered source, unapproved extra source, unknown manifest/schema, absent restoration evidence, changed/missing fence and active writer flags, unknown/malformed/insufficient capacity, exact capacity boundary, no-overwrite marker/replay and preserved partial failure. No Docker client, real source selection, confidential data or production state imported by these tests.

Initial sandbox run:21 passed/1 failed (Windows hard-link AccessDenied). Same tests outside sandbox:22 passed/0failed in0.13s. Original failure logs retained; no source/ACL workaround introduced. Atomic publication is therefore tested only under the ordinary unsandboxed test identity on synthetic NTFS paths, not on a future secured/encrypted destination. Production tool gate remains BLOCKED.

Existing extracted-source lifecycle/ownership/journal/Discord regressions use network/production-data guards. First sandboxed run stalled after reaching adversarial journal fixtures and was cancelled; exact cause unverified. No worker remained in subsequent exact-test identity inspection. Retry evidence and final result live in this milestone evidence folder. Never label interrupted run a pass.

## Capacity-aware scratch restoration, separately approved

Before any restoration: usable protected archive, independently verified manifest/hash/authentication, effective complete storage coverage, compatible exact images locally available, allocated/logical capacity plus scratch database growth, operator and key recovery policy. Reserve disk continuously; never overwrite live source or backup archive.

Use NEW distinct scratch paths/volumes and UUID project, no production mounts, network access, host ports or production Atlas manager/API/collectors/Discord. Source backup is read-only; only scratch destinations RW. Restore permissions and validated external link mappings on scratch, preserving production originals.

Offline: archive completeness/metadata fidelity, symlink target allowlist, journal+commitment/SQLite integrity and recovery continuity, independent witness checks. These require separate payload-read/restore permission even without database startup.

PostgreSQL: separate explicit isolated-container startup approval. Exact major/extension-compatible image; startup/recovery errors fail. Approve bounded scratch catalog/schema/extension and evidence-continuity checks, non-secret summary only. Startup alone is not full semantic correctness. No production connect and no repair of original backup.

Redis: separate isolated-image startup/load approval; validate chosen RDB/AOF format/load and scoped integrity/durability markers on scratch. Offline checker invocation also needs payload authorization; never use repair/fix on the original archive or source. Cannot reconstruct volatile state absent at shutdown.

Actual scratch shutdown and cleanup need explicit exact-ID authorization, with retention of logs/results; disposable means replaceable validation destination, not automatic deletion approval. No production DB/API startup or rebinding old lifecycle receipts is authorized. PAPER_ONLY/MANUAL_ONLY, E136 consent/no-backfill gates and PM-V2 controls persist.

## Exact remaining approval sequence

1. A3 metadata-only helper/tool review and authorization: exact local digest, mount IDs/paths, stat/link metadata, safe allowlisted config parser and volume sizing, no relation/RDB/AOF payloads, no production starts. If helper creation/start is not approved, equivalent authoritative sanitized evidence must be supplied instead. Do not launch it under Stage A2.
2. Separate protected directory creation/ACL and synthetic write verification; reviewed encryption/key-custody/recovery policy; no secrets printed and no live source copied.
3. Concrete production backup-tool implementation/isolated acceptance and maintained writer-exclusion window approval; actual payload/secret backup and helper lifecycle explicitly enumerated.
4. Independent scratch restoration/payload access approval, including isolated database-container startup, bounded validation queries and precise retained-resource lifecycle scope.

Any unresolved prerequisite blocks its dependent step. Cash-scanner acceptance, provider rights/HTTP/stuck workers, Ruff policy, clean-machine/runtime/Gaming/shortcuts, E136 and Discord/Prediction Market Intelligence V2 remain separate gates. No production GO from this contract.
