# Snapshot/transaction guards only. Importing this module never queries Windows,
# writes a registry value, starts a process, reloads a service or grants authority.
# Every effect in Invoke-AtlasTimeGuardedExperiment is an explicitly supplied port.
Set-StrictMode -Version 2.0

function Get-TimeKeys($value) {
    if ($value -is [Collections.IDictionary]) { return @($value.Keys | ForEach-Object { [string]$_ }) }
    if ($value -is [pscustomobject]) { return @($value.psobject.Properties.Name) }
    throw 'TIME_GUARD_PLAIN_OBJECT_REQUIRED'
}

function Copy-TimeValue($value) {
    $text = ConvertTo-Json -InputObject $value -Depth 32 -Compress
    if ($text.Length -gt 131072) { throw 'TIME_GUARD_EVIDENCE_CAPACITY' }
    return ConvertFrom-Json -InputObject $text
}

function Test-TimeInteger($value) { return ($value -is [int] -or $value -is [long]) }

function Assert-TimeRow($row) {
    $keys = @(Get-TimeKeys $row)
    if ($keys.Count -ne 2 -or $keys -cnotcontains 'kind' -or $keys -cnotcontains 'value' -or $row.kind -isnot [string]) {
        throw 'TIME_GUARD_REGISTRY_ROW_SCHEMA'
    }
}

function Assert-TimePair([int]$maximum, [int]$update) {
    if (-not (($maximum -eq 15 -and $update -eq 360000) -or ($maximum -eq 6 -and $update -eq 100))) {
        throw 'TIME_GUARD_UNSUPPORTED_SETTING_PAIR'
    }
}

function Read-TimeBudget($io, $budget) {
    $value = & $io.RemainingSeconds
    if (-not ($value -is [int] -or $value -is [long] -or $value -is [double]) -or
        [double]::IsNaN($value) -or [double]::IsInfinity($value) -or $value -lt 0 -or
        $value -gt 300 -or $value -gt $budget.last) { throw 'TIME_GUARD_INVALID_OR_REVERSED_BUDGET' }
    $budget.last = [double]$value
    return $value
}

function Assert-TimeTargets($snapshot, [int]$maximum, [int]$update) {
    $values = $snapshot.configuration_values
    foreach ($pair in @(@('MaxPollInterval', $maximum), @('UpdateInterval', $update))) {
        $row = $values.($pair[0])
        $keys = @(Get-TimeKeys $row)
        if ($keys.Count -ne 2 -or $keys -cnotcontains 'kind' -or $keys -cnotcontains 'value' -or
            $row.kind -cne 'DWord' -or -not (Test-TimeInteger $row.value) -or $row.value -ne $pair[1]) {
            throw ('TIME_GUARD_TARGET_MISMATCH_' + $pair[0])
        }
    }
}

