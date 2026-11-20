"""Real selected R15 Windows suspended Job Object pre-enrollment checks.

Windows integration tests spawn ONLY the two bounded isolated nonfinancial
installed-R15 Python snippets; no account, provider, clock or writer authority.
"""
import copy
import inspect
import os
import sys
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r15_native_job_admission_preflight as job
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTED_HEAD,
)


def specimen():
    return {
        "schema": job.SCHEMA,
        "status": "REAL_SUSPENDED_R15_JOB_CONTAINMENT_REHEARSAL_PASS",
        "selected_native_head": SELECTED_HEAD,
        "selected_release": str(job.RELEASE),
        "runs": [
            {"mode":"NORMAL_EXIT","native_pid":101,
             "native_creation_filetime":134388536119603538,
             "installed_image_verified":True,
             "suspended_identity_checked_before_resume":True,
             "assigned_to_real_job_before_resume":True,
             "job_kill_on_close_configured":True,
             "bounded_child_exit_observed":True,
             "exit_code":0,"owned_job_active_processes_after_exit":0,
             "no_financial_account_or_provider_usage":True},
            {"mode":"OWNED_JOB_STOP","native_pid":102,
             "native_creation_filetime":134388536122729304,
             "installed_image_verified":True,
             "suspended_identity_checked_before_resume":True,
             "assigned_to_real_job_before_resume":True,
             "job_kill_on_close_configured":True,
             "bounded_child_exit_observed":True,
             "exit_code":1,"owned_job_active_processes_after_exit":0,
             "no_financial_account_or_provider_usage":True},
        ],
        "active_children_after_check":0,
        "new_financial_accounts":0,
        "native_financial_writes":0,
        "persistent_writer_enrolled":False,
        "paper_start_authorized":False,
        "real_money_orders_authorized":False,
        "network_requests":0,
    }


def test_real_job_preflight_pure_result_must_remain_nonfinancial():
    result = specimen()
    old = copy.deepcopy(result)
    assert job.validate_result(result) is result
    assert result == old
    assert result["runs"][0]["exit_code"] == 0
    assert result["runs"][1]["exit_code"] == 1
    assert result["persistent_writer_enrolled"] is False
    assert result["paper_start_authorized"] is False


@pytest.mark.parametrize("damage",[
    "wrong_schema","wrong_status","wrong_selected_head","wrong_release",
    "missing_mode","reordered_modes","extra_run","duplicate_pid",
    "duplicate_creation_filetime","missing_process_pid","invalid_process_pid",
    "missing_creation_time","wrong_exit_normal","wrong_exit_stop",
    "still_active","job_active_after_exit","unverified_image",
    "not_suspended_when_verified","not_assigned_before_resume",
    "not_kill_on_close","not_waited_for_exit","financial_child_side_effect",
    "fake_account_created","fake_financial_write","fake_provider_fetch",
    "fake_writer_enrolled","fake_paper_start","fake_real_order",
    "undisclosed_extra_field",
])
def test_real_job_strict_attestation_refuses_tampered_or_authorized_claim(damage):
    r = specimen()
    run = r["runs"][0]
    if damage=="wrong_schema":r["schema"]="OTHER"
    elif damage=="wrong_status":r["status"]="GO"
    elif damage=="wrong_selected_head":r["selected_native_head"]="0"*64
    elif damage=="wrong_release":r["selected_release"]=r"D:\fake"
    elif damage=="missing_mode":run.pop("mode")
    elif damage=="reordered_modes":r["runs"].reverse()
    elif damage=="extra_run":r["runs"].append(copy.deepcopy(run))
    elif damage=="duplicate_pid":r["runs"][1]["native_pid"]=run["native_pid"]
    elif damage=="duplicate_creation_filetime":
        r["runs"][1]["native_creation_filetime"]=run["native_creation_filetime"]
    elif damage=="missing_process_pid":run.pop("native_pid")
    elif damage=="invalid_process_pid":run["native_pid"]=-1
    elif damage=="missing_creation_time":run.pop("native_creation_filetime")
    elif damage=="wrong_exit_normal":run["exit_code"]=1
    elif damage=="wrong_exit_stop":r["runs"][1]["exit_code"]=0
    elif damage=="still_active":r["active_children_after_check"]=1
    elif damage=="job_active_after_exit":run["owned_job_active_processes_after_exit"]=1
    elif damage=="unverified_image":run["installed_image_verified"]=False
    elif damage=="not_suspended_when_verified":run["suspended_identity_checked_before_resume"]=False
    elif damage=="not_assigned_before_resume":run["assigned_to_real_job_before_resume"]=False
    elif damage=="not_kill_on_close":run["job_kill_on_close_configured"]=False
    elif damage=="not_waited_for_exit":run["bounded_child_exit_observed"]=False
    elif damage=="financial_child_side_effect":run["no_financial_account_or_provider_usage"]=False
    elif damage=="fake_account_created":r["new_financial_accounts"]=1
    elif damage=="fake_financial_write":r["native_financial_writes"]=1
    elif damage=="fake_provider_fetch":r["network_requests"]=1
    elif damage=="fake_writer_enrolled":r["persistent_writer_enrolled"]=True
    elif damage=="fake_paper_start":r["paper_start_authorized"]=True
    elif damage=="fake_real_order":r["real_money_orders_authorized"]=True
    elif damage=="undisclosed_extra_field":r["source_acceptance_approved"]=True
    with pytest.raises((ValueError,KeyError,TypeError)):
        job.validate_result(r)


def test_native_process_creation_adapter_still_explicitly_blocks_default():
    from scripts.observation_runtime.personal_native_windows_api import WindowsJobAPI
    api = object.__new__(WindowsJobAPI)
    with pytest.raises(RuntimeError,match="NATIVE_CHILD_LAUNCH_BLOCKED_PENDING_V5_INTEGRATION"):
        api.create_suspended_child("UNAUTHORIZED_CREATE")
    command, create=job._creator(api,seconds=0.25)
    with pytest.raises(ValueError,match="EXACT_HARMLESS_TEST_CHILD"):
        create(command+" --enable-paper")
    source=inspect.getsource(job._rehearse)
    assert "launch_contained_child" in source
    assert source.index("launch_contained_child") < source.index("_wait_exit")
    assert "os.kill(" not in source and "taskkill" not in source
    assert "api.terminate_job(owner.job)" in source


@pytest.mark.skipif(sys.platform!="win32",reason="Windows real Job Objects required")
def test_actual_selected_r15_suspended_job_and_exact_owned_termination():
    r=job.inspect()
    assert job.validate_result(r) is r
    assert [x["mode"] for x in r["runs"]]==["NORMAL_EXIT","OWNED_JOB_STOP"]
    assert [x["exit_code"] for x in r["runs"]]==[0,1]
    assert r["active_children_after_check"]==0
    assert r["persistent_writer_enrolled"] is False
    assert r["native_financial_writes"]==0
    assert r["network_requests"]==0
