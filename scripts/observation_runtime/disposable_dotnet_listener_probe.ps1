# Disposable .NET listener control; never starts an Atlas host or grants authority.
param([ValidateRange(0,5)][int]$SettleSeconds=0,[switch]$IPv6Loopback)
$ErrorActionPreference='Stop'
$bindAddress=if($IPv6Loopback){[Net.IPAddress]::IPv6Loopback}else{[Net.IPAddress]::Loopback}
$listener=[Net.Sockets.TcpListener]::new($bindAddress,0)
try {
    $listener.Start()
    if($SettleSeconds -gt 0){Start-Sleep -Seconds $SettleSeconds}
    $port=$listener.LocalEndpoint.Port
    $pidOwner=$PID
    $cim=@(Get-CimInstance -Namespace root/StandardCimv2 -ClassName MSFT_NetTCPConnection -Filter "LocalPort=$port")
    $tcp=@(Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue)
    $raw=@(& netstat.exe -ano)
    $matches=@($raw|Where-Object {$_ -match (':'+$port+'\s')})
    [ordered]@{
        schema='ATLAS_DISPOSABLE_DOTNET_LISTENER_V1'
        port=$port
        bind_address=$bindAddress.ToString()
        settle_seconds=$SettleSeconds
        expected_pid=$pidOwner
        cim=@($cim|ForEach-Object {@{pid=$_.OwningProcess;state=if($null -eq $_.State){$null}else{[int]$_.State};address=$_.LocalAddress}})
        nettcp=@($tcp|ForEach-Object {@{pid=$_.OwningProcess;state=if($null -eq $_.State){$null}else{[string]$_.State};address=$_.LocalAddress}})
        netstat_scoped=@($matches)
        operational_listener_accepted=$false
        financial_authorized=$false
    }|ConvertTo-Json -Depth 6 -Compress
} finally {
    $listener.Stop()
}
