# Separate, manual background lifecycle for Project Atlas. Never use the legacy stop path.
#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet("Start", "Status", "Stop", "Worker", "StopWorker")]
    [string]$Action = "Status",
    [string]$RunId = "",
    [switch]$Json
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Backend = Join-Path $Root "backend"
$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"
$RuntimeDir = Join-Path $Root "logs\runtime"
$OwnerPath = Join-Path $RuntimeDir "atlas-background-owner.json"
$LockPath = Join-Path $RuntimeDir "atlas-background-start.lock"
$StopLockPath = Join-Path $RuntimeDir "atlas-background-stop.lock"
$RuntimePath = Join-Path $RuntimeDir "runtime.json"
$StopPath = Join-Path $RuntimeDir "stop.json"
$ManagerPath = Join-Path $PSScriptRoot "Atlas-Background.ps1"
$ReadyPath = Join-Path $PSScriptRoot "Atlas-Ready.ps1"
$ComposePath = Join-Path $Root "docker-compose.yml"
$PowerShellPath = Join-Path $PSHOME "powershell.exe"
Import-Module (Join-Path $PSScriptRoot "Atlas-ContainerOwnership.psm1") -Force

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop)
}

function Write-JsonAtomic($Value, [string]$Path) {
    $temporary = "$Path.$([guid]::NewGuid().ToString('N')).tmp"
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 8), $utf8)
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function New-ExclusiveJsonFile($Value, [string]$Path) {
    $bytes = (New-Object System.Text.UTF8Encoding($false)).GetBytes(
        ($Value | ConvertTo-Json -Depth 8)
    )
    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try { $stream.Write($bytes, 0, $bytes.Length) }
    finally { $stream.Dispose() }
}

function Get-ProcessIdentity([int]$ProcessId) {
    if ($ProcessId -le 4) { throw "Refusing invalid process ID $ProcessId." }
    $process = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $ProcessId) -ErrorAction Stop
    if (-not $process) { return $null }
    return @{
        pid = [int]$process.ProcessId
        executable = [string]$process.ExecutablePath
        command_line = [string]$process.CommandLine
        created_utc = ([datetime]$process.CreationDate).ToUniversalTime().ToString("o")
    }
}

