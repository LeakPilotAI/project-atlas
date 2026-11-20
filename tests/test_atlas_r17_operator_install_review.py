"""R17 precise native CODE-only operator review — no consent granted."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import atlas_r17_operator_install_review as review


def test_original_windows_release_operator_review_is_unapproved_and_nonfinancial():
    if review.installer.TARGET.exists():
        pytest.skip("historical preinstall operator review completed; installed release cannot requalify")
    record = review.operator_review()
    assert record["schema"] == review.SCHEMA
    assert record["status"] == "PREPARED_FOR_DISTINCT_OPERATOR_DECISION_NOT_APPROVED"
    assert record["source_commit"] == review.installer.SOURCE
    assert record["archive_sha256"] == review.installer.ARCHIVE_SHA
    assert record["installer_source_sha256"] == review.installer.source_digest_for_approval()
    assert record["cpu_guard_sha256"] == review.installer.CPU_GUARD_SHA256
    assert record["source_files"] == 1044
    assert record["planned_native_files"] == 10610
    assert record["planned_bytes"] == 264594673
    assert record["selected_native_predecessor"] == "R16"
    assert record["installer_max_logical_processors"] == 2
    assert record["host_busy_threshold_percent"] == 70
    assert len(record["windows_operator_sid_fingerprint_sha256"]) == 64
    assert record["operator_one_shot_authorization_present"] is False
    assert record["new_native_release_installed"] is False
    assert record["native_release_selection_requested"] is False
    assert record["account_creation_or_mutation"] is False
    assert record["provider_or_broker_connections"] is False
    assert record["financial_authority"] is False
    assert record["paper_start_authorized"] is False
    assert record["live_trading_authorized"] is False
    assert record["native_financial_operating_gates_accepted"] == 0
    assert record["next_step_requires_distinct_explicit_operator_action"] is True
    assert not review.installer.TARGET.exists()
    assert review.installer.APPROVAL_SHA256 is None


@pytest.mark.parametrize("changed", [
    "unexpected_install", "unverified_archive", "changed_head",
    "wrong_count", "extra_release_selected", "financial_authority",
    "paper_start", "operator_approval", "cpu_guard",
])
def test_foreign_or_financial_status_never_becomes_a_review_packet(
        monkeypatch, changed):
    # An in-pytest synthetic review cannot grant authority.
    fixture = {
        "status": "FROZEN_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION",
        "installed": False, "separate_approval_pinned": False,
        "source_commit": review.installer.SOURCE,
        "archive_sha256": review.installer.ARCHIVE_SHA,
        "native_target": str(review.installer.TARGET),
        "planned_native_files": 10610,
        "planned_source_files": 1044,
        "planned_bytes": 264594673,
    }
    monkeypatch.setattr(review.installer, "inspect", lambda: deepcopy(fixture))
    monkeypatch.setattr(review.installer, "require_selected_r16", lambda: True)
    monkeypatch.setattr(
        review.installer, "require_original_financial_roots_untouched",
        lambda: True,
    )
    monkeypatch.setattr(review.installer, "require_cpu_budget_pinned", lambda: True)
    if changed == "unexpected_install":
        fixture["installed"] = True
    elif changed == "unverified_archive":
        fixture["archive_sha256"] = "f"*64
    elif changed == "changed_head":
        fixture["source_commit"] = "f"*40
    elif changed == "wrong_count":
        fixture["planned_native_files"] = 10609
    elif changed == "extra_release_selected":
        monkeypatch.setattr(review.os.path, "lexists", lambda path: True)
    elif changed == "financial_authority":
        monkeypatch.setattr(review.installer, "require_original_financial_roots_untouched",
                            lambda: False)
    elif changed == "paper_start":
        monkeypatch.setattr(review.installer, "inspect",
                            lambda: {**fixture, "status":"PAPER_START_AUTHORIZED"})
    elif changed == "operator_approval":
        monkeypatch.setattr(review.installer, "APPROVAL_SHA256", "c"*64)
    elif changed == "cpu_guard":
        monkeypatch.setattr(review.installer, "require_cpu_budget_pinned",
                            lambda: False)
    with pytest.raises(ValueError, match="OPERATOR_REVIEW_PRECONDITIONS"):
        review.operator_review()


def test_review_never_creates_operator_grant_or_native_copy(monkeypatch):
    if review.installer.TARGET.exists():
        pytest.skip("preinstall review tool is deliberately retired after native code installation")
    monkeypatch.setattr(review.installer, "install",
                        lambda **_: pytest.fail("INSTALL_NOT_AUTHORIZED"))
    monkeypatch.setattr(review.selector, "publish",
                        lambda **_: pytest.fail("SELECTION_NOT_AUTHORIZED"))
    monkeypatch.setattr(review.installer, "require_separate_approval",
                        lambda: pytest.fail("APPROVAL_NOT_REQUIRED_FOR_REVIEW"))
    result = review.operator_review()
    assert result["operator_one_shot_authorization_present"] is False
    assert result["native_release_selection_requested"] is False


def test_plain_inspect_cli_only_read_only(capsys):
    if review.installer.TARGET.exists():
        pytest.skip("create-only preinstall CLI must refuse after installation, not issue new approval")
    assert review.main(["--inspect"]) == 0
    output = capsys.readouterr().out
    assert review.SCHEMA in output
    assert '"financial_authority": false' in output
    assert '"paper_start_authorized": false' in output
    assert '"operator_one_shot_authorization_present": false' in output


def test_without_explicit_inspect_argument_cli_refuses():
    with pytest.raises(SystemExit):
        review.main([])


def test_real_completed_r17_one_shot_install_remains_unselected_and_nonfinancial():
    if not review.installer.TARGET.exists():
        pytest.skip("real code-only native installation not yet performed")
    a = review.installer
    assert a.RECEIPT.is_file()
    assert a.require_selected_r16() is True
    assert a.require_original_financial_roots_untouched() is True
    assert a.require_separate_approval()["one_shot"] is True
    receipt = json.loads(a.RECEIPT.read_text(encoding="utf-8"))
    assert receipt["schema"] == "ATLAS_QD_D_RUNTIME_INSTALLATION_V1"
    assert receipt["stage"] == "D_RUNTIME_LAYOUT_VERIFIED"
    assert receipt["source_commit"] == a.SOURCE
    assert receipt["archive_sha256"] == a.ARCHIVE_SHA
    assert len(receipt["files"]) == a.EXPECTED_TOTAL_FILES
    assert len(receipt["directories"]) == a.EXPECTED_TOTAL_DIRECTORIES
    assert receipt["selected"] is False
    assert receipt["financial_effects"] is False
    assert receipt["provider_connections"] is False
    assert receipt["operational_acceptance"] is False
    assert not (Path("D:/AtlasRuntime/selection")/"r0016.json").exists()
    assert not (Path("D:/AtlasRuntime/selection")/"r0016.pending").exists()
