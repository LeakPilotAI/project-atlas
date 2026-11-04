param([Parameter(Mandatory=$true)][string]$DisposableRoot,[switch]$IdentityProbeOnly,[switch]$HttpDiagnosticOnly)
if($IdentityProbeOnly -and $HttpDiagnosticOnly){throw 'ONE_DISPOSABLE_DIAGNOSTIC_MODE_ONLY'}
$ErrorActionPreference='Stop';$repo='D:\Work\Project Atlas';$root=[IO.Path]::GetFullPath($DisposableRoot)
if([IO.Path]::GetDirectoryName($root) -ine (Join-Path $repo 'logs\diagnostics') -or [IO.Path]::GetFileName($root) -cnotmatch '^qd-v6-integrated-rehearsal-[a-zA-Z0-9-]+$' -or (Test-Path -LiteralPath $root)){throw 'FRESH_DISPOSABLE_REHEARSAL_ROOT_REQUIRED'}
[void][IO.Directory]::CreateDirectory($root);[void][IO.Directory]::CreateDirectory((Join-Path $root 'temp'))
$env:PYTHONDONTWRITEBYTECODE='1';$env:TEMP=Join-Path $root 'temp';$env:TMP=$env:TEMP;$env:PSModuleAnalysisCachePath=Join-Path $root 'module.cache'
$source=Get-Content -LiteralPath (Join-Path $repo 'scripts\acceptance_harness_v6\supervise.ps1') -Raw
$start=$source.IndexOf('$assembly=');$end=$source.IndexOf('function Account-Scope')
. ([scriptblock]::Create($source.Substring($start,$end-$start)))
$tree=[Management.Automation.Language.Parser]::ParseInput($source,[ref]$null,[ref]$null)
$create=$tree.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq 'Create-Json'},$true)
. ([scriptblock]::Create($create[0].Extent.Text))
Copy-Item -LiteralPath (Join-Path $repo 'scripts\acceptance_harness_v6\WorkerLog.psm1') -Destination (Join-Path $root 'WorkerLog.psm1')
Import-Module (Join-Path $root 'WorkerLog.psm1') -Force
Copy-Item -LiteralPath (Join-Path $repo 'tests\v6_integrated_rehearsal_worker.py') -Destination (Join-Path $root 'worker.py')
Copy-Item -LiteralPath (Join-Path $repo 'tests\v6_rehearsal_gate.py') -Destination (Join-Path $root 'gate.py')
Copy-Item -LiteralPath (Join-Path $repo 'scripts\acceptance_harness_v5\resource_audit.ps1') -Destination (Join-Path $root 'resource_audit.ps1')
$pins=Get-Content -LiteralPath (Join-Path $repo 'logs\diagnostics\qd-final-installed-v5-preparation-20261103\native-image-pins.json') -Raw|ConvertFrom-Json
$helper=Join-Path $repo 'backend\.venv\Scripts\python.exe'
$f=[IO.File]::Open($helper,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
try{
    $buffer=New-ZeroBuffer 52;Require-Native ($native::GetFileInformationByHandle($f.SafeFileHandle.DangerousGetHandle(),$buffer))
    $bytes=[byte[]]::new(52);[Runtime.InteropServices.Marshal]::Copy($buffer,$bytes,0,52)
    $id=@([BitConverter]::ToUInt32($bytes,28),[BitConverter]::ToUInt32($bytes,44),[BitConverter]::ToUInt32($bytes,48))
    [Runtime.InteropServices.Marshal]::FreeHGlobal($buffer)
}finally{$f.Dispose()}
$helperPin=@{path=$helper;id=$id;sha256=(Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash.ToLowerInvariant()}
$fixtureScope=@{domain='DISPOSABLE_INTEGRATED_ONLY';identity_probe_only=[bool]$IdentityProbeOnly;http_diagnostic_only=[bool]$HttpDiagnosticOnly;ownership=@{images=@{observer=$pins.images.observer;powershell=$pins.images.powershell;installed_python=$helperPin;console=$pins.images.console};diagnostic_images=@{netstat=$pins.images.netstat};console_command='\??\C:\WINDOWS\system32\conhost.exe 0x4';direct_adapter_console_exit_code=0}}
$scope=$fixtureScope
Create-Json 'fixture-scope.json' $fixtureScope
$sourceRows=@()
foreach($path in @((Join-Path $repo 'scripts\acceptance_harness_v6\supervise.ps1'),(Join-Path $repo 'scripts\acceptance_harness_v6\worker_log.py'),(Join-Path $repo 'scripts\acceptance_harness_v5\ownership.py'),(Join-Path $repo 'tests\v6_job_attribution.py'),(Join-Path $root 'WorkerLog.psm1'),(Join-Path $root 'worker.py'),(Join-Path $root 'gate.py'),(Join-Path $root 'resource_audit.ps1'))){$item=Get-Item -LiteralPath $path;$sourceRows+=@{path=$path;bytes=$item.Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}}
Create-Json 'fixture-source-manifest.json' $sourceRows
$python=$pins.images.observer.path
$scopeHashCode="import json,hashlib;from pathlib import Path;p=json.loads(Path(r'"+(Join-Path $root 'fixture-scope.json')+"').read_bytes());print(hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest())"
$ApprovedScopeSha256= & $python -I -B -c $scopeHashCode
if($ApprovedScopeSha256 -cnotmatch '^[0-9a-f]{64}$'){throw 'FIXTURE_SCOPE_HASH_REFUSED'}
$ApprovedCheckpoint='826758c7d6e41141d9cadc8ed504b1630811ecbb'
# The ONLY adapter to the actual outer body is confined resource accounting.
# No read or write of D:\AtlasRuntime occurs during this rehearsal.
function Account-Scope {
    $files=@(Get-ChildItem -LiteralPath $root -Recurse -Force)
    if(@($files|Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw 'FIXTURE_REPARSE'}
    $logical=($files|Where-Object {-not $_.PSIsContainer}|Measure-Object Length -Sum).Sum
    return @{entries=$files.Count+1;logical_bytes=$logical;accounted_bytes=$logical+4096*($files.Count+1)}
}
$bodyStart=$source.IndexOf('$parent=[Diagnostics.Process]::GetCurrentProcess()')
if($bodyStart -lt 0){throw 'ACTUAL_V6_OUTER_BODY_MISSING'}
Create-Json 'actual-source-identity.json' @{domain='DISPOSABLE_INTEGRATED_ONLY';outer_source_sha256=(Get-FileHash -LiteralPath (Join-Path $repo 'scripts\acceptance_harness_v6\supervise.ps1')).Hash.ToLowerInvariant();body_start=$bodyStart;operational_entry_invoked=$false;accounting_adapter='CONFINED_FIXTURE_ONLY';worker_adapter='EXPLICIT_DISPOSABLE_CONTROLLER_AND_BROWSER';maximum_seconds=600;maximum_entries=8192;maximum_accounted_bytes=64MB}
$watch=[Diagnostics.Stopwatch]::StartNew()
. ([scriptblock]::Create($source.Substring($bodyStart)))