function Test-IdentityRecord($Record, [string]$ExpectedExecutable, [string]$RequiredCommand) {
    if (-not $Record -or [int]$Record.pid -le 4) { return $false }
    $current = Get-ProcessIdentity ([int]$Record.pid)
    if (-not $current) { return $false }
    return (
        $current.executable -ieq $ExpectedExecutable -and
        $current.command_line -ceq [string]$Record.command_line -and
        $current.created_utc -ceq [string]$Record.created_utc -and
        $current.command_line.IndexOf($RequiredCommand, [StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

function Get-ApiListeners {
    try {
        $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
            Where-Object { [int]$_.LocalPort -eq 8000 })
        return @($listeners | ForEach-Object { [int]$_.OwningProcess } | Sort-Object -Unique)
    } catch {
        throw "Cannot verify ownership of TCP port 8000: $($_.Exception.Message)"
    }
}

function Get-AtlasApiProcesses {
    try {
        $processes = @(Get-CimInstance Win32_Process `
            -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction Stop)
    } catch {
        throw "Cannot verify Atlas API process ownership: $($_.Exception.Message)"
    }
    $rootPrefix = $Root + "\"
    return @($processes | Where-Object {
        $commandLine = [string]$_.CommandLine
        $executable = [string]$_.ExecutablePath
        ($commandLine -match '(?i)uvicorn\s+app\.main:app') -and
            ($executable -ieq $VenvPy -or
                $commandLine.IndexOf($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -ge 0)
    })
}

function Get-VerifiedState {
    if (Test-Path -LiteralPath $OwnerPath -PathType Leaf) {
        try { $owner = Read-JsonFile $OwnerPath }
        catch { return @{ state="AMBIGUOUS"; message="Background ownership file is unreadable: $($_.Exception.Message)" } }

        if (-not $owner -or $owner.schema_version -ne 1 -or $owner.root -ine $Root -or
            [string]::IsNullOrWhiteSpace([string]$owner.run_id) -or
            [int]$owner.pid -le 4 -or [string]::IsNullOrWhiteSpace([string]$owner.command_line) -or
            [string]::IsNullOrWhiteSpace([string]$owner.created_utc)) {
            return @{ state="AMBIGUOUS"; message="Background ownership record is incomplete or belongs to another root." }
        }
        $ownerRunId = [guid]::Empty
        if (-not [guid]::TryParse([string]$owner.run_id, [ref]$ownerRunId)) {
            return @{ state="AMBIGUOUS"; message="Background owner does not contain a valid unique run ID." }
        }
        if (-not (Test-IdentityRecord $owner $VenvPy "uvicorn app.main:app")) {
            return @{ state="AMBIGUOUS"; message="Recorded Atlas PID or process identity is stale or changed; no process was touched." }
        }
        $apiProcesses = @(Get-AtlasApiProcesses)
        if ($apiProcesses.Count -ne 1 -or [int]$apiProcesses[0].ProcessId -ne [int]$owner.pid) {
            return @{ state="AMBIGUOUS"; message="Atlas API process count or PID does not match the unique recorded owner." }
        }

        if ($owner.state -ne "stopping" -and $owner.state -ne "starting") {
            try { $runtime = Read-JsonFile $RuntimePath }
            catch { return @{ state="AMBIGUOUS"; message="Atlas runtime manifest is unreadable: $($_.Exception.Message)" } }
            if (-not $runtime -or [string]$runtime.run_id -cne [string]$owner.run_id -or
                [int]$runtime.pid -ne [int]$owner.pid) {
                return @{ state="AMBIGUOUS"; message="Runtime manifest does not confirm the recorded unique run ID and PID." }
            }
        } elseif ($owner.state -eq "starting" -and (Test-Path -LiteralPath $RuntimePath -PathType Leaf)) {
            try { $runtime = Read-JsonFile $RuntimePath }
            catch { return @{ state="AMBIGUOUS"; message="Atlas runtime manifest is unreadable: $($_.Exception.Message)" } }
            if (-not $runtime -or [string]$runtime.run_id -cne [string]$owner.run_id -or
                [int]$runtime.pid -ne [int]$owner.pid) {
                return @{ state="AMBIGUOUS"; message="Runtime manifest does not confirm the recorded unique run ID and PID." }
            }
        }

        if ($owner.state -eq "stopping") {
            try { $stopLock = Read-JsonFile $StopLockPath }
            catch { return @{ state="AMBIGUOUS"; message="Background stop lock is unreadable; no process was touched." } }
            if (-not $stopLock) {
                return @{ state="AMBIGUOUS"; message="Stopping run has no stop lock; manual inspection is required." }
            }
            $requiredStopAction = if ($stopLock.phase -eq "waiting") { "-Action StopWorker" } else { "-Action Stop" }
            if ([string]$stopLock.run_id -cne [string]$owner.run_id -or
                -not (Test-IdentityRecord $stopLock $PowerShellPath $requiredStopAction) -or
                $stopLock.command_line.IndexOf($ManagerPath, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
                return @{ state="AMBIGUOUS"; message="Stopping run has no verified stop worker; manual inspection is required." }
            }
        }

        $listeners = @(Get-ApiListeners)
        if ($listeners.Count -gt 1 -or
            ($listeners.Count -eq 1 -and $listeners[0] -ne [int]$owner.pid)) {
            return @{ state="AMBIGUOUS"; message="Port 8000 has an unexpected or multiple listener; no process was touched." }
        }
        if ($owner.state -eq "running" -and $listeners.Count -ne 1) {
            return @{ state="AMBIGUOUS"; message="The recorded API is not the sole TCP 8000 listener." }
        }
        return @{
            state = [string]$owner.state
            message = if ($owner.state -eq "stop_timeout") {
                "Graceful shutdown timed out; Atlas API PID $($owner.pid) remains. No forced termination was attempted. Operator intervention is required. $($owner.last_error)"
            } else {
                "Verified Atlas background run $($owner.run_id), PID $($owner.pid)."
            }
            run_id = [string]$owner.run_id
            pid = [int]$owner.pid
            owner = $owner
        }
    }

    if (Test-Path -LiteralPath $LockPath -PathType Leaf) {
        try { $lock = Read-JsonFile $LockPath }
        catch { return @{ state="AMBIGUOUS"; message="Background start lock is unreadable; manual inspection is required." } }
        if (-not $lock -or @("starting", "launching") -notcontains [string]$lock.phase) {
            return @{ state="AMBIGUOUS"; message="Background start lock has an unrecognized lifecycle phase." }
        }
        $requiredAction = if ($lock.phase -eq "starting") { "-Action Worker" } else { "-Action Start" }
        if ($lock -and $lock.root -ieq $Root -and $lock.run_id -match '^[0-9a-fA-F-]{36}$' -and
            (Test-IdentityRecord $lock $PowerShellPath $requiredAction) -and
            $lock.command_line.IndexOf($ManagerPath, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return @{ state="starting"; message="Verified background worker is starting run $($lock.run_id)."; run_id=[string]$lock.run_id; pid=[int]$lock.pid }
        }
        return @{ state="AMBIGUOUS"; message="A start lock is stale or has an unverified process identity; manual inspection is required." }
    }
    if (Test-Path -LiteralPath $StopLockPath -PathType Leaf) {
        return @{ state="AMBIGUOUS"; message="A stop lock remains without an owner; manual inspection is required." }
    }
    if (Test-Path -LiteralPath $RuntimePath -PathType Leaf) {
        return @{ state="AMBIGUOUS"; message="A runtime manifest exists without a background owner; refusing to infer ownership." }
    }
    $apiProcesses = @(Get-AtlasApiProcesses)
    if ($apiProcesses.Count -gt 0) {
        return @{ state="AMBIGUOUS"; message="An Atlas API process exists without a background owner; refusing to infer ownership." }
    }
    $listeners = @(Get-ApiListeners)
    if ($listeners.Count -gt 0) {
        return @{ state="AMBIGUOUS"; message="Port 8000 is occupied by an unowned process; no process was touched." }
    }
    return @{ state="STOPPED"; message="No Atlas background run is recorded." }
}

function Write-Status($Status) {
    if ($Json) { return ($Status | ConvertTo-Json -Compress -Depth 8) }
    return ("{0}: {1}" -f $Status.state, $Status.message)
}

function Assert-CleanStart {
    $state = Get-VerifiedState
    if ($state.state -eq "running" -or $state.state -eq "starting" -or $state.state -eq "stopping") {
        throw "Atlas background is already $($state.state). $($state.message)"
    }
    if ($state.state -ne "STOPPED") {
        throw "Refusing startup because runtime ownership is ambiguous. $($state.message)"
    }
}

function Get-AtlasContainer([string]$Name, [string]$ExpectedService) {
    $raw = & docker inspect --format '{{json .}}' $Name 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return ConvertFrom-AtlasContainerInspection $Name $ExpectedService $Root ([string]$raw)
}

function Start-AtlasDependencies {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI is unavailable. Start Docker Desktop manually; this launcher will not manage Docker Desktop."
    }
    & docker info 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker engine is unavailable. Start Docker Desktop manually; this launcher will not start or stop it."
    }
    if (-not (Test-Path -LiteralPath $ComposePath -PathType Leaf)) {
        throw "Atlas docker-compose.yml is missing."
    }

    $postgres = Get-AtlasContainer "atlas-postgres" "postgres"
    $redis = Get-AtlasContainer "atlas-redis" "redis"
    if ($postgres -and $redis) {
        if (-not ($postgres.running -and $redis.running)) {
            & docker start atlas-postgres atlas-redis | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Could not start the verified Atlas dependency containers." }
        }
    } elseif (-not $postgres -and -not $redis) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root ".env") -PathType Leaf)) {
            throw "Root .env is required by Docker Compose when Atlas containers must be created; it will not be generated or rewritten."
        }
        & docker compose --project-name atlas --file $ComposePath up -d --no-recreate postgres redis
        if ($LASTEXITCODE -ne 0) { throw "Atlas dependency container creation failed." }
    } else {
        throw "Only one Atlas dependency container exists; refusing partial or destructive repair."
    }

    $deadline = (Get-Date).AddSeconds(120)
    do {
        $postgres = Get-AtlasContainer "atlas-postgres" "postgres"
        $redis = Get-AtlasContainer "atlas-redis" "redis"
        if ($postgres -and $redis -and $postgres.running -and $redis.running -and
            $postgres.health -eq "healthy" -and $redis.health -eq "healthy") { return }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)
    throw "Verified Atlas Postgres/Redis containers did not both become healthy."
}

function Wait-AtlasHttp([string]$Url, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { return }
        } catch { }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "Atlas did not pass HTTP readiness at $Url within $Seconds seconds."
}

function Remove-OwnedFile([string]$Path, [string]$ExpectedRunId) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    $value = Read-JsonFile $Path
    if ([string]$value.run_id -cne $ExpectedRunId) {
        throw "Refusing to remove a lifecycle file owned by a different run ID: $Path"
    }
    Remove-Item -LiteralPath $Path -Force
}

function Stop-OwnedApi($Owner, [int]$TimeoutSeconds = 30) {
    if (-not (Get-ProcessIdentity ([int]$Owner.pid))) { return $true }
    if (-not (Test-IdentityRecord $Owner $VenvPy "uvicorn app.main:app")) {
        throw "Atlas PID identity changed before shutdown; no process was signalled."
    }
    $existingRequest = Read-JsonFile $StopPath
    if ($existingRequest -and [string]$existingRequest.run_id -cne [string]$Owner.run_id) {
        $staleRunId = [guid]::Empty
        if (-not [guid]::TryParse([string]$existingRequest.run_id, [ref]$staleRunId)) {
            throw "A stop request has an invalid run ID; refusing to overwrite it."
        }
    }
    Write-JsonAtomic @{run_id=[string]$Owner.run_id} $StopPath
    $Owner.state = "stopping"
    Write-JsonAtomic $Owner $OwnerPath

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (-not (Get-ProcessIdentity ([int]$Owner.pid))) { return $true }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    if (-not (Test-IdentityRecord $Owner $VenvPy "uvicorn app.main:app")) {
        throw "Atlas PID identity changed during shutdown timeout; refusing fallback termination."
    }
    $Owner.state = "stop_timeout"
    $Owner.last_error = "Graceful shutdown exceeded $TimeoutSeconds seconds. The process and runtime ownership were retained; operator intervention is required. Inspect Atlas logs and reconcile PAPER state before taking manual action."
    Write-JsonAtomic $Owner $OwnerPath
    return $false
}

function Clear-OwnedRuntime($Owner) {
    Remove-OwnedFile $StopPath ([string]$Owner.run_id)
    if (Test-Path -LiteralPath $RuntimePath -PathType Leaf) {
        $runtime = Read-JsonFile $RuntimePath
        if ([string]$runtime.run_id -cne [string]$Owner.run_id -or
            [int]$runtime.pid -ne [int]$Owner.pid) {
            throw "Runtime manifest changed ownership during shutdown; refusing cleanup."
        }
        Remove-Item -LiteralPath $RuntimePath -Force
    }
    Remove-OwnedFile $OwnerPath ([string]$Owner.run_id)
}

function Invoke-BackgroundWorker {
    $lock = Read-JsonFile $LockPath
    if (-not $lock -or [string]$lock.run_id -cne $RunId -or $lock.root -ine $Root -or
        $lock.phase -cne "launching" -or $lock.executable -ine $PowerShellPath -or
        [string]$lock.command_line -notmatch '(?i)-Action\s+Start' -or
        $lock.command_line.IndexOf($ManagerPath, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Background start lock does not match the requested unique run ID."
    }
    $workerIdentity = Get-ProcessIdentity $PID
    if (-not $workerIdentity -or $workerIdentity.executable -ine $PowerShellPath -or
        $workerIdentity.command_line -notmatch '(?i)-Action\s+Worker' -or
        $workerIdentity.command_line.IndexOf($RunId, [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
        $workerIdentity.command_line.IndexOf($ManagerPath, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Could not verify the background worker process identity."
    }
    $lock.pid = [int]$PID
    $lock.executable = $workerIdentity.executable
    $lock.command_line = $workerIdentity.command_line
    $lock.created_utc = $workerIdentity.created_utc
    $lock.phase = "starting"
    Write-JsonAtomic $lock $LockPath

    $owner = $null
    $api = $null
    try {
        if (-not (Test-Path -LiteralPath $VenvPy -PathType Leaf)) {
            throw "Python venv is missing; run the documented first-time setup."
        }
        if (-not ((Test-Path -LiteralPath (Join-Path $Backend ".env") -PathType Leaf) -or
            (Test-Path -LiteralPath (Join-Path $Root ".env") -PathType Leaf))) {
            throw "No backend or root .env exists. Startup will not create or rewrite either file."
        }
        Start-AtlasDependencies

        New-Item -ItemType Directory -Force $RuntimeDir | Out-Null
        $logs = Join-Path $RuntimeDir "background-$RunId"
        $stdout = "$logs.out.log"
        $stderr = "$logs.err.log"
        $env:ATLAS_DESKTOP_CONTROL_DIR = $RuntimeDir
        $env:ATLAS_DESKTOP_RUN_ID = $RunId
        $loggingConfig = Join-Path $Root "deploy\logging-desktop.json"
        $api = Start-Process -FilePath $VenvPy -ArgumentList @(
            "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--log-config", ('"' + $loggingConfig + '"'),
            "--timeout-graceful-shutdown", "20"
        ) -WorkingDirectory $Backend -WindowStyle Hidden -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr -PassThru
        if (-not $api) { throw "Failed to create the Atlas API process." }

        $owner = @{
            schema_version = 1
            root = $Root
            state = "starting"
            run_id = $RunId
            pid = [int]$api.Id
            executable = $VenvPy
            command_line = ""
            created_utc = ""
            started_utc = (Get-Date).ToUniversalTime().ToString("o")
        }
        try { $owner.created_utc = $api.StartTime.ToUniversalTime().ToString("o") } catch { }
        Write-JsonAtomic $owner $OwnerPath

        $deadline = (Get-Date).AddSeconds(15)
        $identity = $null
        do {
            $identity = Get-ProcessIdentity ([int]$api.Id)
            if ($identity) { break }
            Start-Sleep -Milliseconds 250
        } while ((Get-Date) -lt $deadline)
        if (-not $identity -or $identity.executable -ine $VenvPy -or
            $identity.command_line -notmatch '(?i)uvicorn\s+app\.main:app') {
            throw "Started PID did not resolve to the expected Atlas venv Uvicorn process."
        }

        $owner.pid = [int]$identity.pid
        $owner.executable = $identity.executable
        $owner.command_line = $identity.command_line
        $owner.created_utc = $identity.created_utc
        Write-JsonAtomic $owner $OwnerPath
        Wait-AtlasHttp "http://127.0.0.1:8000/health" 120

        & powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $ReadyPath -Root $Root -TimeoutSeconds 180
        if ($LASTEXITCODE -ne 0) { throw "Atlas operator readiness did not stabilize." }

        $owner.state = "running"
        Write-JsonAtomic $owner $OwnerPath
    } catch {
        $failure = $_.Exception.Message
        if ($owner) {
            try {
                if (Get-ProcessIdentity ([int]$owner.pid)) {
                    $stopped = Stop-OwnedApi $owner
                    if ($stopped) { Clear-OwnedRuntime $owner }
                    else {
                        $owner.state = "stop_timeout"
                        $owner.last_error = $failure
                        Write-JsonAtomic $owner $OwnerPath
                    }
                } else {
                    Clear-OwnedRuntime $owner
                }
            } catch {
                $owner.state = "stop_timeout"
                $owner.last_error = "$failure; cleanup: $($_.Exception.Message)"
                Write-JsonAtomic $owner $OwnerPath
            }
        }
        throw "Background Atlas startup failed: $failure"
    } finally {
        if (Test-Path -LiteralPath $LockPath -PathType Leaf) {
            $currentLock = Read-JsonFile $LockPath
            if ($currentLock -and [string]$currentLock.run_id -ceq $RunId -and
                [int]$currentLock.pid -eq [int]$PID) {
                Remove-Item -LiteralPath $LockPath -Force
            }
        }
    }
}

function Invoke-StopWorker {
    $stopLock = Read-JsonFile $StopLockPath
    $workerIdentity = Get-ProcessIdentity $PID
    if (-not $stopLock -or [string]$stopLock.run_id -cne $RunId -or
        -not $workerIdentity -or $workerIdentity.executable -ine $PowerShellPath -or
        $workerIdentity.command_line -notmatch '(?i)-Action\s+StopWorker' -or
        $workerIdentity.command_line.IndexOf($RunId, [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
        $workerIdentity.command_line.IndexOf($ManagerPath, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Stop worker identity or unique run ID could not be verified."
    }
    $stopLock.pid = [int]$PID
    $stopLock.executable = $workerIdentity.executable
    $stopLock.command_line = $workerIdentity.command_line
    $stopLock.created_utc = $workerIdentity.created_utc
    $stopLock.phase = "waiting"
    Write-JsonAtomic $stopLock $StopLockPath

    $state = Get-VerifiedState
    if ($state.state -ne "stopping" -or [string]$state.run_id -cne $RunId) {
        throw "Stop worker could not verify the stopping Atlas run: $($state.message)"
    }
    $owner = $state.owner
    try {
        $stopped = Stop-OwnedApi $owner
        if (-not $stopped) {
            $owner.state = "stop_timeout"
            $owner.last_error = "Graceful shutdown exceeded 30 seconds. No forced termination was attempted. Inspect Atlas logs and PAPER reconciliation, then resolve the verified PID manually."
            Write-JsonAtomic $owner $OwnerPath
            throw "Atlas graceful shutdown timed out after 30 seconds. No forced termination was attempted; operator intervention is required. Review the Atlas logs and PAPER reconciliation before taking manual action."
        }
        Clear-OwnedRuntime $owner
    } finally {
        if (Test-Path -LiteralPath $StopLockPath -PathType Leaf) {
            $stopLock = Read-JsonFile $StopLockPath
            if ($stopLock -and [string]$stopLock.run_id -ceq $RunId) {
                Remove-Item -LiteralPath $StopLockPath -Force
            }
        }
    }
}

if ($Action -eq "Status") {
    return (Write-Status (Get-VerifiedState))
}

if ($Action -eq "Start") {
    Assert-CleanStart
    New-Item -ItemType Directory -Force $RuntimeDir | Out-Null
    $runId = [guid]::NewGuid().ToString()
    $parentIdentity = Get-ProcessIdentity $PID
    $lock = @{
        schema_version = 1
        root = $Root
        run_id = $runId
        phase = "launching"
        pid = [int]$PID
        executable = $parentIdentity.executable
        command_line = $parentIdentity.command_line
        created_utc = $parentIdentity.created_utc
    }
    try { New-ExclusiveJsonFile $lock $LockPath }
    catch { throw "Another start owns the lifecycle lock, or a stale lock exists; refusing duplicate startup." }

    $workerArgs = ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Action Worker -RunId "{1}"' -f $ManagerPath, $runId)
    try {
        $worker = Start-Process -FilePath $PowerShellPath -ArgumentList $workerArgs -WorkingDirectory $Root `
            -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RuntimeDir "background-start.out.log") `
            -RedirectStandardError (Join-Path $RuntimeDir "background-start.err.log") -PassThru
        if (-not $worker) { throw "Worker process was not created." }
    } catch {
        Remove-OwnedFile $LockPath $runId
        throw "Could not start the hidden Atlas background worker: $($_.Exception.Message)"
    }
    return (Write-Status @{state="starting"; message="Atlas background startup was requested. Run ID $runId." ; run_id=$runId; pid=[int]$worker.Id})
}

if ($Action -eq "Stop") {
    $state = Get-VerifiedState
    if ($state.state -eq "stopping") {
        return (Write-Status @{state="stopping"; message="The verified Atlas run is already stopping."; run_id=$state.run_id; pid=$state.pid})
    }
    if ($state.state -ne "running") {
        throw "Refusing stop because there is no verified running background owner. $($state.message)"
    }
    $existingRequest = Read-JsonFile $StopPath
    if ($existingRequest -and [string]$existingRequest.run_id -cne [string]$state.run_id) {
        $staleRunId = [guid]::Empty
        if (-not [guid]::TryParse([string]$existingRequest.run_id, [ref]$staleRunId)) {
            throw "A stop request has an invalid run ID; refusing to overwrite it."
        }
    }
    try {
        $stopIdentity = Get-ProcessIdentity $PID
        $stopLock = @{
            schema_version = 1
            run_id = $state.run_id
            pid = [int]$PID
            executable = $stopIdentity.executable
            command_line = $stopIdentity.command_line
            created_utc = $stopIdentity.created_utc
            phase = "requesting"
        }
        New-ExclusiveJsonFile $stopLock $StopLockPath
    } catch {
        throw "A stop request is already active or its lock is stale; refusing duplicate shutdown."
    }
    $owner = $state.owner
    $owner.state = "stopping"
    Write-JsonAtomic $owner $OwnerPath
    $workerArgs = ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Action StopWorker -RunId "{1}"' -f $ManagerPath, $owner.run_id)
    try {
        $worker = Start-Process -FilePath $PowerShellPath -ArgumentList $workerArgs -WorkingDirectory $Root `
            -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RuntimeDir "background-stop.out.log") `
            -RedirectStandardError (Join-Path $RuntimeDir "background-stop.err.log") -PassThru
        if (-not $worker) { throw "Stop worker process was not created." }
    } catch {
        throw "Graceful stop request was written but the wait worker could not start; ownership was retained. $($_.Exception.Message)"
    }
    return (Write-Status @{state="stopping"; message="Graceful shutdown requested for verified Atlas PID $($owner.pid)."; run_id=$owner.run_id; pid=$owner.pid})
}

if ($Action -eq "Worker") {
    $parsedRunId = [guid]::Empty
    if (-not [guid]::TryParse($RunId, [ref]$parsedRunId)) {
        throw "Invalid background run ID."
    }
    Invoke-BackgroundWorker
    return
}

if ($Action -eq "StopWorker") {
    $parsedRunId = [guid]::Empty
    if (-not [guid]::TryParse($RunId, [ref]$parsedRunId)) {
        throw "Invalid background run ID."
    }
    Invoke-StopWorker
    return
}
