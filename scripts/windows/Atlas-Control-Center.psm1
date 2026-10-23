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
Export-ModuleMember -Function Get-AtlasFullStartupGate, Get-AtlasFullFrontendDecision
