# Explicit opt-in gaming launch for Project Atlas.
# Does not modify .env, start Genesis, or alter the existing manager.
#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet("Start", "Status", "Stop")]
    [string]$Action = "Status",
    [switch]$EnableExtendedHoursResearch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($EnableExtendedHoursResearch -and $Action -ne "Start") {
    throw "Extended-hours opt-in is valid only for an explicitly approved Start."
}

$manager = Join-Path $PSScriptRoot "Atlas-Background.ps1"

if (-not (Test-Path -LiteralPath $manager -PathType Leaf)) {
    throw "Atlas background manager is missing."
}

if ($Action -ne "Start") {
    & $manager -Action $Action
    if (-not $?) {
        throw "Atlas background manager action failed: $Action"
    }
    return
}

$priorGamingMode = [Environment]::GetEnvironmentVariable(
    "ATLAS_GAMING_MODE",
    "Process"
)

try {
    [Environment]::SetEnvironmentVariable(
        "ATLAS_GAMING_MODE",
        "true",
        "Process"
    )

    # The start lock must identify the manager's own invocation, not this wrapper.
    # Keep the existing ownership verifier strict by using its encoded-child form.
    $managerLiteral = $manager.Replace("'", "''")
    $researchArgument = if ($EnableExtendedHoursResearch) { " -EnableExtendedHoursResearch" } else { "" }
    $childScript = "`$ErrorActionPreference = 'Stop'; & '$managerLiteral' -Action Start$researchArgument"
    $encodedScript = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($childScript))
    & (Join-Path $PSHOME "powershell.exe") -NoProfile -ExecutionPolicy Bypass `
        -WindowStyle Hidden -EncodedCommand $encodedScript

    if ($LASTEXITCODE -ne 0) {
        throw "Atlas gaming startup request failed."
    }
}
finally {
    [Environment]::SetEnvironmentVariable(
        "ATLAS_GAMING_MODE",
        $priorGamingMode,
        "Process"
    )
}
