# Future approved desktop PAPER Stop shortcut target (source-only for now).
# No launcher, credential, port, provider, account or financial writer access.
# This request never certifies a closed trade; the accepted installed owner must.
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Atlas-Paper-Owned-Stop-Signal.psm1') -Force -ErrorAction Stop
try {
    $result = Request-AtlasPaperOwnedStopSignal
    if ($result.schema -cne 'ATLAS_PAPER_STOP_SIGNAL_REQUEST_V1' -or
        $result.status -cne 'REQUESTED_NOT_VERIFIED' -or
        $result.financial_flatness_verified -ne $false) {
        throw 'PAPER_DESKTOP_STOP_SIGNAL_RECEIPT_UNVERIFIED'
    }
    Write-Host 'Atlas PAPER Stop requested from the owning session.' -ForegroundColor Yellow
    Write-Host 'Financial flattening and process exit are NOT YET CONFIRMED by this shortcut.' -ForegroundColor Yellow
    Write-Host 'Check the owning Atlas Control Center for the verified two-account receipt.' -ForegroundColor Yellow
} catch {
    Write-Error ('Atlas PAPER Stop request REFUSED or unverified: ' + $_.Exception.Message)
    exit 1
}
