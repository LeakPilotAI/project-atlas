"""Run selected R15 native interpreter with disposable PAPER owner only.

Actual installed R15 app/services plus real Windows test Stop IPC and temporary
SQLite ledger; NO native PersonalPaper enrollment, provider or live orders.
"""
import asyncio
import hashlib
import inspect
import os
import sys
import tempfile
import uuid
from pathlib import Path

RELEASE=Path("D:/AtlasRuntime/releases/2c79a8d846d6b33669008114732ae5896153812a")


def require_real_r15_native_code():
    from app.services import personal_installed_stop_owner as owner
    from app.services import unified_paper_runtime as runtime
    from scripts.observation_runtime import personal_paper_python_stop_signal as signal
    from scripts.observation_runtime.personal_version_safe_release_clock import (
        require_native_version_safe_clock_source,
    )
    assert Path(sys.executable).resolve()==(RELEASE/"python/python.exe").resolve()
    for module,relative in (
        (owner,"backend/app/services/personal_installed_stop_owner.py"),
        (runtime,"backend/app/services/unified_paper_runtime.py"),
        (signal,"scripts/observation_runtime/personal_paper_python_stop_signal.py"),
    ):
        assert Path(inspect.getfile(module)).resolve()==(RELEASE/relative).resolve(),(
            "WORKSPACE_SOURCE_SUBSTITUTION_REFUSED",relative)
    assert require_native_version_safe_clock_source(deep=False)==(
        "274f5b00ee0e2f6271c6dd1dc5316f7d9124e932483038a6d93ef62ddbd2cd25")
    return owner.run_personal_installed_owner_session


async def check_owner_expiry(run):
    from test_personal_installed_owner_lifetime_offline import harness
    from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger
    with tempfile.TemporaryDirectory(prefix="r15-owned-disposable-expiry-") as tmp:
        path=Path(tmp)
        runtime,owner,calls,bridge=harness(path)
        result=await run(owner=owner,seconds=.12,interval=.05,
                         offline_test_id="test-"+uuid.uuid4().hex)
        assert result["outcome"]["position_state"]=="FLAT"
        assert result["outcome"]["process_shutdown"]=="VERIFIED_EXIT"
        assert set(result["outcome"]["lanes"])=={"QUALITY_DIPS","HYPERLIQUID"}
        assert calls==["SHUTDOWN_FLATTEN"]
        assert runtime.state=="STOPPED" and runtime.entry_closed.is_set()
        assert PaperStopReceiptLedger(path/"synthetic-ledger.sqlite").recover(
            owner.session_id,"SHUTDOWN_FLATTEN")["state"]=="RECEIPT_RECORDED"
        return "SELECTED_R15_NATIVE_OWNER_DURABLE_EXPIRY_STOP_PASS"


async def check_owner_manual_stop(run):
    from test_personal_installed_owner_lifetime_offline import harness
    from test_personal_python_run_stop_signal_offline import request_signal
    from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger
    with tempfile.TemporaryDirectory(prefix="r15-owned-disposable-request-") as tmp:
        path=Path(tmp)
        runtime,owner,calls,bridge=harness(path)
        token="test-"+uuid.uuid4().hex
        original_poll=runtime.poll
        async def poll_with_external_signal():
            view=await original_poll()
            await asyncio.to_thread(request_signal,token)
            return view
        runtime.poll=poll_with_external_signal
        result=await run(owner=owner,seconds=.5,interval=.05,
                         offline_test_id=token)
        assert result["phase"]=="FINISHED"
        assert result["outcome"]["position_state"]=="FLAT"
        assert result["outcome"]["process_shutdown"]=="VERIFIED_EXIT"
        assert calls==["SHUTDOWN_FLATTEN"]
        assert runtime.state=="STOPPED"
        receipt=PaperStopReceiptLedger(path/"synthetic-ledger.sqlite").recover(
            owner.session_id,"SHUTDOWN_FLATTEN")
        assert receipt["state"]=="RECEIPT_RECORDED" and receipt["receipt"]==result
        return "SELECTED_R15_NATIVE_OWNER_REAL_WINDOWS_STOP_SIGNAL_PASS"


async def check_unknown_stop_refuses_replay(run):
    from test_personal_installed_owner_lifetime_offline import harness
    with tempfile.TemporaryDirectory(prefix="r15-owned-disposable-uncertain-") as tmp:
        runtime,owner,calls,bridge=harness(Path(tmp))
        def ambiguous(mode):
            calls.append(mode)
            raise OSError("SYNTHETIC_R15_STOP_RECEIPT_UNCERTAIN")
        bridge.request_stop=ambiguous
        try:
            await run(owner=owner,seconds=.12,interval=.05,
                      offline_test_id="test-"+uuid.uuid4().hex)
        except OSError as exc:
            assert "SYNTHETIC_R15_STOP_RECEIPT_UNCERTAIN" in str(exc)
        else:
            raise AssertionError("FINANCIAL_UNKNOWN_STOP_MUST_REFUSE")
        assert calls==["SHUTDOWN_FLATTEN"]
        assert runtime.uncertain and runtime.entry_closed.is_set()
        assert runtime.state=="STOP_INCOMPLETE"
        return "SELECTED_R15_NATIVE_OWNER_UNKNOWN_STOP_REFUSED_NO_RETRY_PASS"


async def main():
    run=require_real_r15_native_code()
    results=[
        await check_owner_expiry(run),
        await check_owner_manual_stop(run),
        await check_unknown_stop_refuses_replay(run),
    ]
    for item in results:print(item,flush=True)
    print("R15_SELECTED_NATIVE_DISPOSABLE_OWNER_THREE_SCENARIOS_PASS",flush=True)
    print("NO_REAL_FINANCIAL_ACCOUNT_PROVIDER_OR_ORDER",flush=True)


if __name__=="__main__":
    asyncio.run(main())
