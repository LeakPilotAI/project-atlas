# Project Atlas final desktop integration smoke check.
# Read-only except optional shortcut installation. Never places orders or changes strategy state.
#Requires -Version 5.1
param(
    [string]$Root = "",
    [switch]$InstallShortcuts,
    [int]$LongevitySeconds = 0,
    [int]$ProbeIntervalSeconds = 15,
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

function Get-LogTail([string]$Path, [int]$Lines = 60) {
    if (-not (Test-Path $Path)) { return @() }
    try { return @(Get-Content $Path -Tail $Lines -ErrorAction SilentlyContinue) } catch { return @() }
}

$start = Test-Shortcut $StartLink $LaunchBat
$stop = Test-Shortcut $StopLink $StopBat
$health = Test-Http "http://127.0.0.1:8000/health"
$dashboard = Test-Http "http://127.0.0.1:8000/dashboard"
$research = Test-Http "http://127.0.0.1:8000/api/research"
$command = Test-Http "http://127.0.0.1:8000/api/command-center/summary"
$reconciliation = Test-Http "http://127.0.0.1:8000/diagnostics/paper-reconciliation"
$autoStarted = $false
if ($StartAtlasIfNeeded -and -not $health.ok) {
    Write-Host "Atlas API is not running; starting the normal desktop launcher..." -ForegroundColor Yellow
    Start-Process -FilePath $LaunchBat | Out-Null
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
    first_failure_probe = $null
    failure_snapshot = $null
}
if ($longevity.requested_seconds -gt 0) {
    $longevity.started_at = (Get-Date).ToUniversalTime().ToString("o")
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
                atlas_containers = @(& docker ps --filter "name=atlas" --format "{{.Names}}" 2>$null)
                api_err_tail = @(Get-LogTail $ApiErrLog 80)
                api_out_tail = @(Get-LogTail $ApiOutLog 80)
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
    longevity = $longevity
    atlas_containers = $containers
    paper_shadow_only = $true
    live_capital_allowed = $false
    automatic_real_money_execution = $false
}
$result.status = if (
    $result.launch_bat_exists -and $result.stop_bat_exists -and
    $start.exists -and $start.target_ok -and $stop.exists -and $stop.target_ok -and
    $health.ok -and $dashboard.ok -and $research.ok -and $command.ok -and $reconciliation.ok -and $longevity.green
) { "ATLAS_DESKTOP_SMOKE_GREEN" } else { "ATLAS_DESKTOP_SMOKE_BLOCKED" }

$json = $result | ConvertTo-Json -Depth 8
$json
$artifactDir = Join-Path $Root "logs\diagnostics"
New-Item -ItemType Directory -Force $artifactDir | Out-Null
$artifactPath = Join-Path $artifactDir "desktop-smoke-latest.json"
$json | Set-Content -Path $artifactPath -Encoding UTF8
Write-Host ("Diagnostic artifact: {0}" -f $artifactPath) -ForegroundColor Cyan
if ($result.status -ne "ATLAS_DESKTOP_SMOKE_GREEN") { exit 2 }
