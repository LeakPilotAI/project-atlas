# Source-only, opt-in client for an explicitly bound, already-owned unified
# PAPER session. Never discovers tokens, sessions, ports, readers or providers.
# No call occurs on import; physical Stop Atlas shortcut remains observation-only.
function Invoke-AtlasBoundPaperDesktopStop {
    param([object]$Binding = $null, [scriptblock]$Sender = $null)

    if ($null -eq $Binding -or $Binding -isnot [System.Collections.IDictionary] -or
        $null -eq $Sender) {
        throw 'PAPER_DESKTOP_STOP_ACCEPTED_BINDING_AND_SENDER_REQUIRED'
    }
    $keys = @($Binding.Keys | ForEach-Object { [string]$_ })
    if ($keys.Count -ne 4 -or
        @($keys | Where-Object { $_ -cnotin @('schema','origin','session_id','control_token') }).Count -ne 0 -or
        $Binding['schema'] -cne 'ATLAS_PAPER_DESKTOP_STOP_BINDING_V1' -or
        $Binding['origin'] -isnot [string] -or
        $Binding['origin'] -cnotmatch '^http://127\.0\.0\.1:([1-9][0-9]{0,4})$' -or
        [int]$Matches[1] -gt 65535 -or
        $Binding['session_id'] -isnot [string] -or
        [string]::IsNullOrWhiteSpace($Binding['session_id']) -or
        $Binding['session_id'].Length -gt 128 -or
        $Binding['control_token'] -isnot [string] -or
        $Binding['control_token'] -cnotmatch '^[A-Za-z0-9_-]{32,256}$') {
        throw 'PAPER_DESKTOP_STOP_EXACT_LOCAL_BINDING_REQUIRED'
    }
    # A client-side binding or token proves no writer authority. Only the
    # *installed* /stop-session endpoint verifies the current native session,
    # does the actual Stop, and independently reads its durable receipt.
    $origin = $Binding['origin']
    $sessionId = $Binding['session_id']
    $token = $Binding['control_token']
    $mode = 'SHUTDOWN_FLATTEN'
    $url = $origin + '/_atlas/control/stop-session'
    $payload = @{session_id=$sessionId;mode=$mode}
    try {
        $result = & $Sender $url $origin $token $payload
    } catch {
        # A request may have reached the financial owner even when this
        # client received an error. Never replay or report Stop completed.
        throw 'PAPER_DESKTOP_STOP_DISPATCH_UNVERIFIED'
    }
    try {
        # Accept JSON-compatible PS objects only, not arbitrary caller-side
        # success flags. JSON roundtrip preserves exact field names on PS 5.1.
        if ($null -eq $result) { throw 'EMPTY_RESULT' }
        $wire = ConvertTo-Json -InputObject $result -Depth 20 -Compress -ErrorAction Stop
        if ($wire.Length -gt 32768) { throw 'OVERSIZE_RESULT' }
        $receipt = ConvertFrom-Json -InputObject $wire -ErrorAction Stop
        $outcome = $receipt.outcome
        $lanes = $outcome.lanes
        $names = if ($null -eq $lanes) { @() } else { @($lanes.PSObject.Properties.Name) }
        if ($receipt.schema -cne 'QD_CONTROL_STOP_V1' -or
            $receipt.phase -cne 'FINISHED' -or
            $null -eq $outcome -or
            $outcome.schema -cne 'QD_AUTO_SHUTDOWN_V1' -or
            $outcome.mode -cne $mode -or
            $outcome.status -cne 'FLATTENED' -or
            $outcome.position_state -cne 'FLAT' -or
            $outcome.process_shutdown -cne 'VERIFIED_EXIT' -or
            $names.Count -ne 2 -or
            -not ($names -ccontains 'QUALITY_DIPS') -or
            -not ($names -ccontains 'HYPERLIQUID') -or
            $lanes.QUALITY_DIPS.state -cne 'ACKNOWLEDGED_FLAT_AND_DRAINED' -or
            $lanes.HYPERLIQUID.state -cne 'ACKNOWLEDGED_FLAT_AND_DRAINED') {
            throw 'RECEIPT_NOT_BOTH_LANES_FLAT'
        }
        return $receipt
    } catch {
        throw 'PAPER_DESKTOP_STOP_RECEIPT_UNVERIFIED'
    }
}

function Send-AtlasExplicitPaperStopHttp {
    param([string]$Url, [string]$Origin, [string]$ControlToken, [object]$Payload)
    # This sends only to a validated per-owner loopback route when explicitly
    # invoked. Binding/session generation and real authorization remain external.
    if ($Origin -cnotmatch '^http://127\.0\.0\.1:([1-9][0-9]{0,4})$' -or
        [int]$Matches[1] -gt 65535 -or
        $Url -cne ($Origin + '/_atlas/control/stop-session') -or
        $ControlToken -cnotmatch '^[A-Za-z0-9_-]{32,256}$' -or
        $null -eq $Payload -or $Payload['mode'] -cne 'SHUTDOWN_FLATTEN' -or
        $Payload['session_id'] -isnot [string]) {
        throw 'PAPER_DESKTOP_STOP_HTTP_BINDING_REQUIRED'
    }
    return Invoke-RestMethod -Method Post -Uri $Url -ContentType 'application/json' `
        -Headers @{Origin=$Origin;'X-Atlas-Control'=$ControlToken} `
        -Body ($Payload | ConvertTo-Json -Compress -Depth 4) `
        -MaximumRedirection 0 -TimeoutSec 15 -ErrorAction Stop
}
Export-ModuleMember -Function Invoke-AtlasBoundPaperDesktopStop, Send-AtlasExplicitPaperStopHttp
