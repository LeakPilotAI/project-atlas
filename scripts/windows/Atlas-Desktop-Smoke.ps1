# Project Atlas final desktop integration smoke check.
# Read-only except optional shortcut installation. Never places orders or changes strategy state.
#Requires -Version 5.1
param(
    [string]$Root = "",
    [switch]$InstallShortcuts,
    [int]$LongevitySeconds = 0,
    [int]$ProbeIntervalSeconds = 15,
    [switch]$StartAtlasIfNeeded,
    [int]$StartupTimeoutSeconds = 180,
    [int]$StableChecksRequired = 3
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

function Test-Http([string]$Url, [switch]$IncludeBody) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        $body = $null
        if ($IncludeBody) { $body = $r.Content | ConvertFrom-Json }
        return @{ body=$body; ok=($r.StatusCode -ge 200 -and $r.StatusCode -lt 400); status=[int]$r.StatusCode; error=$null }
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

function Test-RuntimeOwnership {
    $listeners = @(Get-ApiPortOwnershipSnapshot)
    $rootPrefix = $Root + "\"
    $listenerOk = $listeners.Count -eq 1
    foreach ($listener in $listeners) {
        $owned = ([string]$listener.executable).StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            ([string]$listener.parent_executable).StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)
        $listenerOk = $listenerOk -and $owned -and ($listener.command_line -match "uvicorn.*app\.main:app")
    }
    $containerStates = @()
    try { $containerStates = @(& docker inspect -f '{{.Name}} {{.State.Running}} {{.State.Health.Status}}' atlas-postgres atlas-redis 2>$null) } catch { }
    $containersOk = ($containerStates.Count -eq 2 -and @($containerStates | Where-Object { $_ -notmatch ' true healthy$' }).Count -eq 0)
    $launcherAlive = if ($launcherPid) { [bool](Get-Process -Id $launcherPid -ErrorAction SilentlyContinue) } else { $null }
    return @{ ok=($listenerOk -and $containersOk -and ($launcherAlive -ne $false)); listeners=$listeners; containers=$containerStates; launcher_alive=$launcherAlive }
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
$predictionAutomation = Test-Http "http://127.0.0.1:8000/api/prediction/paper/automation/status" -IncludeBody
$autoStarted = $false
$launcherPid = $null
if ($StartAtlasIfNeeded -and -not $health.ok) {
    Write-Host "Atlas API is not running; starting the normal desktop launcher..." -ForegroundColor Yellow
    $launcherProcess = Start-Process -FilePath $LaunchBat -WindowStyle Hidden -PassThru
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
    $predictionAutomation = Test-Http "http://127.0.0.1:8000/api/prediction/paper/automation/status" -IncludeBody
}

# Warm-up is separate from measured longevity; never discard measured failures.
$stabilization = @{ green=$false; checks=0; failed_checks=0; consecutive_green=0; required=[Math]::Max(2, $StableChecksRequired) }
$warmupDeadline = (Get-Date).AddSeconds([Math]::Max(1, $StartupTimeoutSeconds))
do {
    $health = Test-Http "http://127.0.0.1:8000/health"
    $dashboard = Test-Http "http://127.0.0.1:8000/dashboard"
    $research = Test-Http "http://127.0.0.1:8000/api/research"
    $command = Test-Http "http://127.0.0.1:8000/api/command-center/summary"
    $reconciliation = Test-Http "http://127.0.0.1:8000/diagnostics/paper-reconciliation"
    $predictionAutomation = Test-Http "http://127.0.0.1:8000/api/prediction/paper/automation/status" -IncludeBody
    $predictionBody = $predictionAutomation.body
    $predictionHealthy = [bool]($predictionAutomation.ok -and $predictionBody -and
        $predictionBody.running -eq $true -and
        $predictionBody.execution -eq "PAPER_ONLY" -and
        $predictionBody.unattended_paper_open_enabled -eq $false -and
        $predictionBody.automatic_paper_position_opening -eq $false -and
        $predictionBody.live_capital_allowed -eq $false -and
        $predictionBody.automatic_real_money_execution -eq $false)
    $stabilization.checks++
    if ($health.ok -and $dashboard.ok -and $research.ok -and $command.ok -and $reconciliation.ok -and $predictionHealthy) {
        $stabilization.consecutive_green++
    } else {
        $stabilization.failed_checks++
        $stabilization.last_failure = @{ health=$health; research=$research; command_center=$command; reconciliation=$reconciliation; prediction_automation=$predictionAutomation }
        $stabilization.consecutive_green=0
    }
    if ($stabilization.consecutive_green -ge $stabilization.required) { $stabilization.green=$true; break }
    Write-Host "Startup stabilization: $($stabilization.consecutive_green)/$($stabilization.required) consecutive healthy checks"
    Start-Sleep -Seconds 5
} while ((Get-Date) -lt $warmupDeadline)

$longevity = [ordered]@{
    requested_seconds = [Math]::Max(0, $LongevitySeconds)
    probe_interval_seconds = [Math]::Max(5, $ProbeIntervalSeconds)
    probes = 0
    runtime_failures = 0
    failures = 0
    failed_probe_count = 0
    consecutive_failed_probes = 0
    max_consecutive_failed_probes = 0
    recovered_after_failure = $false
    started_at = $null
    finished_at = $null
    green = $stabilization.green
    auto_started_atlas = $autoStarted
    launcher_process_id = $launcherPid
    first_failure_probe = $null
    failure_snapshot = $null
}
if ($stabilization.green -and $longevity.requested_seconds -gt 0) {
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
            "http://127.0.0.1:8000/api/research",
            "http://127.0.0.1:8000/api/command-center/summary",
            "http://127.0.0.1:8000/diagnostics/paper-reconciliation",
            "http://127.0.0.1:8000/api/prediction/paper/automation/status"
        )) {
            $probe = Test-Http $url
            $probeResults[$url] = $probe
            if (-not $probe.ok) {
                $longevity.failures++
                $probeFailed = $true
            }
        }
        $runtime = Test-RuntimeOwnership
        $longevity.last_runtime = $runtime
        if (-not $runtime.ok) { $probeFailed=$true; $longevity.runtime_failures++ }
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
                runtime_latency = Test-Http "http://127.0.0.1:8000/diagnostics/runtime-latency" -IncludeBody
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
    prediction_paper_automation = $predictionAutomation
    runtime_latency = Test-Http "http://127.0.0.1:8000/diagnostics/runtime-latency" -IncludeBody
    startup_stabilization = $stabilization
    longevity = $longevity
    atlas_containers = $containers
    paper_shadow_only = $true
    live_capital_allowed = $false
    automatic_real_money_execution = $false
}
$safetyBody = $result.runtime_latency.body
$predictionBody = $result.prediction_paper_automation.body
$result.safety_verified = [bool]($result.runtime_latency.ok -and $safetyBody -and
    $safetyBody.execution -eq "PAPER_ONLY" -and
    $safetyBody.live_capital_allowed -eq $false -and
    $safetyBody.automatic_real_money_execution -eq $false -and
    $result.prediction_paper_automation.ok -and $predictionBody -and
    $predictionBody.running -eq $true -and
    $predictionBody.execution -eq "PAPER_ONLY" -and
    $predictionBody.unattended_paper_open_enabled -eq $false -and
    $predictionBody.automatic_paper_position_opening -eq $false -and
    $predictionBody.live_capital_allowed -eq $false -and
    $predictionBody.automatic_real_money_execution -eq $false)
$result.status = if (
    $result.safety_verified -and
    $result.launch_bat_exists -and $result.stop_bat_exists -and
    $start.exists -and $start.target_ok -and $stop.exists -and $stop.target_ok -and
    $health.ok -and $dashboard.ok -and $research.ok -and $command.ok -and $reconciliation.ok -and $longevity.green
) { "ATLAS_DESKTOP_SMOKE_GREEN" } else { "ATLAS_DESKTOP_SMOKE_BLOCKED" }

$json = $result | ConvertTo-Json -Depth 12
$json
$artifactDir = Join-Path $Root "logs\diagnostics"
New-Item -ItemType Directory -Force $artifactDir | Out-Null
$artifactPath = Join-Path $artifactDir "desktop-smoke-latest.json"
$json | Set-Content -Path $artifactPath -Encoding UTF8
Write-Host ("Diagnostic artifact: {0}" -f $artifactPath) -ForegroundColor Cyan
if ($result.status -ne "ATLAS_DESKTOP_SMOKE_GREEN") { exit 2 }
