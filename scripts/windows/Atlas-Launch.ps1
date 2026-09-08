# Project Atlas - one window. Close it to stop the bot. Docker Desktop stays running.
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

function Repair-DotEnv([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    $len = (Get-Item $Path).Length
    if ($len -le 65536) { return }
    $bak = "$Path.bak-oversized"
    try { Copy-Item $Path $bak -Force -ErrorAction SilentlyContinue } catch { }
    Write-Host ("    WARN {0} is {1} bytes - compacting env keys" -f $Path, $len) -ForegroundColor Yellow
    $kept = New-Object System.Collections.Generic.List[string]
    $sr = [System.IO.StreamReader]::new($Path)
    try {
        while ($null -ne ($line = $sr.ReadLine())) {
            if ($line.Length -gt 800) { continue }
            if ($line -match '^\s*$' -or $line -match '^\s*#' -or $line -match '^[A-Za-z_][A-Za-z0-9_]*\s*=') {
                $kept.Add($line)
            }
            if ($kept.Count -ge 400) { break }
        }
    } finally { $sr.Close() }
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($Path, $kept.ToArray(), $utf8)
    Write-Host ("    compacted to {0} bytes" -f (Get-Item $Path).Length)
}

function Rotate-Log([string]$Path, [int]$MaxBytes = 20971520) {
    if (-not (Test-Path $Path)) { return }
    if ((Get-Item $Path).Length -le $MaxBytes) { return }
    Move-Item $Path "$Path.old" -Force -ErrorAction SilentlyContinue
}

function Stop-All {
    if ($script:Stopped) { return }
    $script:Stopped = $true
    Write-Host ""
    Write-Host "Shutting down Atlas bot (Python). Docker Desktop stays up." -ForegroundColor Yellow
    $pids = @()
    if ($script:ApiPid) { $pids += $script:ApiPid }
    if ($script:FePid) { $pids += $script:FePid }
    & $StopScript -Root $Root -ChildPids $pids
}

# CTRL_C / close-window / logoff - Windows only gives a few seconds on X
$code = @"
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
public static class AtlasConsoleTrap {
  public delegate bool HandlerRoutine(int dwCtrlType);
  [DllImport("kernel32.dll", SetLastError = true)]
  public static extern bool SetConsoleCtrlHandler(HandlerRoutine handler, bool add);
}
public static class AtlasJob {
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
  static extern IntPtr CreateJobObject(IntPtr a, string n);
  [DllImport("kernel32.dll", SetLastError = true)]
  static extern bool SetInformationJobObject(IntPtr h, int i, IntPtr p, uint l);
  [DllImport("kernel32.dll", SetLastError = true)]
  static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
  [StructLayout(LayoutKind.Sequential)]
  struct JOBOBJECT_BASIC_LIMIT_INFORMATION {
    public long PerProcessUserTimeLimit;
    public long PerJobUserTimeLimit;
    public uint LimitFlags;
    public UIntPtr MinimumWorkingSetSize;
    public UIntPtr MaximumWorkingSetSize;
    public uint ActiveProcessLimit;
    public long Affinity;
    public uint PriorityClass;
    public uint SchedulingClass;
  }
  [StructLayout(LayoutKind.Sequential)]
  struct IO_COUNTERS {
    public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
    public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
  }
  [StructLayout(LayoutKind.Sequential)]
  struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
    public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
    public IO_COUNTERS IoInfo;
    public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
  }
  static IntPtr job = IntPtr.Zero;
  public static bool Attach(int pid) {
    if (job == IntPtr.Zero) {
      job = CreateJobObject(IntPtr.Zero, null);
      var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
      info.BasicLimitInformation.LimitFlags = 0x2000;
      int length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
      IntPtr ptr = Marshal.AllocHGlobal(length);
      Marshal.StructureToPtr(info, ptr, false);
      SetInformationJobObject(job, 9, ptr, (uint)length);
      Marshal.FreeHGlobal(ptr);
    }
    try {
      var p = Process.GetProcessById(pid);
      return AssignProcessToJobObject(job, p.Handle);
    } catch { return false; }
  }
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

function Ensure-WslMemoryCap {
    $cfg = Join-Path $env:USERPROFILE ".wslconfig"
    $wanted = @"
[wsl2]
memory=2GB
processors=2
swap=0
"@
    if (Test-Path $cfg) {
        $cur = Get-Content $cfg -Raw -ErrorAction SilentlyContinue
        if ($cur -match "memory=") { return }
    }
    Set-Content -Path $cfg -Value $wanted -Encoding ASCII
    Write-Host "    WSL/Docker RAM capped at 2GB ($cfg)"
}

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
        Write-Host ("    waiting for {0} ({1}/{2})" -f $Url, $i, $Tries)
        Start-Sleep -Seconds 2
    }
    return $false
}

