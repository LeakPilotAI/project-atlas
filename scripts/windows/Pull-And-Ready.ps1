# Pull latest main and recreate the desktop shortcut.
# Close the Atlas window first.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

Write-Host "Project Atlas pull in $Root"
git fetch origin
git pull origin main

$VenvPy = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    Write-Host "==> Refresh Python package (validation module)"
    & $VenvPy -m pip install -e (Join-Path $Root "backend") -q
} else {
    Write-Host "[WARN] no venv yet - run Fresh-Setup.ps1"
}

powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "Install-DesktopShortcut.ps1")

Write-Host ""
Write-Host "Ready. Close any running Atlas window, then double-click 'Project Atlas' on the desktop."
Write-Host "Dashboard: http://127.0.0.1:8000/dashboard"
