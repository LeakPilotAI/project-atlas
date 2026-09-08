# Desktop shortcuts: Project Atlas (start) + Stop Atlas. Genesis-style.
#Requires -Version 5.1
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$LaunchBat = Join-Path $Root "ATLAS.bat"
$StopBat = Join-Path $Root "ATLAS-STOP.bat"
$Desktop = [Environment]::GetFolderPath("Desktop")

$old = @(
    "Start Atlas.lnk",
    "START ATLAS.lnk",
    "Atlas Start.lnk",
    "start-atlas.lnk",
    "Project Atlas START.lnk",
    "START_ATLAS.lnk",
    "Start Atlas.bat",
    "stop_atlas.lnk",
    "STOP ATLAS.lnk",
    "Project Atlas STOP.lnk"
)
foreach ($name in $old) {
    $p = Join-Path $Desktop $name
    if (Test-Path $p) {
        Remove-Item $p -Force
        Write-Host "Removed old shortcut: $name"
    }
}

$icon = Join-Path $Root "frontend\src\app\favicon.ico"
$w = New-Object -ComObject WScript.Shell

$lnkPath = Join-Path $Desktop "Project Atlas.lnk"
$s = $w.CreateShortcut($lnkPath)
$s.TargetPath = $LaunchBat
$s.WorkingDirectory = $Root
$s.WindowStyle = 1
$s.Description = "Start Project Atlas. Use Stop Atlas to terminate the bot. Docker Desktop stays running."
if (Test-Path $icon) { $s.IconLocation = $icon }
$s.Save()
Write-Host "Start shortcut: $lnkPath"

$stopPath = Join-Path $Desktop "Stop Atlas.lnk"
$t = $w.CreateShortcut($stopPath)
$t.TargetPath = $StopBat
$t.WorkingDirectory = $Root
$t.WindowStyle = 1
$t.Description = "Stop Project Atlas bot and atlas containers. Does not quit Docker Desktop or Genesis."
if (Test-Path $icon) { $t.IconLocation = $icon }
$t.Save()
Write-Host "Stop shortcut:  $stopPath"

Write-Host "  Start: $LaunchBat"
Write-Host "  Stop:  $StopBat"
Write-Host "  Folder: $Root"
if (-not (Test-Path $LaunchBat)) {
    Write-Host "[ERROR] ATLAS.bat missing at $LaunchBat" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $StopBat)) {
    Write-Host "[ERROR] ATLAS-STOP.bat missing at $StopBat" -ForegroundColor Red
    exit 1
}
