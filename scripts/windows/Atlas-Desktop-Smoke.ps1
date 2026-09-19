# Project Atlas final desktop integration smoke check.
# Read-only except optional shortcut installation. Never places orders or changes strategy state.
#Requires -Version 5.1
param(
    [string]$Root = "",
    [switch]$InstallShortcuts,
    [int]$LongevitySeconds = 0,
    [int]$ProbeIntervalSeconds = 15,
    [int]$StartupStableChecks = 2,
    [int]$StartupStableIntervalSeconds = 5,
    [switch]$StartAtlasIfNeeded
)

$ErrorActionPreference = "Stop"
if (-not $Root) { $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }
$Desktop = [Environment]::GetFolderPath("Desktop")
$LaunchBat = Join-Path $Root "ATLAS.bat"
$StopBat = Join-Path $Root "ATLAS-STOP.bat"
$StartLink = Join-Path $Desktop "Project Atlas.lnk"
$StopLink = Join-Path $Desktop "Stop Atlas.lnk"
$Installer = Join-Path $PSScriptRoot "Install-DesktopShortcut.ps1"
$ApiErrLog = Join-Path $Root "logs\api.err.log"
$ApiOutLog = Join-Path $Root "logs\api.out.log"

if ($InstallShortcuts) { & $Installer }

function Test-Shortcut([string]$Path, [string]$ExpectedTarget) {
    if (-not (Test-Path $Path)) { return @{ exists=$false; target_ok=$false; target=$null } }
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($Path)
    $target = [string]$s.TargetPath
    return @{ exists=$true; target_ok=($target -ieq $ExpectedTarget); target=$target }
}

function Test-HttpJson([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        $body = $null
        try { $body = $r.Content | ConvertFrom-Json } catch { }
        return @{ ok=($r.StatusCode -ge 200 -and $r.StatusCode -lt 400); status=[int]$r.StatusCode; error=$null; body=$body }
    } catch {
        return @{ ok=$false; status=$null; error=$_.Exception.Message; body=$null }
    }
}

function Test-Http([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return @{ ok=($r.StatusCode -ge 200 -and $r.StatusCode -lt 400); status=[int]$r.StatusCode; error=$null }
    } catch {
        return @{ ok=$false; status=$null; error=$_.Exception.Message }
    }
}

function Get-ApiProcessSnapshot {
    $rows = @()
    try {
        Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
            $cl = [string]$_.CommandLine
            if ($cl -match "uvicorn" -and $cl -match "app\.main:app") {
                $rows += @{
                    pid = [int]$_.ProcessId
                    command_line = $cl
                    executable = [string]$_.ExecutablePath
                }
            }
        }
    } catch { }
    return @($rows)
}

function Get-ApiPortOwnershipSnapshot {
    $rows = @()
    try {
        Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
            $ownerPid = [int]$_.OwningProcess
            $proc = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $ownerPid) -ErrorAction SilentlyContinue
            $parent = $null
            if ($proc -and $proc.ParentProcessId) {
                $parent = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f [int]$proc.ParentProcessId) -ErrorAction SilentlyContinue
            }
            $rows += @{
                local_address = [string]$_.LocalAddress
                local_port = [int]$_.LocalPort
                state = [string]$_.State
                owning_pid = $ownerPid
                executable = if ($proc) { [string]$proc.ExecutablePath } else { $null }
                command_line = if ($proc) { [string]$proc.CommandLine } else { $null }
                parent_pid = if ($proc) { [int]$proc.ParentProcessId } else { $null }
                parent_executable = if ($parent) { [string]$parent.ExecutablePath } else { $null }
                parent_command_line = if ($parent) { [string]$parent.CommandLine } else { $null }
            }
        }
    } catch { }
    return @($rows)
}

function Get-ApiProcessTreeSnapshot {
    $rows = @()
    $seen = @{}
    try {
        $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
        $uvicorn = @($all | Where-Object {
            ([string]$_.CommandLine -match "uvicorn") -and ([string]$_.CommandLine -match "app\.main:app")
        })
        foreach ($p in $uvicorn) {
            $processId = [int]$p.ProcessId
            if (-not $seen.ContainsKey($processId)) {
                $seen[$processId] = $true
                $rows += @{
                    pid = $processId
                    parent_pid = [int]$p.ParentProcessId
                    executable = [string]$p.ExecutablePath
                    command_line = [string]$p.CommandLine
                    owns_port_8000 = [bool](Get-NetTCPConnection -LocalPort 8000 -State Listen -OwningProcess $processId -ErrorAction SilentlyContinue)
                }
            }
        }
    } catch { }
    return @($rows)
}

