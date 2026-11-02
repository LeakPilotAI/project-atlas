# Selected immutable release only. No legacy fallback, providers or financial Start.
function Open-AtlasInstalledNonfinancialDashboard {
    param([object]$Binding = $null, [switch]$Approved, [switch]$Disposable)
    if (-not $Approved) { throw 'EXPLICIT_NONFINANCIAL_DESKTOP_AUTHORIZATION_REQUIRED' }
    if ($script:installedNonfinancialOwner) { throw 'OWNED_RUNTIME_MUST_BE_RECONCILED_BEFORE_RESTART' }
    if ($script:installedNonfinancialLastFailure) { throw 'INSTALLED_NONFINANCIAL_RECONCILIATION_REQUIRED' }
    $fields = @('domain','head','native_root','release','requests','schema','seconds','support_sha256')
    $version2 = $null -ne $Binding -and $Binding.schema -ceq 'QD_NONFINANCIAL_DESKTOP_BINDING_V2'
    if ($version2) { $fields += @('deployment_sha256','support_receipt_sha256') }
    if ($Disposable) { $fields += @('fixture_base') }
    $fields = @($fields | Sort-Object)
    $domain = if ($Disposable) { 'DISPOSABLE' } else { 'WINDOWS_LOCAL' }
    if ($null -eq $Binding -or
        (@($Binding.PSObject.Properties.Name | Sort-Object) -join ',') -cne ($fields -join ',') -or
        $Binding.schema -cnotin @('QD_NONFINANCIAL_DESKTOP_BINDING_V1','QD_NONFINANCIAL_DESKTOP_BINDING_V2') -or $Binding.domain -cne $domain -or
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
    $base = 'D:\AtlasRuntime'
    if ($Disposable) {
        if (-not $version2 -or $Binding.fixture_base -cnotmatch '^D:\\Work\\Project Atlas\\logs\\diagnostics\\qd-selector-v1-native-[a-zA-Z0-9-]+\\[a-zA-Z0-9-]+$') {
            throw 'EXACT_DISPOSABLE_DESKTOP_SCOPE_REQUIRED'
        }
        $base=$Binding.fixture_base
    }
    $support = Join-Path $base "launchers\$($Binding.support_sha256)"
    if ($PSScriptRoot -ine (Join-Path $support 'scripts\windows')) {
        throw 'INSTALLED_DESKTOP_ADAPTER_REQUIRED_NO_WORKSPACE_FALLBACK'
    }
    if (-not $version2 -or $Binding.deployment_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
        $Binding.support_receipt_sha256 -cnotmatch '^[a-f0-9]{64}$') { throw 'ACCEPTED_SUPPORT_DEPLOYMENT_PINS_REQUIRED' }
    $release = Join-Path $base "releases\$($Binding.release)"
    $python = Join-Path $release 'python\python.exe'
    $entry = Join-Path $support 'scripts\installed_nonfinancial_launcher.py'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or -not (Test-Path -LiteralPath $entry -PathType Leaf)) {
        throw 'INSTALLED_NONFINANCIAL_DEPENDENCIES_MISSING'
    }
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $python
    $execution = if ($Disposable) { '--execute-disposable-acceptance' } else { '--execute-approved-nonfinancial' }
    $info.Arguments = '-I -B "'+$entry+'" '+$execution+' --release '+$Binding.release+
        ' --expected-head '+$Binding.head+' --support-sha256 '+$Binding.support_sha256+
        ' --deployment-sha256 '+$Binding.deployment_sha256+' --support-receipt-sha256 '+$Binding.support_receipt_sha256+
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
        $expectedMode=if ($Disposable) { 'DISPOSABLE_NONFINANCIAL_ONLY' } else { 'INSTALLED_NONFINANCIAL_ONLY' }
        $checks=[ordered]@{
            running=(-not $process.HasExited)
            schema=($ready.schema -ceq 'QD_INSTALLED_NONFINANCIAL_CONTROLLER_V1')
            pid=($ready.controller.pid -eq $owner.Pid)
            created=($ready.controller.created -eq $owner.Created)
            image=($ready.controller.image -ieq $owner.Image -and $owner.Image -ieq $python)
            release=($ready.dashboard.release -ceq $Binding.release)
            head=($ready.dashboard.head -ceq $Binding.head)
            url=($ready.dashboard.url -cmatch '^http://127\.0\.0\.1:[0-9]+/$')
            mode=($ready.dashboard.mode -ceq $expectedMode)
            providers=($ready.dashboard.providers -is [bool] -and $ready.dashboard.providers -eq $false)
            writers=($ready.dashboard.financial_writers -is [bool] -and $ready.dashboard.financial_writers -eq $false)
            trading=($ready.dashboard.trading -is [bool] -and $ready.dashboard.trading -eq $false)
            autostart=($ready.dashboard.automatic_startup -is [bool] -and $ready.dashboard.automatic_startup -eq $false)
        }
        $failed=@($checks.Keys | Where-Object { $checks[$_] -ne $true })
        if ($failed.Count) { throw ('OWNED_INSTALLED_DESKTOP_READINESS_REFUSED:'+($failed -join ',')) }
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
