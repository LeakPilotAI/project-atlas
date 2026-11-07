# Offline accepted-session desktop stop transport contract. No socket, no process
# startup, no legacy stop, and no provider authorization. This module only
# validates a proposed handoff; callers must separately prove ownership.
function Test-AtlasPaperStopHandoff([object]$Handoff = $null) {
    if ($null -eq $Handoff) { throw 'PAPER_STOP_HANDOFF_NOT_ENROLLED' }
    if ($Handoff -isnot [System.Collections.IDictionary]) { throw 'PAPER_STOP_HANDOFF_INVALID' }
    $keys = @($Handoff.Keys | ForEach-Object { [string]$_ })
    if ($keys.Count -ne 5 -or @($keys | Where-Object { $_ -cnotin @('schema','session_id','mode','paper_only','ownership_verified') }).Count -ne 0) {
        throw 'PAPER_STOP_HANDOFF_INVALID'
    }
    if ($Handoff['schema'] -cne 'ATLAS_PAPER_STOP_HANDOFF_V1' -or
        $Handoff['session_id'] -isnot [string] -or
        [string]::IsNullOrWhiteSpace($Handoff['session_id']) -or
        $Handoff['session_id'].Length -gt 128 -or
        $Handoff['mode'] -cnotin @('SHUTDOWN_FLATTEN','EMERGENCY') -or
        $Handoff['paper_only'] -isnot [bool] -or $Handoff['paper_only'] -ne $true -or
        $Handoff['ownership_verified'] -isnot [bool] -or $Handoff['ownership_verified'] -ne $true) {
        throw 'PAPER_STOP_HANDOFF_INVALID'
    }
    # A self-asserted ownership_verified field is not an authority grant.
    throw 'PAPER_STOP_HANDOFF_AUTHORITY_UNAVAILABLE'
}
Export-ModuleMember -Function Test-AtlasPaperStopHandoff
