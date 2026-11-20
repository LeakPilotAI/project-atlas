"""R23 source-only bundle must not be treated as a financial admission."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import atlas_r22_source_review as predecessor_review
from scripts import atlas_r23_source_review as r23


def test_r23_binds_the_exact_selected_original_r21_without_old_rewrite():
    assert r23.R21_NATIVE_REVISION == 20
    assert r23.R21_SOURCE == "119dd8626da32e74bd7f86db9de1c1a8fd2c20ac"
    assert r23.R21_ARTIFACT == (
        "02c5705e586f92415612c70309bd7051ad76629278f6c22905b056558b602b27"
    )
    assert "R23_SEPARATE_EXPLICIT_APPROVAL_NOT_CREATED" == r23.MISSING_OPERATOR_SCOPE
    assert r23.REVIEW.is_relative_to(r23.ROOT)
    assert r23.PACKAGE.is_relative_to(r23.REVIEW)
    assert r23.BASELINE == predecessor_review.BASELINE
    assert r23.REVIEW != predecessor_review.REVIEW
    assert r23.REVIEW != Path("D:/AtlasRuntime/releases")
    assert r23.SCHEMA == "ATLAS_R23_SELECTED_R21_CODE_ONLY_SOURCE_REVIEW_V1"


def test_r23_needs_all_source_safe_clock_and_legacy_stop_boundaries():
    assert {
        "scripts/observation_runtime/atlas_independent_ntp_clock.py",
        "scripts/observation_runtime/personal_version_safe_release_clock.py",
        "scripts/observation_runtime/atlas_r20_native_iex_latest_readonly.py",
        "scripts/observation_runtime/atlas_r22_precise_live_ntp_readonly.py",
        "backend/app/services/hyperliquid_forward_flat_paper_policy.py",
        "backend/app/services/hyperliquid_intrahour_stop_supervisor.py",
        "backend/app/services/unified_paper_runtime.py",
        "backend/app/services/personal_installed_stop_owner.py",
    } <= r23.REQUIRED_NEW_MODULES


def test_r23_real_predecessor_archive_pinned_not_a_self_issued_source():
    source = r23.source_baseline()
    assert len(source) == 1165
    assert "backend/app/services/unified_paper_runtime.py" in source
    assert "backend/app/services/hyperliquid_intrahour_stop_supervisor.py" not in source
    assert r23.R21_ARCHIVE_SHA == predecessor_review.R21_ARCHIVE_SHA


def test_r23_refuses_preexisting_package_root_before_any_native_checks(
    monkeypatch, tmp_path,
):
    root = tmp_path / "existing"
    root.mkdir()
    monkeypatch.setattr(r23, "REVIEW", root)
    with pytest.raises(ValueError, match="R23_FRESH_D_ONLY_REVIEW_REQUIRED"):
        r23.inspect()


def test_r23_refuses_drifted_tracked_source_before_install_or_package(
    monkeypatch,
):
    monkeypatch.setattr(r23, "selected_r21", lambda: {
        "artifact_digest": r23.R21_ARTIFACT,
    })
    monkeypatch.setattr(r23, "source_baseline", lambda: set())
    monkeypatch.setattr(
        r23, "git",
        lambda *args: (
            ["a" * 40] if args[0] == "rev-parse" else
            [" M backend/app/services/unified_paper_runtime.py"]
            if args[0] == "status" else []
        ),
    )
    with pytest.raises(ValueError, match="CLEAN_NEW_TRACKED_COMMIT_REQUIRED"):
        r23.review_selection()
