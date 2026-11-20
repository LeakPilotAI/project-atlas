# Revert the documented high-accuracy Windows Time trial after actual >500ppm
# measured native slew. Restore the previous, verified standalone host values.
# Only UpdateInterval 100->360000 and FrequencyCorrectRate 2->4 change.
# Preserve PhaseCorrectRate=7, trusted peers, poll settings, all Atlas gates.
#Requires -Version 5.1
param([switch]$ExecuteApproved)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$cfgPath='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config'
$ntpPath='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'
$trusted='time.cloudflare.com,0x8 time.google.com,0x8'
$audit=Join-Path $root 'logs\diagnostics\atlas-windows-time-high-accuracy-20261108.json'
$reversion=Join-Path $root 'logs\diagnostics\atlas-windows-time-high-accuracy-rollback-20261108.json'
$w32tm=Join-Path ([Environment]::SystemDirectory) 'w32tm.exe'
if(-not(Test-Path $audit -PathType Leaf) -or
   (Get-FileHash -LiteralPath $audit -Algorithm SHA256).Hash.ToLowerInvariant() -cne
        '38541f39cbcdd3d826402160cf5a2a534dbcb9ee2ca797ecd62941b897ed9caf'){
    throw 'ATLAS_TIME_HA_ROLLBACK_SOURCE_RECEIPT_MISMATCH'
}
$machine=Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
$cfg=Get-ItemProperty $cfgPath -ErrorAction Stop
$ntp=Get-ItemProperty $ntpPath -ErrorAction Stop
if($machine.PartOfDomain -ne $false -or $machine.DomainRole -ne 0 -or
   $ntp.Type -cne 'NTP' -or $ntp.NtpServer -cne $trusted -or
   $cfg.PhaseCorrectRate -ne 7 -or $cfg.MinPollInterval -ne 6 -or
   $cfg.MaxPollInterval -ne 6 -or $cfg.MaxAllowedPhaseOffset -ne 1 -or
   $cfg.UpdateInterval -ne 100 -or $cfg.FrequencyCorrectRate -ne 2 -or
   (Get-Service W32Time).Status -ne 'Running'){
    throw 'ATLAS_TIME_HA_ROLLBACK_UNREVIEWED_CURRENT_STATE'
}
if(-not $ExecuteApproved){
    Write-Output 'ATLAS_TIME_HA_ROLLBACK_READ_ONLY_VERIFIED_APPLIED_PROFILE'
    Write-Output 'ATLAS_TIME_HA_ROLLBACK_REQUIRES_REAL_ELEVATED_ADMIN_APPROVAL'
    exit 0
}
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
    throw 'ATLAS_TIME_HA_ROLLBACK_ELEVATED_ADMIN_REQUIRED'
}
if(Test-Path -LiteralPath $reversion){
    throw 'ATLAS_TIME_HA_ROLLBACK_EXISTING_RECEIPT_NO_RETRY'
}
$sig=Get-AuthenticodeSignature $w32tm
if($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)'){
    throw 'ATLAS_TIME_HA_ROLLBACK_WINDOWS_SIGNATURE_REFUSED'
}
Set-ItemProperty -LiteralPath $cfgPath -Name UpdateInterval -Value 360000 -ErrorAction Stop
Set-ItemProperty -LiteralPath $cfgPath -Name FrequencyCorrectRate -Value 4 -ErrorAction Stop
$null=& $w32tm /config /update
if($LASTEXITCODE -ne 0){throw 'ATLAS_TIME_HA_ROLLBACK_APPLY_REFUSED'}
$after=Get-ItemProperty $cfgPath
$source=Get-ItemProperty $ntpPath
if($after.UpdateInterval -ne 360000 -or $after.FrequencyCorrectRate -ne 4 -or
   $after.PhaseCorrectRate -ne 7 -or $after.MinPollInterval -ne 6 -or
   $after.MaxPollInterval -ne 6 -or $source.NtpServer -cne $trusted){
    throw 'ATLAS_TIME_HA_ROLLBACK_REGISTRY_READBACK_REFUSED'
}
$effective=(& $w32tm /query /configuration 2>&1 | Out-String)
if($LASTEXITCODE -ne 0 -or
   $effective -notmatch '(?m)^UpdateInterval:\s*360000\s*\(' -or
   $effective -notmatch '(?m)^FrequencyCorrectRate:\s*4\s*\(' -or
   $effective -notmatch '(?m)^PhaseCorrectRate:\s*7\s*\('){
    throw 'ATLAS_TIME_HA_ROLLBACK_EFFECTIVE_CONFIG_REFUSED'
}
$proof=[ordered]@{
    schema='ATLAS_WINDOWS_TIME_HA_PROFILE_REVERTED_AFTER_EXCESS_SLEW_V1'
    utc=[DateTime]::UtcNow.ToString('o')
    rejected_trial_slew_ppm=-3501.78
    restored_update_interval=360000
    restored_frequency_correct_rate=4
    preserved_phase_correct_rate=7
    preserved_ntp_peers=$trusted
    source_audit_sha256='38541f39cbcdd3d826402160cf5a2a534dbcb9ee2ca797ecd62941b897ed9caf'
    windows_time_verified=$true
    atlas_native_180_second_lease_passed=$false
    paper_trading_authorized=$false
    atlas_release_installed=$false
}
$bytes=(New-Object System.Text.UTF8Encoding($false)).GetBytes(($proof | ConvertTo-Json -Compress)+"`n")
$stream=[IO.File]::Open($reversion,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}
finally{$stream.Dispose()}
Write-Output 'ATLAS_TIME_HA_EXCESS_SLEW_TRIAL_REVERTED_TO_REVIEWED_HOST_DEFAULTS'
Write-Output ('ATLAS_TIME_HA_ROLLBACK_RECEIPT='+$reversion)
Write-Output 'NO_ATLAS_NATIVE_CLOCK_QUALIFICATION_OR_FINANCIAL_START'
