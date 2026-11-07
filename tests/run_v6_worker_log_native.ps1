param([Parameter(Mandatory=$true)][string]$DisposableRoot)
$ErrorActionPreference='Stop'
$repo='D:\Work\Project Atlas';$base=[IO.Path]::GetFullPath($DisposableRoot)
if([IO.Path]::GetDirectoryName($base) -ine (Join-Path $repo 'logs\diagnostics') -or [IO.Path]::GetFileName($base) -cnotmatch '^qd-v6-worker-log-native-[a-zA-Z0-9-]+$' -or (Test-Path -LiteralPath $base)){throw 'FRESH_CONFINED_DISPOSABLE_ROOT_REQUIRED'}
[void][IO.Directory]::CreateDirectory($base);[void][IO.Directory]::CreateDirectory((Join-Path $base 'temp'))
$env:TEMP=Join-Path $base 'temp';$env:TMP=$env:TEMP;$env:PYTHONDONTWRITEBYTECODE='1';$env:PSModuleAnalysisCachePath=Join-Path $base 'module.cache'
$root=$base;$watch=[Diagnostics.Stopwatch]::StartNew()
$source=Get-Content -LiteralPath (Join-Path $repo 'scripts\acceptance_harness_v6\supervise.ps1') -Raw
$a=$source.IndexOf('$assembly=');$b=$source.IndexOf('function Account-Scope');if($a -lt 0 -or $b -le $a){throw 'NATIVE_DEFINITIONS_MISSING'}
# Definitions only: no operational entry, grant, selector, worker or gate runs.
. ([scriptblock]::Create($source.Substring($a,$b-$a)))
Import-Module (Join-Path $repo 'scripts\acceptance_harness_v6\WorkerLog.psm1') -Force
$python='C:\Users\renal\AppData\Local\Programs\Python\Python312\python.exe'
$cases=[Collections.Generic.List[object]]::new();$overall=@{passed=$false;domain='DISPOSABLE_LOG_TESTS_ONLY';installed_launches=0;selection_mutations=0;financial_actions=0;cases=$cases}
function Write-Json([string]$Path,$Value){
    $raw=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 12 -Compress))
    if($raw.Length -gt 2MB){throw 'FIXTURE_COMMAND_CAPACITY'}
    $p=$Path+'.writing';$f=[IO.File]::Open($p,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$f.Write($raw,0,$raw.Length);$f.Flush($true)}finally{$f.Dispose()};[IO.File]::Move($p,$Path)
}
function Guard {
    if($watch.Elapsed.TotalSeconds -gt 150){throw 'FIXTURE_CLEANUP_TIME_RESERVE'}
    $paths=@(Get-ChildItem -LiteralPath $base -Recurse -Force)
    if(@($paths|Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw 'FIXTURE_REPARSE_REFUSAL'}
    $bytes=($paths|Where-Object {-not $_.PSIsContainer}|Measure-Object Length -Sum).Sum
    if($paths.Count+1 -gt 2000 -or $bytes+4096*($paths.Count+1) -gt 30MB){throw 'FIXTURE_CAPACITY_RESERVE'}
}
function Wait-File([string]$Path){
    $until=$watch.Elapsed.TotalSeconds+4
    while(-not [IO.File]::Exists($Path)){if($watch.Elapsed.TotalSeconds -gt $until -or $watch.Elapsed.TotalSeconds -gt 150){throw 'FIXTURE_SIGNAL_TIMEOUT'};Start-Sleep -Milliseconds 3}
}
function Send-Command($Value,[switch]$NoWait){
    $script:step++;$name=('cmd-{0:D3}.json' -f $step);Write-Json (Join-Path $caseRoot $name) $Value
    # Producer completion after Move returns; the worker does not open a
    # command merely because its final name has become visible mid-rename.
    [IO.File]::WriteAllBytes((Join-Path $caseRoot ('cmd-{0:D3}.ready' -f $step)),[byte[]]@(1))
    if(-not $NoWait){Wait-File (Join-Path $caseRoot ('done-{0:D3}.json' -f $step))}
}
function Expect-Refusal([scriptblock]$Action,[string]$Pattern){
    try{& $Action|Out-Null}catch{if($_.Exception.ToString() -match $Pattern){return $_.Exception.Message};throw ('WRONG_REFUSAL:'+ $_.Exception.ToString())}
    throw 'EXPECTED_REFUSAL_MISSING'
}
$names=@('original-sharing-reproduction','reader-before-first-entry','writer-before-reader','partial-lines','delayed-flush','concurrent-append','final-backlog','access-denied','exclusive-sharing','missing-declaration','missing-declared-file','unexpected-exit','partial-eof','empty-eof','truncate','rewrite','replacement','wrong-file-id','wrong-worker-id','wrong-root-id','wrong-nonce','malformed-declaration','log-capacity','line-capacity','record-capacity','invalid-utf8','worker-termination','stale-original-handle','repeat-1','repeat-2','repeat-3','repeat-4','repeat-5')
try{
    foreach($name in $names){
        Guard
        $caseRoot=Join-Path $base $name;[void][IO.Directory]::CreateDirectory($caseRoot)
        $row=@{case=$name;passed=$false;forced_cleanup=$false};$job=$hp=$ht=[IntPtr]::Zero;$assigned=$false;$tail=$null;$step=0;$dacl=$null;$restoreFile=$null;$completed=$false
        try{
            $nonce=[guid]::NewGuid().ToString('N')
            $job=$native::CreateJobObjectW([IntPtr]::Zero,$null);if($job -eq [IntPtr]::Zero){throw 'JOB_REQUIRED'}
            $limits=New-ZeroBuffer 144
            try{[Runtime.InteropServices.Marshal]::WriteInt32($limits,16,0x2000);Require-Native ($native::SetInformationJobObject($job,9,$limits,144))}finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($limits)}
            $mode=if($name -eq 'exclusive-sharing'){'exclusive'}elseif($name -eq 'missing-declaration'){'missing'}else{'normal'}
            $command='"'+$python+'" -I -B "'+(Join-Path $repo 'tests\v6_log_writer_fixture.py')+'" --disposable-log-writer "'+$caseRoot+'" '+$mode
            $launch=New-OwnedSuspended $python $command
            Write-Json (Join-Path $caseRoot 'outer-launch.json') @{pid=$launch.pid;created=$launch.created;nonce=$nonce}
            $tail=New-AtlasWorkerLogTail -Kernel $native -Root $caseRoot -WorkerHandle $hp -WorkerPid $launch.pid -WorkerCreated $launch.created -Nonce $nonce
            $early=Read-AtlasWorkerLogTail $tail
            if($early.state -cne 'WAITING_FOR_DECLARATION' -or $early.attributed -or @($early.lines).Count){throw 'MISSING_LOG_TREATED_AS_EVIDENCE'}
            if($native::ResumeThread($ht) -eq [uint32]::MaxValue){throw 'RESUME_FAILED'};Require-Native ($native::CloseHandle($ht));$ht=[IntPtr]::Zero
            Wait-File (Join-Path $caseRoot 'fixture-ready.json')
            $path=Join-Path $caseRoot 'worker-stdout.log'
            switch($name){
                'original-sharing-reproduction' {
                    $row.original_error=Expect-Refusal {[IO.File]::ReadAllText($path)} 'being used by another process'
                    # Original failed cut stays a failure. This is a distinct
                    # explicit corrected-reader test, never a retried grant.
                    $row.original_reader_outcome='REFUSED_SHARING_VIOLATION'
                    $read=Read-AtlasWorkerLogTail $tail
                    if(-not $read.attributed -or @($read.lines).Count){throw 'EMPTY_READ_CLASSIFICATION'}
                }
                'partial-lines' {
                    Send-Command @{action='append';text='partial';flush=$true};$read=Read-AtlasWorkerLogTail $tail
                    if(@($read.lines).Count -ne 0 -or $read.pending_bytes -ne 7){throw 'PARTIAL_PREMATURELY_EMITTED'}
                    Send-Command @{action='append';text="-complete`n"};$read=Read-AtlasWorkerLogTail $tail
                    if(($read.lines -join '') -cne "partial-complete`r`n"){throw 'PARTIAL_JOIN_FAILED'}
                }
                'delayed-flush' {
                    Send-Command @{action='append';text='buffered';flush=$false};$read=Read-AtlasWorkerLogTail $tail
                    if($tail.Length -ne 0 -or @($read.lines).Count){throw 'UNFLUSHED_BYTES_FABRICATED'}
                    Send-Command @{action='flush'};$read=Read-AtlasWorkerLogTail $tail
                    if($read.pending_bytes -ne 8 -or @($read.lines).Count){throw 'DELAYED_FLUSH_FAILED'}
                    Send-Command @{action='append';text="`n"};$read=Read-AtlasWorkerLogTail $tail
                    if(($read.lines -join '') -cne "buffered`r`n"){throw 'DELAYED_LINE_FAILED'}
                }
                'concurrent-append' {
                    Send-Command @{action='many';count=200} -NoWait
                    $received=[Collections.Generic.List[string]]::new();$until=$watch.Elapsed.TotalSeconds+5
                    do{
                        $read=Read-AtlasWorkerLogTail $tail;foreach($line in $read.lines){$received.Add($line.TrimEnd("`r","`n"))}
                        if($watch.Elapsed.TotalSeconds -gt $until){throw 'CONCURRENT_READ_DEADLINE'}
                    }while(-not [IO.File]::Exists((Join-Path $caseRoot 'done-001.json')) -or $received.Count -lt 200)
                    if(($received -join ',') -cne ((0..199|ForEach-Object {'line-'+$_}) -join ',')){throw 'MISSING_OR_DUPLICATE_LINE'}
                    $row.exact_concurrent_lines=$received.Count
                }
                'final-backlog' {
                    Send-Command @{action='append';text=((1..300|ForEach-Object {'backlog-'+$_}) -join "`n")+"`n"}
                    Send-Command @{action='exit'}
                    if($native::WaitForSingleObject($hp,3000) -ne 0){throw 'BACKLOG_WRITER_NOT_EXITED'}
                    $last=Complete-AtlasWorkerLogTail $tail
                    if(@($last.lines).Count -ne 300 -or $last.pending_bytes -ne 0){throw 'FINAL_BACKLOG_LOST_OR_DUPLICATED'}
                    $completed=$true;$row.corrected_reader='VERIFIED_COMPLETE_300_LINE_BACKLOG'
                }
                'access-denied' {
                    $restoreFile=Get-Item -LiteralPath $path;$dacl=$restoreFile.GetAccessControl();$changed=$restoreFile.GetAccessControl()
                    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
                    $changed.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,[Security.AccessControl.FileSystemRights]::ReadData,[Security.AccessControl.AccessControlType]::Deny));$restoreFile.SetAccessControl($changed)
                    $row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'denied'
                    $restoreFile.SetAccessControl($dacl);$dacl=$null;$row.fixture_dacl_restored=$true
                }
                'exclusive-sharing' {$row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'being used by another process'}
                'missing-declaration' {
                    $read=Read-AtlasWorkerLogTail $tail;if($read.attributed){throw 'MISSING_ACCEPTED'}
                    Send-Command @{action='exit'};[void]$native::WaitForSingleObject($hp,3000)
                    $row.expected_refusal=Expect-Refusal {Complete-AtlasWorkerLogTail $tail} 'LOG_DECLARATION_MISSING_AT_WRITER_EXIT'
                }
                'missing-declared-file' {Send-Command @{action='remove'};$row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'does not exist|Cannot find path'}
                'replacement' {Send-Command @{action='replace'};$row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'LOG_FILE_IDENTITY_MISMATCH'}
                {$_ -in @('wrong-file-id','wrong-worker-id','wrong-root-id','wrong-nonce','malformed-declaration')} {
                    $p=Join-Path $caseRoot 'worker-logs.json';$claim=Get-Content -LiteralPath $p -Raw|ConvertFrom-Json
                    if($name -eq 'wrong-file-id'){$claim.files.stdout.id[2]++}
                    if($name -eq 'wrong-worker-id'){$claim.pid++}
                    if($name -eq 'wrong-root-id'){$claim.root_id[2]++}
                    if($name -eq 'wrong-nonce'){$claim.nonce='f'*32}
                    if($name -eq 'malformed-declaration'){$claim|Add-Member NoteProperty extra 'not-allowed'}
                    [IO.File]::WriteAllText($p,($claim|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
                    $row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'LOG_.*MISMATCH'
                }
                {$_ -in @('truncate','rewrite')} {
                    Send-Command @{action='append';text="original`n"};[void](Read-AtlasWorkerLogTail $tail)
                    if($name -eq 'truncate'){Send-Command @{action='truncate'}}else{Send-Command @{action='overwrite';text="changed!`n"}}
                    $row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'LOG_TRUNCATED|LOG_PREFIX_REWRITTEN'
                    Send-Command @{action='append';text="later`n"}
                    $row.later_read_refused=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'LOG_REFUSAL_LATCHED'
                }
                'log-capacity' {Send-Command @{action='append';text=('x'*(1MB+1))};$row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'LOG_CAPACITY_EXCEEDED'}
                'line-capacity' {Send-Command @{action='append';text=('x'*65537)};$row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'LOG_LINE_CAPACITY_EXCEEDED'}
                'record-capacity' {
                    Send-Command @{action='append';text=("`n"*4097)}
                    $row.expected_refusal=Expect-Refusal {for($i=0;$i -lt 33;$i++){[void](Read-AtlasWorkerLogTail $tail)}} 'LOG_RECORD_CAPACITY_EXCEEDED'
                }
                'stale-original-handle' {$tail.WorkerCreated++;$row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'LOG_WORKER_CREATION_MISMATCH'}
                'invalid-utf8' {
                    [void](Read-AtlasWorkerLogTail $tail)
                    $f=[IO.FileStream]::new($path,[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::ReadWrite)
                    try{$f.Write([byte[]]@(255,10),0,2);$f.Flush($true)}finally{$f.Dispose()}
                    $row.expected_refusal=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'Unable to translate|invalid'
                }
                {$_ -in @('unexpected-exit','worker-termination','partial-eof','empty-eof')} {
                    Send-Command @{action='append';text=$(if($name -eq 'partial-eof'){'unterminated'}elseif($name -eq 'empty-eof'){''}else{"last`n"})}
                    [void](Read-AtlasWorkerLogTail $tail)
                    if($name -eq 'unexpected-exit'){Send-Command @{action='abrupt'} -NoWait}
                    elseif($name -eq 'worker-termination'){Require-Native ($native::TerminateJobObject($job,77));$row.intentional_owned_termination_probe=$true}
                    else{Send-Command @{action='exit'}}
                    if($native::WaitForSingleObject($hp,3000) -ne 0){throw 'EXIT_NOT_OBSERVED'}
                    $row.expected_refusal=Expect-Refusal {Complete-AtlasWorkerLogTail $tail} 'LOG_WRITER_EXIT_NONZERO|LOG_INCOMPLETE_FINAL_LINE_OR_UNDRAINED|LOG_EMPTY_AT_WRITER_EXIT'
                }
            }
            if($completed){}
            elseif(-not $tail.Refused){
                Send-Command @{action='append';text="verified-final`n"};$read=Read-AtlasWorkerLogTail $tail
                if(-not $read.attributed -or ($read.lines -join '') -notmatch 'verified-final'){throw 'VERIFIED_LINE_MISSING'}
                Send-Command @{action='exit'}
                if($native::WaitForSingleObject($hp,3000) -ne 0){throw 'WRITER_NOT_EXITED'}
                $last=Complete-AtlasWorkerLogTail $tail
                if($last.writer_exit -ne 0 -or $last.pending_bytes -ne 0){throw 'FINAL_DRAIN_FAILED'}
                $row.corrected_reader='VERIFIED_COMPLETE'
            }else{
                $row.latch_rechecked=Expect-Refusal {Read-AtlasWorkerLogTail $tail} 'LOG_REFUSAL_LATCHED'
                if($native::WaitForSingleObject($hp,0) -eq 258){Send-Command @{action='exit'};if($native::WaitForSingleObject($hp,3000) -ne 0){throw 'NEGATIVE_FIXTURE_DID_NOT_EXIT'}}
            }
            Close-AtlasWorkerLogTail $tail
            if(-not $tail.Closed -or $tail.Leases.Count -or $null -ne $tail.File -or $null -ne $tail.Declaration){throw 'LOG_HANDLES_NOT_CLOSED'}
            $row.reader_handles_closed=$true
            # Rename round-trip proves the writer/reader no-delete leases are
            # released, using only this case's synthetic file.
            if([IO.File]::Exists($path)){[IO.File]::Move($path,$path+'.closed');[IO.File]::Move($path+'.closed',$path)}
            if((Active-JobCount) -ne 0){throw 'OWNED_JOB_NOT_EMPTY'}
            $row.final_job_active=0;$row.passed=$true
        }catch{$row.error=$_.Exception.ToString()}
        finally{
            if($null -ne $dacl){$restoreFile.SetAccessControl($dacl);$row.fixture_dacl_restored=$true}
            if($null -ne $tail){try{Close-AtlasWorkerLogTail $tail}catch{$row.close_error=$_.Exception.Message;$row.passed=$false}}
            if($hp -ne [IntPtr]::Zero -and -not $assigned -and $native::WaitForSingleObject($hp,0) -eq 258){$row.forced_cleanup=$true;[void]$native::TerminateProcess($hp,78);[void]$native::WaitForSingleObject($hp,3000)}
            if($job -ne [IntPtr]::Zero -and (Active-JobCount) -ne 0){$row.forced_cleanup=$true;[void]$native::TerminateJobObject($job,78);if($hp -ne [IntPtr]::Zero){[void]$native::WaitForSingleObject($hp,3000)}}
            foreach($h in @($ht,$hp,$job)){if($h -ne [IntPtr]::Zero){Require-Native ($native::CloseHandle($h))}}
            $row.owner_handles_closed=$true
            if($row.forced_cleanup){$row.passed=$false}
            Write-Json (Join-Path $caseRoot 'case-result.json') $row;$cases.Add($row)
            [ordered]@{case=$name;passed=$row.passed;error=$row.error}|ConvertTo-Json -Compress
        }
        if(-not $row.passed){throw ('CASE_FAILED:'+ $name)}
    }
    $overall.passed=$true
}catch{$overall.error=$_.Exception.ToString()}
finally{
    $overall.seconds=$watch.Elapsed.TotalSeconds
    $files=@(Get-ChildItem -LiteralPath $base -Recurse -Force);$overall.entries=$files.Count+1;$overall.logical_bytes=($files|Where-Object {-not $_.PSIsContainer}|Measure-Object Length -Sum).Sum
    $overall.accounted_bytes=$overall.logical_bytes+4096*$overall.entries
    if($overall.seconds -gt 180 -or $overall.entries+1 -gt 2048 -or $overall.accounted_bytes+16384 -gt 32MB){$overall.passed=$false;$overall.resource_refusal=$true}
    $overall.source_sha256=@{}
    foreach($file in @('scripts/acceptance_harness_v6/WorkerLog.psm1','scripts/acceptance_harness_v6/supervise.ps1','scripts/acceptance_harness_v6/worker_log.py','tests/v6_log_writer_fixture.py','tests/run_v6_worker_log_native.ps1')){$overall.source_sha256[$file]=(Get-FileHash -LiteralPath (Join-Path $repo $file) -Algorithm SHA256).Hash.ToLowerInvariant()}
    Write-Json (Join-Path $base 'native-result.json') $overall
    [ordered]@{passed=$overall.passed;cases=$cases.Count;seconds=$overall.seconds;entries=$overall.entries;accounted_bytes=$overall.accounted_bytes;error=$overall.error}|ConvertTo-Json
}
if(-not $overall.passed){exit 2}
