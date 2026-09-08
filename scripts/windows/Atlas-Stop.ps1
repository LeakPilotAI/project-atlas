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

function Stop-ListenPort([int]$Port) {
    $out = & netstat.exe -ano 2>$null | Select-String ":$Port\s+.*LISTENING"
    foreach ($line in $out) {
        $procId = ($line.ToString().Trim() -split "\s+")[-1]
        if ($procId -match "^\d+$" -and [int]$procId -gt 4) {
            Stop-Tree ([int]$procId)
        }
    }
}

function Stop-AtlasPython {
    $markers = @("uvicorn", "app.main", "Project Atlas", "project-atlas")
    try {
        Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
            $cl = [string]$_.CommandLine
            $exe = [string]$_.ExecutablePath
            $hit = $false
            foreach ($m in $markers) {
                if ($cl -like "*$m*" -or $exe -like "*$m*") { $hit = $true; break }
            }
            if ($VenvPy -and $exe -and ($exe -ieq $VenvPy)) { $hit = $true }
            if ($hit -and $_.ProcessId -gt 4) {
                Stop-Tree ([int]$_.ProcessId)
            }
        }
    } catch { }
}

Write-Host "[stop] Atlas Python..."
foreach ($p in $ChildPids) { Stop-Tree $p }
Stop-AtlasPython
Stop-ListenPort 8000
Stop-ListenPort 3000

Get-Process -Name "node" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
        if ($cl -match "next|frontend") { Stop-Tree $_.Id }
    } catch { }
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
