"""Fail-closed tests for R23 original native create-missing-only recovery.

No test ever writes D:/AtlasRuntime, original financial directories,
original approval receipts, or the release selector.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import atlas_r23_code_only_select as selector
from scripts import atlas_r23_local_operator_consent as old_local
from scripts import atlas_r23_local_recovery_consent as local
from scripts import atlas_r23_native_recovery as recovery


def test_exact_failed_install_audit_is_bound_no_approval():
    result = recovery._audit()
    assert result["existing_native_verified_prefix_files"] == 7910
    assert result["remaining_create_only_files"] == 2853
    assert result["native_original_acl_identity_hash_readback"] is True
    assert result["original_partial_refusal_preserved"] is True
    assert len(result["native_directories"]) == 915
    assert len(result["native_prefix_files"]) == 7910
    assert result["financial_accounts_created"] is False
    assert result["paper_start_authorized"] is False
    assert result["live_trading_authorized"] is False
    assert recovery.AUDIT_SHA == hashlib.sha256(
        recovery.AUDIT.read_bytes(),
    ).hexdigest()
    assert recovery.APPROVAL_PIN is None


def test_recovery_and_selection_are_two_distinct_local_human_decisions():
    assert local.EXPECTED_RECOVERY_SOURCE_SHA256 == recovery.source_hash()
    assert old_local.EXPECTED_SELECTOR_HASH == selector.source_hash()
    assert recovery.SCOPE != selector.SCOPE
    assert recovery.APPROVAL != selector.APPROVAL
    assert recovery.RECOVERY_JOURNAL != recovery.JOURNAL
    assert recovery.RECOVERY_RECEIPT != recovery.RECEIPT
    assert recovery.MIN_PREFIX == recovery.MAX_PREFIX == 7910


def test_human_recovery_decision_carries_no_financial_authority(monkeypatch):
    from scripts.volume_inspector import windows_output

    monkeypatch.setattr(
        windows_output, "current_sid", lambda: "S-1-5-21-fixture",
    )
    monkeypatch.setattr(recovery, "original_selected_r21", lambda: {
        "release": recovery.SOURCE.replace("96c6", "119d"),
        "artifact_digest": "a" * 64,
    })
    decision = local.decision_record({
        "original_refused_journal_sha256": "b" * 64,
    })
    assert decision["schema"] == "ATLAS_R23_NATIVE_PARTIAL_CODE_RECOVERY_APPROVAL_V1"
    assert decision["scope"] == recovery.SCOPE
    assert decision["operator_sid"] == "S-1-5-21-fixture"
    assert decision["read_only_native_audit_sha256"] == recovery.AUDIT_SHA
    assert decision["installer_source_sha256"] == recovery.source_hash()
    assert decision["native_prefix_files"] == 7910
    assert decision["remaining_create_only_files"] == 2853
    assert decision["one_shot"] is True
    for key in (
        "financial_authority", "provider_access", "simulated_accounts",
        "paper_start_authorized", "live_trading_authorized",
    ):
        assert decision[key] is False


def test_no_recovery_without_new_distinct_operator_approval():
    with pytest.raises(ValueError, match="DISTINCT_APPROVAL_REQUIRED"):
        recovery.approval_digest()
    with pytest.raises(ValueError, match="SEPARATE_ONE_SHOT_APPROVAL_REQUIRED"):
        recovery.recover(clock=object(), approved=False)
    assert not Path(recovery.RECOVERY_JOURNAL).exists()
    assert not Path(recovery.RECOVERY_RECEIPT).exists()


def test_remote_or_invisible_console_cannot_issue_recovery(monkeypatch):
    monkeypatch.setattr(
        old_local, "require_visible_local_console",
        lambda: (_ for _ in ()).throw(
            ValueError("R23_VISIBLE_LOCAL_WINDOWS_OPERATOR_CONSOLE_REQUIRED")
        ),
    )
    monkeypatch.setattr(
        local, "review_recovery",
        lambda: pytest.fail("No native recovery review after headless refusal"),
    )
    with pytest.raises(ValueError, match="VISIBLE_LOCAL_WINDOWS_OPERATOR"):
        local.main(["--recover-and-select"])


@pytest.mark.parametrize("second", ("decline", "approve"))
def test_separate_selection_requires_distinct_explicit_phrase(monkeypatch, second):
    monkeypatch.setattr(old_local, "require_visible_local_console", lambda: True)
    monkeypatch.setattr(local, "review_recovery", lambda: {
        "recovery_scope": recovery.SCOPE,
    })
    monkeypatch.setattr(
        local, "pin_after_distinct_human_recovery_approval",
        lambda: "a" * 64,
    )
    monkeypatch.setattr(recovery, "main", lambda argv: {
        "status": "R23_ORIGINAL_NATIVE_RECOVERY_FULL_CODE_ONLY_VERIFIED_UNSELECTED",
        "native_installed_files": 10763,
        "original_native_files_revalidated": 7910,
        "new_native_create_only_files": 2853,
        "financial_authority": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    })
    monkeypatch.setattr(old_local, "selection_review", lambda: {
        "scope": old_local.SELECTION_SCOPE,
    })
    typed = iter([
        recovery.SCOPE,
        old_local.SELECTION_SCOPE if second == "approve" else "",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(typed))
    if second == "decline":
        monkeypatch.setattr(
            old_local, "pin_selection_after_human_action",
            lambda: pytest.fail("Selection cannot be pinned without human scope"),
        )
        assert local.main(["--recover-and-select"]) == 2
    else:
        selection_calls = []
        monkeypatch.setattr(
            old_local, "pin_selection_after_human_action", lambda: "b" * 64,
        )
        monkeypatch.setattr(
            selector, "main",
            lambda argv: selection_calls.append(argv) or {
                "status": "R23_NATIVE_CODE_ONLY_SELECTED_NO_FINANCIAL_START",
            },
        )
        assert local.main(["--recover-and-select"]) == 0
        assert selection_calls == [[
            "--execute-approved-code-only", "--confirm-scope",
            old_local.SELECTION_SCOPE,
        ]]


def _proof_fixture():
    first = json.dumps({
        "schema": "ATLAS_R23_UNSELECTED_CODE_INSTALL_INTENT_V1",
        "source_commit": recovery.SOURCE,
        "archive_sha256": recovery.ARCHIVE_SHA,
        "target": str(recovery.TARGET),
        "financial_authority": False,
        "selection_allowed": False,
        "paper_start_authorized": False,
    }, sort_keys=True).encode()
    refused = json.dumps({
        "stage": "REFUSED_PRESERVE_PARTIAL_NO_RETRY",
    }, sort_keys=True).encode()
    receipt_sha = "b" * 64
    artifact = "c" * 64
    old_sha = hashlib.sha256(b"\n".join((first, refused))).hexdigest()
    third = json.dumps({
        "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
        "receipt_sha256": receipt_sha,
    }, sort_keys=True).encode()
    proof = {
        "schema": recovery.SCHEMA,
        "stage": "RECOVERY_FULL_NATIVE_ORIGINAL_READBACK_ACCEPTED",
        "source_commit": recovery.SOURCE,
        "source_archive_sha256": recovery.ARCHIVE_SHA,
        "original_partial_native_files_rechecked": 7910,
        "new_native_create_only_files": 2853,
        "final_original_native_files": 10763,
        "final_original_native_directories": 915,
        "original_refusal_journal_sha256": old_sha,
        "independent_original_native_installed_readback": True,
        "source_release_artifact_digest": artifact,
        "code_only_release_selected": False,
        "financial_authority": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }
    recovery_journal = b"\n".join([
        json.dumps({
            "schema": recovery.SCHEMA,
            "stage": "RECOVERY_INTENT_VERIFY_EXISTING_CREATE_MISSING_ONLY",
            "original_audit_sha256": recovery.AUDIT_SHA,
            "original_refusal_sha256": old_sha,
            "new_original_root_allowed": False,
            "financial_authority": False,
            "selection_allowed": False,
        }, sort_keys=True).encode(),
        json.dumps({
            "stage": "RECOVERED_FULL_CODE_ONLY_NATIVE_ACK",
            "receipt_sha256": receipt_sha,
        }, sort_keys=True).encode(),
    ])
    return [first, refused, third], receipt_sha, artifact, proof, recovery_journal


@pytest.mark.parametrize("alteration", (
    "valid", "bad_refusal", "bad_original_sha", "bad_file_count",
    "unverified_readback", "bad_recovery_ack", "missing_human_approval",
))
def test_native_selector_requires_complete_nonforged_recovery(
    monkeypatch, alteration,
):
    rows, receipt_sha, artifact, proof, recovery_journal = _proof_fixture()
    if alteration == "bad_refusal":
        rows[1] = json.dumps({"stage": "IGNORED_REFUSAL"}).encode()
    elif alteration == "bad_original_sha":
        proof["original_refusal_journal_sha256"] = "0" * 64
    elif alteration == "bad_file_count":
        proof["new_native_create_only_files"] = 2852
    elif alteration == "unverified_readback":
        proof["independent_original_native_installed_readback"] = False
    elif alteration == "bad_recovery_ack":
        recovery_journal = recovery_journal.replace(
            receipt_sha.encode(), b"d" * 64,
        )
    calls = []
    def original_decision():
        calls.append("distinct_recovery_approval_read")
        if alteration == "missing_human_approval":
            raise ValueError("R23_RECOVERY_DISTINCT_APPROVAL_REQUIRED")
        return "e" * 64
    monkeypatch.setattr(selector, "recovery_approval_digest", original_decision)
    monkeypatch.setattr(
        selector, "source_bytes",
        lambda parent, name, maximum_bytes: (
            json.dumps(proof, sort_keys=True, allow_nan=False).encode()
            if name == recovery.RECOVERY_RECEIPT.name
            else recovery_journal
        ),
    )
    if alteration == "valid":
        assert selector.require_exact_original_recovered_install_ack(
            rows, receipt_sha=receipt_sha, artifact=artifact,
        ) is True
        assert calls == ["distinct_recovery_approval_read"]
    else:
        with pytest.raises(ValueError, match="R23_"):
            selector.require_exact_original_recovered_install_ack(
                rows, receipt_sha=receipt_sha, artifact=artifact,
            )


def test_failed_recovery_result_cannot_proceed_to_selection(monkeypatch):
    monkeypatch.setattr(old_local, "require_visible_local_console", lambda: True)
    monkeypatch.setattr(local, "review_recovery", lambda: {
        "recovery_scope": recovery.SCOPE,
    })
    monkeypatch.setattr(
        local, "pin_after_distinct_human_recovery_approval",
        lambda: "a" * 64,
    )
    monkeypatch.setattr("builtins.input", lambda prompt: recovery.SCOPE)
    monkeypatch.setattr(recovery, "main", lambda argv: {
        "status": "R23_RECOVERY_PARTIAL_UNKNOWN",
        "paper_start_authorized": False,
        "financial_authority": False,
    })
    monkeypatch.setattr(
        old_local, "selection_review",
        lambda: pytest.fail("Never read selector after incomplete recovery"),
    )
    with pytest.raises(ValueError, match="ORIGINAL_RECOVERY_INCOMPLETE"):
        local.main(["--recover-and-select"])
