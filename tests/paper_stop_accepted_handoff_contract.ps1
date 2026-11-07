$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot '../scripts/windows/Atlas-Paper-Stop-Handoff.psm1') -Force
$passed=0
function Refuse($handoff,$session,$reason) {
    $caught=$false
    try { Invoke-AtlasAcceptedPaperStopHandoff $handoff $session | Out-Null }
    catch { if($_.Exception.Message -like "*$reason*"){$caught=$true}else{throw} }
    if(-not $caught){throw "Expected refusal $reason"}
    $script:passed++
}
function Session($id,$verified,$state='FLATTENED') {
    $s=[pscustomobject]@{session_id=$id; verified=$verified; state=$state; calls=0; checks=0}
    $s | Add-Member ScriptMethod verify_session { $this.checks++; return $this.verified }
    $s | Add-Member ScriptMethod request_stop {
        param($mode)
        $this.calls++
        return [pscustomobject]@{
            schema='QD_CONTROL_STOP_V1';phase='FINISHED';
            outcome=[pscustomobject]@{
                schema='QD_AUTO_SHUTDOWN_V1';mode=$mode;status=$this.state;
                position_state='FLAT';process_shutdown='VERIFIED_EXIT'
            }
        }
    }
    return $s
}
$h=@{schema='ATLAS_PAPER_STOP_HANDOFF_V1';session_id='owner1';mode='SHUTDOWN_FLATTEN';paper_only=$true;ownership_verified=$true}
Refuse $h $null 'AUTHORITY_UNAVAILABLE'
$foreign=Session 'other' $true
Refuse $h $foreign 'SESSION_UNVERIFIED'
if($foreign.calls -ne 0){throw 'Foreign session dispatched'}
$bad=Session 'owner1' $false
Refuse $h $bad 'SESSION_UNVERIFIED'
if($bad.calls -ne 0){throw 'Unverified session dispatched'}
$invalid=$h.Clone();$invalid.paper_only=$false
$owner=Session 'owner1' $true
Refuse $invalid $owner 'INVALID'
if($owner.checks -ne 0 -or $owner.calls -ne 0){throw 'Invalid handoff reached owner'}
$incomplete=Session 'owner1' $true 'SHUTDOWN_INCOMPLETE'
Refuse $h $incomplete 'SHUTDOWN_UNVERIFIED'
if($incomplete.calls -ne 1){throw 'Incomplete outcome not dispatched exactly once'}
$result=Invoke-AtlasAcceptedPaperStopHandoff $h $owner
if($result.outcome.status -cne 'FLATTENED' -or $owner.calls -ne 1 -or $owner.checks -ne 1){throw 'Accepted session not dispatched exactly once'}
$passed++
Write-Host "Accepted PAPER handoff offline contract: $passed assertions passed."
# Additional simulated owner-identity mutation tests.
$changing=Session 'owner1' $true
$changing | Add-Member ScriptMethod verify_session {
    $this.checks++; $this.session_id='foreign'; return $true
} -Force
Refuse $h $changing 'SESSION_UNVERIFIED'
if($changing.calls -ne 0){throw 'Mutated owner dispatched'}
$after=Session 'owner1' $true
$after | Add-Member ScriptMethod request_stop {
    param($mode)
    $this.calls++; $this.session_id='foreign'
    return [pscustomobject]@{schema='QD_CONTROL_STOP_V1';phase='FINISHED';outcome=[pscustomobject]@{
        schema='QD_AUTO_SHUTDOWN_V1';mode=$mode;status='FLATTENED';position_state='FLAT';process_shutdown='VERIFIED_EXIT'
    }}
} -Force
Refuse $h $after 'SESSION_CHANGED'
if($after.calls -ne 1){throw 'Unexpected second dispatch'}
$spoof=Session 'owner1' $true
$spoof | Add-Member ScriptMethod request_stop {
    param($mode)
    $this.calls++
    return [pscustomobject]@{schema='QD_CONTROL_STOP_V1';phase='FINISHED';outcome=[pscustomobject]@{
        schema='QD_AUTO_SHUTDOWN_V1';mode='EMERGENCY';status='FLATTENED';position_state='FLAT';process_shutdown='VERIFIED_EXIT'
    }}
} -Force
Refuse $h $spoof 'SHUTDOWN_UNVERIFIED'
Write-Host "Accepted PAPER handoff mutation regressions: 3 additional assertions passed."
