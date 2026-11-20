"""Selected R14 installed native Stop IPC against disposable two-lane PAPER owner.

Actual Windows event + selected R14 PowerShell stop modules, but absolutely no
financial Atlas account, actual PAPER runtime, real desktop shortcut or market.
Synthetic owner keeps a temp SQLite ledger and original two-lane fixture.
"""
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from scripts.observation_runtime.atlas_r14_selected_paper_readiness import (
    collect_selected_reference,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE = Path("D:/AtlasRuntime/releases/7ff9d3dba2eabe110f843c13efac49464805de2a")
MODULE = RELEASE/"scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1"
HANDOFF = RELEASE/"scripts/windows/Atlas-Paper-Stop-Handoff.psm1"
OWNER = ROOT/"tests/fixtures/atlas_disposable_windows_stop_owner.ps1"
EXPECTED = {
    "Atlas-Paper-Owned-Stop-Signal.psm1":
        "893a81bf11f7849f8ba20b31bb9e96b45e30ed09e35485ad018e1d7a21d1e9dc",
    "Atlas-Paper-Stop-Handoff.psm1":
        "f4a795ecd4abcc9a632fd6fadbea4d74aaf4967f5fb3adc214bb553966dd4b4b",
}


def verify_selected_native_source():
    state = collect_selected_reference()
    assert state["revision"] == 13
    assert state["native_selection_record_verified"] is True
    for name, checksum in EXPECTED.items():
        native = RELEASE/"scripts/windows"/name
        assert native.is_file() and not native.is_symlink()
        assert hashlib.sha256(native.read_bytes()).hexdigest() == checksum
        # No copied module or source mix: selected native bytes equal reviewed workspace.
        assert hashlib.sha256((ROOT/"scripts/windows"/name).read_bytes()).hexdigest() == checksum


@pytest.mark.skipif(sys.platform != "win32", reason="Requires real Windows kernel event")
def test_selected_r14_native_stop_module_verifies_two_lane_durable_flatness(tmp_path):
    verify_selected_native_source()
    offline = "test-" + uuid.uuid4().hex
    receipt = tmp_path/"disposable-flatten-receipt.json"
    command = [
        "powershell.exe", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(OWNER),
        "-OfflineTestId", offline, "-ReceiptPath", str(receipt),
        "-SelectedR14StopModule", str(MODULE),
    ]
    owner = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, bufsize=1)
    try:
        ready = owner.stdout.readline().strip()
        assert ready == "DISPOSABLE_NATIVE_OWNER_READY", (
            "Native selected R14 owner never became ready: " + repr(ready))
        environment = {**os.environ, "ATLAS_DISPOSABLE_STOP_ID": offline,
                       "ATLAS_SELECTED_R14_STOP_MODULE": str(MODULE)}
        sender = r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_SELECTED_R14_STOP_MODULE -Force -ErrorAction Stop
$result=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_DISPOSABLE_STOP_ID
if($result.status -cne 'REQUESTED_NOT_VERIFIED' -or $result.financial_flatness_verified -ne $false){
    throw 'SELECTED_R14_SIGNAL_MISLABELLED_FINANCIAL_FLATNESS'
}
Write-Output 'R14_NATIVE_SIGNAL_REQUESTED_NOT_VERIFIED'
"""
        sent = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", sender],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=20)
        assert sent.returncode == 0, sent.stderr
        assert sent.stdout.strip() == "R14_NATIVE_SIGNAL_REQUESTED_NOT_VERIFIED"
        output, errors = owner.communicate(timeout=25)
        assert owner.returncode == 0, errors
        assert "DISPOSABLE_TWO_LANE_DURABLE_FLATTEN_VERIFIED" in output
        persisted = json.loads(receipt.read_text(encoding="utf-8"))
        assert persisted["outcome"]["position_state"] == "FLAT"
        assert persisted["outcome"]["process_shutdown"] == "VERIFIED_EXIT"
        assert persisted["disposable_positions_before"] == {
            "QUALITY_DIPS":5, "HYPERLIQUID":3}
        assert persisted["disposable_positions_after"] == {
            "QUALITY_DIPS":0, "HYPERLIQUID":0}
        assert set(persisted["outcome"]["lanes"]) == {
            "QUALITY_DIPS", "HYPERLIQUID"}
        assert all(x["state"] == "ACKNOWLEDGED_FLAT_AND_DRAINED"
                   for x in persisted["outcome"]["lanes"].values())
        from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger
        db = tmp_path/"disposable-stop-ledger.sqlite"
        assert db.is_file()
        ledger = PaperStopReceiptLedger(db)
        assert ledger.inspect_session("test-disposable-two-lane-session") == {
            "state":"FINISHED", "mode":"SHUTDOWN_FLATTEN", "receipt": persisted}
        assert PaperStopReceiptLedger(db).recover(
            "test-disposable-two-lane-session","SHUTDOWN_FLATTEN") == {
            "state":"RECEIPT_RECORDED", "mode":"SHUTDOWN_FLATTEN", "receipt": persisted}
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.communicate(timeout=10)


@pytest.mark.skipif(sys.platform != "win32", reason="Requires native Windows")
def test_selected_r14_unowned_stop_refuses_without_fake_flatness(tmp_path):
    verify_selected_native_source()
    unique = "test-" + uuid.uuid4().hex
    env = {**os.environ,"ATLAS_DISPOSABLE_STOP_ID":unique,
           "ATLAS_SELECTED_R14_STOP_MODULE":str(MODULE)}
    script = r"""
$ErrorActionPreference='Stop'
Import-Module $env:ATLAS_SELECTED_R14_STOP_MODULE -Force
try {
    $null=Request-AtlasPaperOwnedStopSignal -OfflineTestId $env:ATLAS_DISPOSABLE_STOP_ID
    throw 'UNACCEPTED_NATIVE_SELECTED_R14_STOP'
} catch {
    if($_.Exception.Message -cne 'PAPER_STOP_SIGNAL_NO_OWNED_SESSION'){throw}
    Write-Output 'SELECTED_R14_NO_OWNED_SESSION_REFUSED'
}
"""
    result = subprocess.run(
        ["powershell.exe","-NoProfile","-NonInteractive","-Command",script],
        cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode == 0,result.stderr
    assert result.stdout.strip() == "SELECTED_R14_NO_OWNED_SESSION_REFUSED"
    assert list(tmp_path.iterdir()) == []
