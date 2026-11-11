"""Immutable R16 code-only SOURCE candidate: offline readback, no install.

The frozen source commit predates this audit test and a roadmap-only
checkpoint. Missing diagnostic artifacts are not recreated or adopted.
"""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_release_candidate import verify_candidate
from scripts.native_install_plan import prepare_install_inputs
from scripts.atlas_r14_low_impact_installer import (
    DEPENDENCY,
    DEPENDENCY_RECEIPT_SHA256,
    DEPENDENCY_INVENTORY_SHA256,
)

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/"logs/diagnostics/atlas-r16-source-only-20261111-r01"
R15=ROOT/"logs/diagnostics/atlas-r15-source-only-20261110-r01"
SOURCE="cadb3b5a163b31f9ee7bda32453a5983e809ccc0"
ARCHIVE_SHA="397f6722feb2c2483c3f262e87fae6110d9ba3c8d3f990c62162f090a70afd0a"
INVENTORY="c4b72c58867cbb0a49a2126bae5527ed9b004807bb46cda272c75219c321e341"
ORIGINAL=960
NEW=23
TOTAL=983
DEPENDENCIES=9566
NATIVE_FILES=10549
NATIVE_DIRECTORIES=912
NATIVE_BYTES=263892205


@pytest.fixture(scope="module")
def frozen():
    names=("source-selection.json","source-freeze-review.json",
           "package/release-manifest.json","package/atlas-source.zip")
    if any(not (FROZEN/name).is_file() for name in names):
        pytest.skip("R16 source-only frozen diagnostic not mounted; never fabricate it")
    review=json.loads((FROZEN/"source-freeze-review.json").read_text(encoding="utf-8"))
    selection=json.loads((FROZEN/"source-selection.json").read_text(encoding="utf-8"))
    manifest=json.loads((FROZEN/"package/release-manifest.json").read_text(encoding="utf-8"))
    return review,selection,manifest


def test_sha_pinned_create_only_archive_is_verified_and_never_installed(frozen):
    review,selection,manifest=frozen
    assert review["schema"]=="ATLAS_R16_FROZEN_CODE_ONLY_SOURCE_CANDIDATE_V1"
    assert review["status"]=="TRACKED_SOURCE_AND_DEPENDENCY_PLAN_VERIFIED_NOT_INSTALL_OR_SELECTION_AUTHORIZATION"
    assert review["source_commit"]==selection["source_commit"]==manifest["head"]==SOURCE
    assert review["source_archive_sha256"]==ARCHIVE_SHA
    assert review["selected_source_inventory_sha256"]==INVENTORY
    assert review["source_files"]==TOTAL
    assert manifest["activation_approved"] is False
    assert all(row["git_status"]=="tracked" for row in manifest["files"])
    actual=verify_candidate(FROZEN/"package/atlas-source.zip",expected_sha256=ARCHIVE_SHA)
    assert actual["source_files"]==TOTAL
    assert actual["activation_approved"] is False


def test_source_is_original_reviewed_r15_selection_plus_23_tracked_scripts(frozen):
    review,selection,manifest=frozen
    baseline=json.loads((R15/"package/release-manifest.json").read_text(encoding="utf-8"))
    original={row["path"] for row in baseline["files"]}
    selected={row["path"] for row in selection["files"]}
    assert len(original)==ORIGINAL and len(selected)==TOTAL
    assert original <= selected
    added=selected-original
    assert len(added)==NEW
    assert all(path.startswith("scripts/") for path in added)
    assert "scripts/observation_runtime/personal_r15_owned_job_activation.py" in added
    assert "scripts/observation_runtime/alpaca_iex_basic_subscription_cursor.py" in added
    assert "scripts/atlas_r15_code_only_installer.py" in added
    assert selected=={row["path"] for row in manifest["files"]}
    rows=json.dumps(selection["files"],sort_keys=True,separators=(",",":")).encode()
    assert hashlib.sha256(rows).hexdigest()==INVENTORY
    assert selection["inventory_digest"]==INVENTORY
    assert selection["schema"]=="ATLAS_SOURCE_SELECTION_V1"
    assert review["original_source_paths_preserved"]==ORIGINAL
    assert review["new_tracked_runtime_paths_added"]==NEW


def test_native_dependency_plan_contains_no_financial_permission(frozen):
    review,selection,manifest=frozen
    raw=DEPENDENCY.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==DEPENDENCY_RECEIPT_SHA256
    planned=prepare_install_inputs(
        archive=FROZEN/"package/atlas-source.zip",
        archive_sha256=ARCHIVE_SHA,source_commit=SOURCE,
        dependency_receipt=json.loads(raw),
        dependency_digest=DEPENDENCY_INVENTORY_SHA256,
        inventory_digest=INVENTORY,require_tracked=True)
    assert len(planned["runtime"])==TOTAL
    assert len(planned["dependencies"])==DEPENDENCIES
    assert len(planned["names"])==NATIVE_FILES
    assert len(planned["directories"])+1==NATIVE_DIRECTORIES
    assert planned["total"]==NATIVE_BYTES
    assert review["native_files_planned"]==NATIVE_FILES
    assert review["native_bytes_planned"]==NATIVE_BYTES
    assert review["dependency_receipt_sha256"]==DEPENDENCY_RECEIPT_SHA256
    assert review["dependency_file_inventory_sha256"]==DEPENDENCY_INVENTORY_SHA256


def test_frozen_review_contains_no_approval_or_provider_access(frozen):
    review,selection,manifest=frozen
    assert review["selected_r15_unchanged"] is True
    assert review["selected_r15_selection_record_sha256"]==(
        "b729ff718fc41d90942400db15fc17e1bcf0cac6ae9ccf18e0492e9c6c4f2eb2")
    assert review["financial_operating_gates_accepted"]==0
    for field in (
        "source_installation_authorized","native_installation_executed",
        "native_release_selection_authorized","financial_authority",
        "operator_account_inception","paper_orders_authorized",
        "live_trading_authorized","market_data_provider_requested"):
        assert review[field] is False
    assert review["proposed_create_only_target"]==(
        "D:\\AtlasRuntime\\releases\\"+SOURCE)
