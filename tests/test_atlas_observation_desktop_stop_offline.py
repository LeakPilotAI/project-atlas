"""Observation-only desktop Stop IPC; isolated from real owner and finance."""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest


ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/windows/Atlas-Observation-Stop.ps1"
START=ROOT/"scripts/windows/Atlas-Observation-Shortcut.ps1"


def _call(*args):
    return subprocess.run(
        ["powershell.exe","-NoProfile","-NonInteractive",
         "-ExecutionPolicy","Bypass","-File",str(SCRIPT),*args],
        cwd=ROOT,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},
        capture_output=True,text=True,timeout=9,
    )


def test_observation_launcher_does_not_auto_authorize_market_data_or_legacy_stop():
    text=START.read_text(encoding="utf-8-sig")
    assert "$ready = Open-AtlasObservationDashboard $root\n" in text.replace("\r\n","\n")
    assert "$ready = Open-AtlasObservationDashboard $root -BoundedDataOnly" not in text
    assert "existing Stop Atlas desktop shortcut requests this observation dashboard" in text
    assert "NOT financial PAPER position flattening" in text
    script=SCRIPT.read_text(encoding="utf-8-sig")
    active="\n".join(line for line in script.splitlines()
                     if line.strip() and not line.lstrip().startswith("#"))
    for forbidden in ("Stop-Process","taskkill","docker","Atlas-Stop.ps1",
                      "app.personal_paper","Get-NetTCPConnection","Invoke-WebRequest",
                      "Invoke-RestMethod","-BoundedDataOnly"):
        assert forbidden.lower() not in active.lower()
    assert "OBSERVATION_ONLY_NO_FINANCIAL_FLATNESS_CLAIM" in script


@pytest.mark.skipif(sys.platform!="win32",reason="Windows named kernel handles only")
def test_disposable_observation_owner_receives_one_stop_without_process_kill(tmp_path):
    token="test-"+uuid.uuid4().hex
    fixture=tmp_path/"isolated-observation-owner.ps1"
    fixture.write_text(r"""
param([Parameter(Mandatory=$true)][string]$TestId)
$ErrorActionPreference='Stop'
if($TestId -cnotmatch '^test-[a-f0-9]{32}$'){throw 'BAD_TEST_ID'}
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$mutexName="Local\AtlasObservationOwnerTest_${sid}_$TestId"
$eventName="Local\AtlasObservationStopTest_${sid}_$TestId"
$created=$false
$mutex=New-Object System.Threading.Mutex($true,$mutexName,[ref]$created)
if(-not $created){throw 'TEST_MUTEX_ALREADY_OWNED'}
$event=$null
try {
    $event=New-Object System.Threading.EventWaitHandle($false,[System.Threading.EventResetMode]::AutoReset,$eventName)
    $event.Reset()|Out-Null
    Write-Output 'ISOLATED_OBSERVATION_OWNER_READY'
    [Console]::Out.Flush()
    if(-not $event.WaitOne(7000)){throw 'ISOLATED_OBSERVATION_STOP_NOT_RECEIVED'}
    Write-Output 'ISOLATED_OBSERVATION_OWNER_OBSERVED_STOP'
} finally {
    if($null -ne $event){$event.Dispose()}
    $mutex.ReleaseMutex();$mutex.Dispose()
}
""",encoding="utf-8")
    child=subprocess.Popen(
        ["powershell.exe","-NoProfile","-NonInteractive",
         "-ExecutionPolicy","Bypass","-File",str(fixture),"-TestId",token],
        cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
    )
    try:
        ready=child.stdout.readline().strip()
        if ready!="ISOLATED_OBSERVATION_OWNER_READY":
            _,err=child.communicate(timeout=5)
            raise AssertionError(f"Isolated observation owner failed: {ready!r} {err[-700:]}")
        called=_call("-OfflineTestId",token)
        assert called.returncode==0,called.stderr
        assert called.stdout.count("ATLAS_OBSERVATION_STOP_REQUESTED_NOT_CONFIRMED")==1
        assert "OBSERVATION_ONLY_NO_FINANCIAL_FLATNESS_CLAIM" in called.stdout
        result,err=child.communicate(timeout=8)
        assert child.returncode==0,err
        assert "ISOLATED_OBSERVATION_OWNER_OBSERVED_STOP" in result
        no_owner=_call("-OfflineTestId",token)
        assert no_owner.returncode!=0
        assert "ATLAS_OBSERVATION_STOP_NO_OWNED_SESSION" in no_owner.stderr
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=4)


@pytest.mark.skipif(sys.platform!="win32",reason="Windows named kernel handles only")
def test_isolated_observation_stop_rejects_unowned_invalid_namespace():
    token="test-"+uuid.uuid4().hex
    not_owned=_call("-OfflineTestId",token)
    assert not_owned.returncode!=0
    assert "ATLAS_OBSERVATION_STOP_NO_OWNED_SESSION" in not_owned.stderr
    invalid=_call("-OfflineTestId","test-../../production")
    assert invalid.returncode!=0
    assert "ATLAS_OBSERVATION_STOP_TEST_NAMESPACE_REFUSED" in invalid.stderr
