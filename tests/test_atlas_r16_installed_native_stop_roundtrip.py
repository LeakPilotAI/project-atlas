"""Actual SELECTED R16 native Stop module: disposable two-lane Windows IPC.

The original immutable installed R16 PowerShell Stop signal + handoff are
used as the real transport. A temporary test owner/ledger simulates two
separate PAPER lanes; NO installed financial owner, accounts, provider,
real orders, production desktop shortcut or real Stop side effects.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from app.services.paper_stop_receipt_ledger import (
    PaperStopReceiptLedger, StopReceiptConflict,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    RELEASE, SOURCE, R16_HEAD, selected_code,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

ROOT=Path(__file__).resolve().parents[1]
STOP=RELEASE/"scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1"
HANDOFF=RELEASE/"scripts/windows/Atlas-Paper-Stop-Handoff.psm1"
OWNER=ROOT/"tests/fixtures/atlas_disposable_windows_stop_owner.ps1"
SHA={
    "Atlas-Paper-Owned-Stop-Signal.psm1":
        "893a81bf11f7849f8ba20b31bb9e96b45e30ed09e35485ad018e1d7a21d1e9dc",
    "Atlas-Paper-Stop-Handoff.psm1":
        "f4a795ecd4abcc9a632fd6fadbea4d74aaf4967f5fb3adc214bb553966dd4b4b",
}


def require_original_selected_r16():
    result=selected_code()
    assert result["selected_revision"]==15
    assert result["selected_native_head"]==R16_HEAD
    assert result["selected_release"]==SOURCE
    assert result["code_selection_accepted"] is True
    assert result["financial_writer_operational_accepted"] is False
    assert result["paper_start_authorized"] is False
    assert result["live_trading_authorized"] is False
    for file,sha in SHA.items():
        actual=RELEASE/"scripts/windows"/file
        assert actual.is_file() and not actual.is_symlink()
        assert hashlib.sha256(actual.read_bytes()).hexdigest()==sha
        assert hashlib.sha256(
            (ROOT/"scripts/windows"/file).read_bytes()).hexdigest()==sha
    return result


@pytest.mark.skipif(sys.platform!="win32", reason="requires genuine Windows native events")
def test_selected_r16_original_native_stop_two_lane_disposable_flat_and_durable_replay(tmp_path):
    before=inspect_two_lane_native_roots()
    assert before["all_twelve_distinct_and_empty"] is True
    assert require_original_selected_r16()["selected_revision"]==15
    # One independent full native Windows installed file-handle verification
    # immediately before the actual R16 cross-process Stop roundtrip.
    deep=selected_code(verify_original_installed_handles=True)
    assert deep["installed_original_handles_reverified_in_this_call"] is True
    token="test-"+uuid.uuid4().hex
    receipt=tmp_path/"disposable-flatten-receipt.json"
    ledger=tmp_path/"disposable-stop-ledger.sqlite"
    cmd=[
        "powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass",
        "-File",str(OWNER),"-OfflineTestId",token,"-ReceiptPath",str(receipt),
        "-SelectedR16StopModule",str(STOP),
    ]
    owner=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,text=True,bufsize=1)
    try:
        ready=owner.stdout.readline().strip()
        if ready!="DISPOSABLE_NATIVE_OWNER_READY":
            remainder,errors=owner.communicate(timeout=10)
            raise AssertionError("R16_NATIVE_DISPOSABLE_OWNER_NOT_READY:"+repr(ready)+":"+errors[-1800:])
        request=r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_R16_NATIVE_STOP_MODULE -Force -ErrorAction Stop
$send=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_DISPOSABLE_STOP_ID
if($send.status -cne 'REQUESTED_NOT_VERIFIED' -or $send.financial_flatness_verified -ne $false){
    throw 'R16_STOP_REQUEST_MUST_NOT_CLAIM_FINANCIAL_FLATNESS'
}
Write-Output 'R16_NATIVE_DISPOSABLE_STOP_SIGNAL_REQUESTED_ONLY'
"""
        env={**os.environ,"ATLAS_R16_NATIVE_STOP_MODULE":str(STOP),
             "ATLAS_DISPOSABLE_STOP_ID":token}
        sent=subprocess.run(
            ["powershell.exe","-NoProfile","-NonInteractive","-Command",request],
            cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
        assert sent.returncode==0,sent.stderr
        assert sent.stdout.strip()=="R16_NATIVE_DISPOSABLE_STOP_SIGNAL_REQUESTED_ONLY"
        remainder,errors=owner.communicate(timeout=25)
        assert owner.returncode==0,errors
        assert "DISPOSABLE_TWO_LANE_DURABLE_FLATTEN_VERIFIED" in remainder
        assert receipt.is_file() and ledger.is_file()
        stored=json.loads(receipt.read_bytes())
        assert stored["schema"]=="QD_CONTROL_STOP_V1"
        assert stored["phase"]=="FINISHED"
        assert stored["outcome"]["mode"]=="SHUTDOWN_FLATTEN"
        assert stored["outcome"]["status"]=="FLATTENED"
        assert stored["outcome"]["position_state"]=="FLAT"
        assert stored["outcome"]["process_shutdown"]=="VERIFIED_EXIT"
        assert stored["disposable_positions_before"]=={
            "QUALITY_DIPS":5, "HYPERLIQUID":3}
        assert stored["disposable_positions_after"]=={
            "QUALITY_DIPS":0, "HYPERLIQUID":0}
        assert set(stored["outcome"]["lanes"])=={
            "QUALITY_DIPS","HYPERLIQUID"}
        assert all(
            item["state"]=="ACKNOWLEDGED_FLAT_AND_DRAINED"
            for item in stored["outcome"]["lanes"].values())
        recovered=PaperStopReceiptLedger(ledger).recover(
            "test-disposable-two-lane-session","SHUTDOWN_FLATTEN")
        assert recovered=={
            "state":"RECEIPT_RECORDED",
            "mode":"SHUTDOWN_FLATTEN",
            "receipt":stored,
        }
        with pytest.raises(StopReceiptConflict,match="STOP_INTENT_ALREADY_EXISTS"):
            PaperStopReceiptLedger(ledger).reserve_fresh(
                "test-disposable-two-lane-session","SHUTDOWN_FLATTEN")
        # The original Win32 owner and its event are now gone: a second
        # desktop signal must refuse, never dispatch or imply flatten again.
        retry=r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_R16_NATIVE_STOP_MODULE -Force -ErrorAction Stop
try {
    $null=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_DISPOSABLE_STOP_ID
    throw 'R16_STOP_REPLAY_UNEXPECTEDLY_GRANTED'
} catch {
    if($_.Exception.Message -cne 'PAPER_STOP_SIGNAL_NO_OWNED_SESSION'){throw}
    Write-Output 'R16_ONE_SHOT_STOP_EVENT_GONE_NO_REPLAY'
}
"""
        replay=subprocess.run(
            ["powershell.exe","-NoProfile","-NonInteractive","-Command",retry],
            cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
        assert replay.returncode==0,replay.stderr
        assert replay.stdout.strip()=="R16_ONE_SHOT_STOP_EVENT_GONE_NO_REPLAY"
        assert PaperStopReceiptLedger(ledger).recover(
            "test-disposable-two-lane-session","SHUTDOWN_FLATTEN")==recovered
        assert inspect_two_lane_native_roots()==before
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.communicate(timeout=10)


@pytest.mark.skipif(sys.platform!="win32",reason="requires genuine Windows native event")
def test_selected_r16_signal_without_owner_refuses_and_does_not_create_files(tmp_path):
    require_original_selected_r16()
    token="test-"+uuid.uuid4().hex
    env={**os.environ,"ATLAS_R16_NATIVE_STOP_MODULE":str(STOP),
         "ATLAS_DISPOSABLE_STOP_ID":token}
    sender=r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_R16_NATIVE_STOP_MODULE -Force -ErrorAction Stop
try {
    $null=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_DISPOSABLE_STOP_ID
    throw 'R16_UNOWNED_FINANCIAL_STOP_MUST_REFUSE'
} catch {
    if($_.Exception.Message -cne 'PAPER_STOP_SIGNAL_NO_OWNED_SESSION'){throw}
    Write-Output 'R16_NATIVE_STOP_NO_OWNED_SESSION_REFUSED'
}
"""
    result=subprocess.run(
        ["powershell.exe","-NoProfile","-NonInteractive","-Command",sender],
        cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=="R16_NATIVE_STOP_NO_OWNED_SESSION_REFUSED"
    assert list(tmp_path.iterdir())==[]


@pytest.mark.skipif(sys.platform!="win32",reason="requires Windows PowerShell")
@pytest.mark.parametrize("kind",["foreign_module","ambiguous_r15_r16"])
def test_disposable_owner_refuses_unpinned_r16_and_ambiguous_module_before_receipt(tmp_path,kind):
    require_original_selected_r16()
    token="test-"+uuid.uuid4().hex
    receipt=tmp_path/"disposable-flatten-receipt.json"
    fake=tmp_path/"foreign-stop.psm1"
    fake.write_text("function X { 'DO_NOT_IMPORT' }",encoding="utf-8")
    params=["-SelectedR16StopModule",str(fake)] if kind=="foreign_module" else [
        "-SelectedR16StopModule",str(STOP),
        "-SelectedR15StopModule",
        "D:\\AtlasRuntime\\releases\\2c79a8d846d6b33669008114732ae5896153812a\\scripts\\windows\\Atlas-Paper-Owned-Stop-Signal.psm1",
    ]
    cmd=["powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy",
         "Bypass","-File",str(OWNER),"-OfflineTestId",token,
         "-ReceiptPath",str(receipt),*params]
    out=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert out.returncode!=0
    assert ("DISPOSABLE_SELECTED_R16_NATIVE_STOP_SOURCE_REFUSED" if kind=="foreign_module"
            else "DISPOSABLE_NATIVE_STOP_RELEASE_AMBIGUOUS") in (
                out.stderr+out.stdout)
    assert not receipt.exists()
    assert not (tmp_path/"disposable-stop-ledger.sqlite").exists()


def test_selected_r16_module_identity_is_not_operator_or_paper_activation():
    proof=require_original_selected_r16()
    assert proof["financial_clock_operational_accepted"] is False
    assert proof["provider_source_operational_accepted"] is False
    assert proof["financial_writer_operational_accepted"] is False
    assert proof["paper_start_authorized"] is False
    assert proof["live_trading_authorized"] is False
