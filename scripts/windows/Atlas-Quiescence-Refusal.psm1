# No operational caller imports this module. Observations cannot grant shutdown.
function Get-AtlasQuiescenceRefusal {
    param($Expected, $Before, $After)
    $matched = $true
    foreach ($key in @('pid','created_utc','executable','command_line','run_id','root')) {
        if (-not $Expected -or -not $Before -or -not $After -or
            [string]::IsNullOrWhiteSpace([string]$Expected.$key) -or
            [string]$Expected.$key -cne [string]$Before.$key -or
            [string]$Expected.$key -cne [string]$After.$key) { $matched = $false }
    }
    return @{identity_observations_match=$matched;quiescence='UNKNOWN';shutdown_authorized=$false;
             reason='Fresh native identity, writer admission fence and independent drain acceptance required.'}
}
Export-ModuleMember -Function Get-AtlasQuiescenceRefusal
