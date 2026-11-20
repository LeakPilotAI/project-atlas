# Separate, manual background lifecycle for Project Atlas. Never use the legacy stop path.
#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet("Start", "Status", "Stop", "Worker", "StopWorker")]
    [string]$Action = "Status",
    [string]$RunId = "",
    [string]$ExpectedRunId = "",
    [switch]$EnableExtendedHoursResearch,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Import-Module (Join-Path $PSScriptRoot 'Atlas-StartupAdmission.psm1') -Force
if ($Action -eq 'Start') { Assert-AtlasStartupAdmission -Boundary 'parent' }
if ($Action -eq 'Worker') { Assert-AtlasStartupAdmission -Boundary 'worker-entry' }

if ($EnableExtendedHoursResearch -and $Action -ne "Start") {
    throw "Extended-hours opt-in is valid only for an explicitly approved Start."
}
if ($ExpectedRunId -and $Action -ne "Stop") { throw "ExpectedRunId is valid only for Stop." }

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Backend = Join-Path $Root "backend"
$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"
$RuntimeDir = Join-Path $Root "logs\runtime"
$OwnerPath = Join-Path $RuntimeDir "atlas-background-owner.json"
$LockPath = Join-Path $RuntimeDir "atlas-background-start.lock"
$StopLockPath = Join-Path $RuntimeDir "atlas-background-stop.lock"
$RecoveryLockPath = Join-Path $RuntimeDir "atlas-background-recovery.lock"
$RuntimePath = Join-Path $RuntimeDir "runtime.json"
$StopPath = Join-Path $RuntimeDir "stop.json"
$ManagerPath = Join-Path $PSScriptRoot "Atlas-Background.ps1"
$ReadyPath = Join-Path $PSScriptRoot "Atlas-Ready.ps1"
$ComposePath = Join-Path $Root "docker-compose.yml"
$PowerShellPath = Join-Path $PSHOME "powershell.exe"
$VenvBasePy = ""
Import-Module (Join-Path $PSScriptRoot "Atlas-ContainerOwnership.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "Atlas-ProcessOwnership.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "Atlas-CompleteShutdown.psm1") -Force

