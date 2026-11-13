"""Source-referenced runtime resource closure; no release/finance side effects."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.observation_runtime.native_runtime_document_closure import (
    EXPLICIT_UNAVAILABLE_OPERATOR_INPUT,
    SOURCE_ROOTS,
    NativeRuntimeDocumentClosureRefused,
    required_runtime_documents,
    tracked_selected,
)

ROOT = Path("D:/Work/Project Atlas")
PREVIOUS = ROOT / "logs/diagnostics/atlas-r19-source-only-20261112-r02/package/atlas-source.zip"
R19 = Path("D:/AtlasRuntime/releases/3de954bcfd8533bfaaf32f62745d912a24a71cfc")


@pytest.fixture(scope="module")
def actual_r19_selection():
    with zipfile.ZipFile(PREVIOUS) as archive:
        original = json.loads(archive.read("release-manifest.json"))
    assert original["head"] == "3de954bcfd8533bfaaf32f62745d912a24a71cfc"
    assert len(original["files"]) == 1091
    selection, tracked = tracked_selected(ROOT, original_source=(
        row["path"] for row in original["files"]
    ))
    return selection, tracked


def test_selected_r19_missing_real_runtime_policy_assets_before_paper(
        actual_r19_selection):
    selected, tracked = actual_r19_selection
    report = required_runtime_documents(
        ROOT, selected={p for p in selected if p.startswith(SOURCE_ROOTS)},
        tracked=tracked)
    assets = report["tracked_runtime_document_paths"]
    assert report["tracked_runtime_document_count"] >= 20
    assert report["total_runtime_document_bytes"] > 10_000
    assert ("docs/ATLAS_TWO_ACCOUNT_V5_BASE_FEE_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json"
            in assets)
    assert "docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json" in assets
    assert EXPLICIT_UNAVAILABLE_OPERATOR_INPUT not in assets
    assert report["missing_independent_operator_approval_input"] == [
        EXPLICIT_UNAVAILABLE_OPERATOR_INPUT
    ]
    assert report["missing_operator_input_must_not_be_packaged"] is True
    assert report["paper_start_authorized"] is False
    assert report["financial_accounts_created"] is False
    assert report["live_orders_authorized"] is False
    assert all((ROOT / path).is_file() for path in assets)
    assert all(not (R19 / path).exists() for path in assets)


def test_invalid_scope_never_implicitly_adds_operator_approval(tmp_path):
    file = tmp_path / "scripts/test.py"
    file.parent.mkdir()
    file.write_text(
        'RESOURCE = "docs/LOCAL_OPERATOR_APPROVED_BY_CHAT.json"\n',
        encoding="utf-8")
    with pytest.raises(NativeRuntimeDocumentClosureRefused,
                       match="UNTRACKED_NEW_REQUIRED"):
        required_runtime_documents(tmp_path,
                                   selected={"scripts/test.py"},
                                   tracked={"scripts/test.py"})


def test_genuine_missing_operator_input_is_an_absence_not_permission(tmp_path):
    file = tmp_path / "scripts/test.py"
    file.parent.mkdir()
    file.write_text(
        f'RESOURCE = "{EXPLICIT_UNAVAILABLE_OPERATOR_INPUT}"\n',
        encoding="utf-8")
    report = required_runtime_documents(
        tmp_path, selected={"scripts/test.py"}, tracked={"scripts/test.py"})
    assert report["tracked_runtime_document_paths"] == []
    assert report["missing_independent_operator_approval_input"] == [
        EXPLICIT_UNAVAILABLE_OPERATOR_INPUT]
    assert not (tmp_path / EXPLICIT_UNAVAILABLE_OPERATOR_INPUT).exists()


@pytest.mark.parametrize("invalid", [
    "D:/outside/file.py",
    "docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json",
    "scripts/../secrets.py",
    "scripts/allow.py:bad",
])
def test_non_runtime_source_paths_refused_without_finance(tmp_path, invalid):
    with pytest.raises(NativeRuntimeDocumentClosureRefused):
        required_runtime_documents(tmp_path, selected={invalid}, tracked={invalid})


def test_missing_physical_required_tracked_document_refused(tmp_path):
    file = tmp_path / "scripts/test.py"
    file.parent.mkdir()
    file.write_text('RESOURCE="docs/POLICY.json"', encoding="utf-8")
    with pytest.raises((OSError, ValueError)):
        required_runtime_documents(
            tmp_path, selected={"scripts/test.py"},
            tracked={"scripts/test.py", "docs/POLICY.json"})


def test_exact_required_tracked_document_allowed_but_never_accepted_financial(
        tmp_path):
    script = tmp_path / "scripts/test.py"
    script.parent.mkdir()
    script.write_text('POLICY = "docs/ORIGINAL.json"', encoding="utf-8")
    policy = tmp_path / "docs/ORIGINAL.json"
    policy.parent.mkdir()
    policy.write_text('{"financial_authority":false}', encoding="utf-8")
    report = required_runtime_documents(
        tmp_path, selected={"scripts/test.py"},
        tracked={"scripts/test.py", "docs/ORIGINAL.json"})
    assert report["tracked_runtime_document_paths"] == ["docs/ORIGINAL.json"]
    assert report["financial_accounts_created"] is False
    assert report["paper_start_authorized"] is False
