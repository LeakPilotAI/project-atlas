# Read-only, port-confined diagnostic. No provider, service or application launch.
param([Parameter(Mandatory=$true)][ValidateRange(1,65535)][int]$Port)
$ErrorActionPreference='Stop'
$result=[ordered]@{schema='QD_SOCKET_CIM_RAW_V1';started_ticks=[Diagnostics.Stopwatch]::GetTimestamp();
    frequency=[Diagnostics.Stopwatch]::Frequency;collected_utc=[DateTime]::UtcNow.ToString('o');rows=@();error=$null}
try {
    $rows=@(Get-CimInstance -Namespace root/StandardCimv2 -ClassName MSFT_NetTCPConnection -Filter ('LocalPort='+$Port) -ErrorAction Stop)
    if($rows.Count -gt 1024){throw 'SCOPED_CIM_ROW_CAPACITY'}
    foreach($row in $rows){
        $properties=@($row.CimInstanceProperties|Where-Object {$_.Name -in @('LocalAddress','LocalPort','RemoteAddress','RemotePort','State','OwningProcess')}|ForEach-Object {
            [ordered]@{name=$_.Name;cim_type=$_.CimType.ToString();value=$_.Value;clr_type=$(if($null -eq $_.Value){$null}else{$_.Value.GetType().FullName})}
        })
        $result.rows+=,[ordered]@{direct_state=$row.State;direct_state_type=$(if($null -eq $row.State){$null}else{$row.State.GetType().FullName});
            direct_owner=$row.OwningProcess;properties=$properties;instance_type=$row.GetType().FullName}
    }
} catch {$result.error=$_.Exception.ToString()}
$result.finished_ticks=[Diagnostics.Stopwatch]::GetTimestamp()
$result|ConvertTo-Json -Depth 8 -Compress
if($null -ne $result.error){exit 2}
