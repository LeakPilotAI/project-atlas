# Read-only CIM/NetTCP state representation check on a disposable loopback listener.
$ErrorActionPreference='Stop'
$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
try {
    $listener.Start()
    $port=$listener.LocalEndpoint.Port
    $cim=@(Get-CimInstance -Namespace root/StandardCimv2 -ClassName MSFT_NetTCPConnection -Filter "LocalPort=$port")
    $tcp=@(Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue)
    $records=@()
    foreach($x in $cim) {
        if($x.OwningProcess -ne $PID){continue}
        $v=$x.PSObject.Properties['State'].Value
        $records+=,[pscustomobject]@{reader='cim';direct_type=if($null -eq $x.State){'null'}else{$x.State.GetType().FullName};direct_string=[string]$x.State;property_type=if($null -eq $v){'null'}else{$v.GetType().FullName};property_string=[string]$v;numeric_state=if($null -eq $x.State){$null}else{[int]$x.State}}
    }
    foreach($x in $tcp) {
        if($x.OwningProcess -ne $PID){continue}
        $v=$x.PSObject.Properties['State'].Value
        $records+=,[pscustomobject]@{reader='nettcp';direct_type=if($null -eq $x.State){'null'}else{$x.State.GetType().FullName};direct_string=[string]$x.State;property_type=if($null -eq $v){'null'}else{$v.GetType().FullName};property_string=[string]$v;numeric_state=if($null -eq $x.State){$null}else{[int]$x.State}}
    }
    [ordered]@{schema='ATLAS_SOCKET_PROVIDER_STATE_TYPES_V1';records=$records;socket_accepting=$listener.Server.IsBound;endpoints_redacted=$true;operational_listener_accepted=$false;financial_authorized=$false}|ConvertTo-Json -Depth 5 -Compress
} finally {$listener.Stop()}