function Assert-AtlasTimeScope {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)]$Original, [Parameter(Mandatory=$true)]$Current,
          [Parameter(Mandatory=$true)][int]$ExpectedMaximum,
          [Parameter(Mandatory=$true)][int]$ExpectedUpdate)

    Assert-TimePair $ExpectedMaximum $ExpectedUpdate
    $fields = @('configuration_values','service','startup','source','type','SpecialPollInterval','NtpClientEnabled')
    foreach ($snapshot in @($Original, $Current)) {
        $keys = @(Get-TimeKeys $snapshot)
        if ($keys.Count -ne $fields.Count -or @($fields | Where-Object { $keys -cnotcontains $_ }).Count -ne 0) {
            throw 'TIME_GUARD_SNAPSHOT_SCHEMA'
        }
        foreach ($name in @('service','startup','source','type')) {
            if ($snapshot.$name -isnot [string]) { throw 'TIME_GUARD_SNAPSHOT_STRING_REQUIRED' }
        }
    }
    if ($Current.service -cne 'Running' -or $Current.startup -cne 'Manual' -or
        $Current.source -cne 'time.windows.com,0x9' -or $Current.type -cne 'NTP' -or
        -not (Test-TimeInteger $Current.SpecialPollInterval) -or $Current.SpecialPollInterval -ne 64 -or
        -not (Test-TimeInteger $Current.NtpClientEnabled) -or $Current.NtpClientEnabled -ne 1) {
        throw 'TIME_GUARD_SERVICE_SOURCE_OR_CLIENT_CHANGED'
    }
    Assert-TimeTargets $Current $ExpectedMaximum $ExpectedUpdate
    $names = @(Get-TimeKeys $Original.configuration_values)
    $nowNames = @(Get-TimeKeys $Current.configuration_values)
    if ($names.Count -lt 2 -or $names.Count -gt 128 -or $names.Count -ne $nowNames.Count -or
        @($names | Where-Object { $nowNames -cnotcontains $_ }).Count -ne 0) {
        throw 'TIME_GUARD_CONFIGURATION_NAMESPACE_CHANGED'
    }
    $runtime = @()
    foreach ($name in $names) {
        $before = $Original.configuration_values.$name
        $after = $Current.configuration_values.$name
        Assert-TimeRow $before
        Assert-TimeRow $after
        if ($name -cin @('MaxPollInterval','UpdateInterval')) { continue }
        if ($name -ceq 'LastKnownGoodTime') {
            # Narrow runtime-state rule, not a wildcard for Last*/Time* keys.
            # 300s experiment + at most120s baseline sync age. Never written or
            # rolled back; this progress is NOT clock-accuracy authentication.
            foreach ($row in @($before, $after)) {
                if (@(Get-TimeKeys $row).Count -ne 2 -or $row.kind -cne 'QWord' -or
                    -not (Test-TimeInteger $row.value) -or $row.value -le 0) {
                    throw 'TIME_GUARD_RUNTIME_TIMESTAMP_FORMAT'
                }
                try { $null = [datetime]::FromFileTimeUtc([long]$row.value) }
                catch { throw 'TIME_GUARD_RUNTIME_TIMESTAMP_RANGE' }
            }
            $advance = [decimal]$after.value - [decimal]$before.value
            if ($advance -lt 0 -or $advance -gt [decimal]4200000000) { throw 'TIME_GUARD_RUNTIME_TIMESTAMP_DISCONTINUITY' }
            if ($advance -gt 0) { $runtime += @{name=$name;advance_100ns=[long]$advance} }
        } elseif ($before.kind -cne $after.kind -or
                  (ConvertTo-Json -InputObject $before.value -Depth 16 -Compress) -cne
                  (ConvertTo-Json -InputObject $after.value -Depth 16 -Compress)) {
            throw ('TIME_GUARD_FOREIGN_CONFIGURATION_' + $name)
        }
    }
    return @{schema='ATLAS_TIME_SCOPE_REVIEW_V2';consistent=$true;runtime_changes=$runtime;authority_granted=$false}
}

function Assert-TimeEffectiveTargets([string]$text, [int]$maximum, [int]$update) {
    if ($text.Length -gt 32768) { throw 'TIME_GUARD_EFFECTIVE_CAPACITY' }
    foreach ($pair in @(@('MaxPollInterval',$maximum),@('UpdateInterval',$update))) {
        if ([regex]::Matches($text, '(?m)^'+$pair[0]+':\s*'+$pair[1]+'\s+\(Local\)\r?$').Count -ne 1) {
            throw ('TIME_GUARD_EFFECTIVE_LOCAL_' + $pair[0])
        }
    }
}

function Assert-AtlasTimeTargetReadback {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)]$Current,
          [Parameter(Mandatory=$true)][string]$EffectiveText)
    Assert-TimeTargets $Current 15 360000
    Assert-TimeEffectiveTargets $EffectiveText 15 360000
    return $true
}

function Assert-AtlasTimeEffective {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$OriginalText,
          [Parameter(Mandatory=$true)][string]$CurrentText,
          [Parameter(Mandatory=$true)][int]$ExpectedMaximum,
          [Parameter(Mandatory=$true)][int]$ExpectedUpdate)
    Assert-TimePair $ExpectedMaximum $ExpectedUpdate
    Assert-TimeEffectiveTargets $OriginalText 15 360000
    Assert-TimeEffectiveTargets $CurrentText $ExpectedMaximum $ExpectedUpdate
    foreach ($text in @($OriginalText,$CurrentText)) {
        foreach ($pair in @(@('MinPollInterval',6),@('PhaseCorrectRate',1),@('SpecialPollInterval',64))) {
            if ([regex]::Matches($text,'(?m)^'+$pair[0]+':\s*'+$pair[1]+'\s+\(Local\)\r?$').Count -ne 1) {
                throw ('TIME_GUARD_EFFECTIVE_LOCAL_' + $pair[0])
            }
        }
        if ([regex]::Matches($text,'(?m)^NtpServer:\s*time\.windows\.com,0x9\s+\(Local\)\r?$').Count -ne 1 -or
            [regex]::Matches($text,'(?m)^Type:\s*NTP\s+\(Local\)\r?$').Count -ne 1) {
            throw 'TIME_GUARD_EFFECTIVE_SOURCE_OR_POLICY'
        }
    }
    # The effective query is configuration, not runtime status. Keep every
    # other field/origin/section strict, including NtpClient provider settings.
    $old = $OriginalText.Replace("`r`n","`n").Trim()
    $now = $CurrentText.Replace("`r`n","`n").Trim()
    foreach ($name in @('MaxPollInterval','UpdateInterval')) {
        $old = [regex]::Replace($old,'(?m)^'+$name+':[^\n]*$', $name+':<approved>')
        $now = [regex]::Replace($now,'(?m)^'+$name+':[^\n]*$', $name+':<approved>')
    }
    if ($old -cne $now) { throw 'TIME_GUARD_EFFECTIVE_FOREIGN_CONFIGURATION' }
    return $true
}

