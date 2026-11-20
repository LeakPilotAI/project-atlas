"""Prepare a create-only R19 successor candidate of selected immutable R18.

Review and frozen source package ONLY: NEVER install, select, publish
activation, connect to providers, or touch financial accounts.
Use a verified originally selected R18 native source receipt as baseline,
include changed Git-tracked source (not arbitrary untracked scripts),
preserve independent pinned Python dependency inventory and full immutable
original-file readback. The prepared archive is a technical artifact,
not approval for financial commissioning or one-time native selection.
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
REVIEW = PARENT / "atlas-r19-source-only-20261112-r01"
PACKAGE = REVIEW / "package"
BASELINE = PARENT / "atlas-r18-source-only-20261112-r01/package/atlas-source.zip"
R18_ARCHIVE_SHA = "c162a0f9b5c608b70137a1e9415b4913151572e80678d0bfaf1f5dead6c771ef"
R18_SOURCE = "1389683b2a38a9accc0381c207d36abb2ce21e11"
R18_ARTIFACT = "66ce29256b5230e9abfee076ec73bef36ff69d734c21bc69a8e092dc7b4c72e3"
R18_HEAD = "0507476e4dd18a0a5d07770da2a7b837e4c165fcfc0f8a221bde76580122ce28"
SCHEMA = "ATLAS_R19_TRACKED_CODE_ONLY_SUCCESSOR_REVIEW_V1"
ALLOWED_EXTENSIONS = frozenset((".py", ".ps1", ".psm1", ".js", ".cjs", ".mjs",
                                ".html", ".css", ".json", ".md"))


def git(*args):
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).splitlines()


def source_selection():
    """Read-only native selection/source inventory/financial precondition."""
    store = NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection", native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():
            records = store.records()
            if (len(records) != 17 or records[-1].get("revision") != 17
                    or release_selection.digest(records[-1]) != R18_HEAD):
                raise ValueError("R19_GENUINE_R18_NATIVE_SELECTION_CHAIN_REQUIRED")
            spec = release_selection.validate_spec(
                records[-1].get("selected"), "WINDOWS_LOCAL")
            if (spec["release"] != R18_SOURCE
                    or spec["artifact_digest"] != R18_ARTIFACT):
                raise ValueError("R19_SELECTED_R18_ARTIFACT_IDENTITY_REFUSED")
            with NativeInstalledReleaseVerifier().open(spec) as readback:
                if (readback.get("source_commit") != R18_SOURCE
                        or readback.get("artifact_digest") != R18_ARTIFACT
                        or any(readback.get(k) is not False for k in (
                            "selected", "financial_effects",
                            "provider_connections", "operational_acceptance"))):
                    raise ValueError("R19_ORIGINAL_INSTALLED_R18_CODE_REFUSED")
    finally:
        store.close()
    roots = inspect_two_lane_native_roots()
    if (roots["native_root_total"] != 12
            or roots["native_root_ids_verified"] != 12
            or roots["all_twelve_distinct_and_empty"] is not True):
        raise ValueError("R19_ORIGINAL_NATIVE_FINANCIAL_ACCOUNTS_MUST_STAY_EMPTY")
    verify_candidate(BASELINE, expected_sha256=R18_ARCHIVE_SHA)
    with zipfile.ZipFile(BASELINE) as archive:
        row = json.loads(archive.read("release-manifest.json"))
    if (row.get("head") != R18_SOURCE or row.get("contract") != "R7E46O_SOURCE_V1"
            or len(row.get("files", [])) != 1064
            or any(item.get("git_status") != "tracked" for item in row["files"])):
        raise ValueError("R19_PINNED_R18_BASELINE_SOURCE_REFUSED")
    original = {r["path"] for r in row["files"]}
    head = git("rev-parse", "HEAD")[0]
    if not re.fullmatch("[0-9a-f]{40}", head) or head == R18_SOURCE:
        raise ValueError("R19_NEW_SOURCE_COMMIT_REQUIRED")
    subprocess.check_call(["git", "merge-base", "--is-ancestor", R18_SOURCE, head],
                          cwd=ROOT, stdout=subprocess.DEVNULL)
    changed = set(git("diff", "--name-only", R18_SOURCE, head, "--",
                      "backend/app/", "scripts/", "tests/", "docs/", "frontend/offline/"))
    selected = original | changed
    tracked = set(git("ls-files", "--", "backend/app/", "scripts/", "tests/",
                      "docs/", "frontend/offline/"))
    if (not selected <= tracked or not 1064 <= len(selected) <= 2048
            or not changed or any(not name.startswith(ROOTS) for name in selected)
            or any(Path(name).suffix.lower() not in ALLOWED_EXTENSIONS
                   for name in changed-original)):
        raise ValueError("R19_ONLY_APPROVED_TRACKED_INCREMENTAL_CODE_ALLOWED")
    windows_namespace(selected)
    files = []
    total = 0
    for name in sorted(selected):
        source_path(ROOT, name)
        content = source_bytes(ROOT, name, maximum_bytes=16*1024*1024)
        total += len(content)
        if total > 128*1024*1024:
            raise ValueError("R19_SOURCE_BYTE_BOUND_EXCEEDED")
        files.append({
            "path": name, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    inventory = hashlib.sha256(json.dumps(
        files, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {
        "schema": "ATLAS_SOURCE_SELECTION_V1",
        "source_commit": head,
        "inventory_digest": inventory,
        "files": files,
    }, {
        "base_source_files": len(original),
        "changed_tracked_paths_since_r18": len(changed),
        "new_tracked_source_files": len(selected-original),
        "current_source_files": len(files),
        "current_source_bytes": total,
    }


def inspect():
    if (REVIEW.exists() or REVIEW.is_symlink() or REVIEW.is_junction()
            or not PARENT.is_dir() or PARENT.is_symlink() or PARENT.is_junction()):
        raise ValueError("R19_CREATE_ONLY_FRESH_REVIEW_DESTINATION_REQUIRED")
    selection, counts = source_selection()
    target = Path("D:/AtlasRuntime/releases") / selection["source_commit"]
    if os.path.lexists(target):
        raise ValueError("R19_NEW_NATIVE_RELEASE_TARGET_MUST_NOT_EXIST")
    raw = source_bytes(
        ROOT, DEPENDENCY.relative_to(ROOT).as_posix(),
        maximum_bytes=16*1024*1024)
    if hashlib.sha256(raw).hexdigest() != DEPENDENCY_RECEIPT_SHA256:
        raise ValueError("R19_PINNED_PYTHON_DEPENDENCIES_CHANGED")
    return selection, counts, json.loads(raw), target


def execute_source_only():
    selection, counts, dependencies, target = inspect()
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
        dependency_digest=DEPENDENCY_INVENTORY_SHA256,
        require_tracked=True)
    if (len(prepared["runtime"]) != counts["current_source_files"]
            or len(prepared["dependencies"]) != 9566
            or prepared["verified"].get("activation_approved") is not False
            or len(prepared["names"]) > 12000
            or prepared["total"] > 512*1024*1024):
        raise ValueError("R19_CODE_ONLY_PREPARED_PLAN_REFUSED")
    record = {
        "schema": SCHEMA,
        "status": "TRACKED_SOURCE_AND_PINNED_DEPENDENCY_VERIFIED_ONLY",
        "source_commit": selection["source_commit"],
        "selected_r18_source": R18_SOURCE,
        "selected_r18_native_head": R18_HEAD,
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
        **counts,
        "selected_r18_unchanged": True,
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
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--execute-source-only", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect:
        selection, counts, _dependencies, target = inspect()
        record = {
            "schema": SCHEMA, "status": "CODE_ONLY_R19_SOURCE_PLAN_NOT_PACKAGED",
            "source_commit": selection["source_commit"],
            "source_inventory_sha256": selection["inventory_digest"],
            "code_only_native_target": str(target), **counts,
            "native_code_installed": False,
            "paper_start_authorized": False,
        }
    else:
        record = execute_source_only()
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
