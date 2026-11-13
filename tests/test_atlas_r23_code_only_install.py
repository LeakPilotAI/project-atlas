"""R23 original native one-shot installer must stay refused without consent.

The real read-only 10,763-file frozen plan is checked by separate --inspect
execution on the authorized Windows desktop; these tests never copy a file.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from scripts import atlas_r23_code_only_install as inst
from scripts import atlas_r23_source_review as review


def test_r23_installer_exactly_bound_to_existing_source_archive_and_r21():
    assert inst.SOURCE == "96c6b85f76368a69bfd035cbcf3eb05776c21525"
    assert inst.ARCHIVE_SHA == (
        "8ffd8a429a3a2831a8058e39a234c1b7a8db2caa0e3d4f4bab41a6792021a53e"
    )
    assert inst.REVIEW_SHA == (
        "c97a1e8f44308e061d20c2979e6de5aed62d9ec206cbedc263749abdca2b0c41"
    )
    assert inst.INVENTORY_SHA == (
        "0d4228333d089094248ea2d871204a630dd41411efa6627006600706d1468e5f"
    )
    assert inst.R21_SOURCE == review.R21_SOURCE
    assert inst.REVIEW == review.REVIEW
    assert inst.REVIEW_FILE.is_relative_to(inst.ROOT)
    assert inst.RECEIPT.is_relative_to(inst.ROOT)
    assert inst.APPROVAL.is_relative_to(inst.ROOT)
    assert inst.SCOPE == "APPROVE_ONE_R23_CODE_ONLY_NATIVE_INSTALL_NO_FINANCIAL_START"
    assert inst.DECISION_SCHEMA == "ATLAS_R23_CODE_ONLY_INSTALL_USER_DECISION_V1"
    assert inst.EXPECTED_SOURCE_FILES == 1197
    assert inst.EXPECTED_DEPENDENCY_FILES == 9566
    assert inst.EXPECTED_FILES == 10763
    assert inst.EXPECTED_DIRECTORIES == 915
    assert inst.EXPECTED_BYTES == 265991191
    assert inst.APPROVAL_PIN is None


def test_installer_hash_binds_actual_exact_file_not_a_historical_approval():
    raw = Path(inst.__file__).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == inst.source_hash()
    assert re.fullmatch("[0-9a-f]{64}", inst.source_hash())


def test_no_approval_pin_is_terminal_before_files_or_public_ntp(monkeypatch):
    monkeypatch.setattr(
        inst, "frozen_prepared",
        lambda: pytest.fail("Must never prepare actual code in missing-approval mode"),
    )
    monkeypatch.setattr(
        inst, "IndependentNtpClock",
        lambda *args, **kwargs: pytest.fail("No public NTP before local approval"),
    )
    with pytest.raises(ValueError, match="DISTINCT_SID_OPERATOR_DECISION_REQUIRED"):
        inst.main(["--execute-approved-code-only", "--confirm-scope", inst.SCOPE])
    assert not inst.TARGET.exists()
    assert not inst.RECEIPT.exists()
    assert not inst.JOURNAL.exists()


@pytest.mark.parametrize("supplied", ("", "YES", "APPROVE_ALL", "INSTALL_AND_TRADE"))
def test_no_short_or_broad_operator_scope_can_invoke_native_install(supplied):
    with pytest.raises(ValueError, match="EXACT_OPERATOR_SCOPE_FLAG_REQUIRED"):
        inst.main(["--execute-approved-code-only", "--confirm-scope", supplied])


def test_test_only_boolean_cannot_substitute_for_separate_operator_approval():
    with pytest.raises(ValueError, match="DISTINCT_SID_OPERATOR_DECISION_REQUIRED"):
        inst.install(clock=object(), approved=True)
    with pytest.raises(ValueError, match="INSTALL_OPERATOR_APPROVAL_REQUIRED"):
        inst.install(clock=object(), approved=False)


def test_original_r21_predecessor_cannot_be_relabelled(monkeypatch):
    monkeypatch.setattr(inst, "selected_r21", lambda: {"release": "a" * 40})
    with pytest.raises(ValueError, match="SELECTED_ORIGINAL_R21_CHANGED"):
        inst.original_selected_r21()


def test_installer_has_no_preinstalled_or_financial_runtime_effect():
    assert inst.TARGET == Path("D:/AtlasRuntime/releases") / inst.SOURCE
    assert inst.SOURCE != review.R21_SOURCE
    assert inst.APPROVAL_PIN is None
