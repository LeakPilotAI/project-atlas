"""Parked, detached selected R15 Windows Job and twelve original native roots.

This is a nonfinancial bootstrap test, not an enrolled financial writer.
"""
import copy
import sys

import pytest

from scripts.observation_runtime import atlas_r15_parked_writer_owner as parked


def good():
    return {
        'schema':parked.SCHEMA,
        'status':'PARKED_R15_PREACTIVATION_COOPERATIVE_STOP_NONFINANCIAL_PASS',
        'selected_native_head':parked.SELECTED_HEAD,
        'installed_release':str(parked.RELEASE),
        'child_process_native_identity_verified':True,
        'suspended_before_native_job_assignment':True,
        'ready_from_same_parked_job_child':True,
        'twelve_existing_account_root_handles_held_while_job_active':True,
        'same_parked_job_worker_matches_both_12_role_rosters':True,
        'actual_job_kill_on_close_verified_before_handoff':True,
        'stopped_owned_job_cannot_be_reused_for_paper_activation':True,
        'same_owned_child_retained_across_three_liveness_observations':True,
        'cooperative_stop_signaled_and_child_exited_cleanly':True,
        'owned_job_active_children_before_stop':1,
        'owned_job_active_children_after_stop':0,
        'parked_process_exited_before_return':True,
        'original_native_roots_unchanged_after_stop':True,
        'persistent_writer_enrolled':False,
        'native_financial_accounts_created':0,
        'operator_activation_accepted':False,
        'provider_calls':0,
        'paper_start_authorized':False,
        'live_trading_authorized':False,
    }


def test_exact_parked_owner_proof_is_explicitly_no_financial_authority():
    record=good()
    before=copy.deepcopy(record)
    assert parked.validate_parked_proof(record) is record
    assert record==before
    assert record["owned_job_active_children_before_stop"]==1
    assert record["owned_job_active_children_after_stop"]==0
    assert record["persistent_writer_enrolled"] is False
    assert record["operator_activation_accepted"] is False
    assert record["native_financial_accounts_created"]==0
    assert record["paper_start_authorized"] is False
    assert record["live_trading_authorized"] is False
    assert record["provider_calls"]==0


@pytest.mark.parametrize("field,bad",[
    ("schema","INVALID"),
    ("status","FINANCIAL_OWNER_ACCEPTED"),
    ("selected_native_head","0"*64),
    ("installed_release",r"D:\foreign"),
    ("child_process_native_identity_verified",False),
    ("suspended_before_native_job_assignment",False),
    ("ready_from_same_parked_job_child",False),
    ("twelve_existing_account_root_handles_held_while_job_active",False),
    ("same_parked_job_worker_matches_both_12_role_rosters",False),
    ("actual_job_kill_on_close_verified_before_handoff",False),
    ("stopped_owned_job_cannot_be_reused_for_paper_activation",False),
    ("same_owned_child_retained_across_three_liveness_observations",False),
    ("cooperative_stop_signaled_and_child_exited_cleanly",False),
    ("owned_job_active_children_before_stop",0),
    ("owned_job_active_children_before_stop",2),
    ("owned_job_active_children_after_stop",1),
    ("parked_process_exited_before_return",False),
    ("original_native_roots_unchanged_after_stop",False),
    ("persistent_writer_enrolled",True),
    ("native_financial_accounts_created",1),
    ("operator_activation_accepted",True),
    ("provider_calls",1),
    ("paper_start_authorized",True),
    ("live_trading_authorized",True),
])
def test_unverified_job_or_financial_promotion_cannot_pass(field,bad):
    r=good()
    r[field]=bad
    with pytest.raises(ValueError,match="R15_PARKED_JOB_NONFINANCIAL_NATIVE_PROOF_REFUSED"):
        parked.validate_parked_proof(r)


def test_extra_financial_field_must_fail():
    r=good()
    r["native_activation_id"]="FAKE"
    with pytest.raises(ValueError,match="R15_PARKED_JOB_NONFINANCIAL_NATIVE_PROOF_REFUSED"):
        parked.validate_parked_proof(r)


def test_detached_headless_creator_does_not_import_or_dispatch_financial_runtime():
    assert parked.DETACHED_PROCESS==8
    assert "native_primitives" in parked.CHILD
    assert "WaitForSingleObject(stop,12000)" in parked.CHILD
    assert "SetEvent" in parked.CHILD
    assert "provider_calls" not in parked.CHILD
    assert "AUTO_PAPER" not in parked.CHILD
    assert "FINANCIAL_ORDERS" not in parked.CHILD


@pytest.mark.skipif(sys.platform!="win32",reason="Requires real selected R15 Windows Job and native account directories")
def test_one_real_installed_r15_parked_child_job_holds_all_12_handles_then_stops():
    value=parked.inspect()
    assert value==good()
    assert value["owned_job_active_children_before_stop"]==1
    assert value["owned_job_active_children_after_stop"]==0
    assert value["parked_process_exited_before_return"] is True
    assert value["original_native_roots_unchanged_after_stop"] is True
    assert value["same_owned_child_retained_across_three_liveness_observations"] is True
    assert value["cooperative_stop_signaled_and_child_exited_cleanly"] is True
    assert value["stopped_owned_job_cannot_be_reused_for_paper_activation"] is True
    assert value["persistent_writer_enrolled"] is False


@pytest.mark.skipif(sys.platform!="win32",reason="Requires actual installed R15 Win32 Job containment")
def test_lost_cooperative_stop_refuses_and_kills_only_the_owned_parked_job(monkeypatch):
    """No success receipt, no orphaned worker, no account/root modification."""
    import ctypes
    from ctypes import wintypes
    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        inspect_two_lane_native_roots,
    )
    from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
        _windows_handle_identity,
    )

    before=inspect_two_lane_native_roots()
    original=parked._exact_process
    pid_info=[]

    def capture_native_identity(api,process,**kwargs):
        value=original(api,process,**kwargs)
        pid_info.append(value)
        return value

    def deny_stop(kernel,handle):
        raise ValueError("R15_PARKED_OWNER_COOPERATIVE_CONTROL_UNAVAILABLE_TEST")

    monkeypatch.setattr(parked,"_exact_process",capture_native_identity)
    monkeypatch.setattr(parked,"_signal_parked_stop",deny_stop)
    with pytest.raises(ValueError,match="COOPERATIVE_CONTROL_UNAVAILABLE_TEST"):
        parked.inspect()
    assert pid_info
    assert before==inspect_two_lane_native_roots()
    # Job cleanup must kill this exact native child even if cooperative
    # signaling failed. PID reuse after exit cannot count as an old owner.
    k=ctypes.WinDLL("kernel32",use_last_error=True)
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    k.OpenProcess.restype=wintypes.HANDLE
    k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    k.WaitForSingleObject.restype=wintypes.DWORD
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    k.CloseHandle.restype=wintypes.BOOL
    observed=pid_info[0]
    h=k.OpenProcess(0x1000|0x100000,False,observed["pid"])
    if h:
        try:
            native=_windows_handle_identity(h)
            if native["creation_filetime"]==observed["creation_filetime"]:
                assert k.WaitForSingleObject(h,0)!=258
        finally:
            assert k.CloseHandle(h)
