"""Create-only R21 installation safety boundaries; no native installation."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts import atlas_r21_code_only_install as r21


def test_r21_installer_is_exact_frozen_content_with_no_finance_permissions():
    assert r21.SOURCE == "119dd8626da32e74bd7f86db9de1c1a8fd2c20ac"
    assert r21.EXPECTED_SOURCE_FILES == 1165
    assert r21.EXPECTED_DEPENDENCY_FILES == 9566
    assert r21.EXPECTED_FILES == 10731
    assert r21.EXPECTED_DIRECTORIES == 915
    assert r21.EXPECTED_BYTES == 265741912
    assert r21.TARGET.name == r21.SOURCE
    assert r21.ARCHIVE.is_relative_to(r21.ROOT)
    assert r21.RECEIPT.is_relative_to(r21.ROOT)
    assert r21.JOURNAL.is_relative_to(r21.ROOT)
    assert r21.APPROVAL.is_relative_to(r21.ROOT)
    assert "NO_FINANCIAL_START" in r21.SCOPE
    assert r21.source_hash() != r21.ARCHIVE_SHA


def test_no_install_without_a_distinct_pin(monkeypatch):
    monkeypatch.setattr(r21, "APPROVAL_PIN", None)
    with pytest.raises(ValueError, match="DISTINCT_SID_OPERATOR_DECISION_REQUIRED"):
        r21.approval_digest()
    with pytest.raises(ValueError, match="OPERATOR_APPROVAL_REQUIRED"):
        r21.install(clock=object(), approved=False)


def test_clock_only_exact_original_independent_utc_not_synthetic_report():
    with pytest.raises(ValueError, match="INDEPENDENT_NTP_CLOCK_REQUIRED"):
        r21.clock_required(SimpleNamespace(evidence={
            "bound_ms": 1, "financial_authority": False,
        }))


def test_native_receipt_and_pending_journal_are_distinct_immutable_domains():
    # This test must remain meaningful both before and after a genuine
    # completed installation. The old one-shot R21 attempt has been recovered
    # and selected; asserting its target does NOT exist would be stale.
    assert r21.RECEIPT != r21.JOURNAL
    assert r21.JOURNAL.suffixes == [".pending", ".jsonl"]
    assert r21.TARGET.name == r21.SOURCE
    assert str(r21.TARGET.parent).replace("\\", "/") == "D:/AtlasRuntime/releases"
    assert r21.RECEIPT.parent == r21.ROOT / "logs/diagnostics"
    assert r21.JOURNAL.parent == r21.RECEIPT.parent
    assert "NO_FINANCIAL_START" in r21.SCOPE


def test_original_source_is_separate_from_installer_script_commit():
    assert r21.SOURCE not in str(r21.APPROVAL)
    assert r21.SOURCE != r21.R20_SOURCE
    assert r21.ARCHIVE.name == "atlas-source.zip"
    assert r21.ARCHIVE_SHA != r21.INVENTORY_SHA
