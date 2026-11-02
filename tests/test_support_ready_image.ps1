# Pure mocked readiness contracts. No child, filesystem fixture or native copy.
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$module=Import-Module (Join-Path $repo 'scripts\windows\Atlas-Installed-Nonfinancial.psm1') -PassThru -Force
$cases=@('late-image','foreign-image','missing-image','old-snapshot','wrong-claimed-image',
         'matching-foreign-images','missing-fresh-image-with-old-match','wrong-pid','wrong-created',
         'wrong-release','wrong-head','provider-enabled','provider-integer','trading-enabled','autostart-enabled','exited')
$passed=0
foreach($case in $cases) {
    & $module {
        param($Case)
        $python='D:\synthetic\installed\python\python.exe'
        $process=[pscustomobject]@{HasExited=$false;MainModule=[pscustomobject]@{FileName=$null};FreshImage=$python;Refreshes=0}
        $process | Add-Member ScriptMethod Refresh { $this.Refreshes++; $this.MainModule.FileName=$this.FreshImage }
        $owner=[pscustomobject]@{Process=$process;Pid=42;Created=[long]123456789012345;Image=$null}
        $binding=[pscustomobject]@{release=('a'*40);head=('b'*64)}
        $ready=[pscustomobject]@{schema='QD_INSTALLED_NONFINANCIAL_CONTROLLER_V1';
            controller=[pscustomobject]@{pid=42;created=[long]123456789012345;image=$python};
            dashboard=[pscustomobject]@{release=('a'*40);head=('b'*64);url='http://127.0.0.1:12345/';
                mode='DISPOSABLE_NONFINANCIAL_ONLY';providers=$false;financial_writers=$false;trading=$false;automatic_startup=$false}}
        switch($Case) {
            'foreign-image' {$process.FreshImage='D:\synthetic\foreign.exe'}
            'missing-image' {$process.FreshImage=$null}
            'old-snapshot' {$owner.Image='D:\synthetic\old.exe'}
            'wrong-claimed-image' {$ready.controller.image='D:\synthetic\foreign.exe'}
            'matching-foreign-images' {$process.FreshImage='D:\synthetic\foreign.exe';$ready.controller.image=$process.FreshImage}
            'missing-fresh-image-with-old-match' {$owner.Image=$python;$process.FreshImage=$null}
            'wrong-pid' {$ready.controller.pid=43}
            'wrong-created' {$ready.controller.created++}
            'wrong-release' {$ready.dashboard.release='c'*40}
            'wrong-head' {$ready.dashboard.head='c'*64}
            'provider-enabled' {$ready.dashboard.providers=$true}
            'provider-integer' {$ready.dashboard.providers=0}
            'trading-enabled' {$ready.dashboard.trading=$true}
            'autostart-enabled' {$ready.dashboard.automatic_startup=$true}
            'exited' {$process.HasExited=$true}
        }
        $refused=$false
        try { Assert-AtlasInstalledReadyIdentity -Owner $owner -Ready $ready -Binding $binding -Python $python -Disposable $true }
        catch {
            if($_.Exception.Message -notlike 'OWNED_INSTALLED_DESKTOP_READINESS_REFUSED:*') { throw }
            $refused=$true
        }
        $shouldPass=$Case -in @('late-image','old-snapshot')
        if($refused -eq $shouldPass -or $process.Refreshes -ne 1) { throw ('READINESS_CASE_FAILED:'+ $Case) }
        if($shouldPass -and $owner.Image -cne $python) { throw 'FRESH_NATIVE_IMAGE_WAS_NOT_BOUND' }
    } $case
    $passed++
}
foreach($mode in @('default','fixture_domain','workspace')) {
    $binding=[pscustomobject]@{schema='QD_NONFINANCIAL_DESKTOP_BINDING_V1';domain='WINDOWS_LOCAL';
        release=('a'*40);head=('b'*64);support_sha256=('c'*64);native_root=@(1,2,3);seconds=30;requests=12}
    if($mode -eq 'fixture_domain') { $binding.domain='DISPOSABLE' }
    $expected=switch($mode) {
        'default' {'EXPLICIT_NONFINANCIAL_DESKTOP_AUTHORIZATION_REQUIRED'}
        'fixture_domain' {'EXACT_NONFINANCIAL_DESKTOP_BINDING_REQUIRED'}
        'workspace' {'INSTALLED_DESKTOP_ADAPTER_REQUIRED_NO_WORKSPACE_FALLBACK'}
    }
    $refused=$false
    try {
        if($mode -eq 'default') { Open-AtlasInstalledNonfinancialDashboard -Binding $binding }
        else { Open-AtlasInstalledNonfinancialDashboard -Binding $binding -Approved }
    } catch {
        if($_.Exception.Message -cne $expected) { throw }
        $refused=$true
    }
    if(-not $refused) { throw 'UNEXPECTED_SOURCE_RUNTIME_START' }
    $closed=Close-AtlasInstalledNonfinancialDashboard
    if(-not $closed.closed -or $closed.status -cne 'NO_OWNED_NONFINANCIAL_RUNTIME') { throw 'UNEXPECTED_RUNTIME_OWNER' }
    $passed++
}
Write-Output ('OFFLINE_READY_IMAGE_CONTRACTS '+$passed+' passed, 0 failed; NO_CHILDREN_OR_NATIVE_COPY')
