"""Real Windows kernel Stop IPC with disposable fake owner; NO Atlas services.

Run only on Windows. Uses a unique test event and an isolated temp receipt.
No financial accounts/position writers, provider sockets or desktop shortcut.
"""
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
OWNER=ROOT/'tests/fixtures/atlas_disposable_windows_stop_owner.ps1'
STOP_MODULE=ROOT/'scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1'


@pytest.mark.skipif(sys.platform!='win32',reason='native Windows event only')
def test_real_separate_process_stop_signal_one_owner_two_lanes_and_disk_receipt(tmp_path):
    offline='test-'+uuid.uuid4().hex
    receipt=tmp_path/'disposable-flatten-receipt.json'
    cmd=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
         '-File',str(OWNER),'-OfflineTestId',offline,'-ReceiptPath',str(receipt)]
    owner=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           text=True,bufsize=1)
    try:
        ready=owner.stdout.readline().strip()
        assert ready=='DISPOSABLE_NATIVE_OWNER_READY',f'owner did not bind: {ready!r}'
        env={**os.environ,'ATLAS_DISPOSABLE_STOP_ID':offline,
             'ATLAS_DISPOSABLE_STOP_MODULE':str(STOP_MODULE)}
        sender=r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_DISPOSABLE_STOP_MODULE -Force
$value=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_DISPOSABLE_STOP_ID
if($value.status -cne 'REQUESTED_NOT_VERIFIED' -or $value.financial_flatness_verified -ne $false){throw 'UNVERIFIED_REQUEST_MISLABELLED'}
Write-Output 'DISPOSABLE_STOP_SIGNAL_SENT_UNVERIFIED'
"""
        child=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive',
                              '-Command',sender],cwd=ROOT,env=env,
                              capture_output=True,text=True,timeout=20)
        assert child.returncode==0,child.stderr
        assert child.stdout.strip()=='DISPOSABLE_STOP_SIGNAL_SENT_UNVERIFIED'
        rest,error=owner.communicate(timeout=20)
        assert owner.returncode==0,error
        assert 'DISPOSABLE_TWO_LANE_DURABLE_FLATTEN_VERIFIED' in rest
        assert receipt.is_file()
        persisted=json.loads(receipt.read_text(encoding='utf-8'))
        assert persisted['phase']=='FINISHED'
        assert persisted['outcome']['position_state']=='FLAT'
        assert persisted['outcome']['process_shutdown']=='VERIFIED_EXIT'
        assert set(persisted['outcome']['lanes'])=={'QUALITY_DIPS','HYPERLIQUID'}
        assert all(v['state']=='ACKNOWLEDGED_FLAT_AND_DRAINED'
                   for v in persisted['outcome']['lanes'].values())
        assert persisted['disposable_positions_before']=={'QUALITY_DIPS':5,'HYPERLIQUID':3}
        assert persisted['disposable_positions_after']=={'QUALITY_DIPS':0,'HYPERLIQUID':0}
        from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger, StopReceiptConflict
        db_path=tmp_path/'disposable-stop-ledger.sqlite'
        assert db_path.is_file()
        reopened=PaperStopReceiptLedger(db_path)
        assert reopened.inspect_session('test-disposable-two-lane-session')=={
            'state':'FINISHED','mode':'SHUTDOWN_FLATTEN','receipt':persisted}
        assert PaperStopReceiptLedger(db_path).recover(
            'test-disposable-two-lane-session','SHUTDOWN_FLATTEN')=={
            'state':'RECEIPT_RECORDED','mode':'SHUTDOWN_FLATTEN','receipt':persisted}
        with pytest.raises(StopReceiptConflict,match='STOP_INTENT_ALREADY_EXISTS'):
            reopened.reserve_fresh('test-disposable-two-lane-session','SHUTDOWN_FLATTEN')
        assert not (ROOT/'logs/diagnostics'/'atlas-native-paper-stop-owner-persistent.json').exists()
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.communicate(timeout=10)


@pytest.mark.skipif(sys.platform!='win32',reason='native Windows event only')
def test_unknown_test_namespace_refuses_and_never_creates_durable_receipt(tmp_path):
    offline='test-'+uuid.uuid4().hex
    env={**os.environ,'ATLAS_DISPOSABLE_STOP_ID':offline,
         'ATLAS_DISPOSABLE_STOP_MODULE':str(STOP_MODULE)}
    script=r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_DISPOSABLE_STOP_MODULE -Force
try {
    $null=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_DISPOSABLE_STOP_ID
    throw 'UNACCEPTED_UNOWNED_STOP'
} catch {
    if($_.Exception.Message -cne 'PAPER_STOP_SIGNAL_NO_OWNED_SESSION'){throw}
    Write-Output 'NO_OWNED_PAPER_SESSION_REFUSED'
}
"""
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive',
                           '-Command',script],cwd=ROOT,env=env,
                          capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='NO_OWNED_PAPER_SESSION_REFUSED'
    assert list(tmp_path.iterdir())==[]


