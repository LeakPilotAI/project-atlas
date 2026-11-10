"""Run with selected R14 native Python ONLY. Disposable financial-owner integration.

This proves the installed R14 PersonalInstalledPaperStopOwner + unified async
run-loop + Win32 Stop event can close one synthetic, ledger-backed two-lane
session through an actual second-process request. No real financial writers,
market providers, credentials, startups, native selector mutations or orders.
"""
import asyncio
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

R14 = Path("D:/AtlasRuntime/releases/7ff9d3dba2eabe110f843c13efac49464805de2a")
SOURCES = {
    "backend/app/services/personal_installed_stop_owner.py":
        "73033ec5829b9cd68daf580e6b4e4c6c958651a3e5f49c6e63bf4b84ea226113",
    "backend/app/services/unified_paper_runtime.py":
        "b5d1db20202a337b7ea6a9321377b56fac523ac5c3b67e6f7213eee857742007",
    "scripts/observation_runtime/personal_paper_python_stop_signal.py":
        "d002c7adf8ede7b3cc3aa0602c0807de70407061443781d203b6585fda629715",
    "scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1":
        "893a81bf11f7849f8ba20b31bb9e96b45e30ed09e35485ad018e1d7a21d1e9dc",
}
SELECTED_MODULE = R14 / "scripts/windows/Atlas-Paper-Owned-Stop-Signal.psm1"
STOP_REQUESTED = {"schema":"ATLAS_PAPER_STOP_SIGNAL_REQUEST_V1",
                  "status":"REQUESTED_NOT_VERIFIED","financial_flatness_verified":False}


def check_native_imports():
    from app.services import personal_installed_stop_owner as owner_mod
    from app.services import unified_paper_runtime as runtime_mod
    from scripts.observation_runtime import personal_paper_python_stop_signal as signal_mod

    assert Path(sys.executable).resolve() == (R14/"python/python.exe").resolve()
    for rel, expected in SOURCES.items():
        file = R14/rel
        assert file.is_file() and not file.is_symlink(), rel
        assert hashlib.sha256(file.read_bytes()).hexdigest() == expected, rel
    for module, rel in (
        (owner_mod, "backend/app/services/personal_installed_stop_owner.py"),
        (runtime_mod, "backend/app/services/unified_paper_runtime.py"),
        (signal_mod, "scripts/observation_runtime/personal_paper_python_stop_signal.py"),
    ):
        assert Path(module.__file__).resolve() == (R14/rel).resolve(), (
            "REFUSED_WORKSPACE_MODULE_SUBSTITUTION", module.__file__)
    from app.services.personal_installed_stop_owner import run_personal_installed_owner_session
    return run_personal_installed_owner_session


