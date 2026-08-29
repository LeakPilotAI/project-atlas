# One desktop shortcut: Project Atlas. Removes old Start/Stop icons.
#Requires -Version 5.1
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$LaunchBat = Join-Path $Root "ATLAS.bat"
$Desktop = [Environment]::GetFolderPath("Desktop")

$old = @(
    "Start Atlas.lnk", "Stop Atlas.lnk",
    "START ATLAS.lnk", "STOP ATLAS.lnk",
    "Atlas Start.lnk", "Atlas Stop.lnk",
    "start-atlas.lnk", "stop-atlas.lnk",
    "Project Atlas START.lnk", "Project Atlas STOP.lnk",
    "START_ATLAS.lnk", "stop_atlas.lnk",
    "Start Atlas.bat", "Stop Atlas.bat"
)
foreach ($name in $old) {
    $p = Join-Path $Desktop $name
    if (Test-Path $p) {
        Remove-Item $p -Force
        Write-Host "Removed old shortcut: $name"
    }
}

$icon = Join-Path $Root "frontend\src\app\favicon.ico"
$lnkPath = Join-Path $Desktop "Project Atlas.lnk"
$w = New-Object -ComObject WScript.Shell
$s = $w.CreateShortcut($lnkPath)
$s.TargetPath = $LaunchBat
$s.WorkingDirectory = $Root
$s.WindowStyle = 1
$s.Description = "Project Atlas — dashboard + bot. Close the window to stop Docker too."
if (Test-Path $icon) { $s.IconLocation = $icon }
$s.Save()
Write-Host "Desktop shortcut created: $lnkPath"
Write-Host "Double-click 'Project Atlas'. Close that window to shut everything down."
