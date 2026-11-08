# R7E47D — shared-fence integration and recovery boundary

**ISOLATED CONTRACT ONLY. No production manager/worker/GUI/API/Docker behavior changed.**

## Provisioning and fixed authority

The reusable Registry requires an explicit canonical local NTFS root and expected provisioned instance UUID. Production's proposed logs/runtime/inspection-control path remains uncreated. No environment/CLI fallback to a new root is approved. A future bridge must pin root/instance from independently protected operator configuration; letting each caller choose a different valid registry defeats shared exclusion.

Provision once in an operator-approved stopped window. Exclusive native directory creation with owner/SYSTEM protected DACL prevents concurrent initializers; only one child process succeeds in native tests. Provision/ready witnesses, immutable root/database file identities and revision receipts bind the instance. Missing/partial/corrupt/foreign instance never triggers initialize/reset. Native registry methods do not clear recovery-required markers or expired startup intents.

One native global mutex per verified root identity serializes cooperating processes; its own kernel-object DACL is independently verified for exact owner/SYSTEM mutex rights. SQLite transactions are BEGIN IMMEDIATE, busy timeout0.5s; coordinator acquisition deadline500ms. No parent waits for a worker under these gates. Correct integration order is existing Atlas lifecycle global gate -> registry mutex -> SQLite transaction -> existing ownership/recovery records. No inverted waits. Short local operations only, no Docker/network/helper wait inside the transaction. A blocked native disk I/O can still hold an owner; no hard wall-clock disk deadline is claimed.

## Startup entry-point matrix

| Path | Available isolated API | Actual enforcement today / remaining work |
|---|---|---|
| Background manager Start791 | reserve_start before worker creation | Not connected; add outer existing lifecycle gate and exact run/parent intent |
| Worker585+, dependency616/API626 | bind_worker then independent admit_worker | Not connected; parent/worker handoff proof and pre-side-effect guard required |
| Gaming wrapper/Controls GUI | Delegate authoritative manager API/refusal | Not connected; no Gaming bypass or UI-only grant |
| Legacy ATLAS.bat/Atlas-Launch | Same parent/worker protocol before dependencies | Still bypasses; migration/guard and shortcut changes separately approved |
| Desktop smoke/test launch | Same controlled launcher, no test exemption | No real smoke launched; legacy path needs equivalent guard |
| Direct API/import/lifespan | Protected admission shim and worker proof before writes | Not connected; import-side effects/Redis/schema/collectors need early guard |
| Standalone migration/research writers | Join shared registry before writes | Not connected; raw SQL/Python cannot be assumed cooperative |
| Manual Compose/Desktop/Engine restart | No application authority over these clients | External writer exclusion NOT enforced by this registry |

Parent commits PENDING intent with operation, nonce, process identity and30s window BEFORE creating a worker. It releases locks before spawn/readiness wait. Parent binds exact independently observed worker identity; worker must present matching operation/nonce/identity and obtain STARTING admission before dependencies/API. Early/unbound, delayed, reused, replaced or replayed identities are refused. PENDING/STARTING remain durable after expiration or parent exit; they do not imply a held mutex or an automatic retry permission.

Native self identity uses actual interpreter PID, GetProcessTimes creation time, GetModuleFileNameW executable-content hash and hashed GetCommandLineW. No foreign process enumeration. Windows venv launcher PID/executable can differ from the interpreter; do not bind worker from Popen PID/sys.executable alone. Future independent process ownership collector must bind actual worker image/creation/command/run identity using existing safeguards, not trust self-reported JSON.

## Independent recovery contract

Inspection admission requires explicit approval/fresh stopped/no-pending facts and atomically refuses any startup intent. It persists UNCERTAIN BEFORE any future create action. Exact helper binding is single-use; disconnected/missing helper never clears state. Recovery requires fresh exited PID0/operation/helper proof and a revision/state/proof-bound signed grant from a distinct authority provider. Replay/changed revision/stale/future proof, wrong helper, boolean PID and forged/foreign key grants fail.

Current authority is deliberately FixtureRecoveryAuthority only: ephemeral HMAC keys and synthetic facts for isolated tests, never production credential provisioning or a trusted external witness. A production independent principal/key/witness/rollback authority remains BLOCKED, including existing E136 gates. No real Docker proof acquisition, operation-label discovery or process-exit verifier has been implemented by D. Explicit grant records an INSPECTION_FAILED_EXIT_PROVEN audit event and consumes operation identity; it does not label inspection successful or retry it.

Storage ACL/identity/integrity failures and abandoned coordinators latch recovery-required.json before SQLite can remove sidecar evidence. Normal helper-exit recovery cannot clear this storage latch. A database commit with missing receipt also remains fenced. Independent storage-recovery/migration and failed startup/owned shutdown intent reconciliation need a separately approved protocol; there is no delete/reset escape hatch here.

## SQLite protection and known boundary

Main file is created with explicit protected native DACL. SQLite-created journal/WAL/SHM inherit only owner/SYSTEM grants from the protected root; their ACLs are verified independently while live. Parent protection is not proof of child protection. All four filenames are checked with no-follow native handles, owner/type/link identity checks and before/after path-binding checks. Main file identity is frozen in ready witness.

SQLite's built-in Win32 VFS still opens absolute paths; this is NOT a handle-relative SQLite VFS. Before/after native bindings and ACLs plus cooperating mutex do not eliminate privileged/same-owner directory-reparse or sidecar substitution TOCTOU. Root/ancestor handles deny deletion and tested substitutions are rejected, but concurrent hostile privileged mutation is not proven excluded. An independently reviewed handle-relative VFS/broker or justified operator-exclusive maintenance policy is required before real use. Application exclusion never prevents external Docker or other authorized writers.

Supported isolated profiles: PERSIST and WAL, synchronous FULL, memory temporary store, attachments prohibited, trusted schema off,64KiB SQLite value bound; authorizer refuses journaling/sync/temp-store drift, temporary tables, virtual-table/extension paths and attachments. This narrow fixed-SQL profile is not a general-purpose SQL sandbox against trusted code that can replace the authorizer. SQLite version3.49.1/Python3.12.10 tested. Future SQLite VFS/temp-file changes require reacceptance; no guarantee for arbitrary SQL/ATTACH/VACUUM/other versions.

Receipt files are independent filesystem commitments, detecting a DB-only rollback, audit truncation or commit/receipt gap; they are not tamper-proof against owner/SYSTEM rolling back all files or power loss. Actual flushes/transactions and process-crash tests are not physical disk-power-loss acceptance. Native true symlink fixture remains untested due creation privilege1314; junction tests do not waive it.

Before production integration: independent security/VFS/authority review; trusted fixed location/initialization/sidecar policy; cross-session/SYSTEM/alternate-user and native true-symlink acceptance; all startup paths and lock handoff under isolated cloned lifecycle bridge; independent process/helper proofs and failed-start/shutdown reconciliation; fresh real ownership/image; external writer window. Actual provision, wiring, runtime acceptance or real helper execution each require separate explicit approval.