def request_native_stop(test_id):
    script = (
        "$ErrorActionPreference='Stop'; "
        "Import-Module '" + str(SELECTED_MODULE) + "' -Force -ErrorAction Stop; "
        "Request-AtlasPaperOwnedStopSignal -OfflineTestId '" + test_id +
        "' | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=R14, capture_output=True, text=True, timeout=12,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == STOP_REQUESTED


async def selected_owner_roundtrip(run):
    # Existing synthetic fixture models the already-accepted, installed
    # owner + ledger. It constructs NO real financial runtime or account.
    from test_personal_installed_owner_lifetime_offline import harness
    from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger

    with tempfile.TemporaryDirectory(prefix="atlas-r14-installed-owner-") as tmp:
        folder = Path(tmp)
        runtime, owner, calls, bridge = harness(folder)
        selected_test_id = "test-" + uuid.uuid4().hex
        original_poll = runtime.poll

        async def signal_during_real_run():
            view = await original_poll()
            await asyncio.to_thread(request_native_stop, selected_test_id)
            return view

        runtime.poll = signal_during_real_run
        receipt = await run(owner=owner, seconds=.5, interval=.05,
                            offline_test_id=selected_test_id)
        assert receipt["phase"] == "FINISHED"
        assert receipt["outcome"]["position_state"] == "FLAT"
        assert receipt["outcome"]["process_shutdown"] == "VERIFIED_EXIT"
        assert set(receipt["outcome"]["lanes"]) == {"QUALITY_DIPS","HYPERLIQUID"}
        assert all(v["state"]=="ACKNOWLEDGED_FLAT_AND_DRAINED"
                   for v in receipt["outcome"]["lanes"].values())
        assert calls == ["SHUTDOWN_FLATTEN"]
        assert owner._used and runtime.entry_closed.is_set()
        assert runtime.state == "STOPPED"
        assert not runtime.portfolio.operations
        db = folder/"synthetic-ledger.sqlite"
        reopened = PaperStopReceiptLedger(db)
        assert reopened.recover(owner.session_id,"SHUTDOWN_FLATTEN") == {
            "state":"RECEIPT_RECORDED","mode":"SHUTDOWN_FLATTEN","receipt":receipt}
        # Old Win32 owner event was closed; a second stop must be refused.
        script = (
            "$ErrorActionPreference='Stop';"
            "Import-Module '" + str(SELECTED_MODULE) + "' -Force;"
            "try {$null=Request-AtlasPaperOwnedStopSignal -OfflineTestId '"+
            selected_test_id + "';throw 'EVENT_STILL_OPEN'}"
            "catch {if($_.Exception.Message -cne 'PAPER_STOP_SIGNAL_NO_OWNED_SESSION'){throw};"
            "Write-Output 'R14_EVENT_CLOSED'}"
        )
        response = subprocess.run(
            ["powershell.exe","-NoProfile","-NonInteractive","-Command",script],
            cwd=R14,capture_output=True,text=True,timeout=12)
        assert response.returncode==0,response.stderr
        assert response.stdout.strip()=="R14_EVENT_CLOSED"
        return "SELECTED_R14_NATIVE_OWNER_AND_DURABLE_TWO_LANE_STOP_PASS"


async def selected_owner_expiry(run):
    from test_personal_installed_owner_lifetime_offline import harness
    from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger
    with tempfile.TemporaryDirectory(prefix="atlas-r14-expiry-") as tmp:
        runtime,owner,calls,bridge=harness(Path(tmp))
        result=await run(owner=owner,seconds=.12,interval=.05,
                         offline_test_id="test-"+uuid.uuid4().hex)
        assert result["phase"]=="FINISHED"
        assert calls==["SHUTDOWN_FLATTEN"]
        assert owner._used and runtime.state=="STOPPED" and runtime.entry_closed.is_set()
        assert PaperStopReceiptLedger(Path(tmp)/"synthetic-ledger.sqlite").recover(
            owner.session_id,"SHUTDOWN_FLATTEN")["state"]=="RECEIPT_RECORDED"
        return "SELECTED_R14_NATIVE_OWNER_EXPIRY_DURABLE_STOP_PASS"


async def selected_owner_uncertain(run):
    from test_personal_installed_owner_lifetime_offline import harness
    with tempfile.TemporaryDirectory(prefix="atlas-r14-unknown-") as tmp:
        runtime,owner,calls,bridge=harness(Path(tmp))
        def ambiguity(mode):
            calls.append(mode)
            raise OSError("SYNTHETIC_FINANCIAL_STOP_UNKNOWN")
        bridge.request_stop=ambiguity
        try:
            await run(owner=owner,seconds=.12,interval=.05,
                      offline_test_id="test-"+uuid.uuid4().hex)
        except OSError as err:
            assert "SYNTHETIC_FINANCIAL_STOP_UNKNOWN" in str(err)
        else:
            raise AssertionError("UNKNOWN_FINANCIAL_STOP_MUST_REFUSE")
        assert calls==["SHUTDOWN_FLATTEN"]  # no retry
        assert runtime.entry_closed.is_set() and runtime.uncertain
        assert runtime.state=="STOP_INCOMPLETE"
        return "SELECTED_R14_NATIVE_OWNER_UNKNOWN_STOP_LATCHED_NO_RETRY_PASS"


async def main():
    run = check_native_imports()
    results = [
        await selected_owner_roundtrip(run),
        await selected_owner_expiry(run),
        await selected_owner_uncertain(run),
    ]
    for result in results:
        print(result,flush=True)
    print("R14_NATIVE_OWNER_SUPERVISED_DISPOSABLE_ACCEPTANCE_3_OF_3",flush=True)
    print("NO_FINANCIAL_PROVIDER_ACCOUNT_OR_LIVE_PAPER_ORDERS",flush=True)


if __name__=="__main__":
    asyncio.run(main())
