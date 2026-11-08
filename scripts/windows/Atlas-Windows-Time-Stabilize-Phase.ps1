# Windows 11 standalone W32Time steady phase correction (bounded host-only repair).
# One-time elevated operator action: -ExecuteApproved. Default is read-only.
# Never changes NTP peers, poll interval, Atlas clock thresholds, accounts,
# startup shortcuts, Genesis, trading, time service state or current system time.
# See https://learn.microsoft.com/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings
#Requires -Version 5.1
param([switch]$ExecuteApproved)
$ErrorActionPreference = 'Stop'

$registry = 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config'
$ntp = 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'
$policy = 'HKLM:\SOFTWARE\Policies\Microsoft\W32Time\Config'
$ntpPolicy = 'HKLM:\SOFTWARE\Policies\Microsoft\W32Time\TimeProviders\NtpClient'
$trusted = 'time.cloudflare.com,0x8 time.google.com,0x8'
$w32tm = Join-Path ([Environment]::SystemDirectory) 'w32tm.exe'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$receipt = Join-Path $root 'logs\diagnostics\atlas-windows-time-phase-stability-20261108.json'

function Assert-AtlasHostState {
    $machine = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
    if ($machine.PartOfDomain -ne $false -or $machine.DomainRole -ne 0) {
        throw 'ATLAS_W32TIME_DOMAIN_MANAGED_HOST_REFUSED'
    }
    if (Test-Path -LiteralPath $policy) {
        $gp = Get-ItemProperty -LiteralPath $policy -ErrorAction Stop
        if ($null -ne $gp.PhaseCorrectRate) {
            throw 'ATLAS_W32TIME_PHASE_GROUP_POLICY_OVERRIDE_REFUSED'
        }
    }
    if (Test-Path -LiteralPath $ntpPolicy) {
        $gpNtp = Get-ItemProperty -LiteralPath $ntpPolicy -ErrorAction Stop
        if ($null -ne $gpNtp.NtpServer -or $null -ne $gpNtp.Type) {
            throw 'ATLAS_W32TIME_NTP_GROUP_POLICY_OVERRIDE_REFUSED'
        }
    }
    $source = Get-ItemProperty -LiteralPath $ntp -ErrorAction Stop
    $cfg = Get-ItemProperty -LiteralPath $registry -ErrorAction Stop
    $svc = Get-Service -Name W32Time -ErrorAction Stop
    if ($source.Type -cne 'NTP' -or $source.NtpServer -cne $trusted -or
        $svc.Status -ne 'Running' -or $cfg.MinPollInterval -ne 6 -or
        $cfg.MaxPollInterval -ne 6 -or $cfg.FrequencyCorrectRate -ne 4 -or
        $cfg.UpdateInterval -ne 360000 -or $cfg.MaxAllowedPhaseOffset -ne 1 -or
        $cfg.MaxPosPhaseCorrection -ne 54000 -or $cfg.MaxNegPhaseCorrection -ne 54000) {
        throw 'ATLAS_W32TIME_UNREVIEWED_CONFIGURATION_REFUSED'
    }
    if ($cfg.PhaseCorrectRate -notin @(1, 7)) {
        throw 'ATLAS_W32TIME_UNREVIEWED_PHASE_SETTING_REFUSED'
    }
    return @{ PhaseCorrectRate = [int]$cfg.PhaseCorrectRate; Source = [string]$source.NtpServer }
}

