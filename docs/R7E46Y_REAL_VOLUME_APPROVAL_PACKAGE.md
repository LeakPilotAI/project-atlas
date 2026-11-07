# R7E46Y â€” conditional real-volume inspection approval package

**NOT READY FOR EXECUTION. No real-volume approval is requested until image import and independent Linux synthetic runtime gates pass.** This is a concrete review package, not permission to start a helper. Production NO-GO. No backup, restoration or production startup is included.

## Image identities

Pinned public base linux/amd64: docker.io/library/python@sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d . Anonymous public registry manifest/config bytes were hash-verified; No Docker build, pull, load or container execution occurred.

Proposed helper OCI manifest digest: **sha256:2ec3306c7d7e5714f49db15ea0db636622e01d061e87ceac27d0ec2bbd1b2574**.
Helper source digest: sha256:06d1ba89a7b89d0289ea0db87d5385797536eaa5033555822cb8f5d0325fe9a6.

The deterministic assembler created identical descriptor/config/application-layer bytes twice. A complete OCI layout is now present at D:\Work\Project Atlas\logs\diagnostics\r7e46y-20261018-020241\helper-oci. Public base layers totaling47,558,478bytes were streamed directly from the pinned public registry into this isolated artifact; all compressed blob hashes/sizes and all5uncompressed rootfs diffIDs were independently verified. No production data or Docker daemon was used. Earlier thin descriptors are not complete images and remain historical evidence. The final OCI artifact has NOT been imported into Docker,published or executed. Future runtime reference requires separately approved import and independent verification of the actual loaded manifest/config/source and controls. Both assemblers contain no Docker invocation;materialize_oci.py performs only explicit public-blob artifact assembly.

## Frozen sources â€” reverify before future approval

| Service | Expected source container ID | Expected exact project/service | Exact volume | Helper mount |
|---|---|---|---|---|
| PG | c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1 | projectatlas/postgres | projectatlas_atlas_pgdata | /inspection,readonly,volume-nocopy |
| Redis | 13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193 | projectatlas/redis | projectatlas_atlas_redis | /inspection,readonly,volume-nocopy |

One helper per source, sequentially, never both volumes in one helper. No Docker socket,host root,host PID namespace,host network,extra bind/volume,credential/config env or production client connection. Verify root D:\Work\Project Atlas,single docker-compose.yml,nononeoff,volume labels,CreatedAt,driver/options/mountpoint and exact exited consumers. Before/after metadata must agree and be no more than5seconds old,not future-dated,when making a plan. Missing/malformed/changed evidence fails closed. Optional StopSignal is not required.

Docker volumes lack a separate immutable volume UUID in this evidence. Names/labels/CreatedAt/mountpoint snapshots and reader RO mounts do not provide atomic compare-and-swap against another privileged actor deleting/recreating a named volume between checks. A future approved operation must maintain the supported Atlas lifecycle gate and operator-exclusive Docker/host writer control, recheck after helper creation BEFORE start, and verify actual helper mounts/controls. No fake lock or source ownership change. If that exclusive operational condition cannot be established, do not start. policy.py builds a non-executable plan and checks normalized control evidence; it is not an approved live Docker collector/executor or atomic fence.

## Exact proposed runtime controls

- Platform linux/amd64; immutable helper manifest/config/source verification above; pull=never,restart=no,auto-remove=false.
- Entrypoint python3 -I -B /opt/atlas-inspector/helper.py; sole argument postgres or redis; no database entrypoint.
- User0:0,cap-drop ALL,no-new-privileges,privileged=false,read-only rootfs,network none; default Docker seccomp,never unconfined. No extra capabilities or permission repair on failure.
- CPU0.25,memory128MiB,memory+swap128MiB,PID16,openfiles64. Internal RLIMIT_CPU10seconds,RLIMIT_AS128MiB,RLIMIT_NOFILE64; internal SIGALRM30seconds. Outer observation deadline40seconds.
- Entry cap100000,depth32,max64link reports,max128artifact reports,output65536bytes per helper; bounded mountinfo262144characters. Exceeded limits mean incomplete/failure,not a trusted size.
- Per-volume scalar bytes/counts and bounded known layout/artifact metadata only. No SQL/Redis/config/table/WAL/RDB/AOF content reads. No source write/open-for-write/hash/copy. Unknown names and symlink target strings output SHA256 tokens rather than literal text; known conventional filenames and safe AOF sequence names can appear. Hashes permit guessing and metadata itself is sensitive; preserve operator-only evidence handling.

