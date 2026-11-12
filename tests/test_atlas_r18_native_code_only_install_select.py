"""R18 code-only native release admission: never financial or automatic.

Read-only tests with original selected R17, no selected-state mutation or
release creation. Also prove exact user decision validator refuses fabricated
scopes before creating any filesystem state.
"""
from __future__ import annotations

import os
import sys

import pytest

from scripts import atlas_r18_native_code_only_install as installer
from scripts import atlas_r18_native_code_only_select as selector


@pytest.mark.skipif(sys.platform != "win32", reason="Windows original native selector")
def test_frozen_review_and_original_release_are_same_no_install():
    receipt = installer.frozen_prepared()
    assert len(receipt["runtime"]) == installer.EXPECTED_SOURCE_FILES
    assert len(receipt["dependencies"]) == installer.EXPECTED_DEPENDENCY_FILES
    assert len(receipt["names"]) == installer.EXPECTED_FILES
    assert receipt["total"] == installer.EXPECTED_BYTES
    assert installer.original_accounts() is True
    assert installer.original_predecessor()["release"] == installer.R17_SOURCE
    assert not os.path.lexists(installer.TARGET)
    assert not os.path.lexists(installer.JOURNAL)
    assert not os.path.lexists(installer.RECEIPT)
    assert not os.path.lexists(selector.SELECTION_ROOT / "r0017.json")
    assert not os.path.lexists(selector.SELECTION_ROOT / "r0017.pending")


def test_no_financial_ports_and_source_hashing_has_exact_original_scope():
    for module in (installer, selector):
        assert not hasattr(module, "paper_start")
        assert not hasattr(module, "submit_order")
        assert not hasattr(module, "create_financial_account")
    assert len(installer.source_hash()) == 64
    assert len(selector.approval_source_sha()) == 64
    assert installer.SOURCE == selector.SOURCE
    assert installer.SCOPE != selector.SCOPE
    assert installer.CLOCK_IDENTITY != selector.CLOCK_IDENTITY
    assert installer.EXPECTED_FILES == selector.EXPECTED_FILES


def test_install_and_selection_require_distinct_one_shot_approvals():
    with pytest.raises(ValueError, match="EXPLICIT_EXECUTION|OPERATOR_ONE_TIME"):
        installer.install(clock=None, approved=False)
    with pytest.raises(ValueError, match="EXACT_EXPLICIT"):
        selector.select(clock=None, approved=False)
    if installer.APPROVAL_PIN is None:
        with pytest.raises(ValueError, match="INDEPENDENT_USER_APPROVAL"):
            installer.approval_digest()
    if selector.APPROVAL_PIN is None:
        with pytest.raises(ValueError, match="DISTINCT_USER_APPROVAL"):
            selector.approval_digest({})


@pytest.mark.skipif(sys.platform != "win32", reason="Windows")
def test_selection_refuses_code_only_candidate_before_genuine_install():
    if not installer.TARGET.exists():
        with pytest.raises(ValueError, match="INSTALLED_SOURCE_REQUIRED"):
            selector.candidate()