function Get-LogTail([string]$Path, [int]$Lines = 60) {
    if (-not (Test-Path $Path)) { return @() }
    try { return @([System.IO.File]::ReadLines($Path) | Select-Object -Last $Lines | ForEach-Object { [string]$_ }) } catch { return @() }
}

$start = Test-Shortcut $StartLink $LaunchBat
$stop = Test-Shortcut $StopLink $StopBat
$health = Test-Http "http://127.0.0.1:8000/health"
$dashboard = Test-Http "http://127.0.0.1:8000/dashboard"
$research = Test-Http "http://127.0.0.1:8000/api/research"
$command = Test-Http "http://127.0.0.1:8000/api/command-center/summary"
$reconciliation = Test-Http "http://127.0.0.1:8000/diagnostics/paper-reconciliation"
$autoStarted = $false
$launcherPid = $null
if ($StartAtlasIfNeeded -and -not $health.ok) {
    Write-Host "Atlas API is not running; starting the normal desktop launcher..." -ForegroundColor Yellow
    $launcherProcess = Start-Process -FilePath $LaunchBat -PassThru
    $launcherPid = [int]$launcherProcess.Id
    for ($i = 1; $i -le 60; $i++) {
        Start-Sleep -Seconds 2
        $health = Test-Http "http://127.0.0.1:8000/health"
        if ($health.ok) {
            $autoStarted = $true
            break
        }
        Write-Host ("  waiting for Atlas API ({0}/60)" -f $i)
    }
    $dashboard = Test-Http "http://127.0.0.1:8000/dashboard"
    $research = Test-Http "http://127.0.0.1:8000/api/research"
    $command = Test-Http "http://127.0.0.1:8000/api/command-center/summary"
    $reconciliation = Test-Http "http://127.0.0.1:8000/diagnostics/paper-reconciliation"
}

$startupStabilization = [ordered]@{
    required_consecutive_checks = [Math]::Max(1, $StartupStableChecks)
    interval_seconds = [Math]::Max(1, $StartupStableIntervalSeconds)
    attempts = 0
    consecutive_green = 0
    green = $false
    last_results = $null
}
if ($StartAtlasIfNeeded -and $autoStarted) {
    Write-Host "Atlas API is reachable; waiting for operator surfaces to stabilize before longevity timing..." -ForegroundColor Yellow
    for ($i = 1; $i -le 24; $i++) {
        $startupStabilization.attempts++
        $readyResults = [ordered]@{
            health = Test-Http "http://127.0.0.1:8000/health"
            research = Test-Http "http://127.0.0.1:8000/api/research"
            command_center = Test-Http "http://127.0.0.1:8000/api/command-center/summary"
            reconciliation = Test-Http "http://127.0.0.1:8000/diagnostics/paper-reconciliation"
        }
        $startupStabilization.last_results = $readyResults
        $allReady = $readyResults.health.ok -and $readyResults.research.ok -and $readyResults.command_center.ok -and $readyResults.reconciliation.ok
        if ($allReady) {
            $startupStabilization.consecutive_green++
            Write-Host ("  startup stability check {0}: GREEN ({1}/{2} consecutive)" -f $i, $startupStabilization.consecutive_green, $startupStabilization.required_consecutive_checks) -ForegroundColor Green
            if ($startupStabilization.consecutive_green -ge $startupStabilization.required_consecutive_checks) {
                $startupStabilization.green = $true
                break
            }
        } else {
            $startupStabilization.consecutive_green = 0
            Write-Host ("  startup stability check {0}: warming" -f $i) -ForegroundColor Yellow
        }
        Start-Sleep -Seconds $startupStabilization.interval_seconds
    }
} else {
    $startupStabilization.green = [bool]$health.ok
}

