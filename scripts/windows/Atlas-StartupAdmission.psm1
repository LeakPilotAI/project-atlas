# Stage34E: refusal-only boundary. Offline receipts are never production authority.
function Assert-AtlasStartupAdmission {
    param([string]$Boundary, [object]$Evidence = $null)
    throw "ATLAS_STARTUP_ADMISSION_REFUSED [$Boundary]: native identity, protected durable storage, trusted authority and clock acceptance are incomplete. Offline admission evidence cannot authorize production."
}
Export-ModuleMember -Function Assert-AtlasStartupAdmission
