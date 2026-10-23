# Separate host ownership: never calls the production manager or Docker.
function Open-AtlasReadOnlyDashboard([string]$Root) {
    if ($script:dashboardProcess -and -not $script:dashboardProcess.HasExited) {
        $health = Invoke-RestMethod ($script:dashboardReady.url + 'health') -TimeoutSec 3
        if ($health.host_id -cne $script:dashboardReady.host_id) { throw 'Dashboard ownership mismatch.' }
        Start-Process $script:dashboardReady.url -ErrorAction Stop
        return
    }
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = Join-Path $Root 'backend\.venv\Scripts\python.exe'
    $info.WorkingDirectory = $Root
    $info.Arguments = 'scripts\observation_runtime\readonly_dashboard.py logs\diagnostics\stage24-dashboard-bundle --manifest-sha256 bcd68bfb9a38c754604b59e4e9e7beee4806f1324088c84793b6b6e478b40a2f --port 18764 --gui-control'
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    if (-not $process.Start()) { throw 'Read-only host failed to start.' }
    $script:dashboardProcess = $process
    $script:dashboardShutdownRequested = $false
    try {
        $line = $process.StandardOutput.ReadLineAsync()
        if (-not $line.Wait(15000)) { throw 'Read-only host readiness timed out.' }
        $ready = $line.Result | ConvertFrom-Json -ErrorAction Stop
        if ($process.HasExited -or $ready.url -cne 'http://127.0.0.1:18764/' -or
            $ready.mode -cne 'READ_ONLY_STATIC' -or $ready.host_id -notmatch '^[a-f0-9]{32}$') {
            throw 'Invalid read-only host readiness.'
        }
        $health = Invoke-RestMethod ($ready.url + 'health') -TimeoutSec 3
        if ($health.host_id -cne $ready.host_id) { throw 'Read-only host ownership mismatch.' }
        $script:dashboardReady = $ready
        Start-Process $ready.url -ErrorAction Stop
    } catch {
        Close-AtlasReadOnlyDashboard
        throw
    }
}

function Close-AtlasReadOnlyDashboard {
    $process = $script:dashboardProcess

    if ($null -eq $process) {
        $script:dashboardReady = $null
        $script:dashboardShutdownRequested = $false
        return
    }

    if (-not $process.HasExited) {
        if (-not $script:dashboardShutdownRequested) {
            # Set before closing stdin so retries cannot close it twice.
            $script:dashboardShutdownRequested = $true
            try {
                $process.StandardInput.Close()
            } catch {
                # Preserve ownership; only an observed exit permits cleanup.
                if (-not $process.HasExited) {
                    throw "Read-only host stdin close failed: $($_.Exception.Message)"
                }
            }
        }

        # Bounded grace for Python HTTP shutdown and worker cleanup.
        if (-not $process.WaitForExit(12000)) {
            throw 'Read-only host did not exit; ownership retained; no forced termination attempted.'
        }
    }

    # Only release the reference after confirmed process exit.
    if (-not $process.HasExited) {
        throw 'Read-only host exit not confirmed; ownership retained.'
    }

    $process.Dispose()
    $script:dashboardProcess = $null
    $script:dashboardReady = $null
    $script:dashboardShutdownRequested = $false
}
Export-ModuleMember -Function Open-AtlasReadOnlyDashboard, Close-AtlasReadOnlyDashboard
