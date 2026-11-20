"""Exact selected R15 native Windows Stop IPC against disposable two-lane paper.

Only a synthetic stop owner, temporary SQLite receipt and isolated Win32 test
event are used; no real accounts, native finance writers, or provider access.
"""
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    selected_code,
)
from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger

ROOT=Path(__file__).resolve().parents[1]
RELEASE=Path("D:/AtlasRuntime/releases/2c79a8d846d6b33669008114732ae5896153812a")
MODULE=RELEASE/"scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1"
FIXTURE=ROOT/"tests/fixtures/atlas_disposable_windows_stop_owner.ps1"
MODULE_SHA="893a81bf11f7849f8ba20b31bb9e96b45e30ed09e35485ad018e1d7a21d1e9dc"


def exact_r15_stop_source():
    selected=selected_code()
    assert selected["revision"]==14
    assert selected["selected_native_head"]==(
        "274f5b00ee0e2f6271c6dd1dc5316f7d9124e932483038a6d93ef62ddbd2cd25")
    assert hashlib.sha256(MODULE.read_bytes()).hexdigest()==MODULE_SHA
    assert hashlib.sha256(
        (ROOT/"scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1")
        .read_bytes()).hexdigest()==MODULE_SHA


@pytest.mark.skipif(sys.platform!="win32",reason="Native Windows events only")
def test_selected_r15_native_ipc_verified_two_lane_disposable_stop(tmp_path):
    exact_r15_stop_source()
    token="test-"+uuid.uuid4().hex
    receipt=tmp_path/"disposable-flatten-receipt.json"
    owner=subprocess.Popen(
        ["powershell.exe","-NoProfile","-NonInteractive",
         "-ExecutionPolicy","Bypass","-File",str(FIXTURE),
         "-OfflineTestId",token,
         "-ReceiptPath",str(receipt),
         "-SelectedR15StopModule",str(MODULE)],
        cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        text=True,bufsize=1,
    )
    try:
        ready=owner.stdout.readline().strip()
        if ready!="DISPOSABLE_NATIVE_OWNER_READY":
            remainder,errors=owner.communicate(timeout=8)
            raise AssertionError("R15_DISPOSABLE_OWNER_FAILED:"+repr(ready)+":"+errors[-1800:])
        sender=r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_SELECTED_R15_STOP_MODULE -Force -ErrorAction Stop
$r=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_DISPOSABLE_STOP_ID
if($r.status -cne 'REQUESTED_NOT_VERIFIED' -or $r.financial_flatness_verified -ne $false){
    throw 'FALSE_FINANCIAL_FLATNESS_FROM_UNVERIFIED_SIGNAL'
}
Write-Output 'R15_DISPOSABLE_STOP_SIGNAL_REQUESTED_ONLY'
"""
        env={**os.environ,"ATLAS_SELECTED_R15_STOP_MODULE":str(MODULE),
             "ATLAS_DISPOSABLE_STOP_ID":token}
        sent=subprocess.run(
            ["powershell.exe","-NoProfile","-NonInteractive","-Command",sender],
            cwd=ROOT,env=env,capture_output=True,text=True,timeout=18)
        assert sent.returncode==0,sent.stderr
        assert sent.stdout.strip()=="R15_DISPOSABLE_STOP_SIGNAL_REQUESTED_ONLY"
        output,errors=owner.communicate(timeout=25)
        assert owner.returncode==0,errors
        assert "DISPOSABLE_TWO_LANE_DURABLE_FLATTEN_VERIFIED" in output
        complete=json.loads(receipt.read_bytes())
        assert complete["phase"]=="FINISHED"
        assert complete["outcome"]["position_state"]=="FLAT"
        assert complete["outcome"]["process_shutdown"]=="VERIFIED_EXIT"
        assert complete["disposable_positions_before"]=={
            "QUALITY_DIPS":5,"HYPERLIQUID":3}
        assert complete["disposable_positions_after"]=={
            "QUALITY_DIPS":0,"HYPERLIQUID":0}
        assert all(item["state"]=="ACKNOWLEDGED_FLAT_AND_DRAINED"
                   for item in complete["outcome"]["lanes"].values())
        db=tmp_path/"disposable-stop-ledger.sqlite"
        assert PaperStopReceiptLedger(db).recover(
            "test-disposable-two-lane-session","SHUTDOWN_FLATTEN")=={
                "state":"RECEIPT_RECORDED","mode":"SHUTDOWN_FLATTEN",
                "receipt":complete}
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.communicate(timeout=8)


@pytest.mark.skipif(sys.platform!="win32",reason="Native Windows events only")
def test_selected_r15_stop_without_owner_refuses(tmp_path):
    exact_r15_stop_source()
    env={**os.environ,"ATLAS_SELECTED_R15_STOP_MODULE":str(MODULE),
         "ATLAS_DISPOSABLE_STOP_ID":"test-"+uuid.uuid4().hex}
    sender=r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_SELECTED_R15_STOP_MODULE -Force
try {
    $null=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_DISPOSABLE_STOP_ID
    throw 'UNOWNED_STOP_MUST_NOT_BE_ACCEPTED'
} catch {
    if($_.Exception.Message -cne 'PAPER_STOP_SIGNAL_NO_OWNED_SESSION'){throw}
    Write-Output 'R15_UNOWNED_STOP_REFUSED'
}
"""
    out=subprocess.run(
        ["powershell.exe","-NoProfile","-NonInteractive","-Command",sender],
        cwd=ROOT,env=env,capture_output=True,text=True,timeout=18)
    assert out.returncode==0,out.stderr
    assert out.stdout.strip()=="R15_UNOWNED_STOP_REFUSED"
    assert list(tmp_path.iterdir())==[]
