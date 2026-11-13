"""Source-only successor packaging contracts; never select/install/approve."""
from __future__ import annotations

import copy

import pytest

from scripts import atlas_r21_source_review as r21


def test_required_next_source_components_are_explicit_and_not_trading_rights():
    assert r21.SCHEMA == "ATLAS_R21_SELECTED_R20_CODE_ONLY_SOURCE_REVIEW_V1"
    assert r21.R20_SELECTION_REVISION == 19
    assert "quality_dips_current_producer.py" in str(r21.REQUIRED_NEW_MODULES)
    assert "personal_selected_qd_sec_watch_issuer.py" in str(r21.REQUIRED_NEW_MODULES)
    assert "personal_source_epoch_readback.py" in str(r21.REQUIRED_NEW_MODULES)
    assert "atlas_selected_paper_prelaunch_evidence.py" in str(
        r21.REQUIRED_NEW_MODULES
    )
    assert str(r21.ROOT).replace("\\", "/").endswith("D:/Work/Project Atlas")
    assert str(r21.REVIEW).replace("\\", "/").startswith(
        "D:/Work/Project Atlas/logs/diagnostics/"
    )
    assert "EXPLICIT_APPROVAL_NOT_CREATED" in r21.MISSING_OPERATOR_SCOPE
    assert not r21.REVIEW.samefile(r21.PACKAGE) if r21.PACKAGE.exists() else True


def test_original_r20_source_archive_is_frozen_and_all_tracked_only():
    original = r21.original_baseline()
    assert len(original) == 1119
    assert r21.REQUIRED_NEW_MODULES - original
    assert "scripts/observation_runtime/personal_source_epoch_readback.py" not in original
    assert "scripts/observation_runtime/personal_selected_qd_sec_watch_issuer.py" not in original
    assert "scripts/observation_runtime/atlas_selected_paper_prelaunch_evidence.py" not in original


def test_existing_review_location_refused_before_original_native_reader(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(r21, "REVIEW", tmp_path)
    def impossible(*args, **kwargs):
        raise AssertionError("original installed release should not be examined")
    monkeypatch.setattr(r21, "review_selection", impossible)
    with pytest.raises(ValueError, match="FRESH_D_ONLY_REVIEW"):
        r21.inspect()


def test_importing_r21_plan_does_not_create_release_selection_or_activation():
    assert r21.R20_SOURCE != ""
    assert r21.REQUIRED_NEW_MODULES
    assert not any("activation.json" in x or "alpaca.env" in x
                   for x in r21.REQUIRED_NEW_MODULES)
    assert copy.deepcopy(r21.REQUIRED_NEW_MODULES) == r21.REQUIRED_NEW_MODULES
