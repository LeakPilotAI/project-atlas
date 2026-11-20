$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot '../scripts/windows/Atlas-Control-Center.psm1') -Force
$script:passed=0
function Refuses([scriptblock]$Action,[string]$Reason) {
    try { & $Action | Out-Null; throw 'EXPECTED_REFUSAL_MISSING' }
    catch { if ($_.Exception.Message -notlike ('*'+$Reason+'*')) { throw }; $script:passed++ }
}
$s=[pscustomobject]@{session_id='synthetic-accepted';calls=0;change=$false}
$s | Add-Member ScriptMethod verify_session { return $true }
$s | Add-Member ScriptMethod request_stop {
    param($mode)
    $this.calls++
    if ($this.change) { $this.session_id='foreign' }
    return [pscustomobject]@{schema='QD_CONTROL_STOP_V1';phase='FINISHED';outcome=[pscustomobject]@{schema='QD_AUTO_SHUTDOWN_V1';mode=$mode;status='FLATTENED';position_state='FLAT';process_shutdown='VERIFIED_EXIT';lanes=@{}}}
}
$result=Invoke-AtlasPaperStop $s -RequireSessionIdentity -RequireFinished
if ($result.outcome.status -cne 'FLATTENED' -or $s.calls -ne 1) { throw 'VALID_SESSION_REJECTED' }; $script:passed++
$s.session_id=''; Refuses { Invoke-AtlasPaperStop $s -RequireSessionIdentity -RequireFinished } 'PAPER_STOP_SESSION_IDENTITY_UNVERIFIED'
if ($s.calls -ne 1) { throw 'INVALID_ID_DISPATCHED' }; $script:passed++
$s.session_id='synthetic-accepted'; $s.change=$true
Refuses { Invoke-AtlasPaperStop $s -RequireSessionIdentity -RequireFinished } 'PAPER_STOP_SESSION_IDENTITY_CHANGED'
if ($s.calls -ne 2) { throw 'MUTATION_RETRIED' }; $script:passed++
$s.change=$false; $s.session_id='synthetic-accepted'; $s | Add-Member NoteProperty VerifiedCalls 0
$s | Add-Member ScriptMethod verify_session {
    $this.VerifiedCalls++
    return ($this.VerifiedCalls -eq 1)
} -Force
Refuses { Invoke-AtlasPaperStop $s -RequireSessionIdentity -RequireFinished } 'PAPER_STOP_SESSION_VERIFICATION_LOST'
if ($s.calls -ne 3 -or $s.VerifiedCalls -ne 2) { throw 'POST_DISPATCH_VERIFICATION_NOT_CHECKED' }; $script:passed++
$s | Add-Member ScriptMethod request_stop { param($mode) $this.calls++; throw 'SYNTHETIC_DISPATCH_FAILURE' } -Force
$s | Add-Member ScriptMethod verify_session { return $true } -Force
Refuses { Invoke-AtlasPaperStop $s -RequireSessionIdentity -RequireFinished } 'PAPER_STOP_DISPATCH_UNVERIFIED'
if ($s.calls -ne 4) { throw 'AMBIGUOUS_DISPATCH_RETRIED' }; $script:passed++
$s | Add-Member ScriptMethod request_stop {
    param($mode)
    $this.calls++
    return [pscustomobject]@{schema='QD_CONTROL_STOP_V1';phase='FINISHED';outcome=[pscustomobject]@{schema='QD_AUTO_SHUTDOWN_V1';mode=$mode;status='FLATTENED';position_state='FLAT';process_shutdown='VERIFIED_EXIT'}}
} -Force
Refuses { Invoke-AtlasPaperStop $s -RequireSessionIdentity -RequireFinished } 'PAPER_STOP_NOT_VERIFIED_FLAT'
if ($s.calls -ne 5) { throw 'MISSING_LANE_RECEIPT_RETRIED' }; $script:passed++
Write-Output (@{passed=$script:passed;failed=0;financial_effects=0} | ConvertTo-Json -Compress)
