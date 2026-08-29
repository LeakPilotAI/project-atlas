# Wipe the local Atlas folder and clone GitHub. Must NOT be run with cwd inside the target.
# Example:
#   cd D:\Work
#   powershell -ExecutionPolicy Bypass -File "D:\Work\Project Atlas\scripts\windows\Replace-FromGitHub.ps1"
#Requires -Version 5.1
param(
    [string]$Target = "D:\Work\Project Atlas",
    [string]$Backup = "D:\Work\atlas-backup",
    [string]$Repo = "https://github.com/LeakPilotAI/project-atlas.git"
)

$ErrorActionPreference = "Stop"
$here = (Get-Location).Path.TrimEnd("\", "/")
$targetFull = [IO.Path]::GetFullPath($Target)

if ($here -eq $targetFull -or $here.StartsWith($targetFull + "\", [StringComparison]::OrdinalIgnoreCase)) {
    Write-Host "[ERROR] This window is still inside the Atlas folder." -ForegroundColor Red
    Write-Host "Open a NEW PowerShell, then:"
    Write-Host '  cd D:\Work'
    Write-Host "  powershell -ExecutionPolicy Bypass -File `"$Target\scripts\windows\Replace-FromGitHub.ps1`""
    exit 1
}

New-Item -ItemType Directory -Force $Backup | Out-Null
$envSrc = Join-Path $Target "backend\.env"
if (-not (Test-Path $envSrc)) { $envSrc = Join-Path $Target ".env" }
if (Test-Path $envSrc) {
    Copy-Item $envSrc (Join-Path $Backup ".env") -Force
    Write-Host "Backed up .env"
}
$dataSrc = Join-Path $Target "backend\data"
if (Test-Path $dataSrc) {
    Copy-Item $dataSrc (Join-Path $Backup "data") -Recurse -Force
    Write-Host "Backed up backend\data"
}

Write-Host "Stopping python/node..."
Get-Process python, node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "Removing $Target ..."
cmd /c "rmdir /s /q `"$Target`""
if (Test-Path $Target) {
    $old = "$Target.old"
    if (Test-Path $old) { cmd /c "rmdir /s /q `"$old`"" | Out-Null }
    Rename-Item $Target $old
    Write-Host "Folder was locked; renamed to $old. Delete that after a reboot if it remains."
}

if (Test-Path $Target) {
    Write-Host "[ERROR] Could not free $Target. Close Cursor/Explorer windows on that folder and retry." -ForegroundColor Red
    exit 1
}

Write-Host "Cloning $Repo ..."
git clone $Repo $Target
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$envDst = Join-Path $Backup ".env"
if (Test-Path $envDst) {
    Copy-Item $envDst (Join-Path $Target "backend\.env") -Force
    Copy-Item $envDst (Join-Path $Target ".env") -Force
    Write-Host "Restored .env"
}
if (Test-Path (Join-Path $Backup "data")) {
    $dataDst = Join-Path $Target "backend\data"
    New-Item -ItemType Directory -Force $dataDst | Out-Null
    Copy-Item (Join-Path $Backup "data\*") $dataDst -Recurse -Force
    Write-Host "Restored backend\data"
}

Write-Host "Running Fresh-Setup..."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Target "scripts\windows\Fresh-Setup.ps1")
Write-Host "Done. Double-click Project Atlas on the desktop."
