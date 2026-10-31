# Selected immutable release only. No legacy fallback, providers or financial Start.
function Open-AtlasInstalledNonfinancialDashboard {
    param([object]$Binding = $null, [switch]$Approved)
    if (-not $Approved) { throw 'EXPLICIT_NONFINANCIAL_DESKTOP_AUTHORIZATION_REQUIRED' }
    if ($script:installedNonfinancialOwner) { throw 'OWNED_RUNTIME_MUST_BE_RECONCILED_BEFORE_RESTART' }
    if ($script:installedNonfinancialLastFailure) { throw 'INSTALLED_NONFINANCIAL_RECONCILIATION_REQUIRED' }
    $fields = @('domain','head','native_root','release','requests','schema','seconds','support_sha256')
    if ($null -eq $Binding -or
        (@($Binding.PSObject.Properties.Name | Sort-Object) -join ',') -cne ($fields -join ',') -or
        $Binding.schema -cne 'QD_NONFINANCIAL_DESKTOP_BINDING_V1' -or $Binding.domain -cne 'WINDOWS_LOCAL' -or
        $Binding.release -cnotmatch '^[a-f0-9]{40}$' -or $Binding.head -cnotmatch '^[a-f0-9]{64}$' -or
        $Binding.support_sha256 -cnotmatch '^[a-f0-9]{64}$') { throw 'EXACT_NONFINANCIAL_DESKTOP_BINDING_REQUIRED' }
    foreach ($number in @($Binding.seconds,$Binding.requests)+@($Binding.native_root)) {
        if ($number -isnot [int] -and $number -isnot [long] -and $number -isnot [uint32]) {
            throw 'INTEGER_NONFINANCIAL_LIMIT_AND_NATIVE_ID_REQUIRED'
        }
    }
    if (@($Binding.native_root).Count -ne 3 -or $Binding.seconds -lt 1 -or $Binding.seconds -gt 120 -or
        $Binding.requests -lt 1 -or $Binding.requests -gt 96 -or
        @($Binding.native_root | Where-Object { $_ -lt 0 -or $_ -gt [uint32]::MaxValue }).Count) {
        throw 'BOUNDED_NONFINANCIAL_DESKTOP_REQUIRED'
    }
    $support = "D:\AtlasRuntime\launchers\$($Binding.support_sha256)"
    if ($PSScriptRoot -ine (Join-Path $support 'scripts\windows')) {
        throw 'INSTALLED_DESKTOP_ADAPTER_REQUIRED_NO_WORKSPACE_FALLBACK'
    }
    $release = "D:\AtlasRuntime\releases\$($Binding.release)"
    $python = Join-Path $release 'python\python.exe'
    $entry = Join-Path $support 'scripts\installed_nonfinancial_launcher.py'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or -not (Test-Path -LiteralPath $entry -PathType Leaf)) {
        throw 'INSTALLED_NONFINANCIAL_DEPENDENCIES_MISSING'
    }
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $python
    $info.Arguments = '-I -B "'+$entry+'" --execute-approved-nonfinancial --release '+$Binding.release+
        ' --expected-head '+$Binding.head+' --support-sha256 '+$Binding.support_sha256+
        ' --native-root '+($Binding.native_root -join ' ')+' --seconds '+$Binding.seconds+' --requests '+$Binding.requests
    $info.WorkingDirectory=$release
    $info.UseShellExecute=$false
    $info.CreateNoWindow=$true
    $info.RedirectStandardInput=$true
    $info.RedirectStandardOutput=$true
    $info.RedirectStandardError=$true
    $info.EnvironmentVariables.Remove('PYTHONPATH')
    $info.EnvironmentVariables.Remove('PYTHONHOME')
    $info.EnvironmentVariables['PYTHONDONTWRITEBYTECODE']='1'
    $info.EnvironmentVariables['PYTHONNOUSERSITE']='1'
    $process=New-Object System.Diagnostics.Process
    $process.StartInfo=$info
    if (-not $process.Start()) { $process.Dispose(); throw 'OWNED_NONFINANCIAL_START_REFUSED' }
    $owner=[pscustomobject]@{Process=$process;Pid=$process.Id;Created=$process.StartTime.ToUniversalTime().ToFileTimeUtc();
        Image=$process.MainModule.FileName;Ready=$null;StopWatch=$null;InputClosed=$false;Stderr=$process.StandardError.ReadToEndAsync()}
    $script:installedNonfinancialOwner=$owner
    try {
        $line=$process.StandardOutput.ReadLineAsync()
        if (-not $line.Wait(180000)) { throw 'INSTALLED_NONFINANCIAL_STARTUP_TIMEOUT' }
        $ready=$line.Result | ConvertFrom-Json
        if ($process.HasExited -or $ready.schema -cne 'QD_INSTALLED_NONFINANCIAL_CONTROLLER_V1' -or
            $ready.controller.pid -ne $owner.Pid -or $ready.controller.created -ne $owner.Created -or
            $ready.controller.image -ine $owner.Image -or $owner.Image -ine $python -or
            $ready.dashboard.release -cne $Binding.release -or $ready.dashboard.head -cne $Binding.head -or
            $ready.dashboard.url -cnotmatch '^http://127\.0\.0\.1:[0-9]+/$' -or
            $ready.dashboard.mode -cne 'INSTALLED_NONFINANCIAL_ONLY' -or
            $ready.dashboard.providers -ne $false -or $ready.dashboard.financial_writers -ne $false -or
            $ready.dashboard.trading -ne $false) { throw 'OWNED_INSTALLED_DESKTOP_READINESS_REFUSED' }
        $owner.Ready=$ready.dashboard
        return $ready.dashboard # Existing UI may open this URL after verified readiness.
    } catch {
        $failure=$_.Exception.Message
        try { Close-AtlasInstalledNonfinancialDashboard | Out-Null }
        catch { throw ("START_REFUSED: "+$failure+"; OWNED_CLEANUP_UNRESOLVED: "+$_.Exception.Message) }
        throw $failure
    }
}

