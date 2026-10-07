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
# Ask this desktop run to execute Uvicorn/lifespan cleanup before force fallback.
$controlDir = Join-Path $Root "logs\runtime"
$requestedGraceful = $false
try {
    $manifest = Get-Content (Join-Path $controlDir "runtime.json") -Raw -ErrorAction Stop | ConvertFrom-Json
    if ($owned.Count -gt 0 -and $manifest.run_id) {
        @{run_id=[string]$manifest.run_id} | ConvertTo-Json | Set-Content (Join-Path $controlDir "stop.json") -Encoding UTF8
        $requestedGraceful = $true
        $deadline = (Get-Date).AddSeconds(30)
        do {
            $remaining = @($owned | Where-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue })
            if ($remaining.Count -eq 0) { break }
            Start-Sleep -Milliseconds 500
        } while ((Get-Date) -lt $deadline)
    }
} catch { }
$forced = 0
foreach ($process in $owned) {
    if ($process.ProcessId -gt 4 -and (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue)) {
        $forced++
        Stop-Tree ([int]$process.ProcessId)
    }
}

Write-Host "[stop] Atlas dependency containers (Docker Desktop + Genesis stay up)..."
# Stop only the two exact Atlas dependency containers. Never remove them: keeping
# the containers preserves initialized database identity/configuration across
# launches while still making Atlas fully stopped in Docker. Do not use compose
# down, broad name filters, global Docker/WSL shutdown, or unrelated process kills.
if (Get-Command docker -ErrorAction SilentlyContinue) {
    foreach ($container in @("atlas-postgres", "atlas-redis")) {
        $exists = docker ps -a --filter "name=^/$container$" --format "{{.Names}}" 2>$null
        if ($exists -eq $container) {
            docker stop $container 2>$null | Out-Null
        }
    }
    Write-Host "[stop] Atlas Postgres + Redis stopped; containers preserved."
} else {
    Write-Host "[stop] docker CLI not in PATH - Atlas application processes were still stopped."
}

$diagnostics = Join-Path $Root "logs\diagnostics"
New-Item -ItemType Directory -Force $diagnostics | Out-Null
@{requested_graceful=$requestedGraceful; forced_process_trees=$forced; finished_at=(Get-Date).ToUniversalTime().ToString("o")} | ConvertTo-Json | Set-Content (Join-Path $diagnostics "stop-latest.json") -Encoding UTF8
Write-Host "[stop] done. Docker Desktop / Genesis were not touched."
