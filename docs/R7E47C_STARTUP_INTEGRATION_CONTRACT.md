# R7E47C — independent startup integration contract (NOT ACTIVATED)

Review time: 2026-10-18T07:51:22.811310-05:00. Source-only review; no production startup/shutdown or shortcut changed. The durable inspection fence is currently enforced ONLY by isolated cooperating callers. No actual manager, worker, API or Docker client consults it.

## Entry-point coverage matrix

| Entry point | Exact guard location required | Today / bypass |
|---|---|---|
| Atlas-Background.ps1 Start,791–837 | After existing Enter-AtlasLifecycleGate, before Assert-CleanStart/New-ExclusiveJsonFile/worker creation; reserve durable startup intent | No inspection guard; parent mutex alone insufficient |
| Background worker585+, dependencies616, API626, Worker action896 | Reacquire global lifecycle gate and inspect durable startup intent/fence BEFORE dependencies; reject mismatched run/process identity | Worker may run after parent releases mutex837; direct Worker invocation must not bypass admission |
| Gaming wrapper / GUI | Gaming.ps1 delegates manager; Controls.ps1 normal/GamingStart70–93 and240 must retain authoritative manager guard and clear refusal display | No separate permission from Gaming/env/extended-hours flags; UI checks alone inadequate |
| Legacy start-atlas.bat -> ATLAS.bat -> Atlas-Launch.ps1 | Before Docker Desktop launch241, Compose up259 and API293–294; migrate or guard under separate approval | Bypasses manager; no legacy stop or shortcut executed/modified |
| Desktop smoke harness | Atlas-Desktop-Smoke.ps1 invokes legacy launcher159; must inherit equivalent guard BEFORE launch | Read-only reviewed, never run; cannot treat test tool as exemption |
| Direct uvicorn/debug/reload/API | An admission shim before application import where imports can have effects, plus lifespan first operation108 before Redis125/schema writes136/collectors | Lifespan-only gate is too late to stop launcher dependency startup; unmanaged/import-time writers need review |
| Standalone scripts/jobs/migrations | Before any DB/journal writer or dependency action | Arbitrary Python/admin/SQL commands bypass application guards |
| Manual Compose/Engine/Desktop | Outside Python/PowerShell application authority | PostgreSQL/Redis compose restart=unless-stopped can restore writers when Engine resumes; external control/maintenance window required |

Atlas-Ready is read-only inspection, not an admission authority. Fresh-Setup/Pull-And-Ready can modify installation/configuration and must be prohibited during inspection maintenance; no invocation here. Any future watchdog restart, scheduler or recovery path that starts a writer must join the same contract. Scope is reviewed repository entry points, not a claim to enumerate external scheduled tasks or arbitrary commands. No Genesis resources were inspected.

## Proposed fixed storage and initialization

Proposed, NOT CREATED: `D:\Work\Project Atlas\logs\runtime\inspection-control\fence.sqlite3`. Dedicated control directory, separate from output, journals and backups. Only the approved current Windows owner SID and SYSTEM may write. Alternative service accounts require explicit SID approval; never grant Everyone/Users/Authenticated Users or automatically migrate identities. Validate owner, protected directory DACL, no broad inherited writes, reparse-free pinned handles and expected fixed root. Use the native output backend's handle/DACL principles, but do not assume its JSON publication code secures SQLite automatically.

Provision once during a separately approved verified-stopped maintenance window. Native exclusive protected creation; schema/instance ID bound to Atlas root and approved writer identity; record initial NOT_AUTHORIZED state and independent initialization witness. No initialize-on-start switch, env override or recreate-on-missing behavior. SQLite sidecars must remain inside the protected directory with only approved owner/SYSTEM access; validate native ACLs and reparse/type/link identities. SQLite path-to-handle/sidecar race handling and rollback-resistant authority are still implementation gates. Do not create this production registry during C.

Unavailable, missing, unreadable, unexpected owner/ACL, corrupt, unsupported schema, replaced instance or contradictory state means AMBIGUOUS/refuse startup and inspection. Existing stopped absence must not be interpreted as NOT_AUTHORIZED. Initialization and lost-state recovery are distinct operator-approved operations.

## Lock ordering and startup handoff

Single required order: (1) existing Global Atlas lifecycle mutex (canonical-root SHA256), (2) fixed fence SQLite write transaction, (3) existing run/ownership/recovery records. All participating inspection/start/maintenance operations use that order. Never acquire/wait for global mutex while holding SQLite or wait for a child while holding a mutex the child needs. Existing global mutex uses nonblocking admission and rejects abandonment; retain fail-closed ownership review.

Parent reserves a durable STARTUP_PENDING intent bound to run ID, exact parent/worker creation identity and controlled generation under both gates; inspection must reject any such intent, even with no API listener. Parent may create worker but must release gates without waiting for worker readiness. Worker independently reacquires gates, verifies intent/ownership and active inspection prohibition, marks startup in progress BEFORE dependencies/API. On child creation uncertainty retain intent, never roll back to safe-stopped by assumption. Current B states/records do not implement this bidirectional intent registry, so this is a required future change, not claimed enforcement.

Inspection acquires same gates, independently verifies stopped API/dependencies/no lifecycle intent, commits PRECONDITIONS_VERIFIED/UNCERTAIN-before-create, then releases global mutex with durable inspection prohibition retained through the whole operation. Startup rechecks it under gates; a check-only UI or an expiring lock is insufficient. Short transactions must not span remote Docker I/O. Completion/recovery updates under the same lock order and explicit version/CAS. Do not hold the global mutex for an unbounded helper wait.

## Refusal and recovery ownership

PRECONDITIONS_VERIFIED, IN_PROGRESS, UNCERTAIN or unresolved startup/recovery intent always prohibit new writers. Timeout, process loss, disconnected Engine or no listener is NOT proof of helper exit. Do not auto-expire/clear fences, retry, initialize missing DB, start services or kill processes. Independent read-only witness must revalidate approved operation, exact helper container ID/image/labels/control identity and fresh exited PID0/finished evidence; reconcile all sources/consumers and pending lifecycle records. If create was interrupted before ID persistence, enumerate only approved exact operation-label candidates under a separately reviewed discovery procedure. Zero/ambiguous/unreachable candidates retain uncertainty; no name matching or inferred exit.

Operator/recovery owner approves transition to FAILED after exit proof; never accept partial metadata as complete or replay old inspection. External rollback/tamper of same-user state requires separate trusted witness/rollback-resistant recovery design. Parent/worker crashes, abandoned global mutex, corruption and unknown helper identity require explicit evidence-preserving recovery; no production recovery is implemented here.

## Output and testing contract

Future operation output uses a new explicitly approved private NTFS root; opaque operation names, filtered totals only, all records flushed before no-replace commit link. Readers verify native DACL/type/reparse/link identity and metadata/audit hashes and compare with independent fence digest. Pending files without a valid committed marker are retained/unpublished; do not repair or overwrite. Native output is not backup/encryption, privilege isolation from the same owner/SYSTEM/admin, nor guaranteed power-loss durability.

Before integration approval: native Windows registry/sidecar ACL and handle tests; all listed launch paths; parent/worker handoff races; common lock-order interleavings; DB absent/corrupt/replaced/rollback; crash before/after spawn/create/commit; independent exit-proof and identity replacement; Engine restart and external-writer exclusion; output partial/crash/integrity; Gaming normal PAPER cadence and resource controls; controlled owned-runtime acceptance separately approved. True symlink rejection remains NOT TESTED on this token (creation privilege unavailable); native junction tests do not waive it. No production activation or real-volume helper follows from this design.