function Close-AtlasInstalledNonfinancialDashboard {
    $owner=$script:installedNonfinancialOwner
    if ($null -eq $owner) {
        if ($script:installedNonfinancialLastFailure) { throw $script:installedNonfinancialLastFailure }
        return [pscustomobject]@{closed=$true;status='NO_OWNED_NONFINANCIAL_RUNTIME'}
    }
    if ($null -eq $owner.StopWatch) { $owner.StopWatch=[Diagnostics.Stopwatch]::StartNew() }
    $process=$owner.Process
    if ($process.Id -ne $owner.Pid -or $process.StartTime.ToUniversalTime().ToFileTimeUtc() -ne $owner.Created) {
        throw 'NONFINANCIAL_OWNER_CHANGED_NO_CLOSE'
    }
    if (-not $process.HasExited) {
        if (-not $owner.InputClosed) {
            try {
                if ($owner.Ready) {
                    $process.StandardInput.WriteLine('STOP '+$owner.Ready.host_id)
                    $process.StandardInput.Flush()
                }
            } finally {
                $process.StandardInput.Close()
                $owner.InputClosed=$true
            }
        }
        $remaining=[Math]::Max(1,8000-[int]$owner.StopWatch.ElapsedMilliseconds)
        if (-not $process.WaitForExit($remaining)) { throw 'NONFINANCIAL_STOP_INCOMPLETE_OWNERSHIP_RETAINED' }
    }
    $tail=$process.StandardOutput.ReadToEnd()
    $stderr=$owner.Stderr.GetAwaiter().GetResult()
    $code=$process.ExitCode
    $process.Dispose()
    $script:installedNonfinancialOwner=$null
    $elapsed=$owner.StopWatch.Elapsed.TotalSeconds
    try {
        if ($tail.Length -gt 65536 -or $stderr -or $code -ne 0) { throw 'NONFINANCIAL_CONTROLLER_EXIT_UNVERIFIED' }
        $last=@($tail -split "\r?\n" | Where-Object { $_.Trim() })[-1] | ConvertFrom-Json
        if ($last.closed -ne $true -or $last.within_stop_budget -ne $true -or
            $last.financial_actions -ne 0 -or $elapsed -gt 8) { throw 'NONFINANCIAL_COMPLETE_STOP_NOT_ACCEPTED' }
        return [pscustomobject]@{closed=$true;seconds=$elapsed;financial_actions=0}
    } catch {
        $script:installedNonfinancialLastFailure=$_.Exception.Message
        throw
    }
}

Export-ModuleMember -Function Open-AtlasInstalledNonfinancialDashboard,Close-AtlasInstalledNonfinancialDashboard
