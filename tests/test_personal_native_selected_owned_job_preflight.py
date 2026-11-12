"""Selected-native successor original Job preflight: no financial lease issuer.

All positive cases are PURE roster-validation fixtures for R16-like shape.
No synthetic object is ever accepted for financial activation. The actual
original Windows-handle owner can only run inside a future SELECTED install.
"""
from __future__ import annotations

import copy
import inspect
from typing import ClassVar

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


def test_preinception_structural_owner_cannot_publish_activation(
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
                            match="ACTIVATION_FUTURE_TWO_GENUINE_INITIAL_ACCOUNTS_REQUIRED"),
              activation.retain_activation_writer_guard(
                  qd={"account": "QD"}, perp={"account": "HL"},
                  release_digest=fake.release_digest, owned_job=fake)):
            pytest.fail("FINANCIAL_GUARD_YIELDED")
        assert len(observed) == 0
    finally:
        monkeypatch.setattr(candidate, "RetainedSelectedNativeOwnerPreflight",
                            original_class)


def test_structural_owner_exit_must_recheck_and_refuse_revoked_owner(monkeypatch):
    seen = []
    class SyntheticOriginal:
        release_digest = "f"*64
        _phase = "INITIAL_READBACK_ONLY"
        _initial_cuts = ({}, {})
        _initial_bootstraps = (object(), object())
        origin: ClassVar[dict] = {
            "selected_artifact_digest_bound": True,
            "financial_writer_lease_issued": False,
            "financial_activation_published": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
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
        # This is an activation-only context, NOT a financial operation lease.
        pass
    assert len(seen) == 2


def test_owner_native_selector_head_drift_refused_before_windows_handle_or_network(
        monkeypatch):
    # Inert Python object cannot launch a process; test confirms a changed
    # native selected head blocks before touching any Win32 handle.
    from scripts.observation_runtime import (
        personal_native_selected_owned_job_preflight as owner_module,
    )

    fake_child = ContainedChild(api=object(), job=321, process=654)
    fake_owner = object.__new__(owner_module.RetainedSelectedNativeOwnerPreflight)
    fake_owner.child = fake_child
    fake_owner.api = fake_child.api
    fake_owner.job = fake_child.job
    fake_owner.process = fake_child.process
    fake_owner._selected_head = "EXPECTED_NATIVE_HEAD"
    monkeypatch.setattr(owner_module, "require_native_version_safe_clock_source",
                        lambda *, deep: "FOREIGN_NATIVE_HEAD" if deep is False
                        else pytest.fail("NO_DEEP_FILE_SWEEP_ON_FAST_RECHECK"))
    with pytest.raises(ValueError, match="ORIGINAL_JOB_OR_SELECTION_CHANGED"):
        fake_owner.verify_still_running()


def test_owner_initial_deep_installed_verification_not_repeated_during_each_recheck():
    source = inspect.getsource(candidate.RetainedSelectedNativeOwnerPreflight)
    assert source.count("require_selected_native_origin(") == 1
    assert "require_native_version_safe_clock_source(deep=False)" in source
    assert "return self.verify_still_running()" in source

def _synthetic_inception_owner(monkeypatch):
    """No Job/adoption/finance: synthetic only for state-machine refusal tests."""
    from app.services.paper_financial_replay import digest
    from test_personal_r16_owned_job_activation import rosters

    from scripts.observation_runtime import personal_paper_inception as inception

    _, qd, hl = rosters()
    owner = object.__new__(candidate.RetainedSelectedNativeOwnerPreflight)
    owner._original_qd, owner._original_perp = copy.deepcopy(qd), copy.deepcopy(hl)
    owner._qd, owner._perp = digest(qd), digest(hl)
    owner._phase, owner._initial_cuts = "PREINCEPTION_COORDINATION_READY", None
    binding = tuple(
        (lane, role, entry["path"], tuple(entry["native_id"]))
        for lane, enrollment in (("QUALITY_DIPS", qd), ("HYPERLIQUID", hl))
        for role, entry in enrollment["resources"].items()
    )
    owner._native_binding = binding
    observed = {
        "schema": "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1",
        "lanes": {
            lane: {
                "epoch": enrollment["epoch"],
                "roots": {
                    role: {
                        "path": entry["path"],
                        "native_id": copy.deepcopy(entry["native_id"]),
                        "native_identity_verified": True,
                        "existing_empty_namespace_verified": False,
                    }
                    for role, entry in enrollment["resources"].items()
                },
            } for lane, enrollment in (("QUALITY_DIPS", qd), ("HYPERLIQUID", hl))
        },
        "native_root_total": 12,
        "native_root_ids_verified": 12,
        "existing_empty_root_namespaces": 0,
        "all_twelve_distinct_and_empty": False,
        "operator_account_enrollment_verified": False,
        "writer_ownership_verified": False,
        "financial_inception_verified": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "filesystem_writes": 0,
        "network_requests": 0,
    }
    owner._verify_original_job = lambda: True
    monkeypatch.setattr(candidate, "inspect_two_lane_native_roots", lambda: observed)
    # Synthetic validators only: actual production transition uses genuine
    # NativePersonalInitialReadback over original Windows file handles.
    monkeypatch.setattr(
        inception, "validate_personal_inception",
        lambda row: (row["lane"], row["enrollment"], {"opening_cash": "1000"}),
    )
    check_calls = []
    class SyntheticNativeReadback:
        def verify(self, enrollment, current):
            check_calls.append(enrollment["lane"])
            return current.get("authenticated_initial") is True
    monkeypatch.setattr(inception, "NativePersonalInitialReadback",
                        SyntheticNativeReadback)
    from types import SimpleNamespace

    def synthetic_acknowledged_bootstrap(lane, enrollment):
        row = {"lane": lane, "enrollment": enrollment}
        bootstrap = object.__new__(inception.PersonalInceptionBootstrap)
        bootstrap.enrollment = row
        bootstrap.readback = SyntheticNativeReadback()
        bootstrap.current = {"authenticated_initial": True}
        bootstrap.publication = SimpleNamespace(
            acknowledged=lambda operation: (
                bootstrap.current, {"operation_id": operation, "state": "ACKNOWLEDGED"}))
        bootstrap.scope = lambda: {"operation_id": "synthetic-" + lane}
        return bootstrap

    q = synthetic_acknowledged_bootstrap("QUALITY_DIPS", qd)
    h = synthetic_acknowledged_bootstrap("HYPERLIQUID", hl)
    return owner, observed, q, h, check_calls


def test_two_initial_files_transition_requires_both_native_readbacks(monkeypatch):
    owner, _, q, h, checked = _synthetic_inception_owner(monkeypatch)
    result = owner.observe_verified_initial_inceptions(
        qd_bootstrap=q, hl_bootstrap=h,
    )
    assert result["both_initial_fs1_fs3_readbacks_verified"]
    assert result["financial_writer_lease_issued"] is False
    assert not result["paper_start_authorized"]
    assert owner._phase == "INITIAL_READBACK_ONLY"
    assert checked == ["QUALITY_DIPS", "HYPERLIQUID"] * 2
    # Rechecks preserve populated identities and both native file readers.
    assert owner.verify_still_running() is True
    assert checked == ["QUALITY_DIPS", "HYPERLIQUID"] * 3
    with pytest.raises(ValueError, match="INCEPTION_REPLAY_REFUSED"):
        owner.observe_verified_initial_inceptions(
            qd_bootstrap=q, hl_bootstrap=h,
        )
    assert owner._phase == "INITIAL_READBACK_ONLY"


@pytest.mark.parametrize("damage", ["missing_hl", "foreign_account", "wrong_original_id"])
def test_incomplete_initial_financial_native_cut_poisoned_never_promoted(monkeypatch, damage):
    owner, observed, q, h, _ = _synthetic_inception_owner(monkeypatch)
    if damage == "missing_hl":
        h.current = {"authenticated_initial": False}
    if damage == "foreign_account":
        h.enrollment["enrollment"]["account_id"] = "OTHER_ACCOUNT"
    elif damage == "wrong_original_id":
        observed["lanes"]["HYPERLIQUID"]["roots"]["custody"]["native_id"] = [9, 9, 9]
    with pytest.raises(ValueError):
        owner.observe_verified_initial_inceptions(
            qd_bootstrap=q, hl_bootstrap=h,
        )
    assert owner._phase == "INITIAL_READBACK_PENDING"
    with pytest.raises(ValueError, match="INCEPTION_UNKNOWN_RECONCILIATION_REQUIRED"):
        owner.verify_still_running()
    with pytest.raises(ValueError, match="INCEPTION_REPLAY_REFUSED"):
        owner.observe_verified_initial_inceptions(
            qd_bootstrap=q, hl_bootstrap=h,
        )


def test_late_native_directory_identity_swap_revokes_initial_readback_owner(monkeypatch):
    owner, roots, q, h, _ = _synthetic_inception_owner(monkeypatch)
    owner.observe_verified_initial_inceptions(
        qd_bootstrap=q, hl_bootstrap=h,
    )
    roots["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"] = [7, 7, 7]
    with pytest.raises(ValueError, match="POPULATED_NATIVE_RESOURCE_IDENTITY_CHANGED"):
        owner.verify_still_running()
    assert owner._phase == "INITIAL_READBACK_ONLY"
    assert not hasattr(owner, "lease")


def test_durable_initial_publication_rollback_revokes_owner(monkeypatch):
    owner, _, q, h, _ = _synthetic_inception_owner(monkeypatch)
    owner.observe_verified_initial_inceptions(
        qd_bootstrap=q, hl_bootstrap=h,
    )
    q.current["authenticated_initial"] = False
    with pytest.raises(ValueError, match="PERSONAL_INITIAL_READBACK_REFUSED"):
        owner.verify_still_running()
    assert owner._initial_cuts[0][1] == {"authenticated_initial": True}


def synthetic_postinception_activation_owner(monkeypatch):
    """Pytest-only replacement; NEVER a genuine Job, accounts, or finance issuer."""
    calls = []

    class SyntheticOriginal:
        release_digest = "f" * 64
        _phase = "INITIAL_READBACK_ONLY"
        _initial_cuts = ({}, {})
        _initial_bootstraps = (object(), object())
        origin: ClassVar[dict] = {
            "selected_artifact_digest_bound": True,
            "financial_writer_lease_issued": False,
            "financial_activation_published": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }

        def require_exact_roster(self, *, qd, perp):
            calls.append((qd, perp))
            if getattr(self, "revoked", False):
                raise ValueError("SYNTHETIC_ORIGINAL_JOB_REVOKED")
            return True

        def verify_still_running(self):
            return not getattr(self, "revoked", False)

    monkeypatch.setattr(candidate, "RetainedSelectedNativeOwnerPreflight",
                        SyntheticOriginal)
    return SyntheticOriginal(), calls


def test_postinception_selected_original_owner_can_guard_activation_only(monkeypatch):
    fake, calls = synthetic_postinception_activation_owner(monkeypatch)
    from scripts.observation_runtime import personal_activation_publisher as publisher
    monkeypatch.setattr(publisher, "publish_personal_activation",
                        lambda **kwargs: pytest.fail("NO_NATIVE_ACTIVATION_OUTPUT_IN_TEST"))
    with activation.retain_activation_writer_guard(
        qd={"account": "QD"}, perp={"account": "HL"},
        release_digest=fake.release_digest, owned_job=fake,
    ) as held:
        assert held is fake
        assert not hasattr(held, "lease")
        assert not hasattr(held, "place_order")
        assert len(calls) == 1
    assert len(calls) == 2
    assert calls == [({"account": "QD"}, {"account": "HL"})] * 2


@pytest.mark.parametrize("damage", [
    "no_qd_or_hl_ack", "phase_preinception", "pending_partial_inception",
    "missing_cuts", "missing_bootstraps", "only_one_inception",
    "unverified_origin", "writer_lease_claimed", "activation_claimed",
    "paper_start_claimed", "live_order_claimed", "not_exact_release",
])
def test_postinception_activation_guard_refuses_missing_original_proof(
        monkeypatch, damage):
    fake, calls = synthetic_postinception_activation_owner(monkeypatch)
    required_release = fake.release_digest
    if damage == "no_qd_or_hl_ack":
        fake._initial_cuts = None
        fake._initial_bootstraps = None
    elif damage == "phase_preinception":
        fake._phase = "PREINCEPTION"
    elif damage == "pending_partial_inception":
        fake._phase = "INITIAL_READBACK_PENDING"
    elif damage == "missing_cuts":
        fake._initial_cuts = None
    elif damage == "missing_bootstraps":
        fake._initial_bootstraps = None
    elif damage == "only_one_inception":
        fake._initial_bootstraps = (object(),)
    elif damage == "unverified_origin":
        fake.origin["selected_artifact_digest_bound"] = False
    elif damage == "writer_lease_claimed":
        fake.origin["financial_writer_lease_issued"] = True
    elif damage == "activation_claimed":
        fake.origin["financial_activation_published"] = True
    elif damage == "paper_start_claimed":
        fake.origin["paper_start_authorized"] = True
    elif damage == "live_order_claimed":
        fake.origin["live_trading_authorized"] = True
    elif damage == "not_exact_release":
        required_release = "e" * 64
    with (pytest.raises(ValueError),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest=required_release,
              owned_job=fake)):
        pytest.fail("INCOMPLETE_OR_UNKNOWN_NATIVE_ACCOUNT_ACTIVATION_ACCEPTED")
    assert calls == []


