param([Parameter(Mandatory=$true)][string]$DisposableRoot)
$ErrorActionPreference='Stop'
$repo='D:\Work\Project Atlas'
$expectedParent=Join-Path $repo 'logs\diagnostics'
$root=[IO.Path]::GetFullPath($DisposableRoot)
if([IO.Path]::GetDirectoryName($root) -ine $expectedParent -or [IO.Path]::GetFileName($root) -cnotmatch '^qd-v5-outer-owner-probe-[a-zA-Z0-9-]+$' -or (Test-Path -LiteralPath $root)){
    throw 'FRESH_CONFINED_DISPOSABLE_ROOT_REQUIRED'
}
[void][IO.Directory]::CreateDirectory($root);[void][IO.Directory]::CreateDirectory((Join-Path $root 'temp'))
$env:TEMP=Join-Path $root 'temp';$env:TMP=$env:TEMP;$env:PSModuleAnalysisCachePath=Join-Path $root 'module.cache'
$env:PYTHONDONTWRITEBYTECODE='1'
$source=Get-Content -LiteralPath (Join-Path $repo 'scripts\acceptance_harness_v5\supervise.ps1') -Raw
$begin=$source.IndexOf('$assembly=');$end=$source.IndexOf('function Account-Scope')
if($begin -lt 0 -or $end -le $begin){throw 'EXACT_NATIVE_OWNER_DECLARATIONS_MISSING'}
# Dot-source ONLY the definition block, not the operational entry/body.
. ([scriptblock]::Create($source.Substring($begin,$end-$begin)))
$tokens=$null;$parseErrors=$null
$tree=[Management.Automation.Language.Parser]::ParseInput($source,[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw 'OWNER_SOURCE_PARSE_REFUSED'}
$create=$tree.FindAll({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Create-Json'},$true)
if($create.Count -ne 1){throw 'EXACT_ATOMIC_JSON_FUNCTION_REQUIRED'}
. ([scriptblock]::Create($create[0].Extent.Text))
$pins=Get-Content -LiteralPath (Join-Path $repo 'logs\diagnostics\qd-final-installed-v5-preparation-20261103\native-image-pins.json') -Raw|ConvertFrom-Json
$scope=@{ownership=@{images=@{observer=$pins.images.observer;powershell=$pins.images.powershell;console=$pins.images.console;installed_python=$pins.images.installed_python};diagnostic_images=@{netstat=$pins.images.netstat}}}
Create-Json 'fixture-scope.json' $scope
$watch=[Diagnostics.Stopwatch]::StartNew();$parent=[Diagnostics.Process]::GetCurrentProcess()
$job=$hp=$ht=[IntPtr]::Zero;$assigned=$false;$forced=$false;$result=[ordered]@{accepted=$false;domain='DISPOSABLE_NATIVE_OWNERSHIP_ONLY';installed_launches=0;selection_mutations=0;financial_actions=0}
try{
    $nonce=[guid]::NewGuid().ToString('N');$hash='0'*64;$head='0'*40
    Create-Json 'single-use-claim.json' @{nonce=$nonce;scope_sha256=$hash;approved_checkpoint=$head;deadline_ns=[long](([Diagnostics.Stopwatch]::GetTimestamp()/[double][Diagnostics.Stopwatch]::Frequency+60)*1e9)}
    $job=$native::CreateJobObjectW([IntPtr]::Zero,$null);if($job -eq [IntPtr]::Zero){throw 'FIXTURE_JOB_REQUIRED'}
    $limits=New-ZeroBuffer 144
    try{[Runtime.InteropServices.Marshal]::WriteInt32($limits,16,0x2000);Require-Native ($native::SetInformationJobObject($job,9,$limits,144))}
    finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($limits)}
    $python=$pins.images.observer.path
    $command='"'+$python+'" -I -B "'+(Join-Path $repo 'tests\v5_outer_owner_probe.py')+'" --disposable-native-owner-probe "'+$root+'"'
    $launch=New-OwnedSuspended $python $command;$workerId=$launch.pid
    $result.actual_suspended_creation_and_job_assignment_function=$true
    Create-Json 'outer-launch.json' @{nonce=$nonce;scope_sha256=$hash;checkpoint=$head;role='acceptance_worker';pid=$workerId;created=(Creation $hp);command=$command;
        parent_pid=$PID;parent_created=(Creation $parent.Handle);parent_command=[Environment]::CommandLine;
        parent_handle=(Duplicate-ToWorker $parent.Handle 0x101000);launch_handle=(Duplicate-ToWorker $hp 0x101000)}
    if($native::ResumeThread($ht) -eq [uint32]::MaxValue){throw 'PROBE_RESUME_REFUSED'}
    Require-Native ($native::CloseHandle($ht));$ht=[IntPtr]::Zero
    $sequence=1
    while($native::WaitForSingleObject($hp,0) -eq 258){
        if($watch.Elapsed.TotalSeconds -gt 45){throw 'DISPOSABLE_45_SECOND_CLEANUP_RESERVE'}
        $name=('job-{0:D6}' -f $sequence);$request=Join-Path $root ($name+'.request.json')
        if(Test-Path -LiteralPath $request){
            $q=Get-Content -LiteralPath $request -Raw|ConvertFrom-Json
            if($q.seq -ne $sequence -or $q.nonce -cne $nonce -or $q.scope_sha256 -cne $hash){throw 'PROBE_SESSION_MISMATCH'}
            Create-Json ($name+'.response.json') @{seq=$sequence;nonce=$nonce;scope_sha256=$hash;pids=(Job-Pids);collected_ns=[long]([Diagnostics.Stopwatch]::GetTimestamp()/[double][Diagnostics.Stopwatch]::Frequency*1e9)}
            $sequence++
        }
        Start-Sleep -Milliseconds 10
    }
    $p=New-ZeroBuffer 4
    try{Require-Native ($native::GetExitCodeProcess($hp,$p));$result.worker_exit=[Runtime.InteropServices.Marshal]::ReadInt32($p)}finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($p)}
    $result.final_job_active=Active-JobCount
    $result.replies=$sequence-1
    $child=Get-Content -LiteralPath (Join-Path $root 'probe-result.json') -Raw|ConvertFrom-Json
    if($result.worker_exit -ne 0 -or $result.final_job_active -ne 0 -or -not $child.accepted -or -not $child.duplicate_handles_and_images_closed){throw 'DISPOSABLE_OWNERSHIP_PROOF_FAILED'}
    $result.accepted=$true;$result.child=$child
}catch{$result.error=$_.Exception.Message}
finally{
    if($hp -ne [IntPtr]::Zero -and -not $assigned -and $native::WaitForSingleObject($hp,0) -eq 258){$forced=$true;Require-Native ($native::TerminateProcess($hp,78));[void]$native::WaitForSingleObject($hp,5000)}
    if($job -ne [IntPtr]::Zero -and (Active-JobCount) -gt 0){$forced=$true;Require-Native ($native::TerminateJobObject($job,78));if($hp -ne [IntPtr]::Zero){[void]$native::WaitForSingleObject($hp,5000)}}
    foreach($h in @($ht,$hp,$job)){if($h -ne [IntPtr]::Zero){Require-Native ($native::CloseHandle($h))}}
    $parent.Dispose();$result.handles_closed=$true;$result.forced_cleanup=$forced;$result.seconds=$watch.Elapsed.TotalSeconds
    $files=@(Get-ChildItem -LiteralPath $root -Force -Recurse);$result.entries=$files.Count+1;$result.bytes=($files|Where-Object {-not $_.PSIsContainer}|Measure-Object Length -Sum).Sum
    if($result.seconds -gt 60 -or $result.entries -gt 512 -or $result.bytes -gt 8MB -or $forced){$result.accepted=$false}
    Create-Json 'native-owner-result.json' $result
    $result|ConvertTo-Json -Depth 10
}
if(-not $result.accepted){exit 2}
