# Explicitly approved administrator-only Windows Time maximum poll cap.
# Never installs or starts Atlas, changes NTP peers, or relaxes Atlas clock gates.
# Requires real Windows Administrator elevation and a separate operator decision.
#Requires -Version 5.1
param([switch]$ExecuteApproved)
$ErrorActionPreference='Stop'

if (-not $ExecuteApproved) {
    throw 'ATLAS_V4_POLL_CAP_SEPARATE_OPERATOR_APPROVAL_REQUIRED'
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'ATLAS_V4_POLL_CAP_ELEVATED_ADMIN_REQUIRED'
}

$ntp='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'
$config='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config'
$policy='HKLM:\SOFTWARE\Policies\Microsoft\W32time\Config'
$trusted='time.cloudflare.com,0x8 time.google.com,0x8'
$systemW32tm=Join-Path ([Environment]::SystemDirectory) 'w32tm.exe'
if (Test-Path -LiteralPath $policy) {
    $policyValue=Get-ItemProperty -LiteralPath $policy -ErrorAction Stop
    if ($null -ne $policyValue.MaxPollInterval) {
        throw 'ATLAS_V4_POLL_CAP_GROUP_POLICY_OVERRIDE_REFUSED'
    }
}
$source=Get-ItemProperty -LiteralPath $ntp -ErrorAction Stop
$settings=Get-ItemProperty -LiteralPath $config -ErrorAction Stop
$service=Get-Service -Name 'W32Time' -ErrorAction Stop
if ($source.Type -cne 'NTP' -or $source.NtpServer -cne $trusted -or
    $service.Status -ne 'Running' -or
    $settings.MinPollInterval -ne 6 -or
    $settings.MaxPollInterval -notin @(6,15)) {
    throw 'ATLAS_V4_POLL_CAP_NATIVE_SETTINGS_CHANGED'
}
$sig=Get-AuthenticodeSignature -LiteralPath $systemW32tm
if ($sig.Status -ne 'Valid' -or
    $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)') {
    throw 'ATLAS_V4_POLL_CAP_WINDOWS_TOOL_SIGNATURE_REFUSED'
}

$previous=[int]$settings.MaxPollInterval
if ($previous -eq 6) {
    Write-Output 'ATLAS_V4_WINDOWS_TIME_MAXPOLL_ALREADY_6_VERIFY_ONLY_NO_CHANGE'
    exit 0
}

# Microsoft-supported 2^6=64 second maximum polling interval.
# NO resync/restart: accumulated Windows Time quality must converge naturally.
try {
    Set-ItemProperty -LiteralPath $config -Name 'MaxPollInterval' -Value 6 -ErrorAction Stop
    & $systemW32tm '/config' '/update'
    if ($LASTEXITCODE -ne 0) {
        throw ('ATLAS_V4_POLL_CAP_WINDOWS_UPDATE_REFUSED:' + $LASTEXITCODE)
    }
    $after=Get-ItemProperty -LiteralPath $config -ErrorAction Stop
    $sourceAfter=Get-ItemProperty -LiteralPath $ntp -ErrorAction Stop
    if ($after.MaxPollInterval -ne 6 -or $after.MinPollInterval -ne 6 -or
        $sourceAfter.NtpServer -cne $trusted -or $sourceAfter.Type -cne 'NTP') {
        throw 'ATLAS_V4_POLL_CAP_READBACK_UNVERIFIED'
    }
} catch {
    # Best-effort rollback of only the changed setting; do not claim success
    # if the Windows service/config update fails. Preserve the real exception.
    try {
        Set-ItemProperty -LiteralPath $config -Name 'MaxPollInterval' -Value $previous -ErrorAction Stop
        & $systemW32tm '/config' '/update' | Out-Null
    } catch {
        Write-Warning 'ATLAS_V4_POLL_CAP_ROLLBACK_UNVERIFIED_MANUAL_ADMIN_REVIEW_REQUIRED'
    }
    throw
}
Write-Output 'ATLAS_V4_WINDOWS_TIME_MAXPOLL_6_REQUESTED_CONFIG_READBACK_PASS'
Write-Output 'NOT_INSTALL_AUTHORIZATION: Native 180-second single-lease preflight still required.'