def test_postinception_original_job_revocation_blocks_guard_entry(monkeypatch):
    fake, calls = synthetic_postinception_activation_owner(monkeypatch)
    fake.revoked = True
    with (pytest.raises(ValueError, match="SYNTHETIC_ORIGINAL_JOB_REVOKED"),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest=fake.release_digest,
              owned_job=fake)):
        pytest.fail("REVOKED_ORIGINAL_JOB_ACCEPTED")
    assert len(calls) == 1


def test_postinception_original_job_revocation_blocks_guard_exit(monkeypatch):
    fake, calls = synthetic_postinception_activation_owner(monkeypatch)
    with (pytest.raises(ValueError, match="SYNTHETIC_ORIGINAL_JOB_REVOKED"),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest=fake.release_digest,
              owned_job=fake)):
        fake.revoked = True
    assert len(calls) == 2


def test_postinception_phase_drift_blocks_guard_exit(monkeypatch):
    fake, calls = synthetic_postinception_activation_owner(monkeypatch)
    with (pytest.raises(ValueError, match="INITIAL_OWNER_PHASE_CHANGED"),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest=fake.release_digest,
              owned_job=fake)):
        fake._phase = "INITIAL_READBACK_PENDING"
    assert len(calls) == 2


def _synthetic_preinception_activation_owner(monkeypatch):
    """Pure pytest fake; cannot become original Windows Job or finance issuer."""
    from scripts.observation_runtime import (
        personal_native_selected_owned_job_preflight as native,
    )
    calls = []

    class FakeOwner:
        release_digest = "f" * 64
        _phase = "PREINCEPTION_COORDINATION_READY"
        origin: ClassVar[dict] = {
            "selected_artifact_digest_bound": True,
            "financial_writer_lease_issued": False,
            "financial_activation_published": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }

        def require_exact_roster(self, *, qd, perp):
            calls.append((qd, perp))
            if getattr(self, "revoked", False):
                raise ValueError("SYNTHETIC_OWNER_REVOKED")
            return True

    monkeypatch.setattr(native, "RetainedSelectedNativeOwnerPreflight", FakeOwner)
    return FakeOwner(), calls


