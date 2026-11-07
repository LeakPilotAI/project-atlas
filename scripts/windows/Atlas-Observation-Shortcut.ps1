# Atlas desktop observation-only launcher.
# Does not start legacy Atlas, financial writers, Docker, or Genesis.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$mutexName = "Local\AtlasObservationOwner_$sid"
$eventName = "Local\AtlasObservationStop_$sid"

$created = $false
$mutex = New-Object System.Threading.Mutex($true, $mutexName, [ref]$created)

if (-not $created) {
    Write-Host "Atlas observation launcher is already running." -ForegroundColor Yellow
    $mutex.Dispose()
    exit 0
}

$stopEvent = $null
$started = $false

try {
    $stopEvent = New-Object System.Threading.EventWaitHandle(
        $false,
        [System.Threading.EventResetMode]::AutoReset,
        $eventName
    )

    # Clear any previously signaled request before starting.
    $stopEvent.Reset() | Out-Null

    Import-Module (Join-Path $PSScriptRoot "Atlas-Observation-Dashboard.psm1") -Force

    Write-Host "Starting Project Atlas observation-only dashboard..." -ForegroundColor Cyan

    $ready = Open-AtlasObservationDashboard $root -BoundedDataOnly
    $started = $true

    Write-Host ""
    Write-Host "ATLAS OBSERVATION ONLINE" -ForegroundColor Green
    Write-Host "Dashboard: $($ready.url)"
    # Report actual native PAPER prerequisites at each shortcut launch. This is
    # read-only; never promote observation to PAPER or invent operator authority.
    $python = Join-Path $root "backend\.venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $python -PathType Leaf) {
        $priorPythonPath = $env:PYTHONPATH
        try {
            $env:PYTHONPATH = "$root\backend;$root"
            $preflightRaw = & $python -m scripts.observation_runtime.personal_installation_preflight 2>&1
            if ($LASTEXITCODE -ne 0) { throw "Native PAPER preflight exited $LASTEXITCODE" }
            $preflight = ($preflightRaw | Out-String | ConvertFrom-Json)
            if ($preflight.forward_financial_write_authorized -ne $false -or
                $preflight.live_order_authorized -ne $false) {
                throw "Unexpected preflight authorization claim"
            }
            Write-Host "PAPER prerequisites: $($preflight.blockers -join ', ')" -ForegroundColor Yellow
        }
        catch {
            Write-Host "PAPER prerequisites: UNVERIFIED ($($_.Exception.Message))" -ForegroundColor Yellow
        }
        finally { $env:PYTHONPATH = $priorPythonPath }
    }
    else {
        Write-Host "PAPER prerequisites: UNVERIFIED (Python environment missing)" -ForegroundColor Yellow
    }
    Write-Host "PAPER trading: DISABLED (native operator authorization required)"
    Write-Host "Production trading: DISABLED"
    Write-Host ""
    Write-Host "Keep this window open while using Atlas."
    Write-Host "Use the Stop Atlas desktop shortcut for graceful shutdown."
    Write-Host ""

    $stopEvent.WaitOne() | Out-Null

    Write-Host "Graceful shutdown requested..." -ForegroundColor Yellow
}
catch {
    Write-Host "Atlas observation launcher failed: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to close"
}
finally {
    try {
        if ($started) {
            Close-AtlasObservationDashboard
            Write-Host "Atlas observation host closed." -ForegroundColor Green
        }
    }
    catch {
        Write-Host "Shutdown could not be confirmed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "No process was forcibly terminated." -ForegroundColor Yellow
        Read-Host "Press Enter to close"
    }

    if ($null -ne $stopEvent) {
        $stopEvent.Dispose()
    }

    try { $mutex.ReleaseMutex() } catch {}
    $mutex.Dispose()
}
