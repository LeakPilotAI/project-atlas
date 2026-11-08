# Bounded native Windows 11 time-accuracy profile, only for Atlas's verified
# standalone host. Source: Microsoft "Configuring systems for high accuracy".
# Default is read-only. -ExecuteApproved requires a real elevated Administrator.
# Changes only UpdateInterval 360000->100 and FrequencyCorrectRate 4->2.
# Preserves PhaseCorrectRate=7, both NTP peers, 64s polls, and Atlas clock gates.
#Requires -Version 5.1
param([switch]$ExecuteApproved)
$ErrorActionPreference='Stop'

$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$cfgPath='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config'
$ntpPath='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'
$policy='HKLM:\SOFTWARE\Policies\Microsoft\W32Time\Config'
$ntpPolicy='HKLM:\SOFTWARE\Policies\Microsoft\W32Time\TimeProviders\NtpClient'
$trusted='time.cloudflare.com,0x8 time.google.com,0x8'
$w32tm=Join-Path ([Environment]::SystemDirectory) 'w32tm.exe'
$previousReceipt=Join-Path $root 'logs\diagnostics\atlas-windows-time-phase-stability-20261108.json'
$audit=Join-Path $root 'logs\diagnostics\atlas-windows-time-high-accuracy-20261108.json'

function Assert-AtlasHighAccuracyPrerequisites {
    $machine=Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
    if($machine.PartOfDomain -ne $false -or $machine.DomainRole -ne 0){
        throw 'ATLAS_TIME_HA_STANDALONE_HOST_REQUIRED'
    }
    if(Test-Path -LiteralPath $policy){
        $gp=Get-ItemProperty -LiteralPath $policy -ErrorAction Stop
        if($null -ne $gp.PhaseCorrectRate -or $null -ne $gp.UpdateInterval -or
           $null -ne $gp.FrequencyCorrectRate){
            throw 'ATLAS_TIME_HA_GROUP_POLICY_OVERRIDE_REFUSED'
        }
    }
    if(Test-Path -LiteralPath $ntpPolicy){
        $gpNtp=Get-ItemProperty -LiteralPath $ntpPolicy -ErrorAction Stop
        if($null -ne $gpNtp.NtpServer -or $null -ne $gpNtp.Type){
            throw 'ATLAS_TIME_HA_NTP_POLICY_OVERRIDE_REFUSED'
        }
    }
    $ntp=Get-ItemProperty -LiteralPath $ntpPath -ErrorAction Stop
    $cfg=Get-ItemProperty -LiteralPath $cfgPath -ErrorAction Stop
    $service=Get-Service W32Time -ErrorAction Stop
    if($ntp.Type -cne 'NTP' -or $ntp.NtpServer -cne $trusted -or
       $service.Status -ne 'Running' -or $cfg.PhaseCorrectRate -ne 7 -or
       $cfg.MinPollInterval -ne 6 -or $cfg.MaxPollInterval -ne 6 -or
       $cfg.MaxAllowedPhaseOffset -ne 1 -or
       $cfg.MaxPosPhaseCorrection -ne 54000 -or $cfg.MaxNegPhaseCorrection -ne 54000){
        throw 'ATLAS_TIME_HA_PREVIOUS_TRUSTED_CONFIGURATION_CHANGED'
    }
    $old=[int]$cfg.UpdateInterval
    $freq=[int]$cfg.FrequencyCorrectRate
    if(-not (($old -eq 360000 -and $freq -eq 4) -or ($old -eq 100 -and $freq -eq 2))){
        throw 'ATLAS_TIME_HA_UNREVIEWED_UPDATE_FREQUENCY_PAIR_REFUSED'
    }
    if(-not(Test-Path -LiteralPath $previousReceipt -PathType Leaf)){
        throw 'ATLAS_TIME_HA_PRIOR_PHASE_FIX_EVIDENCE_MISSING'
    }
    $sha=(Get-FileHash -LiteralPath $previousReceipt -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    if($sha -cne '1c67ef71c2f64ef3db0386fd30335fed84c60272023be49fb649cc2da49425df'){
        throw 'ATLAS_TIME_HA_PRIOR_PHASE_FIX_EVIDENCE_CHANGED'
    }
    return @{UpdateInterval=$old;FrequencyCorrectRate=$freq}
}

$state=Assert-AtlasHighAccuracyPrerequisites
if(-not $ExecuteApproved){
    Write-Output ('ATLAS_TIME_HA_READONLY_UPDATE_INTERVAL='+$state.UpdateInterval)
    Write-Output ('ATLAS_TIME_HA_READONLY_FREQUENCY_CORRECT_RATE='+$state.FrequencyCorrectRate)
    Write-Output 'ATLAS_TIME_HA_DOCUMENTED_PROFILE_UPDATE=100_FREQUENCY=2'
    Write-Output 'ATLAS_TIME_HA_NO_OS_MODIFICATION_EXPLICIT_ELEVATED_APPROVAL_REQUIRED'
    exit 0
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$admin=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
    throw 'ATLAS_TIME_HA_ELEVATED_ADMIN_REQUIRED'
}
if($state.UpdateInterval -eq 100){
    Write-Output 'ATLAS_TIME_HA_PROFILE_ALREADY_PRESENT_NO_MUTATION'
    Write-Output 'NOT_A_NATIVE_CLOCK_LEASE_OR_PAPER_START_AUTHORIZATION'
    exit 0
}
if(Test-Path -LiteralPath $audit){
    throw 'ATLAS_TIME_HA_EXISTING_AUDIT_REFUSES_REPEATED_MODIFICATION'
}
$sig=Get-AuthenticodeSignature -LiteralPath $w32tm
if($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)'){
    throw 'ATLAS_TIME_HA_WINDOWS_TOOL_SIGNATURE_REFUSED'
}
$changed=$false
try{
    Set-ItemProperty -LiteralPath $cfgPath -Name UpdateInterval -Value 100 -ErrorAction Stop
    $changed=$true
    Set-ItemProperty -LiteralPath $cfgPath -Name FrequencyCorrectRate -Value 2 -ErrorAction Stop
    $null=& $w32tm /config /update
    if($LASTEXITCODE -ne 0){throw 'ATLAS_TIME_HA_CONFIG_APPLY_REFUSED'}
    $after=Assert-AtlasHighAccuracyPrerequisites
    if($after.UpdateInterval -ne 100 -or $after.FrequencyCorrectRate -ne 2){
        throw 'ATLAS_TIME_HA_NATIVE_REGISTRY_READBACK_REFUSED'
    }
    $effective=(& $w32tm /query /configuration 2>&1 | Out-String)
    if($LASTEXITCODE -ne 0 -or
       $effective -notmatch '(?m)^UpdateInterval:\s*100\s*\(' -or
       $effective -notmatch '(?m)^FrequencyCorrectRate:\s*2\s*\(' -or
       $effective -notmatch '(?m)^PhaseCorrectRate:\s*7\s*\('){
        throw 'ATLAS_TIME_HA_EFFECTIVE_W32TIME_CONFIG_REFUSED'
    }
    $receipt=[ordered]@{
        schema='ATLAS_WINDOWS_TIME_HIGH_ACCURACY_STANDALONE_PROFILE_V1'
        utc=[DateTime]::UtcNow.ToString('o')
        trusted_peers=$trusted
        phase_correct_rate=7
        previous_update_interval=$state.UpdateInterval
        verified_update_interval=100
        previous_frequency_correct_rate=$state.FrequencyCorrectRate
        verified_frequency_correct_rate=2
        previous_phase_receipt_sha256='1c67ef71c2f64ef3db0386fd30335fed84c60272023be49fb649cc2da49425df'
        atlas_180_second_clock_lease_passed=$false
        atlas_code_install_performed=$false
        financial_authority=$false
        atlas_autostart=$false
    }
    $bytes=(New-Object System.Text.UTF8Encoding($false)).GetBytes(($receipt | ConvertTo-Json -Compress)+"`n")
    $stream=[System.IO.File]::Open($audit,[System.IO.FileMode]::CreateNew,
                                  [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
    try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}
    finally{$stream.Dispose()}
    Write-Output 'ATLAS_TIME_HA_MICROSOFT_PROFILE_APPLIED_VERIFIED_UPDATE100_FREQUENCY2_PHASE7'
    Write-Output ('ATLAS_TIME_HA_AUDIT_RECEIPT='+$audit)
    Write-Output 'REAL_CONTINUOUS_180_SECOND_QUALIFICATION_STILL_REQUIRED'
}
catch{
    $original=$_
    if($changed){
        try{
            Set-ItemProperty -LiteralPath $cfgPath -Name UpdateInterval -Value $state.UpdateInterval -ErrorAction Stop
            Set-ItemProperty -LiteralPath $cfgPath -Name FrequencyCorrectRate -Value $state.FrequencyCorrectRate -ErrorAction Stop
            $null=& $w32tm /config /update
            $rollback=Get-ItemProperty -LiteralPath $cfgPath -ErrorAction Stop
            if($LASTEXITCODE -ne 0 -or $rollback.UpdateInterval -ne $state.UpdateInterval -or
               $rollback.FrequencyCorrectRate -ne $state.FrequencyCorrectRate){
                throw 'ATLAS_TIME_HA_ROLLBACK_REFUSED'
            }
            Write-Warning 'ATLAS_TIME_HA_APPLY_FAILED_PREVIOUS_CONFIG_RESTORED'
        }
        catch{Write-Warning 'ATLAS_TIME_HA_ROLLBACK_UNVERIFIED_ADMIN_ATTENTION_REQUIRED'}
    }
    throw $original
}
