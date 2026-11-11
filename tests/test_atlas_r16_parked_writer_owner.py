"""R16 selected original Windows Job + 12 empty root handle admission.

One bounded genuine read-only native parked child is created and stopped;
all synthetic negative cases refuse without creating any native child,
accounts, provider connections, financial leases or orders.
"""
import copy
import sys

import pytest

from scripts.observation_runtime import atlas_r16_parked_writer_owner as gate
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    ARTIFACT_DIGEST, selected_code, inspect as selected_readiness,
)
from scripts.observation_runtime.personal_activation_commission import (
    retain_activation_writer_guard,
)
from scripts.observation_runtime.personal_native_writer_lifetime import (
    writer_roster, retain_live_enrollment_writers,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)


@pytest.mark.skipif(sys.platform!="win32",reason="Selected R16 original Windows Job required")
def test_actual_selected_r16_original_job_holds_and_stops_twelve_empty_native_roots():
    before=inspect_two_lane_native_roots()
    assert before["all_twelve_distinct_and_empty"] is True
    result=gate.inspect()
    assert gate.validate_result(result)==result
    assert result["schema"]==gate.SCHEMA
    assert result["installed_release"]==str(gate.RELEASE)
    assert result["selected_native_head"]==gate.R16_HEAD
    assert result["owned_job_one_process_before_stop"] is True
    assert result["owned_job_zero_processes_after_stop"] is True
    assert result["child_held_all_twelve_original_empty_native_roots"] is True
    assert result["cooperative_stop_acknowledged"] is True
    assert result["owned_job_closed_before_return"] is True
    assert result["twelve_structural_roles_verified_under_original_retained_job"] is True
    assert result["retained_original_job_liveness_checked_three_times"] is True
    assert result["expired_retained_job_refused_after_stop"] is True
    assert result["financial_writer_roles_enrolled"]==0
    assert result["financial_account_files_created"]==0
    assert result["market_provider_requests"]==0
    assert result["paper_start_authorized"] is False
    assert result["live_trading_authorized"] is False
    assert inspect_two_lane_native_roots()==before
    assert selected_code()["selected_revision"]==15
    assert selected_readiness()["decision"]=="NO_GO"


@pytest.mark.parametrize("field,value",[
    ("schema","FORGED"),("status","PAPER_PRODUCTION"),
    ("selected_native_head","0"*64),
    ("installed_release","D:\\FOREIGN\\bad"),
    ("installed_source_commit","f"*40),
    ("parked_original_process_identity_verified",False),
    ("created_suspended_before_owned_job_assignment",False),
    ("original_selected_r16_executable_and_source_verified",False),
    ("child_held_all_twelve_original_empty_native_roots",False),
    ("original_native_roots_unchanged_after_stop",False),
    ("owned_job_one_process_before_stop",False),
    ("owned_job_zero_processes_after_stop",False),
    ("cooperative_stop_acknowledged",False),
    ("owned_process_exited_before_return",False),
    ("owned_job_closed_before_return",False),
    ("twelve_structural_roles_verified_under_original_retained_job",False),
    ("retained_original_job_liveness_checked_three_times",False),
    ("expired_retained_job_refused_after_stop",False),
    ("financial_writer_roles_enrolled",1),
    ("financial_account_files_created",1),
    ("market_provider_requests",1),
    ("paper_start_authorized",True),
    ("live_trading_authorized",True),
])
def test_native_job_report_never_promotes_financial_grants(field,value):
    report={
        "schema":gate.SCHEMA,
        "status":"R16_OWNED_JOB_READ_ONLY_ROOT_HOLD_STOP_PASS",
        "selected_native_head":gate.R16_HEAD,
        "installed_release":str(gate.RELEASE),
        "installed_source_commit":gate.SOURCE,
        "parked_original_process_identity_verified":True,
        "created_suspended_before_owned_job_assignment":True,
        "original_selected_r16_executable_and_source_verified":True,
        "child_held_all_twelve_original_empty_native_roots":True,
        "original_native_roots_unchanged_after_stop":True,
        "owned_job_one_process_before_stop":True,
        "owned_job_zero_processes_after_stop":True,
        "cooperative_stop_acknowledged":True,
        "owned_process_exited_before_return":True,
        "owned_job_closed_before_return":True,
        "twelve_structural_roles_verified_under_original_retained_job":True,
        "retained_original_job_liveness_checked_three_times":True,
        "expired_retained_job_refused_after_stop":True,
        "financial_writer_roles_enrolled":0,
        "financial_account_files_created":0,
        "market_provider_requests":0,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
    }
    report[field]=value
    with pytest.raises(ValueError,match="R16_PARKED_ORIGINAL_JOB_NONFINANCIAL_RESULT_REFUSED"):
        gate.validate_result(report)


