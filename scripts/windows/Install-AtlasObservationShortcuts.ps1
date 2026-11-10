# Install ONLY clearly labeled observation-only desktop shortcuts.
# Never replace Project Atlas.lnk / Stop Atlas.lnk or trigger finance / markets.
#Requires -Version 5.1
param([switch]$ExecuteApproved)
$ErrorActionPreference='Stop'
if(-not $ExecuteApproved){throw 'ATLAS_OBSERVATION_SHORTCUT_EXPLICIT_EXECUTION_REQUIRED'}
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$startScript=Join-Path $PSScriptRoot 'Atlas-Observation-Shortcut.ps1'
$stopScript=Join-Path $PSScriptRoot 'Atlas-Observation-Stop.ps1'
$desktop=[Environment]::GetFolderPath('Desktop')
$powershell=(Join-Path $PSHOME 'powershell.exe')
if(-not (Test-Path -LiteralPath $startScript -PathType Leaf) -or
   -not (Test-Path -LiteralPath $stopScript -PathType Leaf) -or
   -not (Test-Path -LiteralPath $powershell -PathType Leaf) -or
   -not (Test-Path -LiteralPath $desktop -PathType Container)){
    throw 'ATLAS_OBSERVATION_SHORTCUT_CANONICAL_FILES_MISSING'
}
$startLink=Join-Path $desktop 'Atlas Observation (No Trading).lnk'
$stopLink=Join-Path $desktop 'Stop Atlas Observation (No Trading).lnk'
if((Test-Path -LiteralPath $startLink) -or (Test-Path -LiteralPath $stopLink)){
    throw 'ATLAS_OBSERVATION_SHORTCUTS_EXIST_REFUSE_OVERWRITE'
}
$w=New-Object -ComObject WScript.Shell
$created=@()
try{
    foreach($record in @(
        @{path=$startLink;source=$startScript;description='Start local Atlas observation-only dashboard. NO market data or financial orders.'},
        @{path=$stopLink;source=$stopScript;description='Request graceful Stop of Atlas observation-only dashboard; NOT financial trading.'}
    )){
        if(Test-Path -LiteralPath $record.path){
            throw 'ATLAS_OBSERVATION_SHORTCUT_COLLISION_REFUSED'
        }
        $shortcut=$w.CreateShortcut($record.path)
        $shortcut.TargetPath=$powershell
        $shortcut.Arguments=('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $record.source)
        $shortcut.WorkingDirectory=$root
        $shortcut.Description=$record.description
        $shortcut.WindowStyle=1
        $shortcut.Save()
        $created+= $record.path
    }
    Write-Output 'ATLAS_OBSERVATION_ONLY_DESKTOP_SHORTCUTS_CREATE_ONLY_PASS'
    Write-Output ('START_OBSERVATION_SHORTCUT='+$startLink)
    Write-Output ('STOP_OBSERVATION_SHORTCUT='+$stopLink)
    Write-Output 'FINANCIAL_PAPER_AND_LIVE_TRADING_NOT_STARTED'
} catch {
    # Remove only exact files created by this invocation; never touch legacy,
    # unrelated, or preexisting desktop links.
    foreach($path in $created){Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue}
    throw
}
