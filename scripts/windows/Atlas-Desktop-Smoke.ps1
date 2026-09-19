# Project Atlas final desktop integration smoke check.
# Read-only except optional shortcut installation. Never places orders or changes strategy state.
#Requires -Version 5.1
param(
    [string]$Root = "",
    [switch]$InstallShortcuts,
    [int]$LongevitySeconds = 0,
    [int]$ProbeIntervalSeconds = 15
)

$ErrorActionPreference = "Stop"
if (-not $Root) { $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }
$Desktop = [Environment]::GetFolderPath("Desktop")
$LaunchBat = Join-Path $Root "ATLAS.bat"
$StopBat = Join-Path $Root "ATLAS-STOP.bat"
$StartLink = Join-Path $Desktop "Project Atlas.lnk"
$StopLink = Join-Path $Desktop "Stop Atlas.lnk"
$Installer = Join-Path $PSScriptRoot "Install-DesktopShortcut.ps1"

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

$start = Test-Shortcut $StartLink $LaunchBat
$stop = Test-Shortcut $StopLink $StopBat
$health = Test-Http "http://127.0.0.1:8000/health"
$dashboard = Test-Http "http://127.0.0.1:8000/dashboard"
$research = Test-Http "http://127.0.0.1:8000/api/research"
$command = Test-Http "http://127.0.0.1:8000/api/command-center/summary"
$reconciliation = Test-Http "http://127.0.0.1:8000/diagnostics/paper-reconciliation"

$longevity = [ordered]@{
    requested_seconds = [Math]::Max(0, $LongevitySeconds)
    probe_interval_seconds = [Math]::Max(5, $ProbeIntervalSeconds)
    probes = 0
    failures = 0
    started_at = $null
    finished_at = $null
    green = $true
}
if ($longevity.requested_seconds -gt 0) {
    $longevity.started_at = (Get-Date).ToUniversalTime().ToString("o")
    $deadline = (Get-Date).AddSeconds($longevity.requested_seconds)
    while ((Get-Date) -lt $deadline) {
        $longevity.probes++
        foreach ($url in @(
            "http://127.0.0.1:8000/health",
            "http://127.0.0.1:8000/diagnostics/paper-reconciliation"
        )) {
            $probe = Test-Http $url
            if (-not $probe.ok) {
                $longevity.failures++
                $longevity.green = $false
            }
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

$result | ConvertTo-Json -Depth 8
if ($result.status -ne "ATLAS_DESKTOP_SMOKE_GREEN") { exit 2 }
