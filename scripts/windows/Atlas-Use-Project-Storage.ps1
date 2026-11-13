# Atlas per-process temporary/cache containment. Dot-source into launcher.
# This policy is for local transient files only. It does NOT migrate existing
# pinned native release/selection/custody/financial roots outside the project.
# Requires Windows PowerShell 5.1; no system-wide environment changes.
#Requires -Version 5.1
param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$atlasExpectedHome = 'D:\Work\Project Atlas'
$atlasActualHome = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
if (-not [StringComparer]::OrdinalIgnoreCase.Equals($atlasActualHome, $atlasExpectedHome)) {
    throw 'ATLAS_LOCAL_STORAGE_REQUIRES_EXACT_PROJECT_HOME_D_DRIVE'
}
$atlasRealHome = (Get-Item -LiteralPath $atlasActualHome -ErrorAction Stop)
if (-not $atlasRealHome.PSIsContainer -or
    ($atlasRealHome.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'ATLAS_LOCAL_STORAGE_PROJECT_HOME_MUST_BE_ORDINARY_DIRECTORY'
}
$atlasLogs = Join-Path $atlasActualHome 'logs'
$atlasLogsInfo = Get-Item -LiteralPath $atlasLogs -ErrorAction Stop
if (-not $atlasLogsInfo.PSIsContainer -or
    ($atlasLogsInfo.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'ATLAS_LOCAL_STORAGE_EXISTING_LOG_DIRECTORY_REQUIRED'
}
$atlasRelativeDirs = @('temp', 'cache', 'cache\pip', 'cache\ruff')
foreach ($atlasRelative in $atlasRelativeDirs) {
    $atlasDestination = Join-Path $atlasLogs $atlasRelative
    $atlasFull = [IO.Path]::GetFullPath($atlasDestination)
    if (-not $atlasFull.StartsWith($atlasLogs + '\',
        [StringComparison]::OrdinalIgnoreCase)) {
        throw 'ATLAS_LOCAL_STORAGE_PATH_OUTSIDE_PROJECT_REFUSED'
    }
    if (Test-Path -LiteralPath $atlasDestination) {
        $atlasInfo = Get-Item -LiteralPath $atlasDestination -ErrorAction Stop
        if (-not $atlasInfo.PSIsContainer -or
            ($atlasInfo.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'ATLAS_LOCAL_STORAGE_TARGET_MUST_BE_ORDINARY_DIRECTORY'
        }
    }
    else {
        $null = New-Item -ItemType Directory -Path $atlasDestination -ErrorAction Stop
    }
}
$env:ATLAS_PROJECT_ROOT = $atlasActualHome
$env:TEMP = (Join-Path $atlasLogs 'temp')
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$env:PIP_CACHE_DIR = (Join-Path $atlasLogs 'cache\pip')
$env:RUFF_CACHE_DIR = (Join-Path $atlasLogs 'cache\ruff')
$env:XDG_CACHE_HOME = (Join-Path $atlasLogs 'cache')
$env:PYTHONDONTWRITEBYTECODE = '1'
# Do not change USERPROFILE, SYSTEMROOT, PATH, pip/user settings, or Windows
# system temp: that would affect unrelated software. This affects only the
# launcher process and its children.
