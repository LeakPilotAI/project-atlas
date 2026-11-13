"""R21 partial recovery must remain explicitly approved and code-only."""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from scripts import atlas_r21_native_recovery as r21
from scripts import atlas_r21_partial_native_readonly as audit


def test_original_forensic_recovery_scope_not_old_installer_retry():
    assert r21.SOURCE == "119dd8626da32e74bd7f86db9de1c1a8fd2c20ac"
    assert "ORIGINAL_NATIVE_PARTIAL_CODE_RECOVERY_NO_FINANCE" in r21.SCOPE
    assert "COPY" not in r21.SCOPE
    assert r21.MAX_RECOVERY_SECONDS <= 590
    assert r21.MIN_PREFIX == 7000 and r21.MAX_PREFIX == 8000
    assert r21.RECOVERY_JOURNAL.is_relative_to(audit.ROOT)
    assert r21.RECOVERY_RECEIPT.is_relative_to(audit.ROOT)
    assert r21.APPROVAL.is_relative_to(audit.ROOT)
    assert not r21.TARGET.is_relative_to(audit.ROOT)
    assert r21.RECOVERY_JOURNAL != r21.JOURNAL
    assert r21.RECOVERY_RECEIPT != r21.RECEIPT
    assert r21.RECOVERED_ACK_STAGE == "UNSELECTED_CODE_INSTALL_VERIFIED"
    assert r21.AUDIT_SHA == (
        "039e23789d9d7d83f6003834d92c532bd79f45be1e440e2ab288413febce84d1"
    )
    assert r21.source_hash() != r21.ARCHIVE_SHA


def test_original_partial_audit_receipt_is_pinned_and_nonfinancial():
    row = r21._audit()
    assert row["schema"] == audit.SCHEMA
    assert row["expected_file_count"] == 10731
    assert row["existing_native_verified_prefix_files"] == 7350
    assert row["existing_native_verified_prefix_bytes"] == 217782758
    assert row["remaining_create_only_files"] == 3381
    assert len(row["native_prefix_files"]) == 7350
    assert len(row["native_directories"]) == 915
    assert row["original_partial_refusal_preserved"] is True
    assert row["code_only_recovery_write_authorized"] is False
    assert row["paper_start_authorized"] is False
    assert row["live_trading_authorized"] is False


def test_original_partial_approval_must_be_separate_from_old_one_shot(monkeypatch):
    monkeypatch.setattr(r21, "APPROVAL_PIN", None)
    with pytest.raises(ValueError, match="DISTINCT_APPROVAL_REQUIRED"):
        r21.approval_digest()
    with pytest.raises(ValueError, match="SEPARATE_ONE_SHOT_APPROVAL_REQUIRED"):
        r21.recover(clock=object(), approved=False)


def test_original_partial_clock_refuses_synthetic_other_clock():
    with pytest.raises(ValueError, match="ORIGINAL_TWO_PEER_NTP_REQUIRED"):
        r21.clock_required_as_recovery(SimpleNamespace(
            evidence={"domain": "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS",
                      "bound_ms": 1, "financial_authority": False},
        ))


@pytest.mark.parametrize("change", [
    "list_unlisted_suffix", "duplicate_predecessor", "unordered_prefix",
])
def test_native_copy_requires_exact_original_prefix_before_opening_any_files(
    monkeypatch, change,
):
    existing = r21._audit()
    initial = copy.deepcopy(existing)
    if change == "list_unlisted_suffix":
        initial["native_prefix_files"][0]["path"] = "unlisted.exe"
    elif change == "duplicate_predecessor":
        initial["native_prefix_files"][1]["id"] = initial[
            "native_prefix_files"
        ][0]["id"]
    else:
        initial["native_prefix_files"][1]["path"], initial[
            "native_prefix_files"
        ][2]["path"] = initial["native_prefix_files"][2]["path"], initial[
            "native_prefix_files"
        ][1]["path"]
    expected = [row["path"] for row in existing["native_prefix_files"]]
    with pytest.raises(ValueError, match="ORIGINAL_FILE_PREFIX_CHANGED|ORIGINAL_NATIVE_ID_ALIAS"):
        r21._copy_missing_native(
            prepared={
                "names": expected,
                "dependencies": {}, "runtime": {},
            },
            existing=initial, tick=lambda: True,
        )