function Get-VenvBaseExecutable([string]$VenvExecutable) {
    $configPath = Join-Path (Split-Path (Split-Path $VenvExecutable -Parent) -Parent) "pyvenv.cfg"
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { return "" }
    $configText = Get-Content -LiteralPath $configPath -Raw -ErrorAction Stop
    $homeMatch = [regex]::Match($configText, '(?m)^\s*home\s*=\s*(.+?)\s*$')
    $executableMatch = [regex]::Match($configText, '(?m)^\s*executable\s*=\s*(.+?)\s*$')
    if (-not $homeMatch.Success -or -not $executableMatch.Success) { return "" }
    try {
        $venvHome = [System.IO.Path]::GetFullPath($homeMatch.Groups[1].Value.Trim()).TrimEnd("\")
        $executable = [System.IO.Path]::GetFullPath($executableMatch.Groups[1].Value.Trim())
    } catch {
        return ""
    }
    if ($executable.IndexOf($venvHome + "\", [StringComparison]::OrdinalIgnoreCase) -ne 0 -or
        [System.IO.Path]::GetFileName($executable) -notin @("python.exe", "pythonw.exe") -or
        -not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        return ""
    }
    return (Resolve-Path -LiteralPath $executable -ErrorAction Stop).Path
}

$VenvBasePy = Get-VenvBaseExecutable $VenvPy

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

function Set-OwnerLastError($Owner, [string]$Message) {
    if ($null -eq $Owner) {
        throw "Cannot record an error without an owner."
    }
    if ($Owner -is [System.Collections.IDictionary]) {
        $Owner["last_error"] = $Message
    } elseif ($Owner.PSObject.Properties["last_error"]) {
        $Owner.last_error = $Message
    } else {
        $Owner | Add-Member -NotePropertyName "last_error" -NotePropertyValue $Message -ErrorAction Stop
    }
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
        parent_pid = [int]$process.ParentProcessId
        executable = [string]$process.ExecutablePath
        command_line = [string]$process.CommandLine
        created_utc = ([datetime]$process.CreationDate).ToUniversalTime().ToString("o")
    }
}

function Get-CimProcess([int]$ProcessId) {
    if ($ProcessId -le 4) { throw "Refusing invalid process ID $ProcessId." }
    return Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $ProcessId) -ErrorAction Stop
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

function Test-StartCommandLine([string]$CommandLine) {
    if ([string]::IsNullOrWhiteSpace($CommandLine)) { return $false }
    $managerPattern = [regex]::Escape($ManagerPath)
    $directPattern = '(?i)-File\s+["'']?' + $managerPattern +
        '["'']?\s+-Action\s+["'']?Start["'']?(?:\s|$)'
    if ($CommandLine -match $directPattern) { return $true }

    $encoded = [regex]::Match($CommandLine, '(?i)-EncodedCommand\s+["'']?([A-Za-z0-9+/=]+)')
    if (-not $encoded.Success) { return $false }
    try {
        $script = [Text.Encoding]::Unicode.GetString(
            [Convert]::FromBase64String($encoded.Groups[1].Value)
        )
    } catch {
        return $false
    }
    $wrapperPattern = '(?i)&\s+["'']?' + $managerPattern +
        '["'']?\s+-Action\s+["'']?Start["'']?(?:\s|$)'
    return ($script -match $wrapperPattern)
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
    if (Test-Path -LiteralPath $RecoveryLockPath -PathType Leaf) {
        return @{ state="AMBIGUOUS"; message="A background ownership recovery is in progress or left an unverified lock." }
    }
    if (Test-Path -LiteralPath $OwnerPath -PathType Leaf) {
        try { $owner = Read-JsonFile $OwnerPath }
        catch { return @{ state="AMBIGUOUS"; message="Background ownership file is unreadable: $($_.Exception.Message)" } }

        if (-not $owner -or $owner.schema_version -ne 1 -or $owner.root -ine $Root -or
            [string]::IsNullOrWhiteSpace([string]$owner.run_id) -or
            [int]$owner.pid -le 4 -or [string]::IsNullOrWhiteSpace([string]$owner.created_utc) -or
            ($owner.state -ne "starting" -and [string]::IsNullOrWhiteSpace([string]$owner.command_line))) {
            return @{ state="AMBIGUOUS"; message="Background ownership record is incomplete or belongs to another root." }
        }
        $ownerRunId = [guid]::Empty
        if (-not [guid]::TryParse([string]$owner.run_id, [ref]$ownerRunId)) {
            return @{ state="AMBIGUOUS"; message="Background owner does not contain a valid unique run ID." }
        }

        if ($owner.state -eq "starting" -and (Test-Path -LiteralPath $LockPath -PathType Leaf)) {
            try { $lock = Read-JsonFile $LockPath }
            catch { return @{ state="AMBIGUOUS"; message="Background start lock is unreadable; manual inspection is required." } }
            $requiredAction = if ($lock.phase -eq "starting") { "-Action Worker" } else { "-Action Start" }
            if ($lock -and [string]$lock.run_id -ceq [string]$owner.run_id -and
                (Test-IdentityRecord $lock $PowerShellPath $requiredAction) -and
                $lock.command_line.IndexOf($ManagerPath, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                return @{ state="starting"; message="Verified background worker is starting run $($owner.run_id)."; run_id=[string]$owner.run_id; pid=[int]$owner.pid }
            }
            return @{ state="AMBIGUOUS"; message="A start lock is stale or has an unverified process identity; manual inspection is required." }
        }

        try { $runtime = Read-JsonFile $RuntimePath }
        catch { return @{ state="AMBIGUOUS"; message="Atlas runtime manifest is unreadable: $($_.Exception.Message)" } }
        if (-not $runtime -or [string]$runtime.run_id -cne [string]$owner.run_id -or [int]$runtime.pid -le 4) {
            return @{ state="AMBIGUOUS"; message="Runtime manifest does not confirm the recorded unique run ID and a valid API PID." }
        }

        $apiProcesses = @(Get-AtlasApiProcesses)
        $listeners = @(Get-ApiListeners)
        $recordedLauncherPid = 0
        if ($owner.PSObject.Properties["launcher_pid"]) {
            $recordedLauncherPid = [int]$owner.launcher_pid
        }
        $launcherPid = if ($recordedLauncherPid -gt 4) {
            $recordedLauncherPid
        } elseif ([int]$owner.pid -ne [int]$runtime.pid) {
            [int]$owner.pid
        } else {
            0
        }
        if ($apiProcesses.Count -eq 0 -and $listeners.Count -eq 0) {
            $recoveryIdentity = Get-ProcessIdentity $PID
            $recoveryLock = @{
                run_id = [string]$owner.run_id
                pid = [int]$PID
                executable = $recoveryIdentity.executable
                command_line = $recoveryIdentity.command_line
                created_utc = $recoveryIdentity.created_utc
            }
            try { New-ExclusiveJsonFile $recoveryLock $RecoveryLockPath }
            catch {
                return @{ state="AMBIGUOUS"; message="Could not acquire the exclusive stale-session recovery lock; no metadata was moved." }
            }
            $preserveRecoveryLock = $false
            try {
                $latestOwner = Read-JsonFile $OwnerPath
                $latestRuntime = Read-JsonFile $RuntimePath
                if (-not $latestOwner -or -not $latestRuntime -or
                    [string]$latestOwner.run_id -cne [string]$owner.run_id -or
                    [string]$latestRuntime.run_id -cne [string]$runtime.run_id -or
                    [int]$latestOwner.pid -ne [int]$owner.pid -or
                    [int]$latestRuntime.pid -ne [int]$runtime.pid -or
                    (Test-Path -LiteralPath $LockPath -PathType Leaf) -or
                    (Test-Path -LiteralPath $StopLockPath -PathType Leaf)) {
                    throw "Ownership metadata or a lifecycle lock changed during recovery."
                }
                $freshApiProcesses = @(Get-AtlasApiProcesses)
                $freshListeners = @(Get-ApiListeners)
                $existingPids = @()
                foreach ($processId in @([int]$latestOwner.pid, [int]$latestRuntime.pid, $launcherPid) |
                    Where-Object { $_ -gt 4 } | Sort-Object -Unique) {
                    $process = Get-CimProcess ([int]$processId)
                    if ($process) { $existingPids += [int]$process.ProcessId }
                }
                if (-not (Test-AtlasDeadSession $latestOwner $latestRuntime $Root `
                    $existingPids @($freshApiProcesses | ForEach-Object { [int]$_.ProcessId }) `
                    $freshListeners $false)) {
                    throw "The session is still live or ambiguous after exclusive recovery revalidation."
                }
                $archivePath = Move-AtlasDeadSessionMetadata $OwnerPath $RuntimePath `
                    (Join-Path $RuntimeDir "stale-sessions") $latestOwner $latestRuntime $Root `
                    $existingPids @($freshApiProcesses | ForEach-Object { [int]$_.ProcessId }) `
                    $freshListeners $false
            } catch {
                $recoveryFailure = $_.Exception.Message
                if ($recoveryFailure -match "STALE_SESSION_ROLLBACK_FAILED") {
                    $preserveRecoveryLock = $true
                }
                return @{ state="AMBIGUOUS"; message="Stale-session recovery failed; metadata integrity must be verified before further lifecycle operations. $recoveryFailure" }
            } finally {
                if (-not $preserveRecoveryLock -and
                    (Test-Path -LiteralPath $RecoveryLockPath -PathType Leaf)) {
                    $currentRecoveryLock = Read-JsonFile $RecoveryLockPath
                    if ($currentRecoveryLock -and
                        [string]$currentRecoveryLock.run_id -ceq [string]$owner.run_id -and
                        [int]$currentRecoveryLock.pid -eq [int]$PID) {
                        Remove-Item -LiteralPath $RecoveryLockPath -Force
                    }
                }
            }
            return @{ state="STOPPED"; message="A confirmed dead run was archived for review at $archivePath. No process or service was stopped."; archive_path=$archivePath }
        }

        $apiProcess = @($apiProcesses | Where-Object { [int]$_.ProcessId -eq [int]$runtime.pid })
        if ($apiProcess.Count -ne 1) {
            return @{ state="AMBIGUOUS"; message="The runtime manifest PID does not identify exactly one Atlas API process." }
        }
        $ownerProcess = if ($launcherPid -gt 4 -and $launcherPid -ne [int]$runtime.pid) {
            Get-CimProcess $launcherPid
        } else {
            $null
        }
        $unexpectedProcesses = @($apiProcesses | Where-Object {
            [int]$_.ProcessId -ne [int]$runtime.pid -and [int]$_.ProcessId -ne $launcherPid
        })
        if ($unexpectedProcesses.Count -gt 0 -or
            -not (Test-AtlasApiProcessOwnership $owner $runtime $apiProcess[0] `
                $ownerProcess $VenvPy $Root $VenvBasePy)) {
            return @{ state="AMBIGUOUS"; message="API process identity, creation time, parent relationship, or run ownership does not match; no process was touched." }
        }

        if ($owner.state -eq "stopping") {
            try { $stopLock = Read-JsonFile $StopLockPath }
            catch { return @{ state="AMBIGUOUS"; message="Background stop lock is unreadable; no process was touched." } }
            if (-not $stopLock) {
                return @{ state="AMBIGUOUS"; message="Stopping run has no stop lock; manual inspection is required." }
            }
            $requiredStopAction = if ($stopLock.phase -eq "waiting") { "-Action StopWorker" } else { "-Action Stop" }
            $requiredStopScript = $ManagerPath
            $completeScript = Join-Path (Split-Path $ManagerPath -Parent) "Atlas-CompleteShutdown.ps1"
            $completePattern = '(?i)(?:^|\s)-File\s+["'']?' + [regex]::Escape($completeScript) + '["'']?\s+-Complete(?:\s|$)'
            if ($stopLock.phase -eq "requesting" -and $stopLock.command_line -match $completePattern) {
                $requiredStopAction = $completeScript
                $requiredStopScript = $completeScript
            }
            if ([string]$stopLock.run_id -cne [string]$owner.run_id -or
                -not (Test-IdentityRecord $stopLock $PowerShellPath $requiredStopAction) -or
                $stopLock.command_line.IndexOf($requiredStopScript, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
                return @{ state="AMBIGUOUS"; message="Stopping run has no verified stop worker; manual inspection is required." }
            }
        }

        if ($listeners.Count -gt 1 -or
            ($listeners.Count -eq 1 -and $listeners[0] -ne [int]$runtime.pid)) {
            return @{ state="AMBIGUOUS"; message="Port 8000 has an unexpected or multiple listener; no process was touched." }
        }
        if ($owner.state -eq "running" -and $listeners.Count -ne 1) {
            return @{ state="AMBIGUOUS"; message="The recorded API is not the sole TCP 8000 listener." }
        }
        $owner.pid = [int]$runtime.pid
        $owner.executable = [string]$apiProcess[0].ExecutablePath
        $owner.command_line = [string]$apiProcess[0].CommandLine
        $owner.created_utc = ([datetime]$apiProcess[0].CreationDate).ToUniversalTime().ToString("o")
        $effectiveState = [string]$owner.state
        $message = "Verified Atlas background run $($owner.run_id), PID $($runtime.pid)."
        if ($owner.state -eq "stop_timeout" -and
            -not (Test-Path -LiteralPath $StopLockPath -PathType Leaf) -and
            [string]$owner.last_error -match '(?i)no process was signalled') {
            $effectiveState = "running"
            $message = "Verified Atlas background run $($owner.run_id), PID $($runtime.pid). A previous ownership-check failure did not signal the process."

        } elseif ($owner.state -eq "stop_timeout") {
            $message = "Graceful shutdown timed out; Atlas API PID $($owner.pid) remains. No forced termination was attempted. Operator intervention is required. $($owner.last_error)"
        }
        $owner.state = $effectiveState
        return @{
            state = $effectiveState
            message = $message
            run_id = [string]$owner.run_id
            pid = [int]$runtime.pid
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
    $priorErrorPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = & docker inspect --format '{{json .}}' $Name 2>&1
        $inspectExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $priorErrorPreference }
    $text = (@($raw) | ForEach-Object { [string]$_ }) -join "`n"
    if ($inspectExit -ne 0) {
        if ($text.Trim() -ceq "Error: No such object: $Name" -or
            $text.Trim() -ceq "Error response from daemon: No such container: $Name") { return $null }
        throw "Atlas dependency inspection failed; absence is not established."
    }
    return ConvertFrom-AtlasContainerInspection $Name $ExpectedService $Root $text
}

function Start-AtlasDependencies {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI is unavailable. Start Docker Desktop manually; this launcher will not manage Docker Desktop."
    }
    $localEndpoint = Get-AtlasLocalDockerEndpoint
    $priorDockerHost = [Environment]::GetEnvironmentVariable('DOCKER_HOST','Process')
    $priorDockerContext = [Environment]::GetEnvironmentVariable('DOCKER_CONTEXT','Process')
    try {
        [Environment]::SetEnvironmentVariable('DOCKER_HOST',$localEndpoint,'Process')
        [Environment]::SetEnvironmentVariable('DOCKER_CONTEXT',$null,'Process')
        & docker info 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Docker engine is unavailable. Start Docker Desktop manually; this launcher will not start or stop it."
        }
        if (-not (Test-Path -LiteralPath $ComposePath -PathType Leaf)) {
            throw "Atlas docker-compose.yml is missing."
        }

        $postgres = Get-AtlasContainer "atlas-postgres" "postgres"
        $redis = Get-AtlasContainer "atlas-redis" "redis"
        $completeReceipt = Join-Path $RuntimeDir "atlas-complete-shutdown.json"
        if (Test-Path -LiteralPath $completeReceipt) {
            Assert-AtlasCompleteReceipt $Root
            $receipt = Read-JsonFile $completeReceipt
            foreach ($row in @($receipt.services)) {
                $current = if ($row.name -ceq 'atlas-postgres') { $postgres } elseif ($row.name -ceq 'atlas-redis') { $redis } else { throw "Unknown dependency in restoration receipt." }
                if ($row.id -and (-not $current -or $current.id -cne $row.id)) { throw "Dependency restoration identity changed; no recreation or data replacement is allowed." }
            }
        }
        $expectedPostgresId = if ($postgres) { [string]$postgres.id } else { '' }
        $expectedRedisId = if ($redis) { [string]$redis.id } else { '' }
        if ($postgres -and $redis) {
            if ($postgres.id -cnotmatch '^[0-9a-f]{64}$' -or $redis.id -cnotmatch '^[0-9a-f]{64}$' -or
                $postgres.project -cne $redis.project) { throw "Atlas dependency IDs or Compose projects are ambiguous." }
            if (-not ($postgres.running -and $redis.running)) {
                & docker start $postgres.id $redis.id | Out-Null
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
            if ($postgres -and $redis) {
                if ($postgres.id -cnotmatch '^[0-9a-f]{64}$' -or $redis.id -cnotmatch '^[0-9a-f]{64}$' -or
                    ($expectedPostgresId -and $postgres.id -cne $expectedPostgresId) -or
                    ($expectedRedisId -and $redis.id -cne $expectedRedisId) -or $postgres.project -cne $redis.project) {
                    throw "Atlas dependency identity changed during readiness."
                }
                $expectedPostgresId = $postgres.id; $expectedRedisId = $redis.id
                if ($postgres.running -and $redis.running -and $postgres.health -eq "healthy" -and $redis.health -eq "healthy") { return }
            }
            Start-Sleep -Seconds 3
        } while ((Get-Date) -lt $deadline)
        throw "Verified Atlas Postgres/Redis containers did not both become healthy."
    } finally {
        [Environment]::SetEnvironmentVariable('DOCKER_HOST',$priorDockerHost,'Process')
        [Environment]::SetEnvironmentVariable('DOCKER_CONTEXT',$priorDockerContext,'Process')
    }
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

function Test-VerifiedApiIdentity($Owner) {
    # The startup-error cleanup path receives the worker's in-memory dictionary.
    if ($Owner -is [System.Collections.IDictionary]) { $Owner = [pscustomobject]$Owner }
    $runtime = Read-JsonFile $RuntimePath
    if (-not $runtime -or [string]$runtime.run_id -cne [string]$Owner.run_id -or
        [int]$runtime.pid -ne [int]$Owner.pid) { return $false }
    $apiProcesses = @(Get-AtlasApiProcesses | Where-Object {
        [int]$_.ProcessId -eq [int]$runtime.pid
    })
    if ($apiProcesses.Count -ne 1) { return $false }
    $listeners = @(Get-ApiListeners)
    if ($listeners.Count -ne 1 -or $listeners[0] -ne [int]$runtime.pid) { return $false }
    $launcherPid = 0
    if ($Owner.PSObject.Properties["launcher_pid"]) {
        $launcherPid = [int]$Owner.launcher_pid
    }
    $launcher = if ($launcherPid -gt 4 -and $launcherPid -ne [int]$runtime.pid) {
        Get-CimProcess $launcherPid
    } else {
        $null
    }
    return (Test-AtlasApiProcessOwnership $Owner $runtime $apiProcesses[0] `
        $launcher $VenvPy $Root $VenvBasePy)
}

function Stop-OwnedApi($Owner, [int]$TimeoutSeconds = 30) {
    if (-not (Get-ProcessIdentity ([int]$Owner.pid))) { return $true }
    if (-not (Test-VerifiedApiIdentity $Owner)) {
        throw "Atlas API process identity or run ownership changed before shutdown; no process was signalled."
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

    if (-not (Test-VerifiedApiIdentity $Owner)) {
        throw "Atlas API process identity or run ownership changed during shutdown timeout; refusing fallback termination."
    }
    $Owner.state = "stop_timeout"
    Set-OwnerLastError $Owner "Graceful shutdown exceeded $TimeoutSeconds seconds. The process and runtime ownership were retained; operator intervention is required. Inspect Atlas logs and reconcile PAPER state before taking manual action."
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
    Assert-AtlasStartupAdmission -Boundary 'worker-function'
    $lock = Read-JsonFile $LockPath
    if (-not $lock -or [string]$lock.run_id -cne $RunId -or $lock.root -ine $Root -or
        $lock.phase -cne "launching" -or $lock.executable -ine $PowerShellPath -or
        -not (Test-StartCommandLine ([string]$lock.command_line))) {
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
        $launchStartedUtc = (Get-Date).ToUniversalTime().ToString("o")
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
            started_utc = $launchStartedUtc
            launcher_pid = [int]$api.Id
            launcher_executable = $VenvPy
            launcher_command_line = ""
            launcher_created_utc = ""
        }
        $launcherIdentity = $null
        try { $launcherIdentity = Get-ProcessIdentity ([int]$api.Id) } catch { }
        if ($launcherIdentity) {
            $owner.command_line = $launcherIdentity.command_line
            $owner.created_utc = $launcherIdentity.created_utc
            $owner.launcher_executable = $launcherIdentity.executable
            $owner.launcher_command_line = $launcherIdentity.command_line
            $owner.launcher_created_utc = $launcherIdentity.created_utc
        } else {
            try { $owner.created_utc = $api.StartTime.ToUniversalTime().ToString("o") } catch { }
        }
        Write-JsonAtomic $owner $OwnerPath

        $deadline = (Get-Date).AddSeconds(30)
        $runtime = $null
        $apiProcess = $null
        $ownerProcess = $null
        do {
            try { $runtime = Read-JsonFile $RuntimePath } catch { $runtime = $null }
            if ($runtime) {
                if ([string]$runtime.run_id -cne $RunId -or [int]$runtime.pid -le 4) {
                    throw "The API runtime manifest does not match this unique background run."
                }
                $matches = @(Get-AtlasApiProcesses | Where-Object {
                    [int]$_.ProcessId -eq [int]$runtime.pid
                })
                if ($matches.Count -gt 1) {
                    throw "Multiple Atlas API processes claim the runtime manifest PID."
                }
                if ($matches.Count -eq 1) {
                    $apiProcess = $matches[0]
                    if ($api.Id -ne $runtime.pid) {
                        $ownerProcess = Get-CimProcess ([int]$api.Id)
                    }
                    $owner.pid = [int]$runtime.pid
                    $owner.executable = [string]$apiProcess.ExecutablePath
                    $owner.command_line = [string]$apiProcess.CommandLine
                    $owner.created_utc = ([datetime]$apiProcess.CreationDate).ToUniversalTime().ToString("o")
                    if (-not [string]::IsNullOrWhiteSpace([string]$runtime.started_utc)) {
                        $owner.started_utc = [string]$runtime.started_utc
                    }
                    if (Test-AtlasApiProcessOwnership $owner $runtime $apiProcess `
                        $ownerProcess $VenvPy $Root $VenvBasePy) {
                        break
                    }
                    throw "The API PID, process identity, creation time, or launcher relationship could not be verified."
                }
            }
            Start-Sleep -Milliseconds 250
        } while ((Get-Date) -lt $deadline)
        if (-not $runtime -or -not $apiProcess) {
            throw "The Atlas runtime manifest and matching API process did not appear within 30 seconds."
        }

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
                        Set-OwnerLastError $owner $failure
                        Write-JsonAtomic $owner $OwnerPath
                    }
                } else {
                    Clear-OwnedRuntime $owner
                }
            } catch {
                $owner.state = "stop_timeout"
                Set-OwnerLastError $owner "$failure; cleanup: $($_.Exception.Message)"
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
            Set-OwnerLastError $owner "Graceful shutdown exceeded 30 seconds. No forced termination was attempted. Inspect Atlas logs and PAPER reconciliation, then resolve the verified PID manually."
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
    $atlasRequestGate = Enter-AtlasLifecycleGate $Root
    try {
        Assert-AtlasCompleteReceipt $Root
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
        $priorExtendedHours = [Environment]::GetEnvironmentVariable(
            "ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED", "Process"
        )
        try {
            # Never inherit an accidental research opt-in from a desktop/controller.
            # Only this explicit Start switch grants the new worker the feature flag.
            [Environment]::SetEnvironmentVariable(
                "ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED",
                $(if ($EnableExtendedHoursResearch) { "true" } else { "false" }),
                "Process"
            )
            $worker = Start-Process -FilePath $PowerShellPath -ArgumentList $workerArgs -WorkingDirectory $Root `
                -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RuntimeDir "background-start.out.log") `
                -RedirectStandardError (Join-Path $RuntimeDir "background-start.err.log") -PassThru
            if (-not $worker) { throw "Worker process was not created." }
        } catch {
            Remove-OwnedFile $LockPath $runId
            throw "Could not start the hidden Atlas background worker: $($_.Exception.Message)"
        } finally {
            [Environment]::SetEnvironmentVariable(
                "ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED", $priorExtendedHours, "Process"
            )
        }
        return (Write-Status @{state="starting"; message="Atlas background startup was requested. Run ID $runId." ; run_id=$runId; pid=[int]$worker.Id})
    } finally { Exit-AtlasLifecycleGate $atlasRequestGate }
}

if ($Action -eq "Stop") {
    $atlasRequestGate = Enter-AtlasLifecycleGate $Root
    try {
        $state = Get-VerifiedState
        if ($ExpectedRunId -and [string]$state.run_id -cne $ExpectedRunId) {
            throw "Verified backend run changed; no stop was requested."
        }
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
            $launchFailure = $_.Exception.Message
            # A23-G3E3D-R3D1: process creation may succeed even if confirmation fails.
            # The worker may already own the stop lock, be shutting down, or have
            # removed the owner record. Never rewrite owner state from this parent.
            # Preserve the original stopping/lock evidence for independent review.
            throw "STOP_WORKER_LAUNCH_UNCONFIRMED: Stop worker creation could not be confirmed. The worker may already be running or may have completed shutdown. No owner or stop-lock recovery was attempted; verify current process identity and lifecycle evidence before manual intervention. $launchFailure"
        }
        return (Write-Status @{state="stopping"; message="Graceful shutdown requested for verified Atlas PID $($owner.pid)."; run_id=$owner.run_id; pid=$owner.pid})
    } finally { Exit-AtlasLifecycleGate $atlasRequestGate }
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
