"""Actual PowerShell guard/core with exclusively in-memory Windows ports.

No registry, W32Time command, elevation, provider or operational resource access.
"""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUCCESS = {"sync_advance", "runtime_same", "caller_mutates_record", "caller_mutates_ports"}
UNRESOLVED = {
    "runtime_regression", "runtime_bad_kind", "runtime_bool", "runtime_string", "runtime_range", "runtime_large_jump",
    "runtime_unknown_key", "runtime_removed_key", "foreign_poll", "foreign_update",
    "static_row_extra", "static_kind_change", "namespace_replaced", "snapshot_extra",
    "foreign_target_type", "foreign_minimum", "foreign_unknown", "foreign_source",
    "source_array", "service_array", "startup_array", "type_array",
    "foreign_service", "foreign_startup", "foreign_type", "foreign_special", "foreign_client",
    "effective_foreign_only", "rollback_write_failure", "rollback_reload_failure",
    "rollback_query_missing", "rollback_incomplete_effective", "rollback_snapshot_missing",
    "rollback_record_false", "rollback_record_object", "deadline_exhausted", "budget_nan", "budget_string", "budget_increase",
}
PREFLIGHT = {
    "preflight_wrong_value", "preflight_service_stopped", "preflight_budget", "preflight_policy",
    "record_before_false", "record_before_object", "record_intent_false",
}
RESTORED = {
    "interrupted_first_write", "interrupted_second_write", "apply_reload_failure",
    "applied_readback_missing", "effective_duplicate", "record_qualified_false", "record_qualified_object", "record_applied_false",
    "clock_unqualified", "clock_unverified", "clock_incomplete", "clock_1000", "clock_1001",
    "clock_bool", "clock_wrong_domain", "clock_wrong_source", "clock_stale", "clock_negative_age", "clock_nan", "clock_verifier_object",
}


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    output = tmp_path_factory.mktemp("synthetic-time-guard") / "results.json"
    ps = Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    run = subprocess.run(
        [str(ps), "-NoProfile", "-NonInteractive", "-File", str(ROOT / "tests/windows_time_guard_cases.ps1"),
         "-ModulePath", str(ROOT / "scripts/windows/Atlas-WindowsTime-ExperimentGuard.psm1"),
         "-PayloadPath", str(ROOT / "scripts/windows/Atlas-WindowsTime-ExperimentPayloadV2.ps1"), "-OutputPath", str(output)],
        capture_output=True, timeout=35, check=False, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert run.returncode == 0, run.stderr.decode(errors="replace")
    value = json.loads(output.read_text(encoding="utf-8-sig"))
    assert value["windows_calls"] == value["administrator_elevations"] == 0
    assert value["domain"] == "DISPOSABLE_SYNTHETIC"
    value["by_name"] = {row["name"]: row for row in value["cases"]}
    assert set(value["by_name"]) == SUCCESS | UNRESOLVED | PREFLIGHT | RESTORED
    return value


@pytest.mark.parametrize("name", sorted(SUCCESS | UNRESOLVED | PREFLIGHT | RESTORED))
def test_real_guard_and_mocked_transaction_fail_closed(evidence, name):
    row = evidence["by_name"][name]
    result = row["result"]
    assert result["authority_granted"] is False
    assert result["domain"] == "DISPOSABLE_SYNTHETIC"
    assert {w["name"] for w in row["writes"]} <= {"MaxPollInterval", "UpdateInterval"}
    assert row["reloads"].count("apply") <= 1
    assert row["reloads"].count("rollback") <= 1
    assert len(row["writes"]) <= 4
    if name in SUCCESS:
        assert result["status"] == "CLOCK_QUALIFIED_APPLIED_VERIFIED"
        assert result["experiment_success"] and result["full_scope_verified"] and result["evidence_complete"]
        assert row["after"]["configuration_values"]["MaxPollInterval"]["value"] == 6
        assert row["after"]["configuration_values"]["UpdateInterval"]["value"] == 100
        assert row["reloads"] == ["apply"] and row["verify_calls"] == 1
        assert row["peer_revision"] == 9
    else:
        assert result["experiment_success"] is False
        if name in UNRESOLVED:
            assert result["status"] == "UNRESOLVED_ROLLBACK_NOT_CONFIRMED_STOP"
            assert result["rollback_verified"] is False
        elif name in PREFLIGHT:
            assert result["status"] == "REFUSED_BEFORE_CONFIGURATION_CHANGE"
            assert row["writes"] == row["reloads"] == []
        else:
            assert result["status"] == "FAILED_ROLLBACK_CONFIRMED"
            assert result["rollback_verified"] and result["target_restore_readback_verified"]
            assert result["full_scope_verified"] and result["evidence_complete"]
            assert row["after"]["configuration_values"]["MaxPollInterval"]["value"] == 15
            assert row["after"]["configuration_values"]["UpdateInterval"]["value"] == 360000


def test_no_default_windows_adapter(evidence):
    assert evidence["default_refused"] is True


def test_target_restore_fact_does_not_hide_other_verification_failures(evidence):
    for name in ("foreign_source", "foreign_service", "foreign_minimum", "runtime_regression", "rollback_record_false"):
        result = evidence["by_name"][name]["result"]
        assert result["target_restore_readback_verified"] is True
        assert result["rollback_verified"] is result["experiment_success"] is False


def test_external_target_conflicts_are_never_overwritten(evidence):
    for name in ("foreign_poll", "foreign_update", "foreign_target_type"):
        row = evidence["by_name"][name]
        assert len(row["writes"]) == 2  # Only original fixture application; no restoration over foreign data.
        assert row["reloads"] == ["apply"]
        assert row["result"]["target_restore_readback_verified"] is False


def test_real_timestamp_progress_is_not_rewound_by_failed_clock_rollback(evidence):
    row = evidence["by_name"]["clock_unqualified"]
    assert row["after"]["configuration_values"]["LastKnownGoodTime"]["value"] == 134000000645331075
    assert row["result"]["rollback_verified"] is True
    assert row["result"]["experiment_success"] is False


def test_module_has_no_native_or_administrator_implementation():
    source = (ROOT / "scripts/windows/Atlas-WindowsTime-ExperimentGuard.psm1").read_text()
    for forbidden in ("Get-Service", "Set-ItemProperty", "OpenSubKey", "Start-Process", "RunAs", "w32tm.exe", "Win32.Registry"):
        assert forbidden not in source


def test_versioned_successor_uses_the_repaired_guards(evidence):
    assert evidence["successor_wrappers_verified"] is True


def test_versioned_native_template_refuses_without_a_new_explicit_run():
    ps = Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    run = subprocess.run(
        [str(ps), "-NoProfile", "-NonInteractive", "-File", str(ROOT / "scripts/windows/Atlas-WindowsTime-ExperimentPayloadV2.ps1")],
        capture_output=True, timeout=5, check=False, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert run.returncode != 0
    assert b"NEW_EXPLICIT_OPERATOR_EXPERIMENT_AUTHORIZATION_REQUIRED" in run.stderr


def test_successor_pins_guard_text_and_has_only_approved_write_names():
    payload = (ROOT / "scripts/windows/Atlas-WindowsTime-ExperimentPayloadV2.ps1").read_text()
    pin = re.search(r"\$guardHash -cne '([a-f0-9]{64})'", payload)[1]
    module = (ROOT / "scripts/windows/Atlas-WindowsTime-ExperimentGuard.psm1").read_text(encoding="utf-8-sig")
    assert hashlib.sha256(module.replace("\r\n", "\n").encode()).hexdigest() == pin
    assert set(re.findall(r"\.SetValue\('([^']+)'", payload)) == {"MaxPollInterval", "UpdateInterval"}
    assert "target_restore_readback_verified" in payload and "full_scope_verified" in payload


@pytest.mark.parametrize("name", [
    "valid", "zero_bound", "bound_999", "ack_false", "ack_string_false", "ack_integer",
    "missing_bound", "extra_field", "bound_boolean", "bound_string", "bound_float", "bound_negative", "bound_1000",
    "domain_fixture", "domain_array", "source_changed", "source_array", "nonce_wrong", "nonce_array",
    "hash_wrong", "hash_array", "qpc_future", "qpc_stale", "qpc_boundary", "qpc_string", "qpc_boolean",
    "qpc_zero", "frequency_zero", "frequency_float", "now_nan",
])
def test_native_qualification_wrapper_requires_typed_complete_binding(evidence, name):
    by_name = {row["name"]: row for row in evidence["qualification_cases"]}
    assert len(by_name) == 30
    allowed = name in {"valid", "zero_bound", "bound_999", "qpc_boundary"}
    assert by_name[name]["accepted"] is allowed
    if not allowed:
        assert "TIME_GUARD_QUALIFICATION_" in by_name[name]["error"]
