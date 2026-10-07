# Windows operation and recovery

This document describes the current tracked Windows operator contract. It is intentionally scoped to Project Atlas resources: Atlas startup and shutdown must not terminate Docker Desktop, Genesis, unrelated Python/Node processes, unrelated containers, or other projects.

## Prerequisites

Install:

- Git
- Python 3.12+
- Node.js LTS
- Docker Desktop

Atlas secrets and local data are not restored by Git. Keep backups of the local environment files and any durable data you need to preserve.

Typical backup targets:

```text
D:\Work\atlas-backup\
    root.env
    backend.env
    data\
```

Never commit secrets.

## Clean GitHub copy

Open PowerShell outside the existing Project Atlas directory.

Before replacing an existing installation, use the tracked Atlas stop path rather than killing generic Python or Node processes:

```powershell
cd "D:\Work\Project Atlas"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Atlas-Stop.ps1
```

Back up local state before deleting/replacing the folder:

```powershell
New-Item -ItemType Directory -Force D:\Work\atlas-backup | Out-Null
Copy-Item "D:\Work\Project Atlas\.env" D:\Work\atlas-backup\root.env -ErrorAction SilentlyContinue
Copy-Item "D:\Work\Project Atlas\backend\.env" D:\Work\atlas-backup\backend.env -ErrorAction SilentlyContinue
Copy-Item "D:\Work\Project Atlas\backend\data" D:\Work\atlas-backup\data -Recurse -ErrorAction SilentlyContinue
```

Then clone a clean copy:

```powershell
cd D:\Work
Remove-Item -Recurse -Force "D:\Work\Project Atlas"
git clone https://github.com/LeakPilotAI/project-atlas.git "D:\Work\Project Atlas"
cd "D:\Work\Project Atlas"
```

Restore only the local files you intentionally backed up. Keep root and backend environment backups distinct instead of copying one environment file over both locations blindly:

```powershell
Copy-Item D:\Work\atlas-backup\root.env .\.env -ErrorAction SilentlyContinue
Copy-Item D:\Work\atlas-backup\backend.env .\backend\.env -ErrorAction SilentlyContinue
# Optional durable local history:
# Copy-Item D:\Work\atlas-backup\data .\backend\data -Recurse
```

Review `.env.example` when creating or reconciling environment configuration. Do not infer or invent missing credentials.

## First-time setup

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\Fresh-Setup.ps1
```

The setup installs the tracked desktop shortcuts:

- **Project Atlas** -> `ATLAS.bat`
- **Stop Atlas** -> `ATLAS-STOP.bat`

The launcher uses the existing local Docker dependencies, starts Atlas, waits for the established readiness gate, and opens the API-served dashboard only after readiness succeeds.

Dashboard:

```text
http://127.0.0.1:8000/dashboard
```

## Daily operation

1. Double-click **Project Atlas**.
2. Keep the Atlas console available while the local runtime is operating.
3. Use **Stop Atlas** for predictable graceful shutdown.
4. Closing the Atlas console also invokes the tracked Atlas teardown path.

Shutdown is scoped to Atlas-owned resources. Docker Desktop and other projects such as Genesis stay running.

The stop path first requests graceful API shutdown. If the process does not exit within the established timeout, it may force only verified Atlas process trees. It does not use generic Python/Node termination as part of normal operation.

## Readiness and diagnostics

Startup requires the established readiness checks before the browser opens. A failed readiness gate is a failed startup, not permission to bypass the gate.

Useful tracked diagnostics include:

```text
logs/diagnostics/launcher-ready.json
logs/diagnostics/stop-latest.json
```

For the permanent desktop integration smoke diagnostic:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\Atlas-Desktop-Smoke.ps1
```

See `docs/ATLAS_OPERATOR_GUIDE.md` for the current operator contract and diagnostic interpretation.

## Updating an existing copy

Stop Atlas first. Do not update a live Atlas process and assume it has adopted new code.

Use the repository's tracked update workflow only after backing up local secrets/data and reviewing the branch/ref it will install. The operator must not assume that an arbitrary local development branch is the release branch.

If using `scripts\windows\Pull-And-Ready.ps1`, inspect its target ref and effects before execution. It is a destructive tracked-file refresh workflow and is not a substitute for preserving local secrets/data.

After updating, reinstall/reconcile dependencies as required and recreate shortcuts with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\Install-DesktopShortcut.ps1
```

Then start Atlas normally and require the readiness gate to pass.

## Safety boundary

These Windows procedures are operational packaging/recovery instructions only. They do not alter strategy selection, evidence requirements, PAPER/execution authority, promotion gates, Discord lifecycle gating, schedulers, or live-capital permissions.
