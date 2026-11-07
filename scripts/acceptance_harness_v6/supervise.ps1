param([switch]$ExecuteOneApprovedInstalledAcceptance,[string]$ApprovedScopeSha256,[string]$ApprovedScopeRawSha256,[string]$ApprovedCheckpoint)
$ErrorActionPreference='Stop'
if(-not $ExecuteOneApprovedInstalledAcceptance -or $ApprovedScopeSha256 -cnotmatch '^[0-9a-f]{64}$' -or $ApprovedScopeRawSha256 -cnotmatch '^[0-9a-f]{64}$' -or $ApprovedCheckpoint -cnotmatch '^[0-9a-f]{40}$'){
    throw 'FRESH_EXPLICIT_V6_APPROVAL_REQUIRED_NO_NATIVE_ACTION'
}
$watch=[Diagnostics.Stopwatch]::StartNew()
$root=$PSScriptRoot
if([IntPtr]::Size -ne 8){throw 'V6_NATIVE_X64_REQUIRED'}
$commandArgs=[Environment]::GetCommandLineArgs()
if($commandArgs.Count -ne 12 -or $commandArgs[1] -cne '-NoProfile' -or $commandArgs[2] -cne '-NonInteractive' -or $commandArgs[3] -cne '-File' -or $commandArgs[4] -ine $PSCommandPath -or $commandArgs[5] -cne '-ExecuteOneApprovedInstalledAcceptance' -or $commandArgs[6] -cne '-ApprovedScopeSha256' -or $commandArgs[8] -cne '-ApprovedScopeRawSha256' -or $commandArgs[10] -cne '-ApprovedCheckpoint'){
    throw 'DEDICATED_EXACT_V6_POWERSHELL_INVOCATION_REQUIRED_NO_DOT_SOURCE'
}
if((Get-FileHash -LiteralPath (Join-Path $root 'proposal.json') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovedScopeRawSha256){throw 'V6_APPROVED_RAW_SCOPE_HASH_MISMATCH'}
$scope=Get-Content -LiteralPath (Join-Path $root 'proposal.json') -Raw|ConvertFrom-Json
if($scope.evidence_root -cne $root -or $scope.schema -cne 'QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V6'){throw 'EXACT_V6_EXECUTION_ROOT_REQUIRED'}
$python=$scope.ownership.images.observer.path
if((Get-FileHash -LiteralPath (Join-Path $root 'source-manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $scope.source_manifest_sha256){throw 'V6_SOURCE_MANIFEST_HASH_MISMATCH'}
$source=Get-Content -LiteralPath (Join-Path $root 'source-manifest.json') -Raw|ConvertFrom-Json
foreach($row in $source.files){
    $file=[IO.Path]::GetFullPath((Join-Path 'D:\Work\Project Atlas' $row.path))
    if(-not $file.StartsWith('D:\Work\Project Atlas\',[StringComparison]::OrdinalIgnoreCase)){throw 'V6_SOURCE_ESCAPE'}
    $item=Get-Item -LiteralPath $file -Force
    $p=$item
    while($null -ne $p){
        if($p.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'V6_SOURCE_REPARSE'}
        $p=if($p -is [IO.FileInfo]){$p.Directory}else{$p.Parent}
    }
    if($item.Length -ne $row.bytes -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $row.sha256){throw 'V6_SOURCE_PIN_DRIFT'}
}
$logModule=Join-Path $root 'WorkerLog.psm1'
if(@($source.files|Where-Object {[IO.Path]::GetFullPath((Join-Path 'D:\Work\Project Atlas' $_.path)) -ieq $logModule}).Count -ne 1){throw 'V6_EXACT_PINNED_LOG_MODULE_REQUIRED'}
Import-Module $logModule -Force
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=$null;$env:PYTHONHOME=$null
if(Test-Path -LiteralPath (Join-Path $root 'single-use-claim.json')){throw 'V6_GRANT_ALREADY_CONSUMED'}
[void][IO.Directory]::CreateDirectory((Join-Path $root 'temp'))
$env:TEMP=Join-Path $root 'temp';$env:TMP=$env:TEMP
$env:PSModuleAnalysisCachePath=Join-Path $root 'ps-module-analysis.cache'
$env:PSModulePath='C:\Windows\System32\WindowsPowerShell\v1.0\Modules'
# Reflection.Emit creates P/Invoke declarations in memory. No C# compiler,
# temporary DLL, external process or installation is needed.
$assembly=[AppDomain]::CurrentDomain.DefineDynamicAssembly([Reflection.AssemblyName]::new('AtlasV6ReadOwner'),[Reflection.Emit.AssemblyBuilderAccess]::Run)
$module=$assembly.DefineDynamicModule('Native')
$builder=$module.DefineType('AtlasV6OwnerKernel','Public,Abstract,Sealed')
function Import-Native([string]$Name,[Type]$Return,[Type[]]$Parameters){
    $method=$builder.DefinePInvokeMethod($Name,'kernel32.dll',[Reflection.MethodAttributes]'Public,Static,PinvokeImpl',[Reflection.CallingConventions]::Standard,$Return,$Parameters,[Runtime.InteropServices.CallingConvention]::Winapi,[Runtime.InteropServices.CharSet]::Unicode)
    $method.SetImplementationFlags($method.GetMethodImplementationFlags() -bor [Reflection.MethodImplAttributes]::PreserveSig)
}
Import-Native CreateProcessW ([bool]) @([string],[Text.StringBuilder],[IntPtr],[IntPtr],[bool],[uint32],[IntPtr],[string],[IntPtr],[IntPtr])
Import-Native GetProcessId ([uint32]) @([IntPtr])
Import-Native CreateFileW ([IntPtr]) @([string],[uint32],[uint32],[IntPtr],[uint32],[uint32],[IntPtr])
Import-Native CreateJobObjectW ([IntPtr]) @([IntPtr],[string])
Import-Native SetInformationJobObject ([bool]) @([IntPtr],[int],[IntPtr],[uint32])
Import-Native AssignProcessToJobObject ([bool]) @([IntPtr],[IntPtr])
Import-Native DuplicateHandle ([bool]) @([IntPtr],[IntPtr],[IntPtr],[IntPtr],[uint32],[bool],[uint32])
Import-Native ResumeThread ([uint32]) @([IntPtr])
Import-Native GetProcessTimes ([bool]) @([IntPtr],[IntPtr],[IntPtr],[IntPtr],[IntPtr])
Import-Native GetExitCodeProcess ([bool]) @([IntPtr],[IntPtr])
Import-Native QueryInformationJobObject ([bool]) @([IntPtr],[int],[IntPtr],[uint32],[IntPtr])
Import-Native WaitForSingleObject ([uint32]) @([IntPtr],[uint32])
Import-Native TerminateJobObject ([bool]) @([IntPtr],[uint32])
Import-Native TerminateProcess ([bool]) @([IntPtr],[uint32])
Import-Native CloseHandle ([bool]) @([IntPtr])
Import-Native GetFileInformationByHandle ([bool]) @([IntPtr],[IntPtr])
$native=$builder.CreateType()
function Require-Native([bool]$Value){if(-not $Value){throw 'V6_NATIVE_CALL_REFUSED'}}
function New-ZeroBuffer([int]$Size){$p=[Runtime.InteropServices.Marshal]::AllocHGlobal($Size);[Runtime.InteropServices.Marshal]::Copy([byte[]]::new($Size),0,$p,$Size);return $p}
function Creation([IntPtr]$Handle){
    $p=New-ZeroBuffer 32
    try{Require-Native ($native::GetProcessTimes($Handle,$p,[IntPtr]::Add($p,8),[IntPtr]::Add($p,16),[IntPtr]::Add($p,24)));return [Runtime.InteropServices.Marshal]::ReadInt64($p)}
    finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($p)}
}
function Duplicate-ToWorker([IntPtr]$Handle,[uint32]$Access){
    $p=New-ZeroBuffer 8
    try{Require-Native ($native::DuplicateHandle($parent.Handle,$Handle,$hp,$p,$Access,$false,0));return [Runtime.InteropServices.Marshal]::ReadInt64($p)}
    finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($p)}
}
function Active-JobCount {
    $p=New-ZeroBuffer 520
    try{Require-Native ($native::QueryInformationJobObject($job,3,$p,520,[IntPtr]::Zero));$assigned=[Runtime.InteropServices.Marshal]::ReadInt32($p);$count=[Runtime.InteropServices.Marshal]::ReadInt32($p,4);if($assigned -ne $count -or $count -gt 64){throw 'V6_JOB_ENUMERATION_INCOMPLETE'};return $count}
    finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($p)}
}
function Job-Pids {
    $p=New-ZeroBuffer 520
    try{
        Require-Native ($native::QueryInformationJobObject($job,3,$p,520,[IntPtr]::Zero))
        $assigned=[Runtime.InteropServices.Marshal]::ReadInt32($p);$count=[Runtime.InteropServices.Marshal]::ReadInt32($p,4)
        if($assigned -ne $count -or $count -gt 64){throw 'V6_JOB_REPLY_INCOMPLETE'}
        $ids=[Collections.Generic.List[long]]::new()
        for($i=0;$i -lt $count;$i++){$ids.Add([Runtime.InteropServices.Marshal]::ReadInt64($p,8+8*$i))}
        return ,([long[]]$ids.ToArray())
    }finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($p)}
}
function New-OwnedSuspended([string]$Executable,[string]$Command){
    $script:assigned=$false
    $si=New-ZeroBuffer 104;$pi=New-ZeroBuffer 24
    try{
        [Runtime.InteropServices.Marshal]::WriteInt32($si,104)
        Require-Native ($native::CreateProcessW($Executable,[Text.StringBuilder]::new($Command),[IntPtr]::Zero,[IntPtr]::Zero,$false,12,[IntPtr]::Zero,'D:\Work\Project Atlas',$si,$pi))
        # Publish ownership to the outer finally BEFORE assignment can fail.
        $script:hp=[Runtime.InteropServices.Marshal]::ReadIntPtr($pi)
        $script:ht=[Runtime.InteropServices.Marshal]::ReadIntPtr($pi,8)
        $id=[Runtime.InteropServices.Marshal]::ReadInt32($pi,16)
        Require-Native ($native::AssignProcessToJobObject($job,$hp));$script:assigned=$true
        return @{pid=$id;created=(Creation $hp);command=$Command}
    }finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($si);[Runtime.InteropServices.Marshal]::FreeHGlobal($pi)}
}
function Account-Scope {
    $entries=0L;$bytes=0L
    foreach($base in @($root,'D:\AtlasRuntime\launchers','D:\AtlasRuntime\support-installations','D:\AtlasRuntime\selection')){
        $stack=[Collections.Generic.Stack[string]]::new();$stack.Push($base)
        while($stack.Count){
            $path=$stack.Pop();$item=Get-Item -LiteralPath $path -Force
            if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'V6_SCOPE_REPARSE_REFUSAL'}
            $entries++
            if($item.PSIsContainer){foreach($child in [IO.Directory]::EnumerateFileSystemEntries($path)){$stack.Push($child)}}
            else{
                if($item.LinkType -eq 'HardLink' -and $item.DirectoryName -ine 'D:\AtlasRuntime\selection'){throw 'V6_SCOPE_UNEXPECTED_HARDLINK'}
                $bytes+=$item.Length
            }
        }
    }
    return @{entries=$entries;logical_bytes=$bytes;accounted_bytes=($bytes+4096*$entries)}
}
function Create-Json([string]$Name,[object]$Value){
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 12))
    $temporary=Join-Path $root ($Name+'.writing')
    $f=[IO.File]::Open($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$f.Write($bytes,0,$bytes.Length);$f.Flush($true)}finally{$f.Dispose()}
    [IO.File]::Move($temporary,(Join-Path $root $Name))
}
$parent=[Diagnostics.Process]::GetCurrentProcess();$job=$hp=$ht=[IntPtr]::Zero;$lease=$null
$assigned=$false;$tail=$null
$result=[ordered]@{status='REFUSED_PRESERVE_EVIDENCE';authorization_consumed=$false;forced_job_cleanup=$false;worker_exit=$null;handles_closed=$false}
try{
    if([Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'V6_NORMAL_TOKEN_REQUIRED'}
    $nonce=[guid]::NewGuid().ToString('N')
    $deadline=[long](([Diagnostics.Stopwatch]::GetTimestamp()/[double][Diagnostics.Stopwatch]::Frequency+600-$watch.Elapsed.TotalSeconds)*1e9)
    Create-Json 'single-use-claim.json' @{approved_checkpoint=$ApprovedCheckpoint;scope_sha256=$ApprovedScopeSha256;nonce=$nonce;deadline_ns=$deadline}
    $result.authorization_consumed=$true
    $env:ATLAS_AUTH_SCOPE_SHA256=$ApprovedScopeSha256;$env:ATLAS_AUTH_APPROVED_HEAD=$ApprovedCheckpoint;$env:ATLAS_AUTH_DEADLINE_NS=$deadline.ToString()
    $lease=[IO.File]::Open($python,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    if((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash.ToLowerInvariant() -cne $scope.ownership.images.observer.sha256){throw 'V6_OBSERVER_IMAGE_HASH_MISMATCH'}
    $job=$native::CreateJobObjectW([IntPtr]::Zero,$null);if($job -eq [IntPtr]::Zero){throw 'V6_JOB_REQUIRED'}
    $limits=New-ZeroBuffer 144
    try{[Runtime.InteropServices.Marshal]::WriteInt32($limits,16,0x2000);Require-Native ($native::SetInformationJobObject($job,9,$limits,144))}
    finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($limits)}
    $verifyCommand='"'+$python+'" -I -B "'+(Join-Path $root 'gate.py')+'" --verify-only '+$ApprovedScopeSha256+' '+$ApprovedCheckpoint
    $verifier=New-OwnedSuspended $python $verifyCommand
    if($native::ResumeThread($ht) -eq [uint32]::MaxValue){throw 'V6_SCOPE_VERIFIER_RESUME_REFUSED'}
    Require-Native ($native::CloseHandle($ht));$ht=[IntPtr]::Zero
    if($native::WaitForSingleObject($hp,30000) -ne 0){throw 'V6_SCOPE_VERIFIER_TIMEOUT'}
    $p=New-ZeroBuffer 4
    try{Require-Native ($native::GetExitCodeProcess($hp,$p));$verifyExit=[Runtime.InteropServices.Marshal]::ReadInt32($p)}finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($p)}
    if($verifyExit -ne 0 -or (Creation $hp) -ne $verifier.created -or (Active-JobCount) -ne 0){throw 'V6_STATIC_SCOPE_SOURCE_OR_GIT_REFUSED'}
    $result.scope_verifier=@{pid=$verifier.pid;created=$verifier.created;command=$verifyCommand;exit=$verifyExit;original_handle_verified=$true}
    Require-Native ($native::CloseHandle($hp));$hp=[IntPtr]::Zero
    $command='"'+$python+'" -I -B "'+(Join-Path $root 'worker.py')+'" --approved-installed-worker'
    $launch=New-OwnedSuspended $python $command;$workerId=$launch.pid
    $handoff=@{nonce=$nonce;scope_sha256=$ApprovedScopeSha256;checkpoint=$ApprovedCheckpoint;role='acceptance_worker';pid=$workerId;created=(Creation $hp);command=$command;
        parent_pid=$PID;parent_created=(Creation $parent.Handle);parent_command=[Environment]::CommandLine;
        parent_handle=(Duplicate-ToWorker $parent.Handle 0x101000);launch_handle=(Duplicate-ToWorker $hp 0x101000)}
    Create-Json 'outer-launch.json' $handoff
    $tail=New-AtlasWorkerLogTail -Kernel $native -Root $root -WorkerHandle $hp -WorkerPid $workerId -WorkerCreated $handoff.created -Nonce $nonce
    if($native::ResumeThread($ht) -eq [uint32]::MaxValue){throw 'V6_RESUME_REFUSED'}
    Require-Native ($native::CloseHandle($ht));$ht=[IntPtr]::Zero
    $sequence=1
    while($native::WaitForSingleObject($hp,0) -eq 258){
        $name=('job-{0:D6}' -f $sequence)
        $requestPath=Join-Path $root ($name+'.request.json')
        if(Test-Path -LiteralPath $requestPath){
            if((Get-Item -LiteralPath $requestPath).Length -gt 65536){throw 'V6_JOB_QUERY_CAPACITY'}
            $query=Get-Content -LiteralPath $requestPath -Raw|ConvertFrom-Json
            if($query.seq -ne $sequence -or $query.nonce -cne $nonce -or $query.scope_sha256 -cne $ApprovedScopeSha256){throw 'V6_JOB_QUERY_SESSION_MISMATCH'}
            $ids=Job-Pids
            Create-Json ($name+'.response.json') @{seq=$sequence;nonce=$nonce;scope_sha256=$ApprovedScopeSha256;pids=$ids;
                collected_ns=[long]([Diagnostics.Stopwatch]::GetTimestamp()/[double][Diagnostics.Stopwatch]::Frequency*1e9)}
            $sequence++
        }
        $account=Account-Scope
        if($watch.Elapsed.TotalSeconds -ge 540 -or $account.entries -ge 7800 -or $account.accounted_bytes -ge 60MB){throw 'V6_GLOBAL_CLEANUP_RESERVE_REACHED'}
        $batch=Read-AtlasWorkerLogTail $tail
        foreach($line in $batch.lines){[Console]::Out.Write($line)}
        Start-Sleep -Milliseconds 10
    }
    $p=New-ZeroBuffer 4
    try{Require-Native ($native::GetExitCodeProcess($hp,$p));$result.worker_exit=[Runtime.InteropServices.Marshal]::ReadInt32($p)}
    finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($p)}
    if((Creation $hp) -ne $handoff.created){throw 'V6_ORIGINAL_LAUNCH_HANDLE_IDENTITY_CHANGED_AT_EXIT'}
    $batch=Complete-AtlasWorkerLogTail $tail
    foreach($line in $batch.lines){[Console]::Out.Write($line)}
    $result.log_evidence=@{native_identity_verified=$true;complete_lines=$tail.CompleteLines;length=$tail.Length;bounded_read_bytes=$tail.BytesRead}
    $result.job_active_after_worker=Active-JobCount
    if($result.job_active_after_worker -ne 0){throw 'V6_OWNED_DESCENDANTS_NOT_DRAINED'}
    if($result.worker_exit -eq 0){$result.status='COMPLETE'}
}catch{$result.error=$_.Exception.Message}
finally{
    if($null -ne $tail){try{Close-AtlasWorkerLogTail $tail;$result.log_handles_closed=$tail.Closed}catch{$result.status='REFUSED_PRESERVE_EVIDENCE';$result.log_close_error=$_.Exception.Message}}
    if($hp -ne [IntPtr]::Zero -and -not $assigned -and $native::WaitForSingleObject($hp,0) -eq 258){$result.forced_job_cleanup=$true;Require-Native ($native::TerminateProcess($hp,76));[void]$native::WaitForSingleObject($hp,5000)}
    if($job -ne [IntPtr]::Zero -and (Active-JobCount) -gt 0){$result.forced_job_cleanup=$true;Require-Native ($native::TerminateJobObject($job,76));if($hp -ne [IntPtr]::Zero){[void]$native::WaitForSingleObject($hp,10000)}}
    if($job -ne [IntPtr]::Zero){$result.final_job_active=Active-JobCount}
    foreach($h in @($ht,$hp,$job)){if($h -ne [IntPtr]::Zero){Require-Native ($native::CloseHandle($h))}}
    if($null -ne $lease){$lease.Dispose()};$parent.Dispose();$result.handles_closed=$true
    $result.seconds=$watch.Elapsed.TotalSeconds;$result.resources=Account-Scope
    if($result.seconds -gt 600 -or $result.resources.entries+1 -gt 8192 -or $result.resources.accounted_bytes+16384 -gt 64MB){$result.status='REFUSED_RESOURCE_LIMIT'}
    Create-Json 'supervisor-result.json' $result
    $result|ConvertTo-Json -Depth 6
}
if($result.status -cne 'COMPLETE' -or $result.forced_job_cleanup){exit 2}
