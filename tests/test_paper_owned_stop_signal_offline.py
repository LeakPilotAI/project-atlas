"""Real Windows event primitive, synthetic owner only; no Atlas Start/Stop or network."""
import os
import subprocess
import uuid
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1'
PS = 'powershell.exe'

OWNER = r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_OFFLINE_OWNER_MODULE -Force
$case=$env:ATLAS_OFFLINE_OWNER_CASE
$testId=$env:ATLAS_OFFLINE_OWNER_TEST_ID
$fake=[pscustomobject]@{session_id='offline-owner-session';calls=0; durableChecks=0; kind=$case}
$fake | Add-Member -MemberType ScriptMethod -Name verify_session -Value {
 return $this.kind -ne 'owner_unverified'
}
$fake | Add-Member -MemberType ScriptMethod -Name request_stop -Value {
 param($mode)
 $this.calls++
 if($this.kind -eq 'throw_after_stop') {throw 'SIMULATED_DISPATCH_UNCERTAIN'}
 $lanes=@{QUALITY_DIPS=@{state='ACKNOWLEDGED_FLAT_AND_DRAINED'};
          HYPERLIQUID=@{state='ACKNOWLEDGED_FLAT_AND_DRAINED'}}
 if($this.kind -eq 'missing_hl') {$lanes.Remove('HYPERLIQUID')}
 if($this.kind -eq 'unflattened_hl') {$lanes.HYPERLIQUID.state='POSITION_OPEN'}
 if($this.kind -eq 'changed_session') {$this.session_id='OTHER-SESSION'}
 return @{schema='QD_CONTROL_STOP_V1';phase='FINISHED';outcome=@{
  schema='QD_AUTO_SHUTDOWN_V1';mode=$mode;status='FLATTENED';
  position_state='FLAT';process_shutdown='VERIFIED_EXIT';lanes=$lanes}}
}
$fake | Add-Member -MemberType ScriptMethod -Name verify_durable_stop_receipt -Value {
 param($mode,$result)
 $this.durableChecks++
 return $this.kind -ne 'durable_missing'
}
if ($case -eq 'owner_unverified') {
 try {New-AtlasAcceptedPaperStopSignalOwner -AcceptedSession $fake -OfflineTestId $testId | Out-Null;
      Write-Output 'UNEXPECTED_OWNER_ACCEPTED'}
 catch {Write-Output ('REFUSED:'+$_.Exception.Message)}
 exit 0
}
$owner=New-AtlasAcceptedPaperStopSignalOwner -AcceptedSession $fake -OfflineTestId $testId
try {
  if ($case -eq 'duplicate_owner') {
   try {New-AtlasAcceptedPaperStopSignalOwner -AcceptedSession $fake -OfflineTestId $testId | Out-Null;
        Write-Output 'UNEXPECTED_DUPLICATE_OWNER'}
   catch {Write-Output ('REFUSED:'+$_.Exception.Message)}
   exit 0
  }
  if ($env:ATLAS_OFFLINE_WAIT_EXTERNAL -eq 'YES') {
   Write-Output 'READY_FOR_OFFLINE_EXTERNAL_SIGNAL'
  } else {
   $request=Request-AtlasPaperOwnedStopSignal -OfflineTestId $testId
   if ($request.status -ne 'REQUESTED_NOT_VERIFIED' -or $request.financial_flatness_verified -ne $false) {
     throw 'FALSE_CLIENT_FLATNESS_CLAIM'
   }
  }
  try {
    $result=Wait-AtlasOwnedPaperStopSignal -Ownership $owner -TimeoutMilliseconds 7000
    Write-Output ('RESULT:'+$result.phase+':'+$result.outcome.status+':calls='+$fake.calls+':durable='+$fake.durableChecks)
  } catch {Write-Output ('REFUSED:'+$_.Exception.Message+':calls='+$fake.calls+':durable='+$fake.durableChecks)}
  if($case -eq 'double_signal') {
   Request-AtlasPaperOwnedStopSignal -OfflineTestId $testId | Out-Null
   try {Wait-AtlasOwnedPaperStopSignal -Ownership $owner -TimeoutMilliseconds 10 | Out-Null;
        Write-Output 'UNEXPECTED_STOP_REPLAY'}
   catch {Write-Output ('REPLAY_REFUSED:'+$_.Exception.Message+':calls='+$fake.calls)}
  }
} finally {Close-AtlasPaperStopSignalOwner -Ownership $owner}
"""


def env_for(case, test_id):
    return dict(os.environ, ATLAS_OFFLINE_OWNER_MODULE=str(MODULE),
                ATLAS_OFFLINE_OWNER_CASE=case, ATLAS_OFFLINE_OWNER_TEST_ID=test_id)


def invoke(case):
    test_id = 'test-' + uuid.uuid4().hex
    p = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command', OWNER],
                       env=env_for(case, test_id), capture_output=True, text=True,
                       timeout=18, check=False)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def test_owner_signal_verifies_offline_durable_two_account_result_once():
    assert invoke('ok') == 'RESULT:FINISHED:FLATTENED:calls=1:durable=1'


def test_duplicate_owner_refused_at_windows_mutex():
    assert invoke('duplicate_owner') == 'REFUSED:PAPER_STOP_SIGNAL_OTHER_OWNER_ACTIVE'


def test_unknown_owner_not_created_or_accepted():
    assert invoke('owner_unverified') == 'REFUSED:PAPER_STOP_SIGNAL_ACCEPTED_OWNER_REQUIRED'


@pytest.mark.parametrize('case,reason', [
    ('missing_hl','PAPER_STOP_HANDOFF_TWO_ACCOUNT_FLATNESS_UNVERIFIED'),
    ('unflattened_hl','PAPER_STOP_HANDOFF_TWO_ACCOUNT_FLATNESS_UNVERIFIED'),
    ('durable_missing','PAPER_STOP_SIGNAL_DURABLE_RECEIPT_UNVERIFIED'),
    ('changed_session','PAPER_STOP_HANDOFF_SESSION_CHANGED'),
    ('throw_after_stop','PAPER_STOP_HANDOFF_DISPATCH_UNVERIFIED'),
])
def test_no_partial_or_uncertain_financial_stop_is_reported_successful(case, reason):
    result = invoke(case)
    assert result.startswith('REFUSED:' + reason), result
    assert ':calls=1:' in result


def test_signal_cannot_replay_a_finished_owner_stop():
    result = invoke('double_signal')
    assert result.splitlines()[0] == 'RESULT:FINISHED:FLATTENED:calls=1:durable=1'
    assert result.splitlines()[1] == 'REPLAY_REFUSED:PAPER_STOP_SIGNAL_OWNER_BINDING_REQUIRED:calls=1'


def test_separate_shortcut_process_can_signal_synthetic_owner_without_credentials():
    test_id = 'test-' + uuid.uuid4().hex
    env = env_for('ok',test_id)
    env['ATLAS_OFFLINE_WAIT_EXTERNAL'] = 'YES'
    proc = subprocess.Popen([PS,'-NoProfile','-NonInteractive','-Command',OWNER],
                            env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert proc.stdout.readline().strip() == 'READY_FOR_OFFLINE_EXTERNAL_SIGNAL'
        client = subprocess.run([PS,'-NoProfile','-NonInteractive','-Command',
                  'Import-Module $env:ATLAS_OFFLINE_OWNER_MODULE -Force; '
                  'Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_OFFLINE_OWNER_TEST_ID | ConvertTo-Json -Compress'],
                env=env_for('ok',test_id),capture_output=True,text=True,timeout=10,check=False)
        assert client.returncode == 0,client.stderr
        assert 'REQUESTED_NOT_VERIFIED' in client.stdout
        assert 'FLATTENED' not in client.stdout
        stdout,stderr=proc.communicate(timeout=12)
        assert proc.returncode == 0,stderr
        assert stdout.strip() == 'RESULT:FINISHED:FLATTENED:calls=1:durable=1'
    finally:
        if proc.poll() is None:
            proc.kill();proc.communicate(timeout=5)
