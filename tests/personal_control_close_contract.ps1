# Fake session contracts only;no UI,host,provider,financial store or native child.
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '../scripts/windows/Atlas-Control-Center.psm1') -Force
$script:passed = 0
function Fake-Session([string]$Phase, [bool]$Verified = $true) {
    $s = [pscustomobject]@{ Phase=$Phase; Verified=$Verified; Calls=0 }
    $s | Add-Member ScriptMethod verify_session { return $this.Verified }
    $s | Add-Member ScriptMethod request_stop {
        param($mode)
        $this.Calls++
        $outcome = if ($this.Phase -eq 'FINISHED') {
            [pscustomobject]@{schema='QD_AUTO_SHUTDOWN_V1';status='SHUTDOWN_INCOMPLETE';position_state='POSITION_OPEN'}
        } else { $null }
        return [pscustomobject]@{schema='QD_CONTROL_STOP_V1';phase=$this.Phase;outcome=$outcome}
    }
    return $s
}
function Refuses([scriptblock]$Action,[string]$Reason) {
    $refused=$false
    try { & $Action | Out-Null } catch { if($_.Exception.Message -like ('*'+$Reason+'*')){$refused=$true}else{throw} }
    if(-not $refused){throw "Expected refusal: $Reason"}
    $script:passed++
}
$busy=Fake-Session 'IN_PROGRESS'
Refuses { Invoke-AtlasPaperStop $busy -RequireFinished } 'PAPER_STOP_STILL_IN_PROGRESS'
$progress=Invoke-AtlasPaperStop $busy
if($progress.phase -cne 'IN_PROGRESS'){throw 'Ordinary Stop must preserve progress'}
$script:passed++
$finished=Fake-Session 'FINISHED'
$result=Invoke-AtlasPaperStop $finished -RequireFinished
if($result.outcome.position_state -cne 'POSITION_OPEN' -or $result.outcome.status -cne 'SHUTDOWN_INCOMPLETE'){
    throw 'Do not fabricate a flattened outcome for an unresolved position'
}
$script:passed++
Refuses { Invoke-AtlasPaperStop $null -RequireFinished } 'PAPER_STOP_NOT_ENROLLED'
$foreign=Fake-Session 'FINISHED' $false
Refuses { Invoke-AtlasPaperStop $foreign -RequireFinished } 'PAPER_STOP_NOT_ENROLLED'
if($foreign.Calls -ne 0){throw 'Unverified session was dispatched'}
$script:passed++
$bad=Fake-Session 'REFUSED'
Refuses { Invoke-AtlasPaperStop $bad -RequireFinished } 'PAPER_STOP_OUTCOME_UNVERIFIED'
$empty=Fake-Session 'FINISHED'
$empty | Add-Member ScriptMethod request_stop {param($mode) return [pscustomobject]@{schema='QD_CONTROL_STOP_V1';phase='FINISHED';outcome=$null}} -Force
Refuses {Invoke-AtlasPaperStop $empty -RequireFinished} 'PAPER_STOP_OUTCOME_UNVERIFIED'
@{passed=$script:passed;failed=0;native_children=0;financial_effects=0} | ConvertTo-Json -Compress
