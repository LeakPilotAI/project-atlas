# Stop Atlas bot + atlas containers. Never quits Docker Desktop or Genesis.
param(
    [string]$Root = "",
    [int[]]$ChildPids = @(),
    [switch]$KeepDockerDesktop
)

$ErrorActionPreference = "Continue"
if (-not $Root) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
Set-Location $Root
$VenvPy = Join-Path $Root "backend\.venv\Scripts\python.exe"

function Stop-Tree([int]$ProcessId) {
    if ($ProcessId -le 0) { return }
    & taskkill.exe /F /PID $ProcessId /T 2>$null | Out-Null
}

# Only root-qualified executables/commands prove ownership. taskkill /T includes
# the base-Python child of the Atlas venv without matching unrelated uvicorns.
function Test-AtlasProcess($Process) {
    $exe = [string]$Process.ExecutablePath
    $cl = [string]$Process.CommandLine
    $rootOwned = ($exe -ieq $VenvPy -or $cl.IndexOf($Root + "\", [StringComparison]::OrdinalIgnoreCase) -ge 0)
    $serverRole = ($cl -match "uvicorn\s+app\.main:app" -or ($Process.Name -eq "node.exe" -and $cl -match "next"))
    return ($rootOwned -and $serverRole)
}

Write-Host "[stop] Atlas Python..."
$owned = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe' OR Name='node.exe'" -ErrorAction SilentlyContinue | Where-Object { Test-AtlasProcess $_ })
foreach ($process in $owned) {
    if ($process.ProcessId -gt 4) { Stop-Tree ([int]$process.ProcessId) }
}

Write-Host "[stop] Atlas containers (Docker Desktop + Genesis stay up)..."
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $env:COMPOSE_PROJECT_NAME = "atlas"
    docker compose stop 2>$null | Out-Null
    docker compose down --remove-orphans 2>$null | Out-Null
    docker stop atlas-postgres atlas-redis 2>$null | Out-Null
    docker rm -f atlas-postgres atlas-redis 2>$null | Out-Null
    $left = docker ps --filter "name=atlas" --format "{{.Names}}" 2>$null
    if ($left) {
        Write-Host "[stop] still running: $left" -ForegroundColor Yellow
    } else {
        Write-Host "[stop] no atlas containers running"
    }
} else {
    Write-Host "[stop] docker CLI not in PATH - Python was still killed"
}

Write-Host "[stop] done. Docker Desktop / Genesis were not touched."
