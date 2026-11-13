"""R20 installed source-resource closure and one-time code-only safety."""
from __future__ import annotations

import os
import sys

import pytest

from scripts import atlas_r20_code_only_install as installer
from scripts import atlas_r20_code_only_select as selector


@pytest.mark.skipif(sys.platform != "win32", reason="Windows original native R19")
def test_all_runtime_documents_in_frozen_native_file_plan():
    result = installer.frozen_prepared()
    assert len(result["runtime"]) == 1119
    assert len(result["dependencies"]) == 9566
    assert len(result["names"]) == 10685
    assert len(result["directories"])+1 == 915
    assert result["total"] == 265302217
    for name in (
        "docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json",
        "docs/ATLAS_TWO_ACCOUNT_V5_BASE_FEE_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json",
        "docs/ATLAS_UNIFIED_PAPER_COMMISSIONING_SCOPE_2026-11-07.json",
    ):
        assert name in result["runtime"]
    assert "docs/PERSONAL_NATIVE_COMPATIBILITY_OPERATOR_APPROVAL_V5.json" not in result["runtime"]
    assert result["verified"]["activation_approved"] is False


def test_code_only_install_and_selection_are_separately_inert_without_approval():
    assert installer.APPROVAL_PIN is None
    assert selector.APPROVAL_PIN is None
    assert not installer.APPROVAL.exists()
    assert not selector.APPROVAL.exists()
    assert installer.SOURCE == selector.SOURCE
    assert installer.SCOPE != selector.SCOPE
    assert installer.CLOCK_IDENTITY != selector.CLOCK_IDENTITY
    assert len(installer.source_hash()) == 64
    assert len(selector.approval_source_sha()) == 64
    assert installer.REVIEW_SCHEMA == "ATLAS_R20_COMPLETE_RUNTIME_DOC_CODE_ONLY_REVIEW_V1"
    assert installer.SOURCE == "d3c26d8189e4b18c0a88d0b4ebdec48b81838d1a"
    assert selector.RECORD_REVISION == 19
    assert not os.path.lexists(selector.SELECTION_ROOT / "r0019.json")
    assert not os.path.lexists(selector.SELECTION_ROOT / "r0019.pending")
    with pytest.raises(ValueError, match="OPERATOR_APPROVED"):
        installer.install(clock=None, approved=False)
    with pytest.raises(ValueError, match="EXACT_APPROVAL"):
        selector.select(clock=None, approved=False)
    with pytest.raises(ValueError, match="DISTINCT_NATIVE_INSTALL"):
        installer.approval_digest()
    with pytest.raises(ValueError, match="DISTINCT_USER_APPROVAL"):
        selector.approval_digest({})


def test_fake_clock_does_not_grant_code_only_release_admission():
    with pytest.raises(ValueError, match="ORIGINAL_TWO_PEER"):
        installer.clock_required(object())
    with pytest.raises(ValueError, match="ORIGINAL_TWO_PEER"):
        selector.clock_required(object())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows original native")
def test_selector_refuses_uninstalled_r20_or_pending_release():
    if not installer.TARGET.exists():
        with pytest.raises(ValueError, match="UNSELECTED_NATIVE_INSTALLED_CODE"):
            selector.candidate()
