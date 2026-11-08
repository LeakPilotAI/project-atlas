# Windows Time-only qualification for the pinned Atlas V4 release.
# This NEVER installs code, selects releases, starts PAPER, or modifies peers.
# Requires an explicitly approved elevated Windows PowerShell process.
#Requires -Version 5.1
param(
    [switch]$ExecuteApproved,
    [ValidateRange(5, 10)][int]$Samples = 6,
    [ValidateRange(30, 60)][int]$IntervalSeconds = 40
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

# Preserve the system-installed peer roster and existing poll configuration.
# Repeated ordinary W32Time resync is the only privileged service action.
$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = (Join-Path $root 'backend') + ';' + $root
    $runtime = 'atlas-v4-time-qualification-only'
    $qualityScript = 'from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock; c=LocalWindowsClock(expected_source="time.cloudflare.com,0x8 time.google.com,0x8",runtime_id="atlas-v4-time-qualification-only",lifetime=240); c.require_operational("atlas-v4-time-qualification-only"); print("NATIVE_CLOCK_QUALITY_ACCEPTED:"+str(c.evidence["bound_ms"])+"ms")'
    for ($index = 0; $index -lt $Samples; $index++) {
        if ($index -ne 0) { Start-Sleep -Seconds $IntervalSeconds }
        Assert-AtlasTrustedTimeSource
        & $w32tm '/resync' '/rediscover'
        if ($LASTEXITCODE -ne 0) {
            throw ('ATLAS_V4_TIME_SERVICE_RESYNC_REFUSED:' + $LASTEXITCODE)
        }
        Assert-AtlasTrustedTimeSource
        & $python -B -c $qualityScript
        if ($LASTEXITCODE -ne 0) {
            throw ('ATLAS_V4_TIME_NATIVE_QUALITY_REFUSED:' + $LASTEXITCODE)
        }
        Write-Output ('ATLAS_V4_CLOCK_QUALITY_SAMPLE=' + ($index + 1) + '/' + $Samples)
    }
    Write-Output 'ATLAS_V4_CLOCK_WINDOW_SAMPLED_WITH_TRUSTED_NTP_NO_INSTALL_PERFORMED'
}
finally {
    $env:PYTHONPATH = $oldPythonPath
}