def test_original_job_can_guard_first_inception_only_operator_activation(monkeypatch):
    owner, calls = _synthetic_preinception_activation_owner(monkeypatch)
    with activation.retain_activation_writer_guard(
        qd={"lane": "QD"}, perp={"lane": "HL"},
        release_digest=owner.release_digest, owned_job=owner,
        actions=["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"],
    ) as held:
        assert held is owner
        assert not hasattr(held, "lease")
        assert len(calls) == 1
    assert len(calls) == 2
    assert calls == [({"lane": "QD"}, {"lane": "HL"})] * 2


@pytest.mark.parametrize("actions", [
    None, [], ["READ_ONLY"], ["INITIALIZE_SIMULATED_ACCOUNTS"], ["AUTO_PAPER"],
    ["SHUTDOWN_FLATTEN", "INITIALIZE_SIMULATED_ACCOUNTS"],
    ["CONNECT_APPROVED_DATA", "INITIALIZE_SIMULATED_ACCOUNTS"],
    ["INITIALIZE_SIMULATED_ACCOUNTS", "INITIALIZE_SIMULATED_ACCOUNTS"],
    ["INITIALIZE_SIMULATED_ACCOUNTS", "AUTO_PAPER"],
    ["INITIALIZE_SIMULATED_ACCOUNTS", "EMERGENCY_STOP"],
    ["INITIALIZE_SIMULATED_ACCOUNTS", "LIVE_ORDERS"],
    "INITIALIZE_SIMULATED_ACCOUNTS",
])
def test_preinception_activation_never_grants_trading_or_unscoped_actions(
        monkeypatch, actions):
    owner, calls = _synthetic_preinception_activation_owner(monkeypatch)
    with (pytest.raises(ValueError, match="PREINCEPTION_INIT_AND_READ_REQUIRED"),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest=owner.release_digest,
              owned_job=owner, actions=actions)):
        pytest.fail("UNAPPROVED_FIRST_INCEPTION_ACTIVATION")
    assert calls == []


