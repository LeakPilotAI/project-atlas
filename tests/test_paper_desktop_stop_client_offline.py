"""Source-only desktop stop client. Powershell subprocess, NO listener or Atlas."""
import os
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / 'scripts/windows/Atlas-Paper-Desktop-Stop-Client.psm1'
POWERSHELL = r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_OFFLINE_CLIENT_MODULE -Force
$case=$env:ATLAS_OFFLINE_CLIENT_CASE
$binding=@{schema='ATLAS_PAPER_DESKTOP_STOP_BINDING_V1';origin='http://127.0.0.1:18799';
 session_id='atlas-injected-session';control_token=('x'*40)}
switch ($case) {
 'outside_origin' { $binding.origin='http://remote.example:18799' }
 'other_path' { $binding.origin='http://127.0.0.1:18799/foreign' }
 'port_overflow' { $binding.origin='http://127.0.0.1:99999' }
 'zero_port' { $binding.origin='http://127.0.0.1:0' }
 'token_missing' { $binding.control_token='' }
 'session_missing' { $binding.session_id='' }
 'extra_claim' { $binding['ownership_verified']=$true }
 'unbound' { $binding=$null }
}
$sender={
 param($url,$origin,$token,$payload)
 if ($url -cne 'http://127.0.0.1:18799/_atlas/control/stop-session' -or
     $origin -cne 'http://127.0.0.1:18799' -or $token -cne ('x'*40) -or
     $payload.session_id -cne 'atlas-injected-session' -or
     $payload.mode -cne 'SHUTDOWN_FLATTEN') {throw 'UNEXPECTED_HTTP_TARGET_OR_PAYLOAD'}
 if ($env:ATLAS_OFFLINE_CLIENT_CASE -eq 'transport_error') {throw 'SIMULATED_LOST_ACK'}
 $lanes=@{QUALITY_DIPS=@{state='ACKNOWLEDGED_FLAT_AND_DRAINED'};
          HYPERLIQUID=@{state='ACKNOWLEDGED_FLAT_AND_DRAINED'}}
 switch($env:ATLAS_OFFLINE_CLIENT_CASE) {
   'missing_hl' {$lanes.Remove('HYPERLIQUID')}
   'incomplete_qd' {$lanes.QUALITY_DIPS.state='INCOMPLETE'}
   'open_hl' {$lanes.HYPERLIQUID.state='POSITION_OPEN'}
   'foreign_lane' {$lanes['FOREIGN']=@{state='ACKNOWLEDGED_FLAT_AND_DRAINED'}}
   'lowercase_lane' {$lanes.Remove('QUALITY_DIPS');$lanes['quality_dips']=@{state='ACKNOWLEDGED_FLAT_AND_DRAINED'}}
 }
 $result=@{schema='QD_CONTROL_STOP_V1';phase='FINISHED';outcome=@{
   schema='QD_AUTO_SHUTDOWN_V1';mode='SHUTDOWN_FLATTEN';
   status='FLATTENED';position_state='FLAT';process_shutdown='VERIFIED_EXIT';lanes=$lanes}}
 switch($env:ATLAS_OFFLINE_CLIENT_CASE) {
   'running' {$result.phase='IN_PROGRESS'}
   'incomplete' {$result.outcome.status='SHUTDOWN_INCOMPLETE'}
   'unverified_process' {$result.outcome.process_shutdown='NOT_REQUESTED'}
   'wrong_mode' {$result.outcome.mode='EMERGENCY'}
   'no_outcome' {$result.outcome=$null}
   'forged_success_flag' {$result.outcome['ownership_verified']=$true;$result.outcome.status='SHUTDOWN_INCOMPLETE'}
 }
 return $result
}
try {
 if($case -eq 'no_sender'){
    Invoke-AtlasBoundPaperDesktopStop -Binding $binding | Out-Null
 }else{
    $result=Invoke-AtlasBoundPaperDesktopStop -Binding $binding -Sender $sender
    if($result.outcome.lanes.QUALITY_DIPS.state -cne 'ACKNOWLEDGED_FLAT_AND_DRAINED'){
        throw 'UNEXPECTED_LOCAL_VALIDATION'
    }
    Write-Output 'OFFLINE_STOP_RESULT_ACCEPTED'
 }
}catch { Write-Output ('REFUSED:'+ $_.Exception.Message) }
"""


def invoke(case):
    env = dict(os.environ, ATLAS_OFFLINE_CLIENT_CASE=case, ATLAS_OFFLINE_CLIENT_MODULE=str(MOD))
    r = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',POWERSHELL],
                       capture_output=True, text=True, env=env, timeout=25, check=False)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_exact_injected_two_account_receipt_accepts_offline():
    assert invoke('valid') == 'OFFLINE_STOP_RESULT_ACCEPTED'


@pytest.mark.parametrize('case',[
    'outside_origin','other_path','port_overflow','zero_port','token_missing',
    'session_missing','extra_claim','unbound',
])
def test_missing_or_foreign_desktop_binding_refuses_without_dispatch(case):
    assert invoke(case).startswith('REFUSED:PAPER_DESKTOP_STOP_')


@pytest.mark.parametrize('case',[
    'missing_hl','incomplete_qd','open_hl','foreign_lane','lowercase_lane',
    'running','incomplete','unverified_process','wrong_mode','no_outcome','forged_success_flag',
])
def test_forged_or_partial_stop_receipt_never_claims_both_lanes_closed(case):
    assert invoke(case) == 'REFUSED:PAPER_DESKTOP_STOP_RECEIPT_UNVERIFIED'


def test_ambiguous_http_dispatch_never_retries_or_claims_complete():
    assert invoke('transport_error') == 'REFUSED:PAPER_DESKTOP_STOP_DISPATCH_UNVERIFIED'


def test_no_implicit_sender_or_network():
    assert invoke('no_sender') == 'REFUSED:PAPER_DESKTOP_STOP_ACCEPTED_BINDING_AND_SENDER_REQUIRED'
