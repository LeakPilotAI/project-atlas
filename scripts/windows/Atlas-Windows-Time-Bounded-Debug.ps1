# Short, private Windows Time diagnostic capture. Always disable logging.
# No clock/provider/peer configuration change, resync, stop/restart or Atlas startup.
#Requires -Version 5.1
param([switch]$ExecuteApproved)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$w32tm=Join-Path ([Environment]::SystemDirectory) 'w32tm.exe'
$log='C:\Windows\Temp\AtlasW32TimeSample20261108.log'
$receipt=Join-Path $root 'logs\diagnostics\atlas-w32time-native-debug-capture-20261108.json'
$trusted='time.cloudflare.com,0x8 time.google.com,0x8'
$cfgPath='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config'
$cfg=Get-ItemProperty -LiteralPath $cfgPath
$ntp=Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'
if($cfg.PhaseCorrectRate -ne 7 -or $cfg.UpdateInterval -ne 360000 -or
   $cfg.FrequencyCorrectRate -ne 4 -or $cfg.MinPollInterval -ne 6 -or
   $cfg.MaxPollInterval -ne 6 -or $ntp.Type -cne 'NTP' -or
   $ntp.NtpServer -cne $trusted -or (Get-Service W32Time).Status -ne 'Running'){
    throw 'ATLAS_NATIVE_TIME_DEBUG_HOST_UNREVIEWED'
}
if(-not [string]::IsNullOrWhiteSpace([string]$cfg.FileLogEntries) -or
   -not [string]::IsNullOrWhiteSpace([string]$cfg.FileLogName) -or
   ($null -ne $cfg.FileLogSize -and [int]$cfg.FileLogSize -ne 0)){
    throw 'ATLAS_NATIVE_TIME_DEBUG_PREEXISTING_LOGGING_REFUSED'
}
if(Test-Path -LiteralPath $log -PathType Leaf){throw 'ATLAS_TIME_DEBUG_LOG_COLLISION'}
if(Test-Path -LiteralPath $receipt -PathType Leaf){throw 'ATLAS_TIME_DEBUG_AUDIT_COLLISION'}
if(-not $ExecuteApproved){
    Write-Output 'ATLAS_WINDOWS_TIME_DEBUG_READONLY_APPROVED_SCOPE_132SECONDS_2MIB'
    Write-Output 'ATLAS_WINDOWS_TIME_DEBUG_NO_MODIFICATION_ELEVATED_PERMISSION_REQUIRED'
    exit 0
}
$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
    throw 'ATLAS_NATIVE_TIME_DEBUG_ELEVATED_ADMIN_REQUIRED'
}
$sig=Get-AuthenticodeSignature -LiteralPath $w32tm
if($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)'){
    throw 'ATLAS_NATIVE_TIME_DEBUG_WINDOWS_SIGNATURE_REFUSED'
}
$enabled=$false
$disabled=$false
try{
    # Cleanup must run even if the native command partially enables logging.
    $enabled=$true
    $null=& $w32tm /debug /enable ('/file:'+$log) /size:2097152 /entries:0-300
    if($LASTEXITCODE -ne 0){throw 'ATLAS_NATIVE_TIME_DEBUG_ENABLE_REFUSED'}
    Start-Sleep -Seconds 132
}
finally{
    if($enabled){
        $null=& $w32tm /debug /disable
        $disabled=($LASTEXITCODE -eq 0)
        if(-not $disabled){Write-Warning 'ATLAS_NATIVE_TIME_DEBUG_DISABLE_FAILED_HOST_ADMIN_REQUIRED'}
    }
}
if(-not $disabled){throw 'ATLAS_NATIVE_TIME_DEBUG_DISABLE_UNVERIFIED'}
if(-not(Test-Path -LiteralPath $log -PathType Leaf)){
    throw 'ATLAS_NATIVE_TIME_DEBUG_FILE_MISSING_AFTER_CAPTURE'
}
$info=Get-Item -LiteralPath $log
if($info.Length -le 0 -or $info.Length -gt 2097152){
    throw 'ATLAS_NATIVE_TIME_DEBUG_SIZE_UNEXPECTED'
}
$sha=(Get-FileHash -LiteralPath $log -Algorithm SHA256).Hash.ToLowerInvariant()
$event=[ordered]@{
    schema='ATLAS_WINDOWS_TIME_BOUNDED_PRIVATE_DEBUG_CAPTURE_V1'
    utc=[DateTime]::UtcNow.ToString('o')
    log=$log
    log_sha256=$sha
    log_bytes=[long]$info.Length
    period_seconds=132
    windows_debug_disabled=$true
    time_config_changes=0
    atlas_lease_qualified=$false
    atlas_installer_ran=$false
    financial_operations=0
}
$bytes=(New-Object System.Text.UTF8Encoding($false)).GetBytes(($event|ConvertTo-Json -Compress)+"`n")
$s=[IO.File]::Open($receipt,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try{$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}
finally{$s.Dispose()}
Write-Output 'ATLAS_WINDOWS_TIME_BOUNDED_DEBUG_COMPLETED_AND_DISABLED'
Write-Output ('ATLAS_WINDOWS_TIME_DEBUG_AUDIT='+$receipt)
Write-Output 'NO_NATIVE_CLOCK_QUALIFICATION_OR_FINANCIAL_AUTHORITY'
