"""Selected installed R15 Windows self/parent process identity refusal tests.

No financial enrollment, provider connection, process discovery or live orders.
"""
import copy
import ntpath
import os
import sys
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r15_disposable_writer_process_audit as audit
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTED_HEAD,
)


def specimen():
    root = audit.RELEASE
    image = str(root / "python/python.exe")
    source = {
        "personal_writer_self_binding_probe":
            str(root / "scripts/observation_runtime/personal_writer_self_binding_probe.py"),
        "quality_dips_read_service":
            str(root / "scripts/observation_runtime/quality_dips_read_service.py"),
        "personal_version_safe_release_clock":
            str(root / "scripts/observation_runtime/personal_version_safe_release_clock.py"),
    }
    child = {
        "schema": "ATLAS_SELECTED_R15_NATIVE_TEMPORARY_PROCESS_SELF_OBSERVATION_V1",
        "self_binding": {
            "schema": "ATLAS_PERSONAL_WRITER_SELF_BINDING_PROBE_V1",
            "expected_executable": image,
            "observed_process": {
                "pid": 12345, "creation_filetime": 134388500000000000,
                "image": image,
            },
            "installed_executable_matched": True,
            "enrolled_writer_verified": False,
            "ownership_lease_issued": False,
            "paper_start_authorized": False,
        },
        "installed_source_paths": source,
        "selected_clock_source_head": SELECTED_HEAD,
        "financial_account_enrolled": False,
        "writer_ownership_lease_issued": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }
    parent = {
        "creation_filetime": 134388500000000000,
        "image": image,
    }
    return child, parent


def test_native_windows_process_qualification_only_confirms_disposable_process():
    child, parent = specimen()
    copied = copy.deepcopy((child, parent))
    result = audit.validate_report(
        child=child, native_pid=12345, parent=parent,
        release=audit.RELEASE, expected_head=SELECTED_HEAD)
    assert (child, parent) == copied
    assert result["status"] == (
        "INSTALLED_R15_SHORT_LIVED_PROCESS_SELF_AND_PARENT_HANDLE_AGREE")
    assert result["native_module_paths_verified"] == 3
    assert result["independent_parent_windows_handle_identity_agreed"] is True
    assert result["observed_expired_disposable_child_pid"] == 12345
    assert result["native_writer_identity_enrollment_usable"] is False
    for flag in (
        "real_writer_process_currently_enrolled", "financial_account_activated",
        "financial_start_authorized", "live_trading_authorized"):
        assert result[flag] is False
    assert result["provider_requests"] == result["native_account_mutations"] == 0


@pytest.mark.parametrize("damage", [
    "wrong_selected_head", "wrong_child_schema", "unexpected_field",
    "missing_native_source_module", "workspace_source_substituted",
    "other_native_release_module", "wrong_binding_schema",
    "wrong_installed_executable", "missing_installed_match",
    "forged_writer_enrollment", "forged_owner_lease", "forged_paper_start",
    "forged_live_order", "forged_financial_account",
    "other_windows_parent_image", "other_windows_self_image",
    "wrong_parent_creation", "negative_parent_creation",
    "wrong_child_creation", "different_pid", "noninteger_pid",
    "mismatched_selected_executable", "absent_process_identity",
])
def test_native_r15_parent_handle_self_bind_rejects_forgery(damage):
    child, parent = specimen()
    pid = 12345
    if damage == "wrong_selected_head":
        child["selected_clock_source_head"] = "0" * 64
    elif damage == "wrong_child_schema":
        child["schema"] = "UNVERIFIED"
    elif damage == "unexpected_field":
        child["passed_financial_gate"] = True
    elif damage == "missing_native_source_module":
        child["installed_source_paths"].pop("quality_dips_read_service")
    elif damage == "workspace_source_substituted":
        child["installed_source_paths"]["quality_dips_read_service"] = (
            r"D:\Work\Project Atlas\scripts\observation_runtime\quality_dips_read_service.py")
    elif damage == "other_native_release_module":
        child["installed_source_paths"]["personal_version_safe_release_clock"] = (
            r"D:\AtlasRuntime\releases\oldrelease\scripts\observation_runtime\personal_version_safe_release_clock.py")
    elif damage == "wrong_binding_schema":
        child["self_binding"]["schema"] = "OTHER"
    elif damage == "wrong_installed_executable":
        child["self_binding"]["expected_executable"] = r"D:\Python\python.exe"
    elif damage == "missing_installed_match":
        child["self_binding"]["installed_executable_matched"] = False
    elif damage == "forged_writer_enrollment":
        child["self_binding"]["enrolled_writer_verified"] = True
    elif damage == "forged_owner_lease":
        child["writer_ownership_lease_issued"] = True
    elif damage == "forged_paper_start":
        child["self_binding"]["paper_start_authorized"] = True
    elif damage == "forged_live_order":
        child["live_trading_authorized"] = True
    elif damage == "forged_financial_account":
        child["financial_account_enrolled"] = True
    elif damage == "other_windows_parent_image":
        parent["image"] = r"D:\Work\untrusted.exe"
    elif damage == "other_windows_self_image":
        child["self_binding"]["observed_process"]["image"] = r"D:\Work\untrusted.exe"
    elif damage == "wrong_parent_creation":
        parent["creation_filetime"] += 1
    elif damage == "negative_parent_creation":
        parent["creation_filetime"] = -1
    elif damage == "wrong_child_creation":
        child["self_binding"]["observed_process"]["creation_filetime"] += 1
    elif damage == "different_pid":
        pid += 1
    elif damage == "noninteger_pid":
        pid = "12345"
    elif damage == "mismatched_selected_executable":
        child["self_binding"]["observed_process"]["image"] = (
            r"D:\AtlasRuntime\releases\other\python\python.exe")
    elif damage == "absent_process_identity":
        child["self_binding"]["observed_process"] = None
    with pytest.raises((ValueError, TypeError, KeyError)):
        audit.validate_report(
            child=child, native_pid=pid, parent=parent,
            release=audit.RELEASE, expected_head=SELECTED_HEAD)


@pytest.mark.skipif(sys.platform != "win32", reason="Genuine Windows PROCESS HANDLE required")
def test_real_installed_r15_short_lived_process_self_and_parent_handle():
    actual = audit.inspect()
    assert actual["schema"] == audit.SCHEMA
    assert actual["child_exited_and_expired"] is True
    assert actual["parent_reverified_selector_after_exit"] is True
    assert actual["selected_native_head"] == SELECTED_HEAD
    assert actual["native_module_paths_verified"] == 3
    assert actual["child_owns_installed_selected_release"] is True
    assert actual["independent_parent_windows_handle_identity_agreed"] is True
    assert actual["native_writer_identity_enrollment_usable"] is False
    assert actual["real_writer_process_currently_enrolled"] is False
    assert actual["financial_account_activated"] is False
    assert actual["financial_start_authorized"] is False
    assert actual["live_trading_authorized"] is False
    assert actual["provider_requests"] == 0
    assert actual["native_account_mutations"] == 0
