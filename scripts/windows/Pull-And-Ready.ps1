# Overwrite tracked files from GitHub main, keep .env + data, recreate desktop shortcut.
# Close the Atlas window first.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

Write-Host "Project Atlas overwrite in $Root"

function Set-DotEnvKey {
    param([string]$Path, [string]$Key, [string]$Value)
    if (-not (Test-Path $Path)) { return $false }
    $lines = @(Get-Content -Path $Path)
    $found = $false
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        if ($line -match ("^\s*#?\s*" + [regex]::Escape($Key) + "\s*=")) {
            if (-not $found) { $out.Add("$Key=$Value"); $found = $true }
        } else {
            $out.Add($line)
        }
    }
    if (-not $found) { $out.Add("$Key=$Value") }
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($Path, $out.ToArray(), $utf8)
    return $true
}

Write-Host "==> Stop leftover python/node (not Docker)"
Get-Process python, node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Host "==> git fetch + reset --hard origin/main (overwrite tracked files)"
git fetch origin
if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
git reset --hard origin/main
if ($LASTEXITCODE -ne 0) { throw "git reset --hard failed" }

Write-Host "==> Patch .env (does not delete secrets or paper data)"
$keys = @{
    PERP_MICRO_MAX_OPEN = "0"
    QUALITY_DIP_DISCORD_ENABLED = "true"
    INVESTMENT_SCAN_ENABLED = "true"
}
foreach ($envPath in @(
    (Join-Path $Root "backend\.env"),
    (Join-Path $Root ".env")
)) {
    if (-not (Test-Path $envPath)) { continue }
    foreach ($k in $keys.Keys) {
        [void](Set-DotEnvKey -Path $envPath -Key $k -Value $keys[$k])
        Write-Host ("    {0}: {1}={2}" -f $envPath, $k, $keys[$k])
    }
}

$VenvPy = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    Write-Host "==> Refresh Python package"
    & $VenvPy -m pip install -e (Join-Path $Root "backend") -q
    if ($LASTEXITCODE -ne 0) { throw "pip install -e backend failed" }
} else {
    Write-Host "[WARN] no venv yet - run Fresh-Setup.ps1"
}

Write-Host "==> Desktop shortcut"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "Install-DesktopShortcut.ps1")

Write-Host ""
Write-Host "Ready. Close any running Atlas window, then double-click 'Project Atlas' on the desktop."
Write-Host "Dashboard: http://127.0.0.1:8000/dashboard"
Write-Host ".env and backend\data were kept. Tracked files now match origin/main."
