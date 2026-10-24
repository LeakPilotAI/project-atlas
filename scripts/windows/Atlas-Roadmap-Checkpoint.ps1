param(
    [Parameter(Mandatory=$true)]
    [string]$CheckpointFile,

    [string]$RoadmapPath = "PROJECT_ATLAS_MASTER_ROADMAP.txt"
)

$ErrorActionPreference = "Stop"

$start = "=== ATLAS MANAGED CURRENT CHECKPOINT V1 ==="
$end = "=== END ATLAS MANAGED CURRENT CHECKPOINT V1 ==="

$roadmap = (Resolve-Path -LiteralPath $RoadmapPath).Path
$checkpoint = (Resolve-Path -LiteralPath $CheckpointFile).Path

if ($roadmap -eq $checkpoint) {
    throw "Checkpoint input cannot be the roadmap itself."
}

$current = [System.IO.File]::ReadAllText($roadmap)
$newCheckpoint = [System.IO.File]::ReadAllText($checkpoint).Trim()

if ([string]::IsNullOrWhiteSpace($newCheckpoint)) {
    throw "Checkpoint is empty."
}

# Retained nested checkpoints reached 29,969 characters. Keep a finite bound
# while preserving their bytes instead of deleting history to fit the old cap.
if ($newCheckpoint.Length -gt 60000) {
    throw "Checkpoint exceeds maximum allowed length."
}

$required = @(
    "Milestone:",
    "Status:",
    "Evidence:",
    "Next action:"
)

foreach ($field in $required) {
    if (-not $newCheckpoint.Contains($field)) {
        throw "Missing required field: $field"
    }
}

if ($newCheckpoint.Contains($start) -or
    $newCheckpoint.Contains($end)) {
    throw "Checkpoint input contains reserved markers."
}

if (-not $current.Contains(
    "ATLAS PERMANENT FUTURE STRATEGY V1 - MARKET INTELLIGENCE OS"
)) {
    throw "Permanent strategy missing. Refusing update."
}

if (-not $current.Contains(
    "ATLAS PERMANENT EXECUTION AND CONVERSATION RECOVERY CONTRACT V1"
)) {
    throw "Recovery contract missing. Refusing update."
}

$managed = $start + [Environment]::NewLine +
    $newCheckpoint + [Environment]::NewLine + $end

$startIndex = $current.IndexOf(
    $start, [StringComparison]::Ordinal
)

$endIndex = $current.IndexOf(
    $end, [StringComparison]::Ordinal
)

if ($startIndex -ge 0 -and $endIndex -ge $startIndex) {
    if ($current.IndexOf(
        $start,
        $startIndex + $start.Length,
        [StringComparison]::Ordinal
    ) -ge 0) {
        throw "Duplicate checkpoint start marker."
    }

    if ($current.IndexOf(
        $end,
        $endIndex + $end.Length,
        [StringComparison]::Ordinal
    ) -ge 0) {
        throw "Duplicate checkpoint end marker."
    }

    $updated = $current.Substring(0, $startIndex) +
        $managed +
        $current.Substring($endIndex + $end.Length)
}
elseif ($startIndex -lt 0 -and $endIndex -lt 0) {
    $updated = $current.TrimEnd() +
        [Environment]::NewLine +
        [Environment]::NewLine +
        $managed +
        [Environment]::NewLine
}
else {
    throw "Incomplete checkpoint markers."
}

$directory = [System.IO.Path]::GetDirectoryName($roadmap)
$temporary = Join-Path $directory (
    "atlas-roadmap-" + [guid]::NewGuid().ToString("N") + ".tmp"
)
$backup = "$roadmap.checkpoint-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$([guid]::NewGuid().ToString('N').Substring(0,8)).bak"

try {
    [System.IO.File]::WriteAllText(
        $temporary,
        $updated,
        [System.Text.UTF8Encoding]::new($false)
    )

    if ([System.IO.File]::ReadAllText($temporary) -cne $updated) {
        throw "Temporary file verification failed."
    }

    [System.IO.File]::Replace(
        $temporary,
        $roadmap,
        $backup
    )

    $verified = [System.IO.File]::ReadAllText($roadmap)

    if ($verified -cne $updated) {
        throw "Final verification failed. Backup: $backup"
    }

    Write-Host "ATLAS ROADMAP CHECKPOINT VERIFIED" -ForegroundColor Green
    Write-Host "Roadmap: $roadmap"
    Write-Host "Backup: $backup"
}
finally {
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary -Force
    }
}
