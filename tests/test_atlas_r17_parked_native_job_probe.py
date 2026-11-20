"""R17 nonfinancial real native Job original-root owner; no child in tests."""
from __future__ import annotations

import copy

import pytest

from scripts.observation_runtime import atlas_r17_parked_native_job_probe as r17


def fake_report():
    return {
        "schema":r17.SCHEMA,
        "status":"R17_ORIGINAL_JOB_NONFINANCIAL_ROOT_HOLD_STOP_PASS",
        "selected_head":r17.HEAD,
        "installed_release":str(r17.RELEASE),
        "installed_original_python_image_verified":True,
        "suspended_before_owned_job_assignment":True,
        "one_original_job_process_while_ready":True,
        "child_held_all_twelve_original_empty_account_roots":True,
        "original_windows_job_and_process_identity_stable":True,
        "kill_on_job_close_native_policy_verified":True,
        "cooperative_stop_acknowledged":True,
        "owned_child_exited_before_return":True,
        "owned_job_zero_active_processes_after_stop":True,
        "original_native_root_ids_unchanged":True,
        "financial_writer_enrolled":0,
        "native_financial_account_files_created":0,
        "provider_requests":0,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
        "owned_child_retained_after_return":False,
    }


def test_nonfinancial_report_cannot_mint_account_or_trading_authority():
    row=fake_report()
    assert r17.validate_report(row)==row
    assert row["paper_start_authorized"] is False
    assert row["live_trading_authorized"] is False
    assert row["financial_writer_enrolled"] == 0
    assert row["native_financial_account_files_created"] == 0


@pytest.mark.parametrize("name,mutation", [
    ("schema","FAKE"),
    ("status","FINANCIAL_PRODUCTION"),
    ("selected_head","f"*64),
    ("installed_release",r"D:\Bogus"),
    ("installed_original_python_image_verified",False),
    ("suspended_before_owned_job_assignment",False),
    ("one_original_job_process_while_ready",False),
    ("child_held_all_twelve_original_empty_account_roots",False),
    ("original_windows_job_and_process_identity_stable",False),
    ("cooperative_stop_acknowledged",False),
    ("owned_child_exited_before_return",False),
    ("owned_job_zero_active_processes_after_stop",False),
    ("original_native_root_ids_unchanged",False),
    ("financial_writer_enrolled",1),
    ("native_financial_account_files_created",1),
    ("provider_requests",1),
    ("paper_start_authorized",True),
    ("live_trading_authorized",True),
    ("owned_child_retained_after_return",True),
])
def test_forged_native_result_never_promotes_financial_rights(name,mutation):
    row=fake_report()
    row[name]=mutation
    with pytest.raises(ValueError,match="NONFINANCIAL_REPORT_REFUSED"):
        r17.validate_report(row)


def test_extra_financial_permission_field_never_becomes_acceptance():
    with pytest.raises(ValueError,match="NONFINANCIAL_REPORT_REFUSED"):
        r17.validate_report({**fake_report(),"financial_lease_accepted":True})


def test_exact_original_child_has_no_financial_port():
    assert "personal_paper_inception" in r17.CHILD
    assert "native_primitives" in r17.CHILD
    assert "WindowsOutput" in r17.CHILD
    assert "R17_PARKED" in r17.CHILD
    assert "stop_event" in r17.CHILD and "ready_event" in r17.CHILD
    assert all(value not in r17.CHILD for value in (
        "submit_order(", "place_order(", "trading_enabled",
        "ALPACA_API_KEY", "HYPERLIQUID_PRIVATE_KEY",
    ))


def test_real_selected_r17_nonswapping_inspect_never_spawns_native_process(monkeypatch):
    monkeypatch.setattr(r17,"WindowsJobAPI",
                        lambda: pytest.fail("INSPECT_NEVER_CREATES_WINDOWS_JOB"))
    report=r17.inspect()
    assert report["status"]=="R17_EXACT_NONFINANCIAL_JOB_TEST_NOT_EXECUTED"
    assert report["selected_source_commit"]==r17.SOURCE
    assert report["original_twelve_native_roots_verified_empty"] is True
    assert report["windows_job_child_started"] is False
    assert report["paper_start_authorized"] is False


def test_wrong_source_revision_refuses_before_job_or_child(monkeypatch):
    monkeypatch.setattr(r17,"require_selected_r17_nonfinancial",
                        lambda: {"release":"UNTRUSTED","artifact_digest":"0"*64})
    monkeypatch.setattr(r17,"WindowsJobAPI",
                        lambda: pytest.fail("WRONG_NATIVE_RELEASE_MUST_NOT_LAUNCH"))
    with pytest.raises(ValueError,match="REAL_SELECTED_INSTALLED_IMAGE_REQUIRED"):
        r17.probe()


def test_nonempty_native_financial_root_refuses_before_job(monkeypatch):
    changed=copy.deepcopy(r17.inspect_two_lane_native_roots())
    changed["all_twelve_distinct_and_empty"]=False
    monkeypatch.setattr(r17,"inspect_two_lane_native_roots",lambda:changed)
    monkeypatch.setattr(r17,"WindowsJobAPI",
                        lambda: pytest.fail("NONEMPTY_ACCOUNT_MUST_NOT_LAUNCH_CHILD"))
    with pytest.raises(ValueError,match="TWELVE_EMPTY_ORIGINAL_ROOTS_REQUIRED"):
        r17.probe()


def test_live_execution_cli_without_exact_scope_refuses_before_child(monkeypatch):
    monkeypatch.setattr(r17,"probe",
                        lambda: pytest.fail("NO_NATIVE_JOB_WITHOUT_EXACT_USER_SCOPE"))
    with pytest.raises(SystemExit):
        r17.main(["--execute-readonly"])
    with pytest.raises(SystemExit):
        r17.main(["--execute-readonly","--confirm-scope","WRONG"])


def test_readonly_inspect_cli_does_not_accept_execution_scope(monkeypatch):
    monkeypatch.setattr(r17,"probe",
                        lambda: pytest.fail("INSPECT_MUST_NOT_LAUNCH_CHILD"))
    with pytest.raises(SystemExit):
        r17.main(["--inspect","--confirm-scope",r17.SCOPE])


def test_inspect_no_accounts_prices_orders(monkeypatch,capsys):
    monkeypatch.setattr(r17,"WindowsJobAPI",
                        lambda: pytest.fail("INSPECT_SPAWN_REFUSED"))
    assert r17.main(["--inspect"])==0
    raw=capsys.readouterr().out
    assert '"paper_start_authorized": false' in raw
    assert '"native_paper_account_created": false' in raw
    assert '"windows_job_child_started": false' in raw
