# Windows Time-only qualification for the pinned Atlas V4 release.
# This NEVER installs code, selects releases, starts PAPER, or modifies peers.
# Requires an explicitly approved elevated Windows PowerShell process.
#Requires -Version 5.1
param(
    [switch]$ExecuteApproved,
    [ValidateRange(5, 10)][int]$Samples = 6,
    [ValidateRange(30, 60)][int]$IntervalSeconds = 40,
    [ValidateRange(3, 12)][int]$StabilizationChecks = 10,
    [ValidateRange(10, 60)][int]$StabilizationIntervalSeconds = 30
)
$ErrorActionPreference = 'Stop'

if (-not $ExecuteApproved) {
    throw 'ATLAS_V4_TIME_MAINTENANCE_EXPLICIT_APPROVAL_REQUIRED'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'ATLAS_V4_TIME_MAINTENANCE_ELEVATED_ADMIN_REQUIRED'
}

$expected = 'time.cloudflare.com,0x8 time.google.com,0x8'
$registry = 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'
$w32tm = Join-Path ([Environment]::SystemDirectory) 'w32tm.exe'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'

function Assert-AtlasTrustedTimeSource {
    $config = Get-ItemProperty -LiteralPath $registry -ErrorAction Stop
    $service = Get-Service -Name 'W32Time' -ErrorAction Stop
    if ($service.Status -ne 'Running' -or
        $config.Type -cne 'NTP' -or
        $config.NtpServer -cne $expected) {
        throw 'ATLAS_V4_TIME_SOURCE_OR_SERVICE_CHANGED'
    }
}

Assert-AtlasTrustedTimeSource
if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or
    -not (Test-Path -LiteralPath $w32tm -PathType Leaf)) {
    throw 'ATLAS_V4_TIME_NATIVE_TOOLS_UNAVAILABLE'
}
$signature = Get-AuthenticodeSignature -LiteralPath $w32tm
if ($signature.Status -ne 'Valid' -or
    $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)') {
    throw 'ATLAS_V4_TIME_WINDOWS_TOOL_SIGNATURE_REFUSED'
}

# A successful /resync /rediscover is not proof of clock quality and may
# discard W32Time accumulated error statistics. This qualification performs
# NO resync. Let the existing trusted NTP client converge naturally.
$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = (Join-Path $root 'backend') + ';' + $root

    function Test-AtlasGenuineClockQuality {
        Assert-AtlasTrustedTimeSource
        # PowerShell 5.1 can wrap stderr from native Python as ErrorRecords.
        # Capture it only to classify a *transient native quality refusal*;
        # unknown errors and all output mismatches remain hard failures.
        $savedPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $lines = @(& $python -B -m scripts.observation_runtime.atlas_v4_time_quality_probe 2>&1)
            $nativeExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedPreference
        }
        $message = (($lines | ForEach-Object { [string]$_ }) -join [Environment]::NewLine).Trim()
        if ($nativeExit -eq 0) {
            if ($message -cnotmatch '^NATIVE_CLOCK_QUALITY_ACCEPTED:[0-9]+ms$') {
                throw 'ATLAS_V4_TIME_NATIVE_QUALITY_OUTPUT_UNVERIFIED'
            }
            Assert-AtlasTrustedTimeSource
            return @{Accepted=$true; Reason=$message}
        }
        if ($message -match '(NATIVE_CLOCK_QUALITY_REFUSED:CLOCK_UNCERTAINTY_EXCEEDED:[0-9]+ms|NATIVE_CLOCK_QUALITY_REFUSED:CLOCK_STALE_OR_NEGATIVE_QUALITY)') {
            return @{Accepted=$false;Reason=$Matches[1]}
        }
        throw ('ATLAS_V4_TIME_NATIVE_QUALITY_REFUSED:' + $nativeExit + ':' + $message)
    }

    # A bounded warmup is NOT a passed quality sample. It permits existing
    # Windows NTP to stabilize without resetting its filter every check.
    $qualified = $null
    for ($check = 1; $check -le $StabilizationChecks; $check++) {
        $quality = Test-AtlasGenuineClockQuality
        if ($quality.Accepted -eq $true) {
            $qualified = $quality
            break
        }
        Write-Output ('ATLAS_V4_CLOCK_STABILIZING=' + $check + '/' + $StabilizationChecks + ':' + $quality.Reason)
        if ($check -eq $StabilizationChecks) {
            throw ('ATLAS_V4_TIME_STABILIZATION_FAILED:' + $quality.Reason)
        }
        Start-Sleep -Seconds $StabilizationIntervalSeconds
    }
    if ($null -eq $qualified) { throw 'ATLAS_V4_TIME_STABILIZATION_UNVERIFIED' }

    # The FIRST sample is the first genuinely passing Atlas clock result.
    # Every later sample must also pass; any failure invalidates this whole
    # qualification, never replaces it with a synthetic or averaged result.
    Write-Output ('ATLAS_V4_CLOCK_QUALITY_SAMPLE=1/' + $Samples + ':' + $qualified.Reason)
    for ($index = 2; $index -le $Samples; $index++) {
        Start-Sleep -Seconds $IntervalSeconds
        $quality = Test-AtlasGenuineClockQuality
        if ($quality.Accepted -ne $true) {
            throw ('ATLAS_V4_TIME_SUSTAINED_QUALITY_FAILED:' + $quality.Reason)
        }
        Write-Output ('ATLAS_V4_CLOCK_QUALITY_SAMPLE=' + $index + '/' + $Samples + ':' + $quality.Reason)
    }
    # The real code copier keeps ONE LocalWindowsClock across its native
    # creation and readback. Independent 40-second snapshots cannot prove
    # that lease survives the observed 153-second copy horizon. Qualify one
    # single real native capability for 180 seconds before claiming readiness.
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $leaseOutput = @(& $python -B -m scripts.observation_runtime.atlas_v4_installer_clock_lease_preflight 2>&1)
        $leaseExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedPreference
    }
    $leaseText = (($leaseOutput | ForEach-Object { [string]$_ }) -join [Environment]::NewLine).Trim()
    if ($leaseExit -ne 0) {
        throw ('ATLAS_V4_TIME_PERSISTENT_LEASE_REFUSED:' + $leaseExit + ':' + $leaseText)
    }
    if ($leaseText -notmatch '(?m)^CONTINUOUS_NATIVE_LEASE_PREFLIGHT_PASSED_NOT_INSTALLATION_AUTHORITY$' -or
        $leaseText -notmatch '(?m)^ATLAS_V4_INSTALL_CLOCK_PREFLIGHT_SAMPLES=[0-9]+$') {
        throw 'ATLAS_V4_TIME_PERSISTENT_LEASE_OUTPUT_UNVERIFIED'
    }
    Write-Output 'ATLAS_V4_CLOCK_WINDOW_AND_SINGLE_LEASE_QUALIFIED_NO_INSTALL_PERFORMED'
}
finally {
    $env:PYTHONPATH = $oldPythonPath
}