function Invoke-AtlasTimeGuardedExperiment {
    [CmdletBinding()]
    param([Collections.IDictionary]$Ports,
          [ValidateSet('DISPOSABLE_SYNTHETIC','LOCAL_WINDOWS')][string]$EvidenceDomain='DISPOSABLE_SYNTHETIC')

    $required=@('ReadSnapshot','QueryEffective','WriteSetting','Reload','ObserveClock','VerifyClock','Record','RemainingSeconds')
    if ($null -eq $Ports -or $Ports.Count -ne $required.Count) { throw 'TIME_GUARD_EXPLICIT_PORTS_REQUIRED' }
    $io=@{}
    foreach ($name in $required) {
        if (-not $Ports.Contains($name) -or $Ports[$name] -isnot [scriptblock]) { throw 'TIME_GUARD_EXPLICIT_PORTS_REQUIRED' }
        $io[$name]=$Ports[$name]
    }
    $result=@{schema='ATLAS_TIME_GUARDED_FLOW_V2';domain=$EvidenceDomain;status='PREFLIGHT';experiment_success=$false;
        mutation_started=$false;apply_reload_count=0;rollback_reload_count=0;target_restore_readback_verified=$false;
        full_scope_verified=$false;rollback_verified=$false;evidence_complete=$false;authority_granted=$false}
    $before=$null;$originalEffective=$null;$budget=@{last=300.0}
    try {
        $remaining=Read-TimeBudget $io $budget
        if ($remaining -lt 235) { throw 'TIME_GUARD_PREFLIGHT_BUDGET' }
        $before=Copy-TimeValue (& $io.ReadSnapshot)
        Assert-TimeTargets $before 15 360000
        $null=Assert-AtlasTimeScope $before $before 15 360000
        $originalEffective=& $io.QueryEffective
        $null=Assert-AtlasTimeEffective $originalEffective $originalEffective 15 360000
        $result.before=$before
        $ack=& $io.Record 'before' (Copy-TimeValue @{snapshot=$before;effective=$originalEffective})
        if ($ack -isnot [bool] -or -not $ack) { throw 'TIME_GUARD_BEFORE_RECORD' }
        # Record acknowledgements must be exactly True; a nonempty object is not an ACK.
        $ack=& $io.Record 'intent' @{maximum=6;update=100}
        if ($ack -isnot [bool] -or -not $ack) { throw 'TIME_GUARD_INTENT_RECORD' }
        if ((Read-TimeBudget $io $budget) -lt 225) { throw 'TIME_GUARD_APPLY_BUDGET' }
        $result.mutation_started=$true  # Covers interrupted/partial first write.
        $null=& $io.WriteSetting 'MaxPollInterval' 6
        $null=& $io.WriteSetting 'UpdateInterval' 100
        $result.apply_reload_count=1
        $code=& $io.Reload 'apply'
        if ($code -isnot [int] -or $code -ne 0) { throw 'TIME_GUARD_APPLY_RELOAD' }
        $effective=& $io.QueryEffective
        $null=Assert-AtlasTimeEffective $originalEffective $effective 6 100
        $applied=Copy-TimeValue (& $io.ReadSnapshot)
        $review=Assert-AtlasTimeScope $before $applied 6 100
        $result.applied=$applied
        $ack=& $io.Record 'applied' (Copy-TimeValue @{snapshot=$applied;effective=$effective;scope=$review})
        if ($ack -isnot [bool] -or -not $ack) { throw 'TIME_GUARD_APPLIED_RECORD' }
        $clock=Copy-TimeValue (& $io.ObserveClock 180)
        if ((Read-TimeBudget $io $budget) -lt 20) { throw 'TIME_GUARD_FINALIZATION_BUDGET' }
        $age=$clock.age_seconds
        if ($clock.qualified -isnot [bool] -or -not $clock.qualified -or $clock.complete -isnot [bool] -or -not $clock.complete -or
            -not (Test-TimeInteger $clock.bound_ms) -or $clock.bound_ms -lt 0 -or $clock.bound_ms -ge 1000 -or
            -not ($age -is [int] -or $age -is [long] -or $age -is [double]) -or [double]::IsNaN($age) -or
            [double]::IsInfinity($age) -or $age -lt 0 -or $age -gt 120 -or $clock.domain -cne $EvidenceDomain -or
            $clock.source -cne 'time.windows.com,0x9') { throw 'TIME_GUARD_CLOCK_NOT_QUALIFIED' }
        $verified=& $io.VerifyClock $clock
        if ($verified -isnot [bool] -or -not $verified) { throw 'TIME_GUARD_CLOCK_AUTHENTICATION' }
        $effective=& $io.QueryEffective
        $null=Assert-AtlasTimeEffective $originalEffective $effective 6 100
        $result.after=Copy-TimeValue (& $io.ReadSnapshot)
        $review=Assert-AtlasTimeScope $before $result.after 6 100
        $ack=& $io.Record 'qualified' (Copy-TimeValue @{snapshot=$result.after;clock=$clock;scope=$review})
        if ($ack -isnot [bool] -or -not $ack) { throw 'TIME_GUARD_QUALIFIED_RECORD' }
        $result.full_scope_verified=$true;$result.evidence_complete=$true;$result.experiment_success=$true
        $result.status='CLOCK_QUALIFIED_APPLIED_VERIFIED'
    } catch {
        $result.failure=$_.Exception.Message
        if (-not $result.mutation_started) { $result.status='REFUSED_BEFORE_CONFIGURATION_CHANGE';return $result }
        $result.status='UNRESOLVED_ROLLBACK_NOT_CONFIRMED_STOP'
        try {
            if ((Read-TimeBudget $io $budget) -lt 15) { throw 'TIME_GUARD_ROLLBACK_BUDGET' }
            $current=Copy-TimeValue (& $io.ReadSnapshot)
            # Never overwrite a foreign value/type in either approved setting.
            foreach ($pair in @(@('MaxPollInterval',15,6),@('UpdateInterval',360000,100))) {
                $row=$current.configuration_values.($pair[0])
                if ($row.kind -cne 'DWord' -or -not (Test-TimeInteger $row.value) -or $row.value -notin @($pair[1],$pair[2])) {
                    throw 'TIME_GUARD_FOREIGN_TARGET_NO_OVERWRITE'
                }
            }
            $null=& $io.WriteSetting 'MaxPollInterval' 15
            $null=& $io.WriteSetting 'UpdateInterval' 360000
            $result.rollback_reload_count=1
            $code=& $io.Reload 'rollback'
            if ($code -isnot [int] -or $code -ne 0) { throw 'TIME_GUARD_ROLLBACK_RELOAD' }
            $effective=& $io.QueryEffective
            $result.after=Copy-TimeValue (& $io.ReadSnapshot)
            $null=Assert-AtlasTimeTargetReadback $result.after $effective
            # Separate this fact from the full scope/evidence decision.
            $result.target_restore_readback_verified=$true
            $null=Assert-AtlasTimeEffective $originalEffective $effective 15 360000
            $review=Assert-AtlasTimeScope $before $result.after 15 360000
            $result.full_scope_verified=$true
            $ack=& $io.Record 'rollback' (Copy-TimeValue @{snapshot=$result.after;effective=$effective;scope=$review})
            if ($ack -isnot [bool] -or -not $ack) { throw 'TIME_GUARD_ROLLBACK_RECORD' }
            $result.evidence_complete=$true;$result.rollback_verified=$true;$result.status='FAILED_ROLLBACK_CONFIRMED'
        } catch { $result.rollback_error=$_.Exception.Message }
    }
    return $result
}

Export-ModuleMember -Function Assert-AtlasTimeScope,Assert-AtlasTimeEffective,Assert-AtlasTimeTargetReadback,Invoke-AtlasTimeGuardedExperiment
