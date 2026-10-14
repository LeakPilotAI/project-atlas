function Test-AtlasApiProcessOwnership(
    $Owner,
    $Runtime,
    $ApiProcess,
    $OwnerProcess,
    [string]$ExpectedExecutable,
    [string]$ExpectedRoot
) {
    if (-not $Owner -or -not $Runtime -or -not $ApiProcess) { return $false }
    if ([string]$Owner.root -ine $ExpectedRoot -or
        [string]$Owner.run_id -cne [string]$Runtime.run_id -or
        [int]$Runtime.pid -le 4 -or [int]$ApiProcess.ProcessId -ne [int]$Runtime.pid) {
        return $false
    }

    $apiExecutable = [string]$ApiProcess.ExecutablePath
    $apiCommand = [string]$ApiProcess.CommandLine
    if ($apiExecutable -ine $ExpectedExecutable -or
        $apiCommand -notmatch '(?i)uvicorn\s+app\.main:app' -or
        $apiCommand.IndexOf($ExpectedRoot + "\", [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return $false
    }

    try {
        $runtimeStarted = $Runtime.PSObject.Properties["started_utc"]
        $ownerStarted = $Owner.PSObject.Properties["started_utc"]
        $startValue = if ($runtimeStarted -and -not [string]::IsNullOrWhiteSpace([string]$runtimeStarted.Value)) {
            [string]$runtimeStarted.Value
        } else {
            [string]$ownerStarted.Value
        }
        $started = [datetime]::Parse($startValue).ToUniversalTime()
        $apiCreated = ([datetime]$ApiProcess.CreationDate).ToUniversalTime()
    } catch {
        return $false
    }
    $maximumStartSkew = if (-not $runtimeStarted -or
        [string]::IsNullOrWhiteSpace([string]$runtimeStarted.Value)) { 120 } else { 30 }
    if ([math]::Abs(($apiCreated - $started).TotalSeconds) -gt $maximumStartSkew) { return $false }

    if ([int]$Owner.pid -eq [int]$ApiProcess.ProcessId) {
        if ([string]$Owner.created_utc -cne $apiCreated.ToString("o")) { return $false }
        $launcherPidProperty = $Owner.PSObject.Properties["launcher_pid"]
        if ($launcherPidProperty -and [int]$launcherPidProperty.Value -gt 4 -and
            [int]$launcherPidProperty.Value -ne [int]$Runtime.pid) {
            $launcherPid = [int]$launcherPidProperty.Value
            if (-not $OwnerProcess -or
                [int]$OwnerProcess.ProcessId -ne $launcherPid) {
                return $true
            }
            try {
                $launcherCreated = ([datetime]$OwnerProcess.CreationDate).ToUniversalTime()
            } catch {
                return $false
            }
            if ([string]$Owner.launcher_created_utc -cne $launcherCreated.ToString("o") -or
                [string]$Owner.launcher_executable -ine [string]$OwnerProcess.ExecutablePath -or
                [string]$Owner.launcher_command_line -cne [string]$OwnerProcess.CommandLine) {
                return $false
            }
            return ([int]$ApiProcess.ParentProcessId -eq $launcherPid -or
                [int]$OwnerProcess.ParentProcessId -eq [int]$Runtime.pid)
        }
        return $true
    }

    if ($OwnerProcess) {
        try {
            $ownerCreated = ([datetime]$OwnerProcess.CreationDate).ToUniversalTime()
        } catch {
            return $false
        }
        if ([string]$Owner.created_utc -cne $ownerCreated.ToString("o") -or
            [int]$OwnerProcess.ProcessId -ne [int]$Owner.pid) {
            return $false
        }
        return ([int]$ApiProcess.ParentProcessId -eq [int]$Owner.pid -or
            [int]$OwnerProcess.ParentProcessId -eq [int]$Runtime.pid)
    }

    return $true
}

function Test-AtlasDeadSession(
    $Owner,
    $Runtime,
    [string]$ExpectedRoot,
    [int[]]$ExistingPids,
    [int[]]$ApiPids,
    [int[]]$ListenerPids,
    [bool]$HasLifecycleLock
) {
    if (-not $Owner -or -not $Runtime -or $HasLifecycleLock) { return $false }
    if ([string]$Owner.root -ine $ExpectedRoot -or
        [string]$Owner.run_id -cne [string]$Runtime.run_id) {
        return $false
    }
    $runId = [guid]::Empty
    if (-not [guid]::TryParse([string]$Owner.run_id, [ref]$runId) -or
        [int]$Owner.pid -le 4 -or [int]$Runtime.pid -le 4) {
        return $false
    }
    if ($ExistingPids -contains [int]$Owner.pid -or
        $ExistingPids -contains [int]$Runtime.pid -or
        $ApiPids.Count -gt 0 -or $ListenerPids.Count -gt 0) {
        return $false
    }
    return $true
}

function Move-AtlasDeadSessionMetadata(
    [string]$OwnerPath,
    [string]$RuntimePath,
    [string]$ArchiveRoot,
    $Owner,
    $Runtime,
    [string]$ExpectedRoot,
    [int[]]$ExistingPids,
    [int[]]$ApiPids,
    [int[]]$ListenerPids,
    [bool]$HasLifecycleLock
) {
    if (-not (Test-AtlasDeadSession $Owner $Runtime $ExpectedRoot $ExistingPids `
        $ApiPids $ListenerPids $HasLifecycleLock)) {
        throw "Stale background ownership is not proven dead and unambiguous; metadata was not moved."
    }

    $archiveName = "{0}-{1}-{2}" -f [string]$Owner.run_id,
        [datetime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ"), [guid]::NewGuid().ToString("N")
    $archivePath = Join-Path $ArchiveRoot $archiveName
    New-Item -ItemType Directory -Path $archivePath -ErrorAction Stop | Out-Null
    Move-Item -LiteralPath $OwnerPath -Destination (Join-Path $archivePath "atlas-background-owner.json") -ErrorAction Stop
    Move-Item -LiteralPath $RuntimePath -Destination (Join-Path $archivePath "runtime.json") -ErrorAction Stop
    return $archivePath
}

Export-ModuleMember -Function Test-AtlasApiProcessOwnership, Test-AtlasDeadSession, Move-AtlasDeadSessionMetadata
