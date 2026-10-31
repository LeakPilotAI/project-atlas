# R7E47B — startup fence integration plan (NOT ACTIVATED)

No production startup/shutdown file changed. Only isolated_adapter.Fence.startup_guard consumers are enforced today; no real launcher consults it. Do not use the new fence as evidence that Atlas startup is presently prevented.

## Identified admission paths

1. scripts/windows/Atlas-Background.ps1: Start action obtains Enter-AtlasLifecycleGate near line791; Worker path calls Start-AtlasDependencies near616 and spawns API near626. Gate both parent admission and worker immediately before dependency/API actions, including stale/recovery paths. The lock order must be fixed globally; never hold one lock while an inverse path waits for the other.
2. scripts/windows/Atlas-Background-Gaming.ps1 delegates Start to manager; Controls.ps1 GUI normal/GamingStart builds manager invocation; Ui.psm1 routes actions. These must retain delegation and display explicit inspection prohibition, with no bypass in Gaming/extended-hours options.
3. Legacy start-atlas.bat -> ATLAS.bat -> scripts/windows/Atlas-Launch.ps1: directly starts dependencies at259 and API at294. Must migrate or guard before any dependency action; do not run legacy stoppers or edit shortcuts without separate approval.
4. Direct developer `python -m uvicorn app.main:app`, reload workers, IDE/debugger sessions and backend/app/main.py lifespan must honor a common admission contract before collectors/DB writes. API-only guard is too late if launchers already started databases. New workers/reload require separate instance identity to avoid false releases.
5. Manual Docker Compose up/start, Docker Desktop UI and external clients do not run Python/PowerShell application guards. Cannot be fenced by SQLite alone. Operator-exclusive control or independently reviewed external enforcement is required. docker-compose.yml is a dependency entry point; no external-container inspection conducted.
6. Any future restore/migration/collector/admin task writing Atlas volumes or journals must join the same supported lifecycle contract. Raw Python/binaries/administrator operations remain outside application enforcement.

## Proposed safe integration, requiring separate approval

Use one protected fixed Atlas fence registry (not per-client arbitrary files), approved one-time initialization, no recreate-on-missing fallback, retained terminal history and independently reviewed corruption/rollback recovery. Define lock order against existing lifecycle and recovery gates. Startup holds a shared admission transaction through the supported lifecycle transition, inspection serializes admission then revalidates stopped backend/dependencies. Do not conflate a check-only function with atomic admission. Guard worker actions as well as GUI routes; prohibit any bypass when storage is unreadable/missing or state is PRECONDITIONS_VERIFIED/IN_PROGRESS/UNCERTAIN. Decide how first installation distinguishes absent state from lost evidence without silently authorizing startup.

Native Windows ACL/handle protection for registry/output, bound read-only proof collector, independent trusted recovery proof, real Docker streaming/deadline contract and exact created-helper verification are prerequisites. Crash after create before ID needs separately reviewed operation-label discovery; never infer no helper. Native D-state hard exit remains unguaranteed; do not auto-expire or release fence on observer deadline. Privileged external writers/replacement require operator exclusion, not a fictitious lock.

Future isolated acceptance: all startup paths, common-lock interleavings, process interruption, restore/start conflict, corrupted/missing registry, permission failures, helper uncertainty and worker spawn races. Future real runtime acceptance requires separate explicit approval. No shortcut migration or lifecycle action is authorized by this document.