function Wait-Postgres([int]$Seconds = 90) {
    Write-Host "    waiting for postgres to be ready..."
    for ($i = 0; $i -lt $Seconds; $i += 3) {
        $st = docker inspect -f "{{.State.Health.Status}}" atlas-postgres 2>$null
        if ($st -eq "healthy") {
            Write-Host "    postgres healthy"
            return $true
        }
        $run = docker inspect -f "{{.State.Running}}" atlas-postgres 2>$null
        Write-Host ("    postgres status={0} running={1} ({2}s)" -f $st, $run, $i)
        Start-Sleep -Seconds 3
    }
    return $false
}

try {
    Write-Host "========================================"
    Write-Host " PROJECT ATLAS"
    Write-Host " Close this window = stop the bot. Docker Desktop stays running."
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
    Repair-DotEnv (Join-Path $Backend ".env")
    Repair-DotEnv (Join-Path $Root ".env")

    Write-Step "Force-stop leftover Atlas processes"
    & $StopScript -Root $Root -KeepDockerDesktop
    Start-Sleep -Seconds 2

    Ensure-WslMemoryCap

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
    $env:COMPOSE_PROJECT_NAME = "atlas"
    docker rm -f atlas-postgres atlas-redis 2>$null | Out-Null
    docker compose down --remove-orphans 2>$null | Out-Null
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] docker compose up failed." -ForegroundColor Red
        cmd /c pause
        exit 1
    }
    if (-not (Wait-Postgres 90)) {
        Write-Host "[WARN] postgres not healthy yet - starting API anyway" -ForegroundColor Yellow
    }

    $logDir = Join-Path $Root "logs"
    New-Item -ItemType Directory -Force $logDir | Out-Null
    $apiOut = Join-Path $logDir "api.out.log"
    $apiErr = Join-Path $logDir "api.err.log"
    Rotate-Log $apiOut
    Rotate-Log $apiErr

    Write-Step "Checking Python venv"
    Write-Host "    $VenvPy"
    & $VenvPy -c "import fastapi, uvicorn, mplfinance" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] venv is missing packages (likely an old locked copy)." -ForegroundColor Red
        Write-Host "Run this, then double-click Project Atlas again:" -ForegroundColor Yellow
        Write-Host "  `"$VenvPy`" -m pip install -e `"$Backend`""
        cmd /c pause
        exit 1
    }
    Write-Host "    imports ok"

    Write-Step "Starting Atlas API (port 8000)"
    $api = Start-Process -FilePath $VenvPy -ArgumentList @(
        "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8000"
    ) -WorkingDirectory $Backend -PassThru -NoNewWindow -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr
    if (-not $api) {
        Write-Host "[ERROR] failed to start python/uvicorn" -ForegroundColor Red
        cmd /c pause
        exit 1
    }
    $script:ApiPid = $api.Id
    Write-Host ("    API pid {0}  logs {1}" -f $script:ApiPid, $apiErr)
    try {
        if ([AtlasJob]::Attach([int]$script:ApiPid)) {
            Write-Host "    API will die when this window closes (Windows job)"
        }
    } catch {
        Write-Host "    job attach skipped - Stop-All still runs on close"
    }
    if (-not (Wait-Http "http://127.0.0.1:8000/health" 40)) {
        Write-Host "[WARN] API health not OK. Last log lines:" -ForegroundColor Yellow
        if (Test-Path $apiErr) { Get-Content $apiErr -Tail 20 }
        if (Test-Path $apiOut) { Get-Content $apiOut -Tail 20 }
    } else {
        Write-Host "    API healthy"
    }

    Write-Step "Opening dashboard"
    $dash = Join-Path $Backend "app\static\dashboard.html"
    if (-not (Test-Path $dash)) {
        Write-Host "[WARN] dashboard.html missing - git pull origin main" -ForegroundColor Yellow
    }
    Start-Process "http://127.0.0.1:8000/dashboard?v=desk-v5"
    Write-Host "    Dashboard: http://127.0.0.1:8000/dashboard?v=desk-v5"
    Write-Host "    (no Node/Next - served by the API)"

    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor Green
    Write-Host " Atlas is running" -ForegroundColor Green
    Write-Host " Dashboard:  http://127.0.0.1:8000/dashboard?v=desk-v5"
    Write-Host " API:        http://127.0.0.1:8000/health"
    Write-Host ""
    Write-Host " Keep this window open."
    Write-Host " Close it (or press Ctrl+C) to stop the bot only."
    Write-Host " Docker Desktop and other apps (Genesis, etc.) stay running."
    Write-Host "----------------------------------------" -ForegroundColor Green
    Write-Host ""

    while (-not $script:Stopped) {
        Start-Sleep -Seconds 3
        if ($script:ApiPid -and -not (Get-Process -Id $script:ApiPid -ErrorAction SilentlyContinue)) {
            Write-Host "[warn] API process exited - shutting down" -ForegroundColor Yellow
            break
        }
    }
}
finally {
    Stop-All
}