$longevity = [ordered]@{
    requested_seconds = [Math]::Max(0, $LongevitySeconds)
    probe_interval_seconds = [Math]::Max(5, $ProbeIntervalSeconds)
    probes = 0
    failures = 0
    failed_probe_count = 0
    consecutive_failed_probes = 0
    max_consecutive_failed_probes = 0
    recovered_after_failure = $false
    started_at = $null
    finished_at = $null
    green = $true
    auto_started_atlas = $autoStarted
    launcher_process_id = $null
    first_failure_probe = $null
    failure_snapshot = $null
}
if ($longevity.requested_seconds -gt 0) {
    $longevity.started_at = (Get-Date).ToUniversalTime().ToString("o")
    $longevity.launcher_process_id = $launcherPid
    $deadline = (Get-Date).AddSeconds($longevity.requested_seconds)
    while ((Get-Date) -lt $deadline) {
        $longevity.probes++
        Write-Host ("Longevity probe {0}: checking API + reconciliation..." -f $longevity.probes)
        $probeResults = @{}
        $probeFailed = $false
        foreach ($url in @(
            "http://127.0.0.1:8000/health",
            "http://127.0.0.1:8000/diagnostics/paper-reconciliation"
        )) {
            $probe = Test-Http $url
            $probeResults[$url] = $probe
            if (-not $probe.ok) {
                $longevity.failures++
                $probeFailed = $true
            }
        }
        if ($probeFailed) {
            $longevity.failed_probe_count++
            $longevity.consecutive_failed_probes++
            $longevity.max_consecutive_failed_probes = [Math]::Max(
                $longevity.max_consecutive_failed_probes,
                $longevity.consecutive_failed_probes
            )
            $longevity.green = $false
        } else {
            if ($longevity.consecutive_failed_probes -gt 0) {
                $longevity.recovered_after_failure = $true
            }
            $longevity.consecutive_failed_probes = 0
        }
        if ($probeFailed -and $null -eq $longevity.first_failure_probe) {
            $longevity.first_failure_probe = $longevity.probes
            $longevity.failure_snapshot = @{
                captured_at = (Get-Date).ToUniversalTime().ToString("o")
                probe_results = $probeResults
                api_processes = @(Get-ApiProcessSnapshot)
                api_process_tree = @(Get-ApiProcessTreeSnapshot)
                port_8000_listeners = @(Get-ApiPortOwnershipSnapshot)
                launcher_process_id = $launcherPid
                launcher_alive = if ($launcherPid) { [bool](Get-Process -Id $launcherPid -ErrorAction SilentlyContinue) } else { $null }
                atlas_containers = @(& docker ps --filter "name=atlas" --format "{{.Names}}" 2>$null)
                api_err_tail = @(Get-LogTail $ApiErrLog 80)
                api_out_tail = @(Get-LogTail $ApiOutLog 80)
                runtime_latency = Test-HttpJson "http://127.0.0.1:8000/diagnostics/runtime-latency"
            }
            Write-Host "  captured failure snapshot" -ForegroundColor Yellow
        }
        if (-not $probeFailed) {
            if ($longevity.recovered_after_failure) { Write-Host "  GREEN (runtime recovered after earlier transient failure)" -ForegroundColor Green }
            else { Write-Host "  GREEN" -ForegroundColor Green }
        } else {
            Write-Host ("  FAILED (consecutive failed probes: {0})" -f $longevity.consecutive_failed_probes) -ForegroundColor Red
        }
        Start-Sleep -Seconds $longevity.probe_interval_seconds
    }
    $longevity.finished_at = (Get-Date).ToUniversalTime().ToString("o")
}

$containers = @()
if (Get-Command docker -ErrorAction SilentlyContinue) {
    try { $containers = @(& docker ps --filter "name=atlas" --format "{{.Names}}" 2>$null) } catch { }
}

$result = [ordered]@{
    mode = "ATLAS_DESKTOP_INTEGRATION_SMOKE"
    root = $Root
    desktop = $Desktop
    start_shortcut = $start
    stop_shortcut = $stop
    launch_bat_exists = (Test-Path $LaunchBat)
    stop_bat_exists = (Test-Path $StopBat)
    health = $health
    dashboard = $dashboard
    research = $research
    command_center = $command
    reconciliation = $reconciliation
    startup_stabilization = $startupStabilization
    longevity = $longevity
    atlas_containers = $containers
    paper_shadow_only = $true
    live_capital_allowed = $false
    automatic_real_money_execution = $false
}
$result.status = if (
    $result.launch_bat_exists -and $result.stop_bat_exists -and
    $start.exists -and $start.target_ok -and $stop.exists -and $stop.target_ok -and
    $health.ok -and $dashboard.ok -and $research.ok -and $command.ok -and $reconciliation.ok -and $startupStabilization.green -and $longevity.green
) { "ATLAS_DESKTOP_SMOKE_GREEN" } else { "ATLAS_DESKTOP_SMOKE_BLOCKED" }

$json = $result | ConvertTo-Json -Depth 6
$json
$artifactDir = Join-Path $Root "logs\diagnostics"
New-Item -ItemType Directory -Force $artifactDir | Out-Null
$artifactPath = Join-Path $artifactDir "desktop-smoke-latest.json"
$json | Set-Content -Path $artifactPath -Encoding UTF8
Write-Host ("Diagnostic artifact: {0}" -f $artifactPath) -ForegroundColor Cyan
if ($result.status -ne "ATLAS_DESKTOP_SMOKE_GREEN") { exit 2 }
