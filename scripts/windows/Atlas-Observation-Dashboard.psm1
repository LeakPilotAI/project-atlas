# Original UI observation host only. No production manager or financial resources.
function Open-AtlasObservationDashboard([string]$Root, [switch]$BoundedDataOnly, [switch]$NoBrowser, [string]$ExistingDataBudget = '') {
    if ($script:observationProcess -and -not $script:observationProcess.HasExited) {
        $health=Invoke-RestMethod ($script:observationReady.url+'health') -TimeoutSec 3
        if ($health.host_id -cne $script:observationReady.host_id) { throw 'Observation ownership changed.' }
        if (-not $NoBrowser) { Start-Process $script:observationReady.url }
        return $script:observationReady
    }
    $info=New-Object System.Diagnostics.ProcessStartInfo
    $venv=Join-Path $Root 'backend\.venv\Scripts\python.exe'
    $base = (& $venv -I -c 'import sys; print(sys._base_executable)').Trim()
    if ($LASTEXITCODE -ne 0 -or -not [IO.Path]::IsPathRooted($base) -or -not (Test-Path -LiteralPath $base)) { throw 'Existing Python interpreter unavailable.' }
    $info.FileName=$base
    $info.EnvironmentVariables['PYTHONPATH']=(Join-Path $Root 'backend\.venv\Lib\site-packages')+';'+(Join-Path $Root 'backend')
    $info.Arguments='-B scripts\observation_runtime\desktop_observation.py'
    if ($BoundedDataOnly) { $info.Arguments+=' --data-only-seconds 30 --operator-data-only-approved' }
    if ($ExistingDataBudget) { $info.Arguments+=' --existing-data-budget "'+$ExistingDataBudget+'"' }
    $info.WorkingDirectory=$Root;$info.UseShellExecute=$false;$info.CreateNoWindow=$true
    $info.RedirectStandardInput=$true;$info.RedirectStandardOutput=$true
    $process=New-Object System.Diagnostics.Process;$process.StartInfo=$info
    if (-not $process.Start()) { throw 'Observation host did not start.' }
    $script:observationProcess=$process
    try {
        $line=$process.StandardOutput.ReadLineAsync()
        if (-not $line.Wait(15000)) { throw 'Observation readiness timed out.' }
        $ready=$line.Result | ConvertFrom-Json
        if ($process.HasExited -or $ready.mode -cne 'OBSERVATION_ONLY' -or $ready.pid -ne $process.Id -or
            $ready.url -notmatch '^http://127\.0\.0\.1:[0-9]+/$' -or
            $ready.creation_filetime -ne $process.StartTime.ToUniversalTime().ToFileTimeUtc() -or
            $ready.image -ine $process.MainModule.FileName) { throw 'Exact observation process identity refused.' }
        $health=Invoke-RestMethod ($ready.url+'health') -TimeoutSec 3
        if ($health.host_id -cne $ready.host_id -or $health.financial_writers -ne $false) { throw 'Observation HTTP readiness refused.' }
        $script:observationReady=$ready
        if (-not $NoBrowser) { Start-Process $ready.url }
        return $ready
    } catch { Close-AtlasObservationDashboard; throw }
}
function Close-AtlasObservationDashboard {
    $process=$script:observationProcess
    if ($null -eq $process) { return }
    if (-not $process.HasExited) {
        if ($script:observationReady -and ($process.Id -ne $script:observationReady.pid -or
            $process.StartTime.ToUniversalTime().ToFileTimeUtc() -ne $script:observationReady.creation_filetime)) { throw 'Observation identity mismatch; no close.' }
        $process.StandardInput.Close()
        if (-not $process.WaitForExit(12000)) { throw 'Observation exit unconfirmed; ownership retained; no forced termination.' }
    }
    $process.Dispose();$script:observationProcess=$null;$script:observationReady=$null
}
Export-ModuleMember -Function Open-AtlasObservationDashboard,Close-AtlasObservationDashboard
