# Gate probe imports only the independent authorization module, never app.main.
function Get-AtlasFullStartupGate([string]$Root) {
    $python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
    $gate = Join-Path $Root 'backend\app\core\production_startup_lock.py'
    if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $gate)) {
        return 'BLOCKED: Startup authorization evidence unavailable.'
    }
    # Current contract is an unconditional refusal. Do not reinterpret a changed module
    # as permission: future integration requires independent release acceptance.
    $expected = 'raise ProductionStartupRefused('
    if (-not ([IO.File]::ReadAllText($gate).Contains($expected))) {
        return 'BLOCKED: Startup contract changed; independent acceptance required.'
    }
    return 'BLOCKED: Atlas production startup is disabled. Use the separate offline observation entry point.'
}

function Get-AtlasFullFrontendDecision([string]$Root) {
    return (Get-AtlasFullStartupGate $Root) + ' Full frontend ownership/readiness is not established; read-only dashboard remains separate.'
}
function Invoke-AtlasPaperStop([object]$AcceptedSession = $null, [switch]$Emergency, [switch]$RequireFinished) {
    if ($null -eq $AcceptedSession -or $AcceptedSession.verify_session() -isnot [bool] -or
        -not $AcceptedSession.verify_session()) {
        throw 'PAPER_STOP_NOT_ENROLLED: no accepted owned session; no legacy stop fallback.'
    }
    $mode = if ($Emergency) { 'EMERGENCY' } else { 'SHUTDOWN_FLATTEN' }
    $result = $AcceptedSession.request_stop($mode)
    if ($result.schema -cne 'QD_CONTROL_STOP_V1' -or
        $result.phase -cnotin @('FINISHED', 'IN_PROGRESS')) {
        throw 'PAPER_STOP_OUTCOME_UNVERIFIED'
    }
    # Window close must not discard a pending financial drain. The normal Stop
    # button may still display IN_PROGRESS while the coordinator retains work.
    if ($RequireFinished -and $result.phase -cne 'FINISHED') {
        throw 'PAPER_STOP_STILL_IN_PROGRESS: keep the Control Center open until drain finishes.'
    }
    if ($RequireFinished -and $null -eq $result.outcome) {
        throw 'PAPER_STOP_OUTCOME_UNVERIFIED: no finished outcome; ownership retained.'
    }
    return $result
}
function Format-AtlasIEXDataStatus([object]$Snapshot = $null) {
    if ($null -eq $Snapshot -or $Snapshot.schema -cne 'ATLAS_ALPACA_IEX_VIEW_V1' -or
        $Snapshot.feed -cne 'IEX' -or $Snapshot.scope -cne 'SINGLE_EXCHANGE_NOT_NBBO' -or
        $Snapshot.paper_startup_authorized -ne $false) { return 'IEX data: UNAVAILABLE; PAPER authorization: NO' }
    $fresh = @($Snapshot.quotes | Where-Object { $_.state -ceq 'FRESH' }).Count
    return "IEX data: $($Snapshot.connection), fresh quotes $fresh (single exchange, NOT NBBO); PAPER authorization: NO"
}
function Format-AtlasUnifiedPaperStatus([object]$Snapshot = $null) {
    if ($null -eq $Snapshot -or $Snapshot.schema -cne 'ATLAS_UNIFIED_PAPER_VIEW_V1' -or
        $Snapshot.startup_authorized -ne $false -or $null -ne $Snapshot.total_cash -or
        $null -ne $Snapshot.total_equity) { return 'Multi-market PAPER: UNAVAILABLE; startup authorization: NO' }
    $rows = @()
    foreach ($name in @('QUALITY_DIPS', 'HYPERLIQUID')) {
        $row = $Snapshot.lanes.$name
        if ($null -eq $row -or $row.lane -cne $name) { $rows += "${name}: UNAVAILABLE"; continue }
        $age = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $row.at
        $connection = if ($age -lt 0 -or $age -gt 5) { 'STALE' } else { $row.connection }
        $rows += "${name}: $connection / $($row.session)"
    }
    return ($rows -join '; ') + '; separate accounts; startup authorization: NO'
}
Export-ModuleMember -Function Get-AtlasFullStartupGate, Get-AtlasFullFrontendDecision, Invoke-AtlasPaperStop, Format-AtlasIEXDataStatus, Format-AtlasUnifiedPaperStatus
