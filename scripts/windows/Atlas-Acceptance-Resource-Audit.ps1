# Acceptance-orchestration observer only. No application start, Stop or selection.
param([int]$OwnedPort,[string]$OwnedAddress='127.0.0.1')
$ErrorActionPreference='Stop'
$result=[ordered]@{schema='QD_SOCKET_CLEANUP_CIM_V1';protocol='TCP';query_port=$OwnedPort;query_address=$OwnedAddress;
    started_ticks=[Diagnostics.Stopwatch]::GetTimestamp();finished_ticks=$null;frequency=[Diagnostics.Stopwatch]::Frequency;
    collected_utc=[DateTime]::UtcNow.ToString('o');rows=@();non_helpers=$null;error=$null}
try {
    $target=[Net.IPAddress]::Parse($OwnedAddress)
    if($OwnedPort -lt 1 -or $OwnedPort -gt 65535 -or -not [Net.IPAddress]::IsLoopback($target)){throw 'EXACT_LOOPBACK_ENDPOINT_REQUIRED'}
    $connections=@(Get-CimInstance -Namespace root/StandardCimv2 -ClassName MSFT_NetTCPConnection -Filter ('LocalPort='+$OwnedPort) -ErrorAction Stop)
    if($connections.Count -gt 1024){throw 'SOCKET_ENUMERATION_CAPACITY'}
    foreach($connection in $connections){
        $local=[Net.IPAddress]::Parse($connection.LocalAddress)
        $family=if($local.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork){4}else{6}
        $ownerPresent=($null -ne $connection.PSObject.Properties['OwningProcess'] -and $null -ne $connection.OwningProcess)
        $owner=if($ownerPresent){$connection.OwningProcess}else{$null}
        $result.rows+=@{protocol='TCP';family=$family;local_address=$connection.LocalAddress;local_port=$connection.LocalPort;
            remote_address=$connection.RemoteAddress;remote_port=$connection.RemotePort;state=$connection.State;
            owner_present=$ownerPresent;owner_pid=$owner}
    }
    $filter="ExecutablePath LIKE 'D:\\AtlasRuntime\\%' OR ExecutablePath LIKE 'D:\\Work\\Project Atlas\\%' OR (Name='python.exe' AND CommandLine LIKE '%D:\\Work\\Project Atlas%')"
    $processes=@(Get-CimInstance Win32_Process -Filter $filter)
    # Windows PowerShell 5.1 emits a JSON array as one pipeline object.
    # Deserialize first; enumerate the resulting array in a separate step.
    $parsedClaims=ConvertFrom-Json -InputObject $env:ATLAS_AUTH_HELPER_CLAIMS
    if($null -eq $parsedClaims -or $parsedClaims -isnot [System.Array]){throw 'DIAGNOSTIC_HELPER_CLAIMS_ARRAY_REQUIRED'}
    $claims=@($parsedClaims)
    if($claims.Count -eq 0){throw 'DIAGNOSTIC_HELPER_CLAIMS_EMPTY'}
    foreach($identity in $claims){
        if($null -eq $identity -or $identity -is [System.Array] -or
            (($identity.PSObject.Properties.Name|Sort-Object)-join ',') -cne 'created,image,pid' -or
            ($identity.pid -isnot [int] -and $identity.pid -isnot [long]) -or
            $identity.pid -le 0 -or $identity.pid -gt [uint32]::MaxValue -or
            ($identity.created -isnot [int] -and $identity.created -isnot [long]) -or
            $identity.created -le 0 -or $identity.image -isnot [string] -or
            [string]::IsNullOrWhiteSpace($identity.image)){throw 'DIAGNOSTIC_HELPER_CLAIM_FIELD_TYPE'}
    }
    $others=@()
    foreach($candidate in $processes){
        $claim=@($claims|Where-Object {$_.pid -eq $candidate.ProcessId})
        if($claim.Count -ge 1){
            $live=[Diagnostics.Process]::GetProcessById($candidate.ProcessId)
            try {
                foreach($identity in $claim){
                    # Preserve scalar comparison evidence privately before any refusal.
                    $observedCreated=$live.StartTime.ToUniversalTime().ToFileTimeUtc()
                    $observedImage=$live.MainModule.FileName
                    if(-not $result.Contains('helper_identity_comparisons')){$result.helper_identity_comparisons=@()}
                    $result.helper_identity_comparisons+=@{expected_pid=$identity.pid;observed_pid=$live.Id;expected_created=$identity.created.ToString();observed_created=$observedCreated.ToString();expected_image=$identity.image;observed_image=$observedImage;pid_equal=($live.Id -eq $identity.pid);created_equal=($observedCreated -eq $identity.created);image_equal=($observedImage -ieq $identity.image)}
                    if($live.StartTime.ToUniversalTime().ToFileTimeUtc() -ne $identity.created -or $live.MainModule.FileName -ine $identity.image){throw 'DIAGNOSTIC_HELPER_OWNERSHIP_MISMATCH'}
                }
            } finally {$live.Dispose()}
        }else{$others+=,$candidate}
    }
    $result.non_helpers=$others.Count
    if($others.Count -ne 0){throw 'APP_PROCESS_NOT_RELEASED'}
} catch {$result.error=$_.Exception.ToString()}
$result.finished_ticks=[Diagnostics.Stopwatch]::GetTimestamp()
$result|ConvertTo-Json -Depth 8 -Compress
# Query failures remain explicit JSON evidence, never an empty successful table.
if($null -ne $result.error){exit 2}
