"""Pure in-memory PowerShell handoff tests. Never start Atlas or access providers."""

import os
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-Paper-Stop-Handoff.psm1"

SCRIPT = r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_TEST_HANDOFF_MODULE -Force
$kind = $env:ATLAS_TEST_HANDOFF_CASE
$handoff = @{schema='ATLAS_PAPER_STOP_HANDOFF_V1';session_id='offline-unified-session';mode='SHUTDOWN_FLATTEN';paper_only=$true;ownership_verified=$true}
if ($kind -eq 'wrong_handoff_mode') { $handoff.mode = 'FORGED_MODE' }
if ($kind -eq 'wrong_handoff_session') { $handoff.session_id = 'other-session' }
$session = [pscustomobject]@{session_id='offline-unified-session';kind=$kind}
$session | Add-Member -MemberType ScriptMethod -Name verify_session -Value { return $this.kind -ne 'failed_ownership' }
$session | Add-Member -MemberType ScriptMethod -Name request_stop -Value {
    param($mode)
    if ($this.kind -eq 'dispatch_exception') { throw 'SIMULATED_DISPATCH_UNKNOWN' }
    $lanes = @{
        QUALITY_DIPS = @{state='ACKNOWLEDGED_FLAT_AND_DRAINED'}
        HYPERLIQUID = @{state='ACKNOWLEDGED_FLAT_AND_DRAINED'}
    }
    switch ($this.kind) {
        'missing_hyperliquid' { $lanes.Remove('HYPERLIQUID') }
        'hyperliquid_open' { $lanes.HYPERLIQUID.state='POSITION_OPEN' }
        'qd_incomplete' { $lanes.QUALITY_DIPS.state='INCOMPLETE' }
        'extra_lane' { $lanes['FOREIGN'] = @{state='ACKNOWLEDGED_FLAT_AND_DRAINED'} }
        'no_hl_state' { $lanes.HYPERLIQUID.Remove('state') }
        'changed_session' { $this.session_id='changed-after-stop' }
    }
    $phase = if ($this.kind -eq 'stop_still_running') {'IN_PROGRESS'} else {'FINISHED'}
    $status = if ($this.kind -eq 'incomplete_overall') {'SHUTDOWN_INCOMPLETE'} else {'FLATTENED'}
    $position = if ($this.kind -eq 'open_overall') {'POSITION_OPEN'} else {'FLAT'}
    $process = if ($this.kind -eq 'no_verified_process_exit') {'UNVERIFIED'} else {'VERIFIED_EXIT'}
    return @{schema='QD_CONTROL_STOP_V1';phase=$phase;outcome=@{
        schema='QD_AUTO_SHUTDOWN_V1';mode=$mode;status=$status;
        position_state=$position;process_shutdown=$process;lanes=$lanes
    }}
}
try {
    $result = Invoke-AtlasAcceptedPaperStopHandoff $handoff $session
    if ($result.outcome.status -ne 'FLATTENED') { throw 'UNEXPECTED_RESPONSE' }
    Write-Output 'ACCEPTED_SIMULATED_BOTH_LANES'
} catch {
    Write-Output ('REFUSED:' + $_.Exception.Message)
}
"""


def invoke(case):
    env = dict(os.environ, ATLAS_TEST_HANDOFF_CASE=case,
               ATLAS_TEST_HANDOFF_MODULE=str(MODULE))
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", SCRIPT],
        capture_output=True, text=True, timeout=25, env=env, check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_verified_both_lane_flat_and_owned_stop_receipt_is_accepted_offline():
    assert invoke("both_flat") == "ACCEPTED_SIMULATED_BOTH_LANES"


@pytest.mark.parametrize("case", [
    "missing_hyperliquid", "hyperliquid_open", "qd_incomplete",
    "extra_lane", "no_hl_state",
])
def test_unverified_single_or_partial_lane_cannot_claim_financial_flatness(case):
    assert invoke(case) == "REFUSED:PAPER_STOP_HANDOFF_TWO_ACCOUNT_FLATNESS_UNVERIFIED"


@pytest.mark.parametrize("case,reason", [
    ("changed_session", "PAPER_STOP_HANDOFF_SESSION_CHANGED"),
    ("wrong_handoff_session", "PAPER_STOP_HANDOFF_SESSION_UNVERIFIED"),
    ("wrong_handoff_mode", "PAPER_STOP_HANDOFF_INVALID"),
    ("failed_ownership", "PAPER_STOP_HANDOFF_SESSION_UNVERIFIED"),
    ("dispatch_exception", "PAPER_STOP_HANDOFF_DISPATCH_UNVERIFIED"),
    ("stop_still_running", "PAPER_STOP_HANDOFF_SHUTDOWN_UNVERIFIED"),
    ("incomplete_overall", "PAPER_STOP_HANDOFF_SHUTDOWN_UNVERIFIED"),
    ("open_overall", "PAPER_STOP_HANDOFF_SHUTDOWN_UNVERIFIED"),
    ("no_verified_process_exit", "PAPER_STOP_HANDOFF_SHUTDOWN_UNVERIFIED"),
])
def test_unverified_owner_or_dispatch_never_claims_flat_stop(case, reason):
    assert invoke(case) == "REFUSED:" + reason
