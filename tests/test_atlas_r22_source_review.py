"""R22 code-only candidate is pinned to genuine native selected R21."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import atlas_r22_source_review as r22


def test_r22_requires_selected_immutable_original_r21_predecessor():
    assert r22.R21_NATIVE_REVISION == 20
    assert r22.R21_SOURCE == "119dd8626da32e74bd7f86db9de1c1a8fd2c20ac"
    assert r22.R21_ARTIFACT == (
        "02c5705e586f92415612c70309bd7051ad76629278f6c22905b056558b602b27"
    )
    assert "R22_SEPARATE_EXPLICIT_APPROVAL_NOT_CREATED" == r22.MISSING_OPERATOR_SCOPE
    assert r22.REVIEW.is_relative_to(r22.ROOT)
    assert r22.PACKAGE.is_relative_to(r22.REVIEW)
    assert r22.BASELINE.is_relative_to(r22.ROOT)
    assert set(r22.REQUIRED_NEW_MODULES) == {
        "scripts/observation_runtime/atlas_independent_ntp_clock.py",
        "scripts/observation_runtime/personal_version_safe_release_clock.py",
        "scripts/observation_runtime/atlas_r20_native_iex_latest_readonly.py",
        "scripts/observation_runtime/atlas_r22_precise_live_ntp_readonly.py",
    }


def test_existing_r21_original_frozen_archive_is_exact_predecessor():
    rows = r22.source_baseline()
    assert len(rows) == 1165
    assert "scripts/observation_runtime/atlas_r20_native_iex_latest_readonly.py" in rows
    assert "scripts/observation_runtime/atlas_r22_precise_live_ntp_readonly.py" not in rows
    assert "scripts/atlas_r22_source_review.py" not in rows


@pytest.mark.parametrize("already_exists", [True, False])
def test_inspect_refuses_existing_output_or_untrusted_current_source(
    monkeypatch, tmp_path, already_exists,
):
    # This is a disposable test directory, never an installation target.
    review = tmp_path / "review"
    if already_exists:
        review.mkdir()
        monkeypatch.setattr(r22, "REVIEW", review)
        with pytest.raises(ValueError, match="FRESH_D_ONLY_REVIEW"):
            r22.inspect()
    else:
        monkeypatch.setattr(r22, "selected_r21", lambda: {
            "artifact_digest": r22.R21_ARTIFACT,
        })
        monkeypatch.setattr(r22, "source_baseline", lambda: set())
        monkeypatch.setattr(
            r22, "git",
            lambda *args: (
                ["0" * 40] if args[0] == "rev-parse" else
                [" M scripts/foreign.py"] if args[0] == "status" else
                []
            ),
        )
        with pytest.raises(ValueError, match="CLEAN_NEW_TRACKED_COMMIT"):
            r22.review_selection()


def test_source_review_never_uses_old_selected_release_as_new_release():
    from scripts.atlas_r21_source_review import R20_SELECTION_REVISION

    assert R20_SELECTION_REVISION == 19
    assert r22.R21_NATIVE_REVISION == 20
    assert r22.R21_SOURCE != "d3c26d8189e4b18c0a88d0b4ebdec48b81838d1a"
    assert r22.REVIEW != Path("D:/AtlasRuntime/releases")
