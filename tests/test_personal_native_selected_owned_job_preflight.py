"""Selected-native successor original Job preflight: no financial lease issuer.

All positive cases are PURE roster-validation fixtures for R16-like shape.
No synthetic object is ever accepted for financial activation. The actual
original Windows-handle owner can only run inside a future SELECTED install.
"""
from __future__ import annotations

import copy
import inspect

import pytest
from test_personal_r16_owned_job_activation import rosters

from scripts.observation_runtime import personal_activation_commission as activation
from scripts.observation_runtime import (
    personal_native_selected_owned_job_preflight as candidate,
)
from scripts.observation_runtime.personal_native_job import ContainedChild
from scripts.observation_runtime.personal_native_windows_api import WindowsJobAPI


def test_pure_dual_account_twelve_role_original_process_shape_no_finance_lease():
    original, qd, hl = rosters()
    preserved = copy.deepcopy([qd, hl])
    roles, checked_qd, checked_hl = candidate.validate_selected_two_lane_rosters(
        qd, hl, original_process=original,
        release_digest=qd["release_digest"], image=original["image"],
    )
    assert len(roles) == 12
    assert len(set(roles.values())) == 1
    assert checked_qd["account_id"] != checked_hl["account_id"]
    assert checked_qd["release_digest"] == checked_hl["release_digest"]
    assert [qd, hl] == preserved
    assert not hasattr(candidate.RetainedSelectedNativeOwnerPreflight, "lease")
    assert not hasattr(candidate.RetainedSelectedNativeOwnerPreflight, "commit")


@pytest.mark.parametrize("change", [
    "different_child_image", "missing_process_field", "missing_created",
    "boolean_pid", "missing_writer", "foreign_writer_pid", "reused_pid_new_creation",
    "foreign_writer_image", "wrong_qd_release", "wrong_hl_release",
    "same_account", "same_epoch", "same_acceptance", "clock_mismatch",
    "foreign_clock", "duplicate_resource_identity", "wrong_resource_path",
    "unsupported_release_digest", "fake_process_id_schema", "extra_role",
])
def test_pure_owner_preflight_refuses_unbound_original_handles_or_accounts(change):
    original, qd, hl = rosters()
    image, release_digest = original["image"], qd["release_digest"]
    if change == "different_child_image":
        image = r"D:\AtlasRuntime\other\python.exe"
    elif change == "missing_process_field":
        original.pop("creation_filetime")
    elif change == "missing_created":
        original["creation_filetime"] = 0
    elif change == "boolean_pid":
        original["pid"] = True
    elif change == "missing_writer":
        qd["writers"].pop("source")
    elif change == "foreign_writer_pid":
        qd["writers"]["source"]["pid"] += 1
    elif change == "reused_pid_new_creation":
        hl["writers"]["funding"]["creation_filetime"] += 1
    elif change == "foreign_writer_image":
        hl["writers"]["mark"]["image"] = r"D:\Untrusted\python.exe"
    elif change == "wrong_qd_release":
        qd["release_digest"] = "e"*64
    elif change == "wrong_hl_release":
        hl["release_digest"] = "e"*64
    elif change == "same_account":
        hl["account_id"] = qd["account_id"]
    elif change == "same_epoch":
        hl["epoch"] = qd["epoch"]
    elif change == "same_acceptance":
        hl["acceptance_id"] = qd["acceptance_id"]
    elif change == "clock_mismatch":
        hl["clock_source"] = "FOREIGN_CLOCK"
    elif change == "foreign_clock":
        qd["clock_source"] = "FOREIGN_CLOCK"
    elif change == "duplicate_resource_identity":
        hl["resources"]["source"]["native_id"] = qd["resources"]["source"]["native_id"]
    elif change == "wrong_resource_path":
        hl["resources"]["report"]["path"] = r"C:\Forbidden\report"
    elif change == "unsupported_release_digest":
        release_digest = "NOT_THE_SELECTED_ARTIFACT"
    elif change == "fake_process_id_schema":
        qd["writers"]["source"]["schema"] = "UNVERIFIED_PID"
    elif change == "extra_role":
        hl["writers"]["unknown"] = copy.deepcopy(hl["writers"]["mark"])
    with pytest.raises((ValueError, TypeError, KeyError)):
        candidate.validate_selected_two_lane_rosters(
            qd, hl, original_process=original,
            release_digest=release_digest, image=image,
        )


