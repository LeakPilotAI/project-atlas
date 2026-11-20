# Adds only the separate Atlas Background control shortcut. Existing Atlas shortcuts are untouched.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Atlas Background.lnk"
$PowerShell = Join-Path $PSHOME "powershell.exe"
$Controls = Join-Path $PSScriptRoot "Atlas-Background-Controls.ps1"
$Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -STA -File "{0}"' -f $Controls

if (-not (Test-Path -LiteralPath $Desktop -PathType Container)) {
    throw "The configured Windows Desktop directory is unavailable: $Desktop"
}
$shell = New-Object -ComObject WScript.Shell
if (Test-Path -LiteralPath $ShortcutPath -PathType Leaf) {
    $existing = $shell.CreateShortcut($ShortcutPath)
    if ($existing.TargetPath -ine $PowerShell -or $existing.Arguments -cne $Arguments -or
        $existing.WorkingDirectory -ine $Root) {
        throw "Atlas Background.lnk already exists with a different target; refusing to overwrite it."
    }
    Write-Host "Atlas Background shortcut is already installed; existing Atlas shortcuts were not changed."
    return
}

$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $PowerShell
$shortcut.Arguments = $Arguments
$shortcut.WorkingDirectory = $Root
$shortcut.WindowStyle = 7
$shortcut.Description = "Manually start, inspect, or gracefully stop Atlas background mode. No auto-start."
$shortcut.Save()
Write-Host "Installed only: $ShortcutPath"
