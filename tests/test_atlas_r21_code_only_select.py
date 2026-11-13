"""Exact R21 source-only native selector safety, no financial effects."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts import atlas_r21_code_only_select as r21


def test_one_time_original_selector_requires_distinct_code_only_approval():
    assert r21.RECORD_REVISION == 20
    assert "R21_CODE_ONLY_NATIVE_SELECTION_NO_FINANCIAL_START" in r21.SCOPE
    assert r21.SOURCE == "119dd8626da32e74bd7f86db9de1c1a8fd2c20ac"
    assert r21.EXPECTED_FILES == 10731
    assert r21.EXPECTED_DIRECTORIES == 915
    assert str(r21.APPROVAL).replace("\\", "/").startswith(
        "D:/Work/Project Atlas/logs/diagnostics/"
    )
    assert r21.source_hash() != r21.ARCHIVE_SHA
    assert r21.APPROVAL != r21.RECEIPT
    assert r21.SELECTION_ACTION == b"ATLAS_R21_NATIVE_CODE_ONLY_REV20_SELECTION_V1"


def test_no_source_selection_from_a_missing_or_foreign_approval(monkeypatch):
    monkeypatch.setattr(r21, "APPROVAL_PIN", None)
    with pytest.raises(ValueError, match="DISTINCT_SELECTION_USER_APPROVAL"):
        r21.approval_digest({})
    with pytest.raises(ValueError, match="SELECTED_OPERATOR_APPROVAL"):
        r21.select(clock=object(), approved=False)


def test_no_selected_native_release_from_faked_clock_report():
    with pytest.raises(ValueError, match="ORIGINAL_TWO_PEER_NTP_REQUIRED"):
        r21.clock_required(SimpleNamespace(evidence={
            "domain": "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS",
            "bound_ms": 1,
            "financial_authority": False,
        }))


def test_original_candidate_requires_real_installed_release_root(monkeypatch):
    monkeypatch.setattr(
        r21, "original_selected_r20",
        lambda: {"release": "d3c26d8189e4b18c0a88d0b4ebdec48b81838d1a"},
    )
    monkeypatch.setattr(r21, "original_accounts", lambda: True)
    monkeypatch.setattr(r21, "TARGET", r21.ROOT / "no-such-r21-native-release")
    with pytest.raises(ValueError, match="UNSELECTED_CODE_INSTALL_REQUIRED"):
        r21.candidate()


def test_native_selector_only_appends_revision_20_never_financial_receipt():
    assert r21.RECORD_REVISION != 19
    assert r21.SCOPE.endswith("NO_FINANCIAL_START")
    assert r21.SELECTION_ROOT.name == "selection"