$state = Assert-AtlasHostState
if (-not $ExecuteApproved) {
    Write-Output ('ATLAS_W32TIME_READ_ONLY_PHASE_CURRENT=' + $state.PhaseCorrectRate)
    Write-Output 'ATLAS_W32TIME_DOCUMENTED_STANDALONE_DEFAULT_PHASE=7'
    Write-Output 'ATLAS_W32TIME_NO_MODIFICATION; USE_SEPARATE_ELEVATED_EXECUTE_APPROVED'
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'ATLAS_W32TIME_ELEVATED_ADMIN_REQUIRED'
}
if ($state.PhaseCorrectRate -eq 7) {
    Write-Output 'ATLAS_W32TIME_PHASE_7_ALREADY_CONFIGURED_NO_MUTATION'
    Write-Output 'NOT_ATLAS_CLOCK_180_SECOND_QUALIFICATION'
    exit 0
}
if (Test-Path -LiteralPath $receipt) {
    throw 'ATLAS_W32TIME_PRIOR_APPLY_RECEIPT_EXISTS_MANUAL_REVIEW_REQUIRED'
}
$signature = Get-AuthenticodeSignature -LiteralPath $w32tm
if ($signature.Status -ne 'Valid' -or
    $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)') {
    throw 'ATLAS_W32TIME_WINDOWS_SYSTEM_TOOL_SIGNATURE_REFUSED'
}
$old = $state.PhaseCorrectRate
$changed = $false
try {
    # Exactly one Windows registry value, reverting to the documented default
    # for a non-domain-joined/standalone Windows client. No clock steps/resync.
    Set-ItemProperty -LiteralPath $registry -Name PhaseCorrectRate -Value 7 -ErrorAction Stop
    $changed = $true
    $null = & $w32tm /config /update
    if ($LASTEXITCODE -ne 0) {
        throw 'ATLAS_W32TIME_CONFIG_UPDATE_REFUSED'
    }
    $after = Assert-AtlasHostState
    if ($after.PhaseCorrectRate -ne 7 -or $after.Source -cne $trusted) {
        throw 'ATLAS_W32TIME_PHASE_READBACK_REFUSED'
    }
    $effective = (& $w32tm /query /configuration 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or
        $effective -notmatch '(?m)^PhaseCorrectRate:\s*7\s*\(') {
        throw 'ATLAS_W32TIME_EFFECTIVE_CONFIG_READBACK_REFUSED'
    }
    $evidence = [ordered]@{
        schema = 'ATLAS_W32TIME_STANDALONE_PHASE_STABILITY_CHANGE_V1'
        utc = [DateTime]::UtcNow.ToString('o')
        host_role = 'STANDALONE_WORKGROUP_WINDOWS_CLIENT'
        source = $trusted
        phase_correct_rate_previous = $old
        phase_correct_rate_verified = 7
        min_poll_interval = 6
        max_poll_interval = 6
        effect = 'ONLY_W32TIME_PHASE_CORRECT_RATE_UPDATED'
        continuous_clock_180_seconds_accepted = $false
        atlas_code_installed = $false
        financial_authority = $false
        auto_start_atlas = $false
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $bytes = $utf8.GetBytes(($evidence | ConvertTo-Json -Compress) + "`n")
    $stream = [System.IO.File]::Open($receipt, [System.IO.FileMode]::CreateNew,
                                    [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    Write-Output 'ATLAS_W32TIME_STANDALONE_PHASE_7_APPLIED_AND_NATIVE_READBACK_PASS'
    Write-Output ('ATLAS_W32TIME_CHANGE_RECEIPT=' + $receipt)
    Write-Output 'NOT_A_PROOF_OF_SUSTAINED_180_SECOND_CLOCK_QUALITY_OR_FINANCIAL_START'
}
catch {
    $cause = $_
    if ($changed) {
        try {
            Set-ItemProperty -LiteralPath $registry -Name PhaseCorrectRate -Value $old -ErrorAction Stop
            $null = & $w32tm /config /update
            if ($LASTEXITCODE -ne 0 -or (Get-ItemProperty -LiteralPath $registry).PhaseCorrectRate -ne $old) {
                throw 'ATLAS_W32TIME_RESTORE_UNVERIFIED'
            }
            Write-Warning 'ATLAS_W32TIME_APPLY_FAILED_ORIGINAL_PHASE_SETTING_RESTORED'
        }
        catch {
            Write-Warning 'ATLAS_W32TIME_ROLLBACK_UNVERIFIED_HOST_ADMIN_REVIEW_REQUIRED'
        }
    }
    throw $cause
}