def test_forged_extra_financial_authority_field_is_not_accepted():
    with pytest.raises(ValueError,match="R16_PARKED_ORIGINAL_JOB_NONFINANCIAL_RESULT_REFUSED"):
        gate.validate_result({"financial_owner_lease_issued":True})


def test_r16_selected_job_refuses_release_head_drift_before_spawn(monkeypatch):
    record=selected_code()
    record["selected_native_head"]="0"*64
    monkeypatch.setattr(gate,"selected_code",lambda **_:record)
    monkeypatch.setattr(gate,"WindowsJobAPI",lambda:pytest.fail("NO_JOB_ON_WRONG_RELEASE"))
    with pytest.raises(ValueError,match="R16_PARKED_EXACT_CURRENT_SELECTED_RELEASE_REQUIRED"):
        gate.inspect()


def test_r16_selected_job_refuses_nonempty_root_before_spawn(monkeypatch):
    original=inspect_two_lane_native_roots()
    changed=copy.deepcopy(original)
    changed["all_twelve_distinct_and_empty"]=False
    changed["existing_empty_root_namespaces"]=11
    monkeypatch.setattr(gate,"inspect_two_lane_native_roots",lambda:changed)
    monkeypatch.setattr(gate,"WindowsJobAPI",lambda:pytest.fail("NO_JOB_ON_NONEMPTY_ROOT"))
    with pytest.raises(ValueError,match="R16_PARKED_PREINCEPTION_TWELVE_EMPTY_NATIVE_ROOTS_REQUIRED"):
        gate.inspect()
    assert inspect_two_lane_native_roots()==original


@pytest.mark.parametrize("foreign",[None,{},object(),False,123])
def test_r16_activation_guard_refuses_pid_only_and_unowned_job_before_clock_or_open(monkeypatch,foreign):
    from scripts.observation_runtime import personal_native_writer_lifetime as legacy
    def forbid(*args,**kwargs):
        pytest.fail("SELECTED_R16_CANNOT_REOPEN_ENROLLMENT_SUPPLIED_PID")
    monkeypatch.setattr(legacy,"retain_live_enrollment_writers",forbid)
    with pytest.raises(ValueError,match="ACTIVATION_R16_RETAINED_FINANCIAL_OWNER_JOB_NOT_YET_ACCEPTED"):
        with retain_activation_writer_guard(
                qd={},perp={},release_digest=ARTIFACT_DIGEST,owned_job=foreign):
            pytest.fail("R16_UNOWNED_RELEASE_MUST_NOT_ACTIVATE")


def test_r16_legacy_writer_roster_direct_call_refuses_pid_only():
    with pytest.raises(ValueError,match="PERSONAL_ACTIVATION_R16_PID_ONLY_ROSTER_REFUSED"):
        writer_roster({}, {}, release_digest=ARTIFACT_DIGEST)
    with pytest.raises(ValueError,match="PERSONAL_ACTIVATION_R16_PID_ONLY_ROSTER_REFUSED"):
        with retain_live_enrollment_writers({},{},release_digest=ARTIFACT_DIGEST):
            pytest.fail("NO_NATIVE_PID_ONLY_HANDLES_FOR_R16")


def test_child_program_exact_source_no_provider_or_trading_endpoint():
    assert "personal_paper_inception" in gate.CHILD
    assert "native_primitives" in gate.CHILD
    assert "stop_event" in gate.CHILD and "ready_event" in gate.CHILD
    assert "WindowsOutput" in gate.CHILD
    assert "R16_PARKED" in gate.CHILD
    assert gate.IMAGE.lower().endswith("python\\python.exe")