def test_real_desktop_shortcut_still_points_to_nonfinancial_observation_stop():
    # Static historical shell target; NEVER edits actual desktop link.
    file=ROOT/'scripts/windows/Atlas-Observation-Shortcut-Stop.ps1'
    source=file.read_text(encoding='utf-8-sig')
    assert 'AtlasObservationStop_' in source
    assert 'AtlasFinancialPaperStop_' not in source
    assert 'Financial flattening' not in source
    future=(ROOT/'scripts/windows/Atlas-Paper-Stop-Request.ps1').read_text(encoding='utf-8-sig')
    assert 'REQUESTED_NOT_VERIFIED' in future
    assert 'NOT YET CONFIRMED' in future
    assert 'Atlas-Paper-Owned-Stop-Signal.psm1' in future


def test_actual_stop_sqlite_fixture_refuses_forged_flat_and_preserves_pending(tmp_path):
    """Real ledger, synthetic receipt. A false flat claim must stay pending."""
    from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger
    from tests.fixtures.atlas_disposable_stop_sqlite import operate, SESSION, MODE
    db=tmp_path/'disposable-stop-ledger.sqlite'
    receipt=tmp_path/'disposable-flatten-receipt.json'
    operate('reserve',db,receipt)
    forged={'schema':'QD_CONTROL_STOP_V1','phase':'FINISHED','outcome':{
        'schema':'QD_AUTO_SHUTDOWN_V1','mode':MODE,'status':'FLATTENED',
        'position_state':'FLAT','process_shutdown':'VERIFIED_EXIT',
        'lanes':{'QUALITY_DIPS':{'state':'ACKNOWLEDGED_FLAT_AND_DRAINED'},
                 'HYPERLIQUID':{'state':'ACKNOWLEDGED_FLAT_AND_DRAINED'}}},
        'disposable_positions_before':{'QUALITY_DIPS':5,'HYPERLIQUID':3},
        'disposable_positions_after':{'QUALITY_DIPS':1,'HYPERLIQUID':0}}
    receipt.write_text(json.dumps(forged),encoding='utf-8')
    with pytest.raises(ValueError,match='DISPOSABLE_NATIVE_STOP_TWO_LANE_FLATNESS_REFUSED'):
        operate('finish',db,receipt)
    assert PaperStopReceiptLedger(db).recover(SESSION,MODE)=={
        'state':'SHUTDOWN_UNVERIFIED','mode':MODE,'receipt':None}
    assert PaperStopReceiptLedger(db).summarize_recovery()['pending_unverified']==1
    with pytest.raises(ValueError,match='DISPOSABLE_STOP_LEDGER_CREATE_ONCE_REQUIRED'):
        operate('reserve',db,receipt)


def test_real_stop_sqlite_fixture_requires_existing_pending_intent(tmp_path):
    from tests.fixtures.atlas_disposable_stop_sqlite import operate
    db=tmp_path/'disposable-stop-ledger.sqlite'
    receipt=tmp_path/'disposable-flatten-receipt.json'
    with pytest.raises(ValueError,match='DISPOSABLE_STOP_LEDGER_MISSING'):
        operate('finish',db,receipt)
    with pytest.raises(ValueError,match='DISPOSABLE_STOP_LEDGER_MISSING'):
        operate('verify',db,receipt)