@pytest.mark.parametrize("mutation", [
    "foreign_release", "selected_unbound", "financial_lease",
    "already_activated", "paper_enabled", "live_enabled",
    "not_real_owner", "already_initializing",
])
def test_preinception_operator_guard_refuses_untrusted_source_or_owner(
        monkeypatch, mutation):
    owner, calls = _synthetic_preinception_activation_owner(monkeypatch)
    release = owner.release_digest
    if mutation == "foreign_release":
        release = "e" * 64
    elif mutation == "selected_unbound":
        owner.origin["selected_artifact_digest_bound"] = False
    elif mutation == "financial_lease":
        owner.origin["financial_writer_lease_issued"] = True
    elif mutation == "already_activated":
        owner.origin["financial_activation_published"] = True
    elif mutation == "paper_enabled":
        owner.origin["paper_start_authorized"] = True
    elif mutation == "live_enabled":
        owner.origin["live_trading_authorized"] = True
    elif mutation == "not_real_owner":
        owner = object()
    elif mutation == "already_initializing":
        owner._phase = "INITIAL_READBACK_PENDING"
    with pytest.raises(ValueError), activation.retain_activation_writer_guard(
        qd={}, perp={}, release_digest=release,
        owned_job=owner,
        actions=["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"],
    ):
        pytest.fail("UNACCEPTED_SELECTED_INCEPTION_OWNER")
    assert calls == []


