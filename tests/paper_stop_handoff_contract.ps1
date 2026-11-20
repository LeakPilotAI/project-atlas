$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot '../scripts/windows/Atlas-Paper-Stop-Handoff.psm1') -Force
$passed=0
function Refuse($value,$reason) {
    $caught=$false
    try { Test-AtlasPaperStopHandoff $value | Out-Null }
    catch { if ($_.Exception.Message -like "*$reason*") { $caught=$true } else { throw } }
    if (-not $caught) { throw "Expected refusal: $reason" }
    $script:passed++
}
Refuse $null 'NOT_ENROLLED'
Refuse 'string' 'INVALID'
$valid=@{schema='ATLAS_PAPER_STOP_HANDOFF_V1';session_id='s1';mode='SHUTDOWN_FLATTEN';paper_only=$true;ownership_verified=$true}
Refuse $valid 'AUTHORITY_UNAVAILABLE'
foreach ($mode in @('SHUTDOWN_FLATTEN','EMERGENCY')) {
    $case=$valid.Clone(); $case.mode=$mode
    Refuse $case 'AUTHORITY_UNAVAILABLE'
}
foreach ($change in @(
    @{session_id=''},
    @{mode='UNKNOWN'},
    @{paper_only='true'},
    @{paper_only=$false},
    @{ownership_verified=$false},
    @{ownership_verified='true'},
    @{schema='ATLAS_PAPER_STOP_HANDOFF_V2'}
)) {
    $case=$valid.Clone()
    foreach($key in $change.Keys){$case[$key]=$change[$key]}
    Refuse $case 'INVALID'
}
$extra=$valid.Clone(); $extra['live_enabled']=$true
Refuse $extra 'INVALID'
Write-Host "PAPER handoff contract: $passed refusal assertions passed."
