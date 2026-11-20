Set-StrictMode -Version Latest

function Get-AtlasLogNativeInfo($Kernel,[IntPtr]$Handle){
    $buffer=[Runtime.InteropServices.Marshal]::AllocHGlobal(52)
    try{
        if(-not $Kernel::GetFileInformationByHandle($Handle,$buffer)){throw 'LOG_NATIVE_FILE_QUERY_FAILED'}
        $raw=[byte[]]::new(52);[Runtime.InteropServices.Marshal]::Copy($buffer,$raw,0,52)
        return @{id=@([BitConverter]::ToUInt32($raw,28),[BitConverter]::ToUInt32($raw,44),[BitConverter]::ToUInt32($raw,48));
            created=[BitConverter]::ToInt64($raw,4);attrs=[BitConverter]::ToUInt32($raw,0);links=[BitConverter]::ToUInt32($raw,40)}
    }finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($buffer)}
}
function Assert-AtlasLogPin($Info,$Expected){
    if($Info.attrs -band 0x410 -or $Info.links -ne 1 -or ($Info.id -join ',') -cne ($Expected.id -join ',') -or $Info.created -ne $Expected.created){throw 'LOG_FILE_IDENTITY_MISMATCH'}
}
function Get-AtlasLogWriter($State){
    $kernel=$State.Kernel
    if($kernel::GetProcessId($State.WorkerHandle) -ne $State.WorkerPid){throw 'LOG_WORKER_PID_MISMATCH'}
    $buffer=[Runtime.InteropServices.Marshal]::AllocHGlobal(32)
    try{
        if(-not $kernel::GetProcessTimes($State.WorkerHandle,$buffer,[IntPtr]::Add($buffer,8),[IntPtr]::Add($buffer,16),[IntPtr]::Add($buffer,24))){throw 'LOG_WORKER_CREATION_QUERY_FAILED'}
        if([Runtime.InteropServices.Marshal]::ReadInt64($buffer) -ne $State.WorkerCreated){throw 'LOG_WORKER_CREATION_MISMATCH'}
    }finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($buffer)}
    $wait=$kernel::WaitForSingleObject($State.WorkerHandle,0)
    if($wait -eq 258){return @{alive=$true;exit=$null}}
    if($wait -ne 0){throw 'LOG_WORKER_LIFETIME_QUERY_FAILED'}
    $buffer=[Runtime.InteropServices.Marshal]::AllocHGlobal(4)
    try{
        if(-not $kernel::GetExitCodeProcess($State.WorkerHandle,$buffer)){throw 'LOG_WORKER_EXIT_QUERY_FAILED'}
        return @{alive=$false;exit=[Runtime.InteropServices.Marshal]::ReadInt32($buffer)}
    }finally{[Runtime.InteropServices.Marshal]::FreeHGlobal($buffer)}
}
function New-AtlasWorkerLogTail($Kernel,[string]$Root,[IntPtr]$WorkerHandle,[int]$WorkerPid,[long]$WorkerCreated,[string]$Nonce){
    if($Nonce -cnotmatch '^[0-9a-f]{32}$' -or $WorkerHandle -eq [IntPtr]::Zero -or $WorkerPid -le 4 -or $WorkerCreated -le 0){throw 'LOG_EXACT_LAUNCH_BINDING_REQUIRED'}
    $absolute=[IO.Path]::GetFullPath($Root)
    if($absolute -cne $Root -or -not [IO.Directory]::Exists($Root)){throw 'LOG_EXISTING_EXACT_ROOT_REQUIRED'}
    $state=@{Kernel=$Kernel;Root=$Root;WorkerHandle=$WorkerHandle;WorkerPid=$WorkerPid;WorkerCreated=$WorkerCreated;Nonce=$Nonce;
        Leases=[Collections.Generic.List[IntPtr]]::new();RootId=$null;File=$null;Declaration=$null;Pin=$null;
        Length=0L;Emitted=0L;CompleteLines=0L;Hash=$null;Refused=$false;Closed=$false;Reason=$null;BytesRead=0L}
    try{
        [void](Get-AtlasLogWriter $state)
        $path=Get-Item -LiteralPath $Root -Force
        while($null -ne $path){
            if($path -isnot [IO.DirectoryInfo] -or $path.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'LOG_ANCESTOR_REPARSE_OR_NOT_DIRECTORY'}
            $h=$Kernel::CreateFileW($path.FullName,0x80,3,[IntPtr]::Zero,3,0x02200000,[IntPtr]::Zero)
            if($h -eq [IntPtr]::Zero -or $h -eq [IntPtr](-1)){throw 'LOG_DIRECTORY_LEASE_FAILED'}
            $state.Leases.Add($h)
            $info=Get-AtlasLogNativeInfo $Kernel $h
            if($info.attrs -band 0x400 -or -not ($info.attrs -band 0x10)){throw 'LOG_NATIVE_DIRECTORY_REFUSAL'}
            if($null -eq $state.RootId){$state.RootId=$info.id}
            $path=$path.Parent
        }
        return $state
    }catch{Close-AtlasWorkerLogTail $state;throw}
}
function Read-AtlasWorkerLogTail($State){
    if($State.Closed){throw 'LOG_READER_CLOSED'}
    if($State.Refused){throw ('LOG_REFUSAL_LATCHED:'+ $State.Reason)}
    try{
        $writer=Get-AtlasLogWriter $State
        if($null -eq $State.File){
            $packet=Join-Path $State.Root 'worker-logs.json'
            if(-not [IO.File]::Exists((Join-Path $State.Root 'worker-logs.ready')) -or -not [IO.File]::Exists($packet)){
                if(-not $writer.alive){throw 'LOG_DECLARATION_MISSING_AT_WRITER_EXIT'}
                return @{state='WAITING_FOR_DECLARATION';lines=@();attributed=$false;writer_alive=$true;pending_bytes=0}
            }
            $item=Get-Item -LiteralPath $packet -Force
            if($item.Attributes -band [IO.FileAttributes]::ReparsePoint -or $item.Length -gt 8192){throw 'LOG_DECLARATION_NAMESPACE_OR_CAPACITY'}
            $State.Declaration=[IO.FileStream]::new($packet,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
            if($State.Declaration.Length -gt 8192){throw 'LOG_DECLARATION_CAPACITY_AFTER_OPEN'}
            $info=Get-AtlasLogNativeInfo $State.Kernel $State.Declaration.SafeFileHandle.DangerousGetHandle()
            if($info.attrs -band 0x410 -or $info.links -ne 1){throw 'LOG_DECLARATION_NATIVE_NAMESPACE'}
            $decoder=[IO.StreamReader]::new($State.Declaration,[Text.UTF8Encoding]::new($false,$true),$false,4096,$true)
            try{$claim=$decoder.ReadToEnd()|ConvertFrom-Json}finally{$decoder.Dispose()}
            if((($claim.PSObject.Properties.Name|Sort-Object)-join ',') -cne 'created,files,nonce,pid,root_id,schema' -or $claim.schema -cne 'QD_WORKER_LOG_HANDLES_V6' -or $claim.nonce -isnot [string] -or $claim.nonce -cne $State.Nonce -or ($claim.pid -isnot [int] -and $claim.pid -isnot [long]) -or ($claim.created -isnot [int] -and $claim.created -isnot [long]) -or $claim.pid -ne $State.WorkerPid -or $claim.created -ne $State.WorkerCreated -or @($claim.root_id).Count -ne 3 -or ($claim.root_id -join ',') -cne ($State.RootId -join ',')){throw 'LOG_DECLARATION_LAUNCH_OR_ROOT_MISMATCH'}
            foreach($n in $claim.root_id){if(($n -isnot [int] -and $n -isnot [long]) -or $n -lt 0 -or $n -gt [uint32]::MaxValue){throw 'LOG_DECLARATION_NATIVE_ROOT_TYPE'}}
            if((($claim.files.PSObject.Properties.Name|Sort-Object)-join ',') -cne 'stderr,stdout'){throw 'LOG_DECLARATION_FILES_REQUIRED'}
            foreach($name in @('stdout','stderr')){
                $pin=$claim.files.$name
                if((($pin.PSObject.Properties.Name|Sort-Object)-join ',') -cne 'created,id' -or @($pin.id).Count -ne 3 -or ($pin.created -isnot [int] -and $pin.created -isnot [long]) -or $pin.created -lt $State.WorkerCreated){throw 'LOG_DECLARATION_FILE_PIN_REQUIRED'}
                foreach($n in $pin.id){if(($n -isnot [int] -and $n -isnot [long]) -or $n -lt 0 -or $n -gt [uint32]::MaxValue){throw 'LOG_DECLARATION_NATIVE_ID_TYPE'}}
            }
            $State.Pin=$claim.files.stdout
            $path=Join-Path $State.Root 'worker-stdout.log'
            $item=Get-Item -LiteralPath $path -Force -ErrorAction Stop
            if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'LOG_FILE_REPARSE'}
            # Read-only access with READ+WRITE sharing permits the existing
            # Python writer. No DELETE sharing: pathname replacement refuses.
            $State.File=[IO.FileStream]::new($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite,4096)
            Assert-AtlasLogPin (Get-AtlasLogNativeInfo $State.Kernel $State.File.SafeFileHandle.DangerousGetHandle()) $State.Pin
        }
        Assert-AtlasLogPin (Get-AtlasLogNativeInfo $State.Kernel $State.File.SafeFileHandle.DangerousGetHandle()) $State.Pin
        $length=$State.File.Length
        if($length -lt $State.Length){throw 'LOG_TRUNCATED'}
        if($length -gt 1MB){throw 'LOG_CAPACITY_EXCEEDED'}
        $data=[byte[]]::new([int]$length);[void]$State.File.Seek(0,[IO.SeekOrigin]::Begin)
        $offset=0
        while($offset -lt $length){
            $read=$State.File.Read($data,$offset,[Math]::Min(16384,$length-$offset))
            if($read -le 0){throw 'LOG_UNEXPECTED_EOF_DURING_SNAPSHOT'}
            $offset+=$read
        }
        $State.BytesRead+=$offset
        $hash=[Security.Cryptography.SHA256]::Create()
        try{
            if($null -ne $State.Hash -and [Convert]::ToBase64String($hash.ComputeHash($data,0,[int]$State.Length)) -cne $State.Hash){throw 'LOG_PREFIX_REWRITTEN'}
            $State.Hash=[Convert]::ToBase64String($hash.ComputeHash($data))
        }finally{$hash.Dispose()}
        $State.Length=$length
        $lines=[Collections.Generic.List[string]]::new();$start=[int]$State.Emitted
        for($i=$start;$i -lt $length;$i++){
            if($i-$start -ge 65536){throw 'LOG_LINE_CAPACITY_EXCEEDED'}
            if($data[$i] -eq 10){
                $lines.Add([Text.UTF8Encoding]::new($false,$true).GetString($data,$start,$i-$start+1))
                $start=$i+1;$State.Emitted=$start;$State.CompleteLines++
                if($State.CompleteLines -gt 4096){throw 'LOG_RECORD_CAPACITY_EXCEEDED'}
                if($lines.Count -ge 128){break}
            }
        }
        # Recheck size/identity and original process after the read. A live
        # file's current end is not a completed writer or successful evidence.
        Assert-AtlasLogPin (Get-AtlasLogNativeInfo $State.Kernel $State.File.SafeFileHandle.DangerousGetHandle()) $State.Pin
        if($State.File.Length -lt $length){throw 'LOG_TRUNCATED_DURING_READ'}
        $writer=Get-AtlasLogWriter $State
        return @{state=$(if($writer.alive){'FOLLOWING'}else{'WRITER_EXITED'});lines=@($lines.ToArray());attributed=$true;
            writer_alive=$writer.alive;writer_exit=$writer.exit;pending_bytes=$State.Length-$State.Emitted}
    }catch{
        $State.Refused=$true;$State.Reason=$_.Exception.Message
        throw
    }
}
function Complete-AtlasWorkerLogTail($State){
    try{
        $lines=[Collections.Generic.List[string]]::new()
        for($i=0;$i -lt 32;$i++){
            $previous=$State.Emitted
            $batch=Read-AtlasWorkerLogTail $State
            if($batch.writer_alive){throw 'LOG_WRITER_STILL_RUNNING'}
            if($batch.writer_exit -ne 0){throw 'LOG_WRITER_EXIT_NONZERO'}
            foreach($line in $batch.lines){$lines.Add($line)}
            if($batch.pending_bytes -eq 0){break}
            if($State.Emitted -eq $previous){throw 'LOG_INCOMPLETE_FINAL_LINE_OR_UNDRAINED'}
        }
        if($batch.pending_bytes -ne 0){throw 'LOG_RECORD_CAPACITY_EXCEEDED'}
        if($State.CompleteLines -eq 0){throw 'LOG_EMPTY_AT_WRITER_EXIT'}
        $batch.lines=@($lines.ToArray())
        return $batch
    }catch{$State.Refused=$true;$State.Reason=$_.Exception.Message;throw}
}
function Close-AtlasWorkerLogTail($State){
    if($null -eq $State -or $State.Closed){return}
    $errors=[Collections.Generic.List[string]]::new()
    foreach($name in @('File','Declaration')){
        if($null -ne $State[$name]){try{$State[$name].Dispose();$State[$name]=$null}catch{$errors.Add($_.Exception.Message)}}
    }
    $kernel=$State.Kernel
    foreach($h in @($State.Leases.ToArray())){
        if($kernel::CloseHandle($h)){[void]$State.Leases.Remove($h)}else{$errors.Add('LOG_DIRECTORY_HANDLE_CLOSE_FAILED')}
    }
    $State.Closed=($errors.Count -eq 0)
    if(-not $State.Closed){$State.Refused=$true;$State.Reason='LOG_HANDLE_CLOSE_INCOMPLETE';throw ($State.Reason+':'+($errors -join ';'))}
}
Export-ModuleMember -Function New-AtlasWorkerLogTail,Read-AtlasWorkerLogTail,Complete-AtlasWorkerLogTail,Close-AtlasWorkerLogTail
