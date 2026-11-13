# Atlas execution-end cleanup: ONLY orphaned Atlas-specific test Chrome
# profiles in THIS Windows user's C: Temp. Does not touch other applications,
# shared caches, Atlas financial roots, installed releases, or active workers.
# Default read-only; -ExecuteVerified requests the narrowly bounded cleanup.
#Requires -Version 5.1
[CmdletBinding()]
param([switch]$ExecuteVerified)
$ErrorActionPreference = 'Stop'
$base = [IO.Path]::GetFullPath([IO.Path]::Combine(
    [Environment]::GetFolderPath('LocalApplicationData'), 'Temp'))
if ([IO.Path]::GetPathRoot($env:USERPROFILE)[0] -ne 'C' -or
    [IO.Path]::GetPathRoot($base)[0] -ne 'C') {
    throw 'ATLAS_TEMP_CLEANUP_USER_PROFILE_NOT_ON_EXPECTED_C_DRIVE'
}
if (-not $base.StartsWith([IO.Path]::GetFullPath($env:USERPROFILE),
    [StringComparison]::OrdinalIgnoreCase)) {
    throw 'ATLAS_TEMP_CLEANUP_UNEXPECTED_WINDOWS_TEMP'
}
$root = Get-Item -LiteralPath $base -ErrorAction Stop
if (-not $root.PSIsContainer -or
    ($root.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'ATLAS_TEMP_CLEANUP_ROOT_REPARSE_REFUSED'
}
$active = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
    $_.CommandLine -match 'atlas-disposable-chrome-[a-z0-9_]{8}'
})
if ($active.Count -gt 0) {
    Write-Output 'ATLAS_POST_EXEC_TEMP_CLEANUP_REFUSED_ACTIVE_PROFILES'
    return
}
$targets = @(Get-ChildItem -LiteralPath $base -Directory -Force -ErrorAction Stop |
    Where-Object { $_.Name -cmatch '^atlas-disposable-chrome-[a-z0-9_]{8}$' })
if ($targets.Count -gt 75) { throw 'ATLAS_TEMP_CLEANUP_TARGET_COUNT_BOUND_EXCEEDED' }
$count=0
$bytes=[long]0
$ready=@()
foreach($target in $targets) {
    if ($target.FullName -ne (Join-Path $base $target.Name) -or
        ($target.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        ((Get-Date) - $target.LastWriteTime).TotalMinutes -lt 5) {
        continue
    }
    $stack=New-Object 'System.Collections.Generic.Stack[string]'
    $stack.Push($target.FullName)
    $ok=$true
    while($stack.Count -gt 0) {
        $next=$stack.Pop()
        foreach($entry in @(Get-ChildItem -LiteralPath $next -Force -ErrorAction Stop)) {
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                $ok=$false;break
            }
            $count+=1
            if ($count -gt 25000) { throw 'ATLAS_TEMP_CLEANUP_DESCENDANT_COUNT_REFUSED' }
            if ($entry.PSIsContainer) {
                $stack.Push($entry.FullName)
            } else {
                $bytes += $entry.Length
            }
        }
        if (-not $ok) {break}
    }
    if($ok) { $ready += $target }
}
if ($bytes -gt 536870912) { throw 'ATLAS_TEMP_CLEANUP_TOTAL_BYTE_BOUND_REFUSED' }
if ($ExecuteVerified) {
    foreach($target in $ready) {
        Remove-Item -LiteralPath $target.FullName -Recurse -Force -ErrorAction Stop
    }
}
Write-Output ('ATLAS_POST_EXEC_TEMP_ELIGIBLE_PROFILES='+$ready.Count)
Write-Output ('ATLAS_POST_EXEC_TEMP_ELIGIBLE_BYTES='+$bytes)
Write-Output ('ATLAS_POST_EXEC_TEMP_EXECUTED='+[bool]$ExecuteVerified)
Write-Output 'ATLAS_NATIVE_RELEASES_AND_FINANCIAL_ACCOUNTS_UNTOUCHED=True'
Write-Output 'ATLAS_SHARED_C_CACHES_AND_WINDOWS_OS_FILES_UNTOUCHED=True'
