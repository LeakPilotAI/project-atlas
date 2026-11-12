"""R17 one-shot CODE-only installer admission. Real inspect, no native writes.

All positive decisions are pure, synthetic records. No signed-in operator
decision is written or pinned by these tests; no native install may execute.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts import atlas_r17_code_only_installer as installer

SID = "S-1-5-21-100-200-300-400"


def specimen():
    return {
        "schema": "ATLAS_R17_CODE_ONLY_NATIVE_INSTALL_APPROVAL_V1",
        "operation": installer.OPERATION,
        "scope": installer.SCOPE,
        "operator_sid": SID,
        "source_commit": installer.SOURCE,
        "archive_sha256": installer.ARCHIVE_SHA,
        "inventory_sha256": installer.INVENTORY_SHA,
        "dependency_inventory_sha256": installer.DEPENDENCY_INVENTORY_SHA256,
        "selected_predecessor_head": installer.PREDECESSOR_HEAD,
        "selected_predecessor_record_sha256": installer.PREDECESSOR_RECORD_SHA,
        "selected_predecessor_artifact_digest": installer.PREDECESSOR_ARTIFACT,
        "installer_source_sha256": installer.source_digest_for_approval(),
        "destination": str(installer.TARGET),
        "receipt": str(installer.RECEIPT),
        "one_shot": True,
        "selection_allowed": False,
        "financial_authority": False,
        "provider_access": False,
        "paper_accounts": False,
        "startup_authorized": False,
        "paper_orders_authorized": False,
        "live_orders_authorized": False,
    }


def test_synthetic_exact_decision_only_no_operational_permission():
    record = specimen()
    assert installer.validate_operator_decision(
        record, sid=SID, installer_source_sha256=installer.source_digest_for_approval()
    ) is record
    for name in (
        "selection_allowed", "financial_authority", "provider_access",
        "paper_accounts", "startup_authorized", "paper_orders_authorized",
        "live_orders_authorized",
    ):
        assert record[name] is False


@pytest.mark.parametrize("damage", [
    "schema", "operation", "scope", "operator_sid", "source_commit",
    "archive_sha256", "inventory_sha256", "dependency_inventory_sha256",
    "selected_predecessor_head", "selected_predecessor_record_sha256",
    "selected_predecessor_artifact_digest", "installer_source_sha256",
    "destination", "receipt", "one_shot", "selection_allowed",
    "financial_authority", "provider_access", "paper_accounts",
    "startup_authorized", "paper_orders_authorized", "live_orders_authorized",
    "extra_permission", "missing_field", "boolean_as_sid",
])
def test_one_shot_install_scope_fails_closed_on_any_identity_or_capability_drift(damage):
    row = copy.deepcopy(specimen())
    if damage == "extra_permission":
        row["financial_lease_issuer"] = True
    elif damage == "missing_field":
        row.pop("receipt")
    elif damage == "boolean_as_sid":
        row["operator_sid"] = True
    elif damage == "one_shot":
        row[damage] = False
    elif damage in (
        "selection_allowed", "financial_authority", "provider_access",
        "paper_accounts", "startup_authorized",
        "paper_orders_authorized", "live_orders_authorized",
    ):
        row[damage] = True
    else:
        row[damage] = "UNREVIEWED"
    with pytest.raises(ValueError, match="R17_EXACT_SID_BOUND"):
        installer.validate_operator_decision(
            row, sid=SID, installer_source_sha256=installer.source_digest_for_approval()
        )


def test_different_current_windows_operator_cannot_reuse_approval():
    with pytest.raises(ValueError, match="R17_EXACT_SID_BOUND"):
        installer.validate_operator_decision(
            specimen(), sid="S-1-5-21-999-999-999-999",
            installer_source_sha256=installer.source_digest_for_approval(),
        )


def test_changed_installer_source_digest_cannot_reuse_synthetic_decision():
    with pytest.raises(ValueError, match="R17_EXACT_SID_BOUND"):
        installer.validate_operator_decision(
            specimen(), sid=SID, installer_source_sha256="f"*64,
        )


def test_live_one_shot_approval_unpinned_refuses_before_copy_or_utc(monkeypatch):
    assert installer.APPROVAL_SHA256 is None
    monkeypatch.setattr(
        installer, "require_code_install_host_ready",
        lambda *_a, **_k: pytest.fail("COPY_HOST_NOT_ENTERED"),
    )
    monkeypatch.setattr(
        installer, "inspect_prepared",
        lambda: pytest.fail("FROZEN_ARCHIVE_NOT_CONSUMED"),
    )
    with pytest.raises(ValueError, match="R17_CODE_INSTALL_SEPARATE_PINNED_OPERATOR"):
        installer.install(approved_execution=True, clock=None)
    with pytest.raises(ValueError, match="R17_CODE_INSTALL_SEPARATE_PINNED_OPERATOR"):
        installer.main(["--execute-one-shot-code-install", "--confirm-scope", installer.SCOPE])


def test_nonexact_cli_scope_refused_before_any_clock_or_approval(monkeypatch):
    monkeypatch.setattr(
        installer, "require_separate_approval",
        lambda: pytest.fail("WRONG_SCOPE_OPENED_APPROVAL"),
    )
    with pytest.raises(ValueError, match="R17_ONE_SHOT_EXACT_SCOPE"):
        installer.main(["--execute-one-shot-code-install", "--confirm-scope",
                        "INSTALL_AND_TRADE"])


def test_execute_flag_not_supplied_refuses_even_exact_approval():
    with pytest.raises(ValueError, match="R17_ONE_SHOT_CODE_INSTALL_EXPLICIT"):
        installer.install(approved_execution=False, clock=None)


def test_host_inspection_only_verifies_real_selected_predecessor_without_native_write():
    assert installer.require_selected_r16()
    assert installer.require_original_financial_roots_untouched()
    assert installer.require_create_only_target()
    assert not installer.TARGET.exists()
    assert not installer.RECEIPT.exists()


def test_pinned_review_and_archive_exact_real_plan_readonly():
    before = (installer.TARGET.exists(), installer.RECEIPT.exists(),
              installer.RECEIPT.with_suffix(".pending.jsonl").exists())
    preview = installer.inspect()
    assert preview["selected_predecessor"] == "R16"
    assert preview["source_commit"] == installer.SOURCE
    assert preview["planned_source_files"] == 1033
    assert preview["planned_native_files"] == 10599
    assert preview["planned_bytes"] == 264437110
    assert preview["separate_approval_pinned"] is False
    assert not preview["installed"]
    assert not preview["selection_allowed"]
    assert not preview["financial_authority"]
    assert not preview["paper_start_authorized"]
    assert not preview["live_orders_authorized"]
    assert before == (installer.TARGET.exists(), installer.RECEIPT.exists(),
                      installer.RECEIPT.with_suffix(".pending.jsonl").exists())


def test_installer_runtime_source_cannot_be_pinned_by_arbitrary_hash():
    assert len(installer.source_digest_for_approval()) == 64
    assert Path(installer.__file__).is_file()


def test_future_release_must_not_inherit_r16_install_approval():
    from scripts.atlas_r16_code_only_installer import APPROVAL as R16_APPROVAL
    assert installer.APPROVAL != R16_APPROVAL
    assert installer.OPERATION != "APPROVE_ONE_R16_CODE_ONLY_NATIVE_INSTALL"


class FakeCopyEnvelope:
    def __init__(self):
        self.now = 100.0
        self.checks = 0

    def tick(self):
        self.checks += 1

    def monotonic(self):
        return self.now


class FakeUtcClock:
    def __init__(self):
        self.samples = []

    def require_operational(self, name):
        self.samples.append(name)


def test_low_resource_native_admission_rate_limits_real_checks(monkeypatch):
    calls = []
    monkeypatch.setattr(installer, "require_code_install_host_ready",
                        lambda path: calls.append("host"))
    monkeypatch.setattr(installer, "require_selected_r16",
                        lambda: calls.append("selected"))
    monkeypatch.setattr(installer, "require_original_financial_roots_untouched",
                        lambda: calls.append("roots"))
    monkeypatch.setattr(installer, "require_separate_approval",
                        lambda: calls.append("consent"))
    env, utc = FakeCopyEnvelope(), FakeUtcClock()
    assert installer._check_live_copy_admission(clock=utc, envelope=env)
    assert env.checks == 1
    assert len(utc.samples) == 1
    assert calls == ["host", "selected", "roots", "consent"]
    for _ in range(200):
        assert installer._check_live_copy_admission(clock=utc, envelope=env)
    assert len(utc.samples) == 1
    assert len(calls) == 4
    env.now += installer.NTP_ADMISSION_REFRESH_SECONDS
    installer._check_live_copy_admission(clock=utc, envelope=env)
    assert len(utc.samples) == 2
    assert len(calls) == 4
    env.now += installer.HOST_ADMISSION_REFRESH_SECONDS
    installer._check_live_copy_admission(clock=utc, envelope=env)
    assert len(utc.samples) == 3
    assert calls == ["host", "selected", "roots", "consent"] * 2


def test_copy_admission_revokes_when_predecessor_selection_drifts(monkeypatch):
    monkeypatch.setattr(installer, "require_code_install_host_ready",
                        lambda path: True)
    monkeypatch.setattr(installer, "require_selected_r16",
                        lambda: (_ for _ in ()).throw(
                            ValueError("R16_SELECTION_DRIFT")))
    env, utc = FakeCopyEnvelope(), FakeUtcClock()
    with pytest.raises(ValueError, match="R16_SELECTION_DRIFT"):
        installer._check_live_copy_admission(clock=utc, envelope=env)
    assert len(utc.samples) == 1


def test_copy_admission_refuses_clock_without_entering_native_copy(monkeypatch):
    class RevokedUtc:
        def require_operational(self, name):
            raise ValueError("TWO_PEER_UTC_REVOKED")

    monkeypatch.setattr(installer, "require_code_install_host_ready",
                        lambda path: pytest.fail("NO_COPY_WHEN_CLOCK_REVOKED"))
    with pytest.raises(ValueError, match="TWO_PEER_UTC_REVOKED"):
        installer._check_live_copy_admission(
            clock=RevokedUtc(), envelope=FakeCopyEnvelope())