UID0 without DAC override capabilities may not traverse PostgreSQL0700 owned by another UID. That is a safe permission failure,not permission to add CAP_DAC_READ_SEARCH,change source modes or silently choose another user. If blocked,a separate metadata/UID decision and approval is required. No successful readability is assumed.

## Metadata scope and limits

Allowed: directory fd opens with O_NOFOLLOW/O_DIRECTORY; scandir; lstat/fstat without symlink following; readlink strings only; inode/device comparisons,hardlink de-duplication; size/st_blocks/count aggregation. Reads only kernel /proc/self/mountinfo to independently require exact RO source mount and reject nested mounts. Regular database/configuration files are never opened.

Reports logical unique regular-file bytes and allocated regular-file/tree-entry blocks where available. This is not underlying shared-filesystem capacity or exact physical reclaimable size. Directories/root/symlinks contribute tree blocks; hardlinks deduplicate by inode/device. Sparse files have different logical/allocated sizes. No st_blocks means unknown rather than0. External symlink targets are hashed,classed blocked and never traversed; they are not accounted storage. Effective settings are always NOT_ESTABLISHED,even if postgresql.conf or dump.rdb filenames are present. Configuration includes/data_directory and Redis CONFIG SET histories require a separate safe-parser/runtime-evidence authorization.

Read-only source mounts constrain writes through that mount; they do not provide a database snapshot,exclusive writer fence or guarantee zero host/device writes. Docker helper creation/mount/log metadata,VM/page-cache bookkeeping and other existing RW actors remain outside that guarantee. volume-nocopy avoids initial source population but not a race creating a missing named volume,which must be excluded operationally. Opening directories can affect access-time/cache accounting depending on mount/filesystem behavior; no source metadata-preservation guarantee is asserted without runtime verification.

## Output, abort and retention

Future approved output directory: D:\Work\Project Atlas\logs\diagnostics\r7e46z-inspection-<UTC>-<UUID>;new exact per-service metadata.json,exit/ownership/control records only. No D:\Work\atlas-backup creation,source copy/encryption or payload archive. This directory has not been created for real inspection. Future operator approval must define restrictive output access from creation; Y changes no production ACL.

Before start abort on identity/state/fence change,missing image,unverified limits,mount RW,extra mount/socket,permission or platform mismatch. During/after operation any helper exit!=0,truncated/invalid output,unknown state,limit,external link,source drift or deadline means BLOCKED/INCOMPLETE and no size acceptance. A completed traversal explicitly says METADATA_COMPLETE_COVERAGE_UNPROVEN,not recovered/backup-complete.

Helper should exit normally within30seconds. Linux D-state/syscall stalls can defeat an in-process alarm; actual cgroup limits/exit behavior require synthetic runtime tests. On40second outer deadline preserve exact created helper ID/process/operation record; no automatic SIGKILL,global Docker stop or cleanup. Any separately approved graceful SIGTERM may target only that positively verified helper; if it remains unresolved,preserve the fence/evidence and request recovery. Production Atlas/DB remain stopped. No --rm,container/volume/image deletion or automatic cleanup authorized. Later cleanup needs explicit exact-resource permission; no source volume removal ever implied.

## Required approvals, in order

1. Separately approve import of the complete pinned OCI artifact and independently validate loaded manifest/source/dependencies and licenses; separately authorize Linux synthetic-only helper/container lifecycle with disposable fixtures,RO proof,cgroup limits,deadline and permission tests. No real Atlas volumes.
2. Review actual runtime findings and close required gaps. Only then approve exact operation ID,tool image,source fingerprints,exclusive window,controls,output policy,normal-exit and uncertain-failure handling for the real metadata-only helper.
3. Backup destination/security/key handling,actual data backup and independent scratch restoration remain separately approved milestones. No production startup,live trading,Discord or shortcut migration follows from inspection.
