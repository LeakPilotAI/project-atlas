"""Selected R16 joined Windows original Job + external Stop + cold ledger tests.

Real native child/Win32 test namespace only; no account inception, financial
runtime, real trading provider or production desktop Stop.
"""
import sys

import pytest

from scripts.observation_runtime import (
    atlas_r16_disposable_original_job_stop as joined,
    atlas_r16_parked_writer_owner as parked,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)


@pytest.mark.skipif(sys.platform!="win32", reason="native Windows only")
def test_same_original_selected_r16_job_receives_external_stop_and_cold_nonfinancial_ledger():
    before=inspect_two_lane_native_roots()
    assert before["native_root_total"]==12
    assert before["all_twelve_distinct_and_empty"] is True
    result=joined.run()
    assert result=={
        "schema":joined.SCHEMA,
        "status":"R16_ORIGINAL_JOB_EXTERNAL_WINDOWS_STOP_OBSERVED",
        "selected_native_head":joined.R16_HEAD,
        "installed_original_job_process_exited":True,
        "external_windows_stop_request_observed":True,
        "durable_observation_receipt_reopened":True,
        "cold_separate_process_sqlite_recovery_verified":True,
        "double_stop_intent_refused":True,
        "requires_independent_financial_reconciliation":True,
        "actual_financial_flatness_verified":False,
        "native_financial_roots_changed":False,
        "financial_writer_roles_enrolled":0,
        "native_financial_account_files_created":0,
        "provider_requests":0,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
    }
    assert inspect_two_lane_native_roots()==before


@pytest.mark.parametrize("token", [
    None,False,123,"test-"+"a"*31,
    "test-"+"G"*32, "a"*32,
    "test-"+"a"*32+"-LIVE",
    "",
])
def test_unisolated_stop_namespace_refuses_before_any_windows_event(monkeypatch,token):
    class NoWindowsStop:
        def __init__(self): pytest.fail("FOREIGN_TEST_NAMESPACE_MUST_NOT_OPEN_EVENT")
    monkeypatch.setattr(joined,"WindowsStopEvents",NoWindowsStop)
    with pytest.raises(ValueError,match="R16_DISPOSABLE_EXTERNAL_STOP_TEST_NAMESPACE_REQUIRED"):
        joined.request_disposable_external_stop(test_id=token)


def test_native_stop_source_drift_refuses_before_owning_original_process(monkeypatch):
    monkeypatch.setattr(joined,"STOP_SHA","0"*64)
    def forbidden(*args,**kwargs):
        pytest.fail("NO_R16_JOB_WITH_FOREIGN_INSTALLED_STOP_BYTES")
    monkeypatch.setattr(joined,"inspect_original_job",forbidden)
    with pytest.raises(ValueError,match="R16_DISPOSABLE_ORIGINAL_INSTALLED_STOP_MODULE_REQUIRED"):
        joined.run()


@pytest.mark.skipif(sys.platform!="win32",reason="native Job needed")
def test_financial_flatness_claim_by_disposable_external_stop_refuses_and_drains_job():
    before=inspect_two_lane_native_roots()
    def fake_claim():
        return {
            "schema":joined.REQUEST_SCHEMA,
            "status":"REQUESTED_NOT_VERIFIED",
            "native_signal_received":True,
            "financial_flatness_verified":True,
        }
    with pytest.raises(ValueError,match="R16_PARKED_UNVERIFIED_EXTERNAL_STOP_REQUEST_REFUSED"):
        parked.inspect(disposable_stop_requester=fake_claim)
    # The parent's finally must close kill-on-close Job even on refusal.
    assert inspect_two_lane_native_roots()==before


@pytest.mark.parametrize("bad", [None,123,True,"external",{}])
def test_untrusted_stop_requester_type_refuses_without_spawning(monkeypatch,bad):
    # None is the explicitly supported original cooperative Stop; do not
    # invoke it here. Other noncallables must refuse pre-spawn.
    if bad is None:
        assert bad is None
        return
    monkeypatch.setattr(
        parked,"selected_code",
        lambda **kwargs: pytest.fail("BAD_CALLABLE_MUST_REFUSE_BEFORE_NATIVE_READBACK"))
    with pytest.raises(ValueError,match="R16_PARKED_DISPOSABLE_STOP_CALLBACK_REQUIRED"):
        parked.inspect(disposable_stop_requester=bad)


def test_joined_stop_receipt_cannot_be_equated_with_real_financial_flatness():
    import inspect
    source=inspect.getsource(joined.run)
    assert '"position_state": "UNKNOWN_NOT_FINANCIAL_CUSTODY"' in source
    assert '"financial_flatness_verified": False' in source
    assert '"startup_authorized":False' in source
    assert '"receipts_without_flatten_claim":1' in source
    assert '"requires_independent_position_reconciliation":True' in source
