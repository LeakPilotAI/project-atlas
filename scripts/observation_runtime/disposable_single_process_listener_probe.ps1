# Disposable .NET loopback listener; all observations in one PowerShell process.
param([ValidateRange(2,5)][int]$Rounds=3)
$ErrorActionPreference='Stop'
$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
try {
    $listener.Start()
    $port=$listener.LocalEndpoint.Port
    $ownerPid=$PID
    $samples=@()
    for($i=0;$i -lt $Rounds;$i++) {
        $cim=@(Get-CimInstance -Namespace root/StandardCimv2 -ClassName MSFT_NetTCPConnection -Filter "LocalPort=$port")
        $tcp=@(Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue)
        $raw=@(& netstat.exe -ano -p tcp)
        $netstatMatches=@($raw|Where-Object {$_ -match (':'+$port+'\s')})
        $samples+=,[pscustomobject]@{
            cim_states=@($cim|Where-Object {$_.OwningProcess -eq $ownerPid}|ForEach-Object {[int]$_.State})
            cmdlet_states=@($tcp|Where-Object {$_.OwningProcess -eq $ownerPid}|ForEach-Object {if($null -eq $_.State){$null}else{[string]$_.State}})
            netstat_listener_present=[bool](@($netstatMatches|Where-Object {$_ -match 'LISTENING'}).Count -gt 0)
            socket_accepting=$listener.Server.IsBound
        }
        if($i+1 -lt $Rounds){Start-Sleep -Milliseconds 200}
    }
    [ordered]@{
        schema='ATLAS_SINGLE_PROCESS_DISPOSABLE_LISTENER_V1'
        rounds=$Rounds
        samples=$samples
        endpoints_redacted=$true
        operational_listener_accepted=$false
        financial_authorized=$false
    }|ConvertTo-Json -Depth 6 -Compress
} finally {
    $listener.Stop()
}
