# Read-only exact-PID observations. Never authorizes startup/shutdown or termination.
function Get-AtlasNativeIdentityObservation {
    param([int]$ProcessId, $Expected)
    if ($ProcessId -le 4 -or -not $Expected) { throw 'Explicit expected identity required.' }
    $observed = @()
    foreach ($sample in 1..2) {
        if ($ProcessId -eq $PID) {
            # Supported self-observation avoids WMI permissions. Never use the
            # caller's command line as evidence for a different process.
            $self = [System.Diagnostics.Process]::GetCurrentProcess()
            try {
                $row = @{
                    pid = $PID
                    created_utc = $self.StartTime.ToUniversalTime().ToString('o')
                    executable = $self.MainModule.FileName
                    command_line = [Environment]::CommandLine
                }
            } finally { $self.Dispose() }
        } else {
        $process = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $ProcessId" -OperationTimeoutSec 2 -ErrorAction Stop
        if (-not $process) { throw 'Exact process unavailable.' }
        $row = @{
            pid = [int]$process.ProcessId
            created_utc = ([datetime]$process.CreationDate).ToUniversalTime().ToString('o')
            executable = [string]$process.ExecutablePath
            command_line = [string]$process.CommandLine
        }
        }
        foreach ($key in @('pid','created_utc','executable','command_line')) {
            if ([string]::IsNullOrWhiteSpace([string]$row[$key]) -or
                [string]$row[$key] -cne [string]$Expected[$key]) { throw 'Native identity mismatch.' }
        }
        $observed += $row
    }
    return @{identity=$observed[1];observed_utc=[datetime]::UtcNow.ToString('o');
             samples=2;quiescence='UNKNOWN';production_authorized=$false}
}
Export-ModuleMember -Function Get-AtlasNativeIdentityObservation

function Get-AtlasFixtureChildObservation {
    param([System.Diagnostics.Process]$OwnedChild, $Expected)
    if (-not $OwnedChild -or -not $Expected) { throw 'Exact retained fixture process required.' }
    $rows = @()
    foreach ($sample in 1..2) {
        $OwnedChild.Refresh()
        if ($OwnedChild.HasExited) { throw 'Fixture process exited; live identity unavailable.' }
        $row = @{
            pid = $OwnedChild.Id
            created_utc = $OwnedChild.StartTime.ToUniversalTime().ToString('o')
            executable = $OwnedChild.MainModule.FileName
        }
        foreach ($key in @('pid','created_utc','executable')) {
            if ([string]::IsNullOrWhiteSpace([string]$row[$key]) -or
                [string]$row[$key] -cne [string]$Expected[$key]) { throw 'Fixture child identity mismatch.' }
        }
        $rows += $row
    }
    return @{identity=$rows[1];command_line_verified=$false;ownership_independently_verified=$false;
             quiescence='UNKNOWN';production_authorized=$false}
}
Export-ModuleMember -Function Get-AtlasFixtureChildObservation

function Wait-AtlasFixtureChildExit {
    param([System.Diagnostics.Process]$OwnedChild, $Expected, [int]$TimeoutMilliseconds)
    if ($TimeoutMilliseconds -lt 0 -or $TimeoutMilliseconds -gt 5000) { throw 'Bounded fixture wait required.' }
    $observation = Get-AtlasFixtureChildObservation $OwnedChild $Expected
    $exited = $OwnedChild.WaitForExit($TimeoutMilliseconds)
    return @{process_exited=$exited;quiescence=$(if($exited){'EXACT_FIXTURE_PROCESS_EXITED'}else{'UNKNOWN'});
             production_authorized=$false;ownership_independently_verified=$false}
}
Export-ModuleMember -Function Wait-AtlasFixtureChildExit

function Get-AtlasFixtureCommandObservation {
    param([System.Diagnostics.Process]$OwnedChild, $Expected)
    # Retained live handle fences PID lifetime. CIM account identity is not an
    # Atlas ownership grant, and no production caller imports this observation.
    $before = Get-AtlasFixtureChildObservation $OwnedChild $Expected
    foreach ($key in @('command_line','account_sid','parent_pid')) {
        if ([string]::IsNullOrWhiteSpace([string]$Expected[$key])) { throw 'Missing fixture command context.' }
    }
    $last = $null
    foreach ($sample in 1..2) {
        $rows = @(Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $($OwnedChild.Id)" -OperationTimeoutSec 2 -ErrorAction Stop)
        if ($rows.Count -ne 1) { throw 'Exact fixture command unavailable.' }
        $row = $rows[0]
        # CIM CreationDate has microsecond resolution. Exact StartTime continuity
        # is independently retained by the live Process handle before and after.
        $nativeTicks = ([datetime]$row.CreationDate).ToUniversalTime().Ticks
        $handleTicks = $OwnedChild.StartTime.ToUniversalTime().Ticks
        if ([int]$row.ProcessId -ne $OwnedChild.Id -or
            [string]$row.ExecutablePath -cne [string]$Expected.executable -or
            [string]$row.CommandLine -cne [string]$Expected.command_line -or
            [int]$row.ParentProcessId -ne [int]$Expected.parent_pid -or
            ($nativeTicks - ($nativeTicks % 10)) -ne ($handleTicks - ($handleTicks % 10))) {
            throw 'Fixture native command identity mismatch.'
        }
        $account = Invoke-CimMethod -InputObject $row -MethodName GetOwnerSid -OperationTimeoutSec 2 -ErrorAction Stop
        if ($account.ReturnValue -ne 0 -or [string]$account.Sid -cne [string]$Expected.account_sid) {
            throw 'Fixture Windows account mismatch or unavailable.'
        }
        $last = @{pid=[int]$row.ProcessId;command_line=[string]$row.CommandLine;
                  executable=[string]$row.ExecutablePath;account_sid=[string]$account.Sid;
                  parent_pid=[int]$row.ParentProcessId}
    }
    $after = Get-AtlasFixtureChildObservation $OwnedChild $Expected
    return @{identity=$last;samples=2;observed_utc=[datetime]::UtcNow.ToString('o');
             command_line_verified=$true;windows_account_verified=$true;
             ownership_independently_verified=$false;quiescence='UNKNOWN';
             startup_authorized=$false;shutdown_authorized=$false;production_authorized=$false}
}
Export-ModuleMember -Function Get-AtlasFixtureCommandObservation
