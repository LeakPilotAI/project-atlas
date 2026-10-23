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
