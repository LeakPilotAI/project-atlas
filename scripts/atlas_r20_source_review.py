"""R20 create-only corrected self-contained native source review.

Successor of genuinely selected Windows R19, not historical R18.
Packages source plus the 25+ pinned tracked runtime policy/history documents
omitted by R19. Never issues operator approval, installs/selects a release,
opens financial accounts, starts PAPER or interacts with providers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path

from scripts import release_selection
from scripts.atlas_r14_low_impact_installer import (
    DEPENDENCY,
    DEPENDENCY_INVENTORY_SHA256,
    DEPENDENCY_RECEIPT_SHA256,
)
from scripts.build_release_candidate import (
    ROOTS,
    build_selected,
    source_bytes,
    source_path,
    verify_candidate,
    windows_namespace,
)
from scripts.native_install_plan import prepare_install_inputs
from scripts.observation_runtime.native_runtime_document_closure import (
    EXPLICIT_UNAVAILABLE_OPERATOR_INPUT,
    SOURCE_ROOTS,
    required_runtime_documents,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    SELECTOR_NATIVE,
)
from scripts.release_selection import NativeInstalledReleaseVerifier
from scripts.release_selection_store import NativeSelectionStore

ROOT = Path("D:/Work/Project Atlas")
PARENT = ROOT / "logs/diagnostics"
REVIEW = PARENT / "atlas-r20-source-only-20261112-r01"
PACKAGE = REVIEW / "package"
BASELINE = PARENT / "atlas-r19-source-only-20261112-r02/package/atlas-source.zip"
R19_ARCHIVE_SHA = "55d7da9e24b1c20fe1b9a72ea25efb2d6ce0bdd00199f2c60cb8c94ae55d6ed8"
R19_SOURCE = "3de954bcfd8533bfaaf32f62745d912a24a71cfc"
R19_ARTIFACT = "102c94fff81035bb714200cef666784061256cb963281dab7dfa145d75b19876"
R19_HEAD = "45a0f20c567aa185743d4c90f260aa2feafc5cc3f09080034d6cd7bcb09d6243"
SCHEMA = "ATLAS_R20_COMPLETE_RUNTIME_DOC_CODE_ONLY_REVIEW_V1"
PINNED_V5_HISTORICAL_BUNDLE = (
    "docs/ATLAS_TWO_ACCOUNT_V5_BASE_FEE_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json"
)
V5_ORIGINAL_SHA = "d4b439d8b7c4ea8d51cd3a003f1cf68cc22f008b500b4c58acdf357af0cf6800"
PINNED_POLICY = "docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json"
ALLOWED_EXTENSIONS = frozenset((
    ".py", ".ps1", ".psm1", ".js", ".cjs", ".mjs",
    ".html", ".css", ".json", ".md",
))


def git(*args):
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).splitlines()


def selected_predecessor():
    """Live native chain AND original immutable selected R19 file readback."""
    store = NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection",
        native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():
            records = store.records()
            if (len(records) != 18 or records[-1].get("revision") != 18
                    or release_selection.digest(records[-1]) != R19_HEAD):
                raise ValueError("R20_GENUINE_NATIVE_REVISION18_HEAD_REQUIRED")
            spec = release_selection.validate_spec(
                records[-1].get("selected"), "WINDOWS_LOCAL")
            if (spec["release"] != R19_SOURCE
                    or spec["artifact_digest"] != R19_ARTIFACT):
                raise ValueError("R20_GENUINE_SELECTED_R19_ARTIFACT_REQUIRED")
            with NativeInstalledReleaseVerifier().open(spec) as readback:
                if (readback.get("source_commit") != R19_SOURCE
                        or readback.get("artifact_digest") != R19_ARTIFACT
                        or any(readback.get(k) is not False for k in (
                            "selected", "financial_effects",
                            "provider_connections", "operational_acceptance"))):
                    raise ValueError("R20_GENUINE_R19_NATIVE_INSTALLED_READBACK_REQUIRED")
    finally:
        store.close()
    roots = inspect_two_lane_native_roots()
    if (roots["native_root_total"] != 12
            or roots["native_root_ids_verified"] != 12
            or roots["all_twelve_distinct_and_empty"] is not True):
        raise ValueError("R20_ORIGINAL_FINANCIAL_ROOTS_MUST_STAY_EMPTY")
    verify_candidate(BASELINE, expected_sha256=R19_ARCHIVE_SHA)
    with zipfile.ZipFile(BASELINE) as archive:
        baseline = json.loads(archive.read("release-manifest.json"))
    if (baseline.get("head") != R19_SOURCE
            or baseline.get("contract") != "R7E46O_SOURCE_V1"
            or len(baseline.get("files", [])) != 1091
            or any(row.get("git_status") != "tracked"
                   for row in baseline["files"])):
        raise ValueError("R20_EXACT_FROZEN_R19_SOURCE_BASELINE_REQUIRED")
    return {row["path"] for row in baseline["files"]}


def source_selection():
    original = selected_predecessor()
    head = git("rev-parse", "HEAD")[0]
    if not re.fullmatch("[0-9a-f]{40}", head) or head == R19_SOURCE:
        raise ValueError("R20_NEW_COMMITTED_REVIEW_SOURCE_REQUIRED")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("R20_TRACKED_SOURCE_MUST_BE_COMMITTED_AND_CLEAN")
    subprocess.check_call(
        ["git", "merge-base", "--is-ancestor", R19_SOURCE, head],
        cwd=ROOT, stdout=subprocess.DEVNULL)
    changed = set(git(
        "diff", "--name-only", R19_SOURCE, head, "--",
        "backend/app/", "scripts/", "tests/", "docs/", "frontend/offline/"))
    tracked = set(git(
        "ls-files", "--", "backend/app/", "scripts/", "tests/", "docs/",
        "frontend/offline/"))
    code = original | changed
    if (not code <= tracked or not changed
            or any(not name.startswith(ROOTS) for name in code)
            or any(Path(name).suffix.lower() not in ALLOWED_EXTENSIONS
                   for name in changed - original)):
        raise ValueError("R20_TRACKED_SOURCE_AND_EXTENSION_BOUNDS_REQUIRED")
    closure = required_runtime_documents(
        ROOT, selected={f for f in code if f.startswith(SOURCE_ROOTS)},
        tracked=tracked)
    if (closure["missing_independent_operator_approval_input"]
            != [EXPLICIT_UNAVAILABLE_OPERATOR_INPUT]
            or closure["missing_operator_input_must_not_be_packaged"] is not True
            or PINNED_V5_HISTORICAL_BUNDLE not in closure["tracked_runtime_document_paths"]
            or PINNED_POLICY not in closure["tracked_runtime_document_paths"]
            or not 20 <= closure["tracked_runtime_document_count"] <= 100
            or EXPLICIT_UNAVAILABLE_OPERATOR_INPUT in code):
        raise ValueError("R20_RUNTIME_DOCS_AND_EXPLICIT_MISSING_OPERATOR_MUST_REMAIN_DISTINCT")
    if hashlib.sha256(source_bytes(
            ROOT, PINNED_V5_HISTORICAL_BUNDLE,
            maximum_bytes=32_768)).hexdigest() != V5_ORIGINAL_SHA:
        raise ValueError("R20_ORIGINAL_HISTORICAL_ACCOUNT_BUNDLE_PIN_CHANGED")
    selected = code | set(closure["tracked_runtime_document_paths"])
    if not 1100 <= len(selected) <= 2048 or not selected <= tracked:
        raise ValueError("R20_COMPLETE_SOURCE_AND_RUNTIME_DOC_BOUNDS_REQUIRED")
    windows_namespace(selected)
    rows = []
    total = 0
    for name in sorted(selected):
        source_path(ROOT, name)
        content = source_bytes(ROOT, name, maximum_bytes=16*1024*1024)
        total += len(content)
        if total > 128*1024*1024:
            raise ValueError("R20_SOURCE_BYTE_LIMIT")
        rows.append({
            "path": name, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    digest = hashlib.sha256(json.dumps(
        rows, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    selection = {
        "schema": "ATLAS_SOURCE_SELECTION_V1",
        "source_commit": head,
        "inventory_digest": digest, "files": rows,
    }
    summary = {
        "predecessor_revision": 18,
        "predecessor_source": R19_SOURCE,
        "base_source_files": len(original),
        "changed_tracked_paths_since_r19": len(changed),
        "runtime_document_count": closure["tracked_runtime_document_count"],
        "runtime_document_bytes": closure["total_runtime_document_bytes"],
        "runtime_documents_bundled": closure["tracked_runtime_document_paths"],
        "required_operator_approval_input_is_missing": True,
        "source_files": len(rows), "source_bytes": total,
    }
    return selection, summary


def inspect():
    if (REVIEW.exists() or REVIEW.is_symlink() or REVIEW.is_junction()
            or not PARENT.is_dir() or PARENT.is_symlink() or PARENT.is_junction()):
        raise ValueError("R20_CREATE_ONLY_FRESH_REVIEW_DESTINATION_REQUIRED")
    selection, summary = source_selection()
    target = Path("D:/AtlasRuntime/releases") / selection["source_commit"]
    if os.path.lexists(target):
        raise ValueError("R20_NATIVE_TARGET_MUST_BE_UNUSED")
    raw = source_bytes(
        ROOT, DEPENDENCY.relative_to(ROOT).as_posix(),
        maximum_bytes=16*1024*1024)
    if hashlib.sha256(raw).hexdigest() != DEPENDENCY_RECEIPT_SHA256:
        raise ValueError("R20_PINNED_PYTHON_DEPENDENCIES_CHANGED")
    return selection, summary, json.loads(raw), target


def execute_source_only():
    selection, summary, dependencies, target = inspect()
    REVIEW.mkdir(parents=False, exist_ok=False)
    (REVIEW / "selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True), encoding="utf-8")
    archive_sha = build_selected(
        PACKAGE, selection=selection,
        expected_inventory_sha256=selection["inventory_digest"])
    prepared = prepare_install_inputs(
        archive=PACKAGE / "atlas-source.zip", archive_sha256=archive_sha,
        source_commit=selection["source_commit"],
        inventory_digest=selection["inventory_digest"],
        dependency_receipt=dependencies,
        dependency_digest=DEPENDENCY_INVENTORY_SHA256, require_tracked=True)
    if (len(prepared["runtime"]) != summary["source_files"]
            or len(prepared["dependencies"]) != 9566
            or prepared["verified"].get("activation_approved") is not False
            or len(prepared["names"]) > 12000
            or prepared["total"] > 512*1024*1024):
        raise ValueError("R20_COMPLETE_CODE_RUNTIME_PLAN_REFUSED")
    document_paths = set(summary["runtime_documents_bundled"])
    if not document_paths <= set(prepared["runtime"]):
        raise ValueError("R20_RUNTIME_DOCUMENTS_NOT_INCLUDED_IN_NATIVE_FILE_PLAN")
    review = {
        "schema": SCHEMA,
        "status": "R20_COMPLETE_RUNTIME_DOC_CODE_ONLY_VERIFIED_NOT_INSTALLED",
        "source_commit": selection["source_commit"],
        "selected_r19_source": R19_SOURCE,
        "selected_r19_native_head": R19_HEAD,
        "source_inventory_sha256": selection["inventory_digest"],
        "source_archive_sha256": archive_sha,
        "pinned_dependency_receipt_sha256": DEPENDENCY_RECEIPT_SHA256,
        "pinned_dependency_inventory_sha256": DEPENDENCY_INVENTORY_SHA256,
        "code_only_native_target": str(target),
        "planned_source_files": len(prepared["runtime"]),
        "planned_dependency_files": len(prepared["dependencies"]),
        "planned_native_files": len(prepared["names"]),
        "planned_native_directories": len(prepared["directories"])+1,
        "planned_native_bytes": prepared["total"],
        **summary,
        "selected_r19_unchanged": True,
        "original_financial_roots_untouched": True,
        "native_code_installed": False,
        "new_release_selected": False,
        "financial_activation_accepted": False,
        "paper_accounts_opened": False,
        "market_feed_entitlements_accepted": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }
    (REVIEW / "source-only-review.json").write_text(
        json.dumps(review, indent=2, sort_keys=True), encoding="utf-8")
    return review


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--execute-source-only", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect:
        selection, summary, _dep, target = inspect()
        result = {
            "schema": SCHEMA,
            "status": "R20_SOURCE_ONLY_PLAN_NOT_PACKAGED",
            "source_commit": selection["source_commit"],
            "source_inventory_sha256": selection["inventory_digest"],
            "target": str(target), **summary,
            "native_code_installed": False,
            "paper_start_authorized": False,
        }
    else:
        result = execute_source_only()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