@pytest.mark.parametrize("fake", [
    None, False, 123, "PID", {}, object(),
])
def test_future_original_native_job_refuses_foreign_unowned_claim(fake):
    with pytest.raises(ValueError, match="EXACT_ORIGINAL_JOB_PROCESS_REQUIRED"):
        candidate.RetainedSelectedNativeOwnerPreflight(
            child=fake, qd={}, perp={}, release_digest="f"*64,
        )


def test_pid_only_contained_child_cannot_claim_windows_original_job():
    fake_child = ContainedChild(api=None, job=123, process=456)
    with pytest.raises(ValueError, match="EXACT_ORIGINAL_JOB_PROCESS_REQUIRED"):
        candidate.RetainedSelectedNativeOwnerPreflight(
            child=fake_child, qd={}, perp={}, release_digest="f"*64,
        )


def test_unselected_workspace_refuses_even_fake_well_typed_job_before_any_network():
    # A class-compatible object with fabricated handles is not proof of
    # actual ownership. The installed release check refuses immediately.
    api = object.__new__(WindowsJobAPI)
    child = ContainedChild(api=api, job=123, process=456)
    with pytest.raises(ValueError, match="FINANCIAL_ACTIVATION_SOURCE_MUST_BE_INSTALLED"):
        candidate.RetainedSelectedNativeOwnerPreflight(
            child=child, qd={}, perp={}, release_digest="f"*64,
        )


def test_selected_native_future_owner_is_structural_never_a_financial_issuer():
    source = inspect.getsource(candidate)
    assert "IsProcessInJob" in source
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in source
    assert "require_selected_native_origin" in source
    assert "require_exact_roster" in source
    assert "publish_personal_activation(" not in source
    assert "submit_order(" not in source
    assert "place_order(" not in source
    assert '"financial_writer_lease_issued": False' in source
    assert '"paper_start_authorized": False' in source
    assert '"live_trading_authorized": False' in source


def test_future_install_guard_requires_real_owner_before_legacy_writer_port(monkeypatch):
    from scripts.observation_runtime import personal_native_writer_lifetime as legacy
    monkeypatch.setattr(legacy, "retain_live_enrollment_writers",
                        lambda *_a, **_k: pytest.fail("PID_ONLY_PORT_BYPASS"))
    with (pytest.raises(ValueError, match="FUTURE_NATIVE_FINANCIAL_JOB_ISSUER_MISSING"),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest="f"*64, owned_job=None)):
        pytest.fail("UNOWNED_FUTURE_RELEASE_ENTERED_FINANCE")


def test_structural_owner_may_be_verified_twice_but_never_publish_activation(
        monkeypatch):
    observed = []
    original_class = candidate.RetainedSelectedNativeOwnerPreflight

    class SyntheticOriginal:
        release_digest = "f"*64
        def require_exact_roster(self, *, qd, perp):
            observed.append((qd, perp))
            return True

    monkeypatch.setattr(candidate, "RetainedSelectedNativeOwnerPreflight",
                        SyntheticOriginal)
    from scripts.observation_runtime import personal_activation_publisher as publisher
    monkeypatch.setattr(publisher, "publish_personal_activation",
                        lambda **kwargs: pytest.fail("NO_FINANCE_ISSUER"))
    fake = SyntheticOriginal()
    try:
        with (pytest.raises(ValueError,
                            match="ACTIVATION_FUTURE_INDEPENDENT_FINANCIAL_LEASE_NOT_ACCEPTED"),
              activation.retain_activation_writer_guard(
                  qd={"account": "QD"}, perp={"account": "HL"},
                  release_digest=fake.release_digest, owned_job=fake)):
            pytest.fail("FINANCIAL_GUARD_YIELDED")
        assert len(observed) == 2
    finally:
        monkeypatch.setattr(candidate, "RetainedSelectedNativeOwnerPreflight",
                            original_class)


def test_structural_owner_exit_must_recheck_and_refuse_revoked_owner(monkeypatch):
    seen = []
    class SyntheticOriginal:
        release_digest = "f"*64
        def require_exact_roster(self, *, qd, perp):
            seen.append((qd, perp))
            if len(seen) == 2:
                raise ValueError("STRUCTURAL_OWNER_EXIT_REVOKED")
            return True
    monkeypatch.setattr(candidate, "RetainedSelectedNativeOwnerPreflight",
                        SyntheticOriginal)
    with (pytest.raises(ValueError, match="STRUCTURAL_OWNER_EXIT_REVOKED"),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest="f"*64, owned_job=SyntheticOriginal())):
        pytest.fail("NEVER_FINANCIAL")
    assert len(seen) == 2
