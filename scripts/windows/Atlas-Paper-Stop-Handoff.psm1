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
# Offline in-process bridge only. The caller must supply the actual accepted
# session object, never deserialize a caller-supplied "verified" boolean.
function Invoke-AtlasAcceptedPaperStopHandoff([object]$Handoff = $null, [object]$AcceptedSession = $null) {
    if ($null -eq $Handoff -or $Handoff -isnot [System.Collections.IDictionary]) {
        throw 'PAPER_STOP_HANDOFF_NOT_ENROLLED'
    }
    $keys = @($Handoff.Keys | ForEach-Object { [string]$_ })
    if ($keys.Count -ne 5 -or @($keys | Where-Object { $_ -cnotin @('schema','session_id','mode','paper_only','ownership_verified') }).Count -ne 0 -or
        $Handoff['schema'] -cne 'ATLAS_PAPER_STOP_HANDOFF_V1' -or
        $Handoff['session_id'] -isnot [string] -or
        [string]::IsNullOrWhiteSpace($Handoff['session_id']) -or $Handoff['session_id'].Length -gt 128 -or
        $Handoff['mode'] -cnotin @('SHUTDOWN_FLATTEN','EMERGENCY') -or
        $Handoff['paper_only'] -isnot [bool] -or $Handoff['paper_only'] -ne $true -or
        $Handoff['ownership_verified'] -isnot [bool] -or $Handoff['ownership_verified'] -ne $true) {
        throw 'PAPER_STOP_HANDOFF_INVALID'
    }
    if ($null -eq $AcceptedSession) { throw 'PAPER_STOP_HANDOFF_AUTHORITY_UNAVAILABLE' }
    # The session's own verification is the only authority; identity must match.
    # Re-check the owner identity after verification: an object changing its
    # session binding between checks must not receive a stop request.
    $beforeId = $AcceptedSession.session_id
    if ($beforeId -isnot [string] -or $beforeId -cne $Handoff['session_id']) {
        throw 'PAPER_STOP_HANDOFF_SESSION_UNVERIFIED'
    }
    $verified = $AcceptedSession.verify_session()
    if ($verified -isnot [bool] -or -not $verified -or
        $AcceptedSession.session_id -isnot [string] -or
        $AcceptedSession.session_id -cne $Handoff['session_id']) {
        throw 'PAPER_STOP_HANDOFF_SESSION_UNVERIFIED'
    }
    $result = $AcceptedSession.request_stop($Handoff['mode'])
    if ($AcceptedSession.session_id -isnot [string] -or
        $AcceptedSession.session_id -cne $beforeId) {
        throw 'PAPER_STOP_HANDOFF_SESSION_CHANGED'
    }
    if ($null -eq $result -or $result.schema -cne 'QD_CONTROL_STOP_V1' -or
        $result.phase -cne 'FINISHED' -or $null -eq $result.outcome -or
        $result.outcome.schema -cne 'QD_AUTO_SHUTDOWN_V1' -or
        $result.outcome.mode -cne $Handoff['mode'] -or
        $result.outcome.status -cne 'FLATTENED' -or
        $result.outcome.position_state -cne 'FLAT' -or
        $result.outcome.process_shutdown -cne 'VERIFIED_EXIT') {
        throw 'PAPER_STOP_HANDOFF_SHUTDOWN_UNVERIFIED'
    }
    return $result
}
Export-ModuleMember -Function Test-AtlasPaperStopHandoff, Invoke-AtlasAcceptedPaperStopHandoff