def test_preinception_native_job_revocation_on_exit_refuses_activation(monkeypatch):
    owner, calls = _synthetic_preinception_activation_owner(monkeypatch)
    with (pytest.raises(ValueError, match="SYNTHETIC_OWNER_REVOKED"),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest=owner.release_digest,
              owned_job=owner, actions=["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"])):
        owner.revoked = True
    assert len(calls) == 2


def test_preinception_owner_phase_drift_on_exit_refuses_activation(monkeypatch):
    owner, calls = _synthetic_preinception_activation_owner(monkeypatch)
    with (pytest.raises(ValueError, match="PREINCEPTION_OWNER_PHASE_CHANGED"),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest=owner.release_digest,
              owned_job=owner, actions=["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"])):
        owner._phase = "INITIAL_READBACK_ONLY"
    assert len(calls) == 2


@pytest.mark.parametrize("actions", [
    ["INITIALIZE_SIMULATED_ACCOUNTS"],
    ["AUTO_PAPER", "INITIALIZE_SIMULATED_ACCOUNTS"],
    ["INITIALIZE_SIMULATED_ACCOUNTS", "READ_ONLY"],
])
def test_postinception_operator_activation_must_not_reuse_initializer(
        monkeypatch, actions):
    owner, calls = synthetic_postinception_activation_owner(monkeypatch)
    with (pytest.raises(ValueError, match="POSTINCEPTION_INIT_REUSE_REFUSED"),
          activation.retain_activation_writer_guard(
              qd={}, perp={}, release_digest=owner.release_digest,
              owned_job=owner, actions=actions)):
        pytest.fail("POSTINCEPTION_ACCOUNT_INITIALIZATION_REPLAY")
    assert calls == []


def test_commission_function_passes_actual_operator_record_action_to_native_guard():
    source = inspect.getsource(activation.commission)
    assert "actions=record['actions']" in source
    assert "publish_personal_activation(" in source
