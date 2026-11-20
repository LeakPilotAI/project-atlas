$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot '../scripts/windows/Atlas-Control-Center.psm1') -Force
$passed=0
function Refuse($h,$session,$reason) {
    $caught=$false
    try { Invoke-AtlasPaperStopWithHandoff $h $session | Out-Null }
    catch { if($_.Exception.Message -like "*$reason*"){$caught=$true}else{throw} }
    if(-not $caught){throw "Expected refusal $reason"}
    $script:passed++
}
$h=@{schema='ATLAS_PAPER_STOP_HANDOFF_V1';session_id='s1';mode='SHUTDOWN_FLATTEN';paper_only=$true;ownership_verified=$true}
Refuse $h $null 'AUTHORITY_UNAVAILABLE'
$s=[pscustomobject]@{session_id='s1';calls=0}
$s | Add-Member ScriptMethod verify_session { return $true }
$s | Add-Member ScriptMethod request_stop {
    param($mode)
    $this.calls++
    return [pscustomobject]@{schema='QD_CONTROL_STOP_V1';phase='FINISHED';outcome=[pscustomobject]@{
        schema='QD_AUTO_SHUTDOWN_V1';mode=$mode;status='FLATTENED';position_state='FLAT';process_shutdown='VERIFIED_EXIT';lanes=@{}
    }}
}
$r=Invoke-AtlasPaperStopWithHandoff $h $s
if($r.outcome.status -cne 'FLATTENED' -or $s.calls -ne 1){throw 'Control Center bridge dispatch mismatch'}
$passed++
$bad=$h.Clone();$bad.session_id='foreign'
Refuse $bad $s 'SESSION_UNVERIFIED'
if($s.calls -ne 1){throw 'Foreign request dispatched'}
Write-Host "Control Center accepted handoff integration: $passed assertions passed."
