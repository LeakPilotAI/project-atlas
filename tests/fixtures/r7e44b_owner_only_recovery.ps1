# Test-only recovery primitives. Variables and lock checks are injected by temporary fixtures.
# No entrypoint, process inspection, lifecycle action, or production path.
function Get-BytesHash([string]$Path) {
    $sha=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($Path)))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
function Assert-RecordSet([bool]$Recovered) {
    foreach($path in @($RuntimePath,$LockPath,$StopLockPath)) {
        if(Test-Path -LiteralPath $path) { throw "Unexpected lifecycle record: $path" }
    }
    if(-not (Test-Path -LiteralPath $StopPath -PathType Leaf) -or
       (Get-BytesHash $StopPath) -cne $ExpectedStopHash) { throw 'Stop record changed' }
    if($Recovered) {
        if(Test-Path -LiteralPath $OwnerPath) { throw 'Owner unexpectedly present after archive' }
    } else {
        if(-not (Test-Path -LiteralPath $OwnerPath -PathType Leaf) -or
           (Get-BytesHash $OwnerPath) -cne $ExpectedOwnerHash) { throw 'Owner record changed' }
        $owner=Read-JsonFile $OwnerPath
        if($owner.schema_version -ne 1 -or $owner.root -ine $Root -or
           $owner.run_id -cne $ExpectedRun -or $owner.state -cne 'stop_timeout' -or
           $owner.pid -ne 31552 -or $owner.launcher_pid -ne 24880) { throw 'Owner identity contradicts approval' }
    }
}
function Move-OnlyStaleOwner([string]$ArchivePath) {
    Assert-RecoveryLock
    Assert-RecordSet $false
    $full=[IO.Path]::GetFullPath($ArchivePath)
    $parent=[IO.Path]::GetFullPath((Join-Path $RuntimeDir 'stale-sessions'))+'\'
    if(-not $full.StartsWith($parent,[StringComparison]::OrdinalIgnoreCase) -or
       [IO.Path]::GetFileName($full) -cne 'atlas-background-owner.json') { throw 'Archive target outside approved tree' }
    if(Test-Path -LiteralPath $full) { throw 'Archive destination exists; no overwrite allowed' }
    [IO.File]::Move($OwnerPath,$full)
    if((Get-BytesHash $full) -cne $ExpectedOwnerHash) { throw 'Archived owner hash mismatch; retain lock' }
}