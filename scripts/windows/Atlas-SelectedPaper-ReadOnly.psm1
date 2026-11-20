# No default launcher, enrollment, issuer, command dispatcher or factory path.
# AcceptedBridge may only be injected by a separately accepted in-process
# composition. A caller object/file/environment value is not production trust.
function Open-AtlasSelectedPaperDashboard([string]$Root, [object]$AcceptedBridge = $null) {
    if ($null -eq $AcceptedBridge) {
        throw 'SELECTED_READ_NOT_ENROLLED: accepted account, resource custody, clock and read-service ownership are required. No service was started.'
    }
    if ($script:selectedReadBridge -and $script:selectedReadBridge -ne $AcceptedBridge) {
        throw 'SELECTED_READ_OWNERSHIP_MISMATCH: existing session retained.'
    }
    $script:selectedReadBridge = $AcceptedBridge
    try {
        $ready = $AcceptedBridge.open_read_only_session()
        $script:selectedReadReady = $ready
        if ($ready.mode -cne 'QD_OPERATIONAL_READ_ONLY' -or
            $ready.host_id -cnotmatch '^[a-f0-9]{32}$' -or
            $ready.url -cnotmatch '^http://127\.0\.0\.1:([1-9][0-9]{0,4})/quality_dips\.html\?mode=selected-paper$' -or
            ([uri]$ready.url).Port -gt 65535 -or
            $ready.process.pid -le 0 -or $ready.process.creation_filetime -le 0 -or
            [string]::IsNullOrWhiteSpace($ready.process.image)) {
            throw 'SELECTED_READ_OWNERSHIP_UNVERIFIED'
        }
        $verified = $AcceptedBridge.verify_read_only_session($ready)
        if ($verified -isnot [bool] -or -not $verified) { throw 'SELECTED_READ_OWNERSHIP_UNVERIFIED' }
        Start-Process -FilePath $ready.url -ErrorAction Stop
    } catch {
        # Bridge owns exact service lifetime. Never dispose unknown ownership or
        # kill by PID/name/port. A failure remains visible and blocks GUI close.
        if ($script:selectedReadReady) { Close-AtlasSelectedPaperDashboard }
        throw
    }
}

function Close-AtlasSelectedPaperDashboard {
    if ($null -eq $script:selectedReadBridge) { return }
    $closed = $script:selectedReadBridge.close_read_only_session($script:selectedReadReady)
    if ($closed -isnot [bool] -or -not $closed) {
        throw 'SELECTED_READ_EXIT_UNCONFIRMED: ownership retained; no forced termination.'
    }
    $script:selectedReadBridge = $null
    $script:selectedReadReady = $null
}

Export-ModuleMember -Function Open-AtlasSelectedPaperDashboard, Close-AtlasSelectedPaperDashboard
