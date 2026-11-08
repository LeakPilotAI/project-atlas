# Export the completed Windows Time private trace after debug logging is
# disabled. No Windows Time configuration change, logging or other service action.
#Requires -Version 5.1
param([switch]$ExecuteApproved)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$receipt=Join-Path $root 'logs\diagnostics\atlas-w32time-native-debug-capture-20261108.json'
$dest=Join-Path $root 'logs\diagnostics\atlas-w32time-native-debug-private-20261108.log'
$expected='C:\Windows\Temp\AtlasW32TimeSample20261108.log'
if(-not $ExecuteApproved){
    Write-Output 'ATLAS_W32TIME_PRIVATE_TRACE_EXPORT_REQUIRES_ADMIN_APPROVAL'
    exit 0
}
$p=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
    throw 'ATLAS_W32TIME_PRIVATE_TRACE_EXPORT_ELEVATED_ADMIN_REQUIRED'
}
if(-not(Test-Path -LiteralPath $receipt -PathType Leaf)){
    throw 'ATLAS_W32TIME_PRIVATE_TRACE_FINAL_AUDIT_NOT_PRESENT'
}
$evidence=Get-Content -LiteralPath $receipt -Raw -ErrorAction Stop | ConvertFrom-Json
if($evidence.schema -cne 'ATLAS_WINDOWS_TIME_BOUNDED_PRIVATE_DEBUG_CAPTURE_V1' -or
   $evidence.windows_debug_disabled -ne $true -or $evidence.log -cne $expected -or
   $evidence.log_bytes -le 0 -or $evidence.log_bytes -gt 2097152 -or
   $evidence.time_config_changes -ne 0){
    throw 'ATLAS_W32TIME_PRIVATE_TRACE_AUDIT_INVALID'
}
if(Test-Path -LiteralPath $dest){throw 'ATLAS_W32TIME_TRACE_DEST_ALREADY_PRESENT_NO_REPLACE'}
$raw=[IO.File]::ReadAllBytes($expected)
if($raw.Length -ne $evidence.log_bytes){
    throw 'ATLAS_W32TIME_PRIVATE_TRACE_FILE_CHANGED'
}
$sha=[BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($raw)).Replace('-','').ToLowerInvariant()
if($sha -cne $evidence.log_sha256){
    throw 'ATLAS_W32TIME_PRIVATE_TRACE_SHA_CHANGED'
}
$f=[IO.File]::Open($dest,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try{$f.Write($raw,0,$raw.Length);$f.Flush($true)}
finally{$f.Dispose()}
Write-Output 'ATLAS_W32TIME_DEBUG_TRACE_EXPORTED_TO_PRIVATE_LOCAL_DIAGNOSTICS'
Write-Output ('ATLAS_W32TIME_DEBUG_EXPORTED_SHA256='+$sha)
Write-Output 'NO_WINDOWS_CLOCK_CHANGES_NO_FINANCIAL_START'
