# Offline dependency-injected sequencing only. Not imported by production manager.
function Invoke-AtlasPaperShutdownFixture {
    param([scriptblock]$Quiesce, [scriptblock]$Drain, [scriptblock]$Liquidate,
          [scriptblock]$ReconcileAndReport, [scriptblock]$StopOwnedFixture)
    foreach ($step in @($Quiesce,$Drain,$Liquidate,$ReconcileAndReport,$StopOwnedFixture)) {
        if (-not $step) { throw 'Missing fixture shutdown step.' }
    }
    $completed = @()
    try {
        foreach ($item in @(
            @{name='quiesce'; action=$Quiesce}, @{name='drain'; action=$Drain},
            @{name='liquidate'; action=$Liquidate}, @{name='report'; action=$ReconcileAndReport},
            @{name='stop-owned-fixture'; action=$StopOwnedFixture}
        )) {
            $result = & $item.action
            if ($result -isnot [bool] -or $result -ne $true) { throw "Unconfirmed $($item.name)" }
            $completed += $item.name
        }
        return @{outcome='COMPLETE_FIXTURE_ONLY'; completed=$completed; production_authorized=$false}
    } catch {
        return @{outcome='INCOMPLETE'; completed=$completed; error=$_.Exception.Message; production_authorized=$false}
    }
}
Export-ModuleMember -Function Invoke-AtlasPaperShutdownFixture
