# Windows: clean GitHub copy + one desktop shortcut

One shortcut. It starts Docker, the API, and the **frontend dashboard**,
then opens the browser. **Close that Atlas window** to force-stop the bot
and Docker Desktop.

There is no separate Start / Stop desktop icon.

## Save secrets before deleting the old folder

GitHub does **not** contain `.env`, the Python venv, or `backend/data`.
Copy these somewhere safe first:

```
D:\Work\atlas-backup\
    .env                  ← copy of backend\.env  (Discord token, DB password)
    data\                 ← optional: paper journal / investment files
```

In PowerShell:

```powershell
New-Item -ItemType Directory -Force D:\Work\atlas-backup | Out-Null
Copy-Item "D:\Work\Project Atlas\backend\.env" D:\Work\atlas-backup\.env -ErrorAction SilentlyContinue
Copy-Item "D:\Work\Project Atlas\.env" D:\Work\atlas-backup\root.env -ErrorAction SilentlyContinue
Copy-Item "D:\Work\Project Atlas\backend\data" D:\Work\atlas-backup\data -Recurse -ErrorAction SilentlyContinue
```

## Replace the folder with GitHub

Close Atlas / Docker if they are running. Then:

```powershell
# stop leftover python/node if needed
Get-Process python, node -ErrorAction SilentlyContinue | Stop-Process -Force

Remove-Item -Recurse -Force "D:\Work\Project Atlas"

git clone https://github.com/LeakPilotAI/project-atlas.git "D:\Work\Project Atlas"

Copy-Item D:\Work\atlas-backup\.env "D:\Work\Project Atlas\backend\.env"
Copy-Item D:\Work\atlas-backup\.env "D:\Work\Project Atlas\.env"
# optional paper/investment history:
# Copy-Item D:\Work\atlas-backup\data "D:\Work\Project Atlas\backend\data" -Recurse
```

Need: Git, **Python 3.12+**, **Node.js LTS**, **Docker Desktop**.

## First-time setup (venv + frontend + shortcut)

```powershell
cd "D:\Work\Project Atlas"
powershell -ExecutionPolicy Bypass -File scripts\windows\Fresh-Setup.ps1
```

That creates **one** desktop icon named **Project Atlas** and deletes old
Start/Stop Atlas icons.

## Every day

1. Double-click **Project Atlas** on the desktop.
2. A console window stays open. The dashboard opens at
   [http://127.0.0.1:3000](http://127.0.0.1:3000).
3. Close that console (or Ctrl+C) when you are done. That:
   - kills the API
   - kills the frontend
   - `docker compose down`
   - force-quits Docker Desktop

Do not use the old Start / Stop shortcuts.

## Later updates (do not delete the folder)

```powershell
cd "D:\Work\Project Atlas"
git pull origin main
```

`.env` and `backend\data` stay on disk. Re-run `Fresh-Setup.ps1` only if
Python packages or the frontend install break.
