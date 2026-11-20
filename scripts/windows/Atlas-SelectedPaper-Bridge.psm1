# Source-only bridge. No launcher, enrollment loader, credentials or process kill.
function New-AtlasSelectedReadBridge {
    param([System.Diagnostics.Process]$OwnedProcess, [object]$ExpectedContext, [scriptblock]$Authorize)
    if ($null -eq $OwnedProcess -or $null -eq $ExpectedContext -or $null -eq $Authorize) {
        throw 'ACCEPTED_BRIDGE_DEPENDENCIES_REQUIRED'
    }
    $frozen=$ExpectedContext | ConvertTo-Json -Depth 12 -Compress | ConvertFrom-Json
    $state = [pscustomobject]@{ Process=$OwnedProcess; Expected=$frozen; Authorize=$Authorize; Sequence=0; Ready=$null; Closed=$false; Gate=(New-Object object); Poisoned=$false }
    $invoke = {
        param($s, [string]$Action, $ExpectedReady)
        if (-not [System.Threading.Monitor]::TryEnter($s.Gate)) { throw 'BRIDGE_REQUEST_IN_PROGRESS' }
        $sent=$false
        try {
            $p=$s.Process; $e=$s.Expected
            if ($s.Closed) { if ($Action -eq 'CLOSE') { return $true }; throw 'BRIDGE_CONTEXT_RETIRED' }
            if ($p.HasExited) { throw 'BRIDGE_CHILD_EXITED_UNEXPECTEDLY' }
            if ($e.schema -cne 'QD_OP_BRIDGE_CONTEXT_V1' -or $e.host_id -cnotmatch '^[a-f0-9]{32}$' -or
                $e.process.pid -ne $p.Id -or $e.process.creation_filetime -ne $p.StartTime.ToUniversalTime().ToFileTimeUtc() -or
                $e.process.image -cne $p.MainModule.FileName) { throw 'BRIDGE_NATIVE_OWNERSHIP_MISMATCH' }
            if ($s.Poisoned) {
                if ($Action -ne 'CLOSE') { throw 'BRIDGE_UNCERTAIN_RESPONSE_REPLAY_REFUSED' }
                $p.StandardInput.Close()
                if (-not $p.WaitForExit(12000) -or $p.ExitCode -ne 0) { throw 'BRIDGE_EXIT_UNCONFIRMED_OWNERSHIP_RETAINED' }
                $s.Ready=$null;$s.Closed=$true;return $true
            }
            if ($Action -ne 'CLOSE') {
                $accepted=& $s.Authorize $e
                if ($accepted -isnot [bool] -or -not $accepted) { throw 'BRIDGE_INDEPENDENT_AUTHORITY_REQUIRED' }
            }
            if ($Action -ne 'OPEN' -and (($ExpectedReady | ConvertTo-Json -Depth 12 -Compress) -cne ($s.Ready | ConvertTo-Json -Depth 12 -Compress))) {
                throw 'BRIDGE_SESSION_OWNERSHIP_MISMATCH'
            }
            $request=@{schema='QD_OP_BRIDGE_COMMAND_V1';sequence=($s.Sequence+1);host_id=$e.host_id;process=$e.process;action=$Action;ready=$ExpectedReady}
            $watch=[System.Diagnostics.Stopwatch]::StartNew()
            $sent=$true
            $p.StandardInput.WriteLine(($request | ConvertTo-Json -Depth 12 -Compress));$p.StandardInput.Flush()
            $pending=$p.StandardOutput.ReadLineAsync()
            $budget=15000; if($Action -eq 'CLOSE'){$budget=12000}
            if (-not $pending.Wait($budget)) { throw 'BRIDGE_RESPONSE_TIMEOUT_OWNERSHIP_RETAINED' }
            $raw=$pending.Result
            if ($null -eq $raw -or $raw.Length -gt 8192) { throw 'BRIDGE_RESPONSE_UNAVAILABLE' }
            $r=$raw | ConvertFrom-Json
            # This flat protocol has globally unique field names, including the
            # single ready/process object. Reject duplicate/escaped/extra keys
            # before trusting ConvertFrom-Json (which otherwise keeps the last).
            $keys=@([regex]::Matches($raw,'(?<!\\)"((?:[^"\\]|\\.)*)":') | ForEach-Object {$_.Groups[1].Value})
            $expectedKeys=@('ready','schema','sequence','status')
            if($null -ne $r.ready){$expectedKeys+=@('host_id','mode','process','url','creation_filetime','image','pid')}
            if((($keys | Sort-Object) -join ',') -cne (($expectedKeys | Sort-Object) -join ',') -or
                ($r.sequence -isnot [int] -and $r.sequence -isnot [long])) {throw 'BRIDGE_STRICT_RESPONSE_REQUIRED'}
            if ((($r.PSObject.Properties.Name | Sort-Object) -join ',') -cne 'ready,schema,sequence,status' -or
                $r.schema -cne 'QD_OP_BRIDGE_RESPONSE_V1' -or $r.sequence -ne ($s.Sequence+1) -or $r.status -cne 'OK') {
                throw 'BRIDGE_RESPONSE_REFUSED'
            }
            $s.Sequence++
            if ($Action -eq 'CLOSE') {
                $remaining=[Math]::Max(0,12000-$watch.ElapsedMilliseconds)
                $p.StandardInput.Close()
                if (-not $p.WaitForExit([int]$remaining)) { throw 'BRIDGE_EXIT_TIMEOUT_OWNERSHIP_RETAINED' }
                if ($p.ExitCode -ne 0) { throw 'BRIDGE_CHILD_EXIT_FAILED' }
                $s.Ready=$null;$s.Closed=$true;return $true
            }
            $ready=$r.ready
            if ($ready.mode -cne 'QD_OPERATIONAL_READ_ONLY' -or $ready.host_id -cne $e.host_id -or
                ($ready.process | ConvertTo-Json -Compress) -cne ($e.process | ConvertTo-Json -Compress) -or
                $ready.url -cnotmatch '^http://127\.0\.0\.1:([1-9][0-9]{0,4})/quality_dips\.html\?mode=selected-paper$' -or
                ([uri]$ready.url).Port -gt 65535) { throw 'BRIDGE_HTTP_OWNERSHIP_MISMATCH' }
            if ($Action -eq 'OPEN') {$s.Ready=$ready;return $ready}
            return $true
        } catch {
            if($sent){$s.Poisoned=$true}
            throw
        } finally { [System.Threading.Monitor]::Exit($s.Gate) }
    }.GetNewClosure()
    $result=New-Object psobject
    $result | Add-Member ScriptMethod open_read_only_session { & $invoke $state 'OPEN' $null }.GetNewClosure()
    $result | Add-Member ScriptMethod verify_read_only_session { param($ready) & $invoke $state 'VERIFY' $ready }.GetNewClosure()
    $result | Add-Member ScriptMethod close_read_only_session { param($ready) & $invoke $state 'CLOSE' $ready }.GetNewClosure()
    return $result
}
Export-ModuleMember -Function New-AtlasSelectedReadBridge
