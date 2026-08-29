# Project Atlas - one window. Close it to stop API + frontend + Docker.
#Requires -Version 5.1
$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"
$StopScript = Join-Path $PSScriptRoot "Atlas-Stop.ps1"
$script:ApiPid = 0
$script:FePid = 0
$script:Stopped = $false

Set-Location $Root
$host.UI.RawUI.WindowTitle = "Project Atlas - close this window to stop everything"

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }

function Stop-All {
    if ($script:Stopped) { return }
    $script:Stopped = $true
    Write-Host ""
    Write-Host "Shutting down Atlas (API, frontend, Docker)..." -ForegroundColor Yellow
    $pids = @()
    if ($script:ApiPid) { $pids += $script:ApiPid }
    if ($script:FePid) { $pids += $script:FePid }
    & $StopScript -Root $Root -ChildPids $pids
}

# CTRL_C / close-window / logoff - Windows only gives a few seconds on X
$code = @"
using System;
using System.Runtime.InteropServices;
public static class AtlasConsoleTrap {
  public delegate bool HandlerRoutine(int dwCtrlType);
  [DllImport("kernel32.dll", SetLastError = true)]
  public static extern bool SetConsoleCtrlHandler(HandlerRoutine handler, bool add);
}
"@
try { Add-Type -TypeDefinition $code -ErrorAction Stop } catch { }
$script:Trap = [AtlasConsoleTrap+HandlerRoutine]{
    param([int]$ctrlType)
    Stop-All
    return $true
}
try { [void][AtlasConsoleTrap]::SetConsoleCtrlHandler($script:Trap, $true) } catch { }
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { } -ErrorAction SilentlyContinue
trap { Stop-All; break }

function Get-DockerDesktop {
    @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Docker\Docker\Docker Desktop.exe")
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

function Wait-Docker([int]$Seconds = 120) {
    for ($i = 0; $i -lt $Seconds; $i += 2) {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 2
        Write-Host "    waiting for Docker engine... ($i s)"
    }
    return $false
}

function Wait-Http([string]$Url, [int]$Tries = 40) {
    for ($i = 1; $i -le $Tries; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch { }
        Start-Sleep -Seconds 2
    }
    return $false
}

try {
    Write-Host "========================================"
    Write-Host " PROJECT ATLAS"
    Write-Host " Close this window = stop bot + Docker"
    Write-Host " Frontend will open in your browser"
    Write-Host "========================================"
    Write-Host "Folder: $Root"

    if (-not (Test-Path $VenvPy)) {
        Write-Host "[ERROR] venv missing. Run scripts\windows\Fresh-Setup.ps1 first." -ForegroundColor Red
        cmd /c pause
        exit 1
    }
    $envFile = Join-Path $Backend ".env"
    if (-not (Test-Path $envFile)) { $envFile = Join-Path $Root ".env" }
    if (-not (Test-Path $envFile)) {
        Write-Host "[ERROR] .env missing. Copy your backup to backend\.env" -ForegroundColor Red
        cmd /c pause
        exit 1
    }

    Write-Step "Force-stop leftover Atlas processes"
    & $StopScript -Root $Root -KeepDockerDesktop
    Start-Sleep -Seconds 2

    $dd = Get-DockerDesktop
    if (-not $dd) {
        Write-Host "[ERROR] Docker Desktop not installed." -ForegroundColor Red
        cmd /c pause
        exit 1
    }

    Write-Step "Starting Docker Desktop"
    $engineUp = $false
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $engineUp = $true }
    if (-not $engineUp) {
        Start-Process $dd | Out-Null
        if (-not (Wait-Docker 150)) {
            Write-Host "[ERROR] Docker engine did not start. Open Docker Desktop once, then retry." -ForegroundColor Red
            cmd /c pause
            exit 1
        }
    }

    Write-Step "Starting Postgres + Redis (docker compose)"
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] docker compose up failed." -ForegroundColor Red
        cmd /c pause
        exit 1
    }
    Start-Sleep -Seconds 5

    Write-Step "Starting Atlas API (port 8000)"
    $api = Start-Process -FilePath $VenvPy -ArgumentList @(
        "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--app-dir", $Backend
    ) -WorkingDirectory $Backend -PassThru -WindowStyle Minimized
    $script:ApiPid = $api.Id
    if (-not (Wait-Http "http://127.0.0.1:8000/health" 30)) {
        Write-Host "[WARN] API health not OK yet - continuing" -ForegroundColor Yellow
    } else {
        Write-Host "    API healthy"
    }

    Write-Step "Starting frontend dashboard (port 3000)"
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { $npm = Get-Command npm -ErrorAction SilentlyContinue }
    if (-not $npm) {
        Write-Host "[ERROR] npm/node not in PATH. Install Node.js LTS, then re-run Fresh-Setup." -ForegroundColor Red
        Stop-All
        cmd /c pause
        exit 1
    }
    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Write-Host "    npm install (first run)..."
        Push-Location $Frontend
        & npm.cmd install
        Pop-Location
    }
    $fe = Start-Process -FilePath "cmd.exe" -ArgumentList @(
        "/c", "npm.cmd run dev -- --hostname 127.0.0.1 --port 3000"
    ) -WorkingDirectory $Frontend -PassThru -WindowStyle Minimized
    $script:FePid = $fe.Id
    if (-not (Wait-Http "http://127.0.0.1:3000" 45)) {
        Write-Host "[WARN] Frontend not answering yet - opening browser anyway" -ForegroundColor Yellow
    } else {
        Write-Host "    Frontend ready"
    }

    Write-Step "Opening dashboard"
    Start-Process "http://127.0.0.1:3000"

    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor Green
    Write-Host " Atlas is running" -ForegroundColor Green
    Write-Host " Dashboard:  http://127.0.0.1:3000"
    Write-Host " API:        http://127.0.0.1:8000/health"
    Write-Host ""
    Write-Host " Keep this window open."
    Write-Host " Close it (or press Ctrl+C) to stop the bot,"
    Write-Host " the dashboard, and Docker Desktop."
    Write-Host "----------------------------------------" -ForegroundColor Green
    Write-Host ""

    while (-not $script:Stopped) {
        Start-Sleep -Seconds 3
        if ($script:ApiPid -and -not (Get-Process -Id $script:ApiPid -ErrorAction SilentlyContinue)) {
            Write-Host "[warn] API process exited" -ForegroundColor Yellow
        }
    }
}
finally {
    Stop-All
}
