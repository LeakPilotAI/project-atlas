"""Prepare a create-only R18 CODE-ONLY SOURCE successor to installed R17.

This is an immutable source-and-dependency review, NOT installation or
selection. No financial account, provider, process, trading or Start action.
R17's pinned tracked source inventory is preserved, then only newly changed
Git-tracked in-scope paths are added. Fail on any private/untracked data or
mutable source. Review output lives in diagnostics, never AtlasRuntime.
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
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    SOURCE as R17_SOURCE,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    require_selected_r17_nonfinancial,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

ROOT = Path("D:/Work/Project Atlas")
PARENT = ROOT / "logs/diagnostics"
REVIEW = PARENT / "atlas-r18-source-only-20261112-r01"
PACKAGE = REVIEW / "package"
BASELINE = (
    PARENT / "atlas-r17-source-only-20261112-r07/package/atlas-source.zip"
)
R17_ARCHIVE_SHA = (
    "246be0782ce96b6013cff80b029d92ab8219f2dc139d3ee3b483d7bd6a73aa89"
)
ARTIFACTS = {"selection.json", "source-only-review.json"}
SCHEMA = "ATLAS_R18_TRACKED_CODE_ONLY_SUCCESSOR_REVIEW_V1"
ALLOWED_EXTENSIONS = frozenset((
    ".py", ".ps1", ".psm1", ".js", ".cjs", ".mjs",
    ".html", ".css", ".json", ".md",
))


def git(*args):
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).splitlines()


def _selected_r17():
    verify_candidate(BASELINE, expected_sha256=R17_ARCHIVE_SHA)
    with zipfile.ZipFile(BASELINE, "r") as bundle:
        row = json.loads(bundle.read("release-manifest.json"))
    if (type(row) is not dict
            or row.get("head") != R17_SOURCE
            or row.get("contract") != "R7E46O_SOURCE_V1"
            or type(row.get("files")) is not list
            or len(row["files"]) != 1044
            or any(type(f) is not dict or f.get("git_status") != "tracked"
                   or type(f.get("path")) is not str
                   for f in row["files"])):
        raise ValueError("R18_ORIGINAL_PINNED_R17_SOURCE_INVENTORY_REFUSED")
    return [item["path"] for item in row["files"]]


def source_selection():
    """Pure package-plan inspection; no writes, finance or network."""
    require_selected_r17_nonfinancial()
    roots = inspect_two_lane_native_roots()
    if (roots.get("native_root_total") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R18_ORIGINAL_FINANCIAL_ROOTS_UNTOUCHED_REQUIRED")
    head = git("rev-parse", "HEAD")[0]
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("R18_PINNED_GIT_HEAD_REQUIRED")
    subprocess.check_call(
        ["git", "merge-base", "--is-ancestor", R17_SOURCE, head],
        cwd=ROOT, stdout=subprocess.DEVNULL)
    existing = set(_selected_r17())
    changed = set(git(
        "diff", "--name-only", R17_SOURCE, head, "--",
        "backend/app/", "scripts/", "tests/", "docs/", "frontend/offline/"))
    # A renamed/deleted R17 input must be refused, not silently dropped.
    all_names = existing | changed
    tracked = set(git("ls-files", "--",
        "backend/app/", "scripts/", "tests/", "docs/", "frontend/offline/"))
    if (not all_names <= tracked or len(all_names) > 2048
            or any(not path.startswith(ROOTS) for path in all_names)
            or any(Path(path).suffix.lower() not in ALLOWED_EXTENSIONS
                   for path in changed - existing)):
        raise ValueError("R18_ONLY_PRIOR_AND_CHANGED_TRACKED_RUNTIME_ALLOWED")
    windows_namespace(all_names)
    files = []
    total = 0
    for name in sorted(all_names):
        source_path(ROOT, name)
        raw = source_bytes(ROOT, name, maximum_bytes=16*1024*1024)
        total += len(raw)
        if total > 128*1024*1024:
            raise ValueError("R18_BOUNDED_TRACKED_RUNTIME_CAPACITY")
        files.append({
            "path": name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    encoded = json.dumps(
        files, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    inventory = hashlib.sha256(encoded).hexdigest()
    return {
        "schema": "ATLAS_SOURCE_SELECTION_V1",
        "source_commit": head,
        "inventory_digest": inventory,
        "files": files,
    }, {
        "base_source_files": len(existing),
        "new_tracked_source_files": len(all_names - existing),
        "current_source_files": len(files),
        "current_source_bytes": total,
    }


def current_prerequisites():
    if (REVIEW.exists() or REVIEW.is_symlink()
            or REVIEW.is_junction()
            or not PARENT.is_dir()
            or PARENT.is_symlink() or PARENT.is_junction()):
        raise ValueError("R18_NEW_CREATE_ONLY_SOURCE_REVIEW_REQUIRED")
    target = Path("D:/AtlasRuntime/releases") / git("rev-parse", "HEAD")[0]
    if os.path.lexists(target):
        raise ValueError("R18_CODE_ONLY_SUCCESSOR_TARGET_ALREADY_EXISTS")
    raw = source_bytes(
        ROOT, DEPENDENCY.relative_to(ROOT).as_posix(),
        maximum_bytes=16*1024*1024)
    if hashlib.sha256(raw).hexdigest() != DEPENDENCY_RECEIPT_SHA256:
        raise ValueError("R18_PINNED_DEPENDENCIES_CHANGED")
    return json.loads(raw), str(target)


def inspect():
    selection, counts = source_selection()
    dependencies, target = current_prerequisites()
    return selection, counts, dependencies, target


def execute_source_only():
    selection, counts, dependencies, target = inspect()
    REVIEW.mkdir(parents=False, exist_ok=False)
    try:
        (REVIEW / "selection.json").write_text(
            json.dumps(selection, indent=2, sort_keys=True),
            encoding="utf-8")
        archive_hash = build_selected(
            PACKAGE, selection=selection,
            expected_inventory_sha256=selection["inventory_digest"])
        prepared = prepare_install_inputs(
            archive=PACKAGE / "atlas-source.zip",
            archive_sha256=archive_hash,
            source_commit=selection["source_commit"],
            inventory_digest=selection["inventory_digest"],
            dependency_receipt=dependencies,
            dependency_digest=DEPENDENCY_INVENTORY_SHA256,
            require_tracked=True,
        )
        if (len(prepared["runtime"]) != counts["current_source_files"]
                or prepared["verified"].get("activation_approved") is not False
                or len(prepared["names"]) > 12000
                or prepared["total"] > 512*1024*1024):
            raise ValueError("R18_EXACT_BOUNDED_CODE_ONLY_PLAN_REFUSED")
        record = {
            "schema": SCHEMA,
            "status": "TRACKED_SOURCE_AND_PINNED_DEPENDENCY_VERIFIED_ONLY",
            "source_commit": selection["source_commit"],
            "predecessor_r17": R17_SOURCE,
            "source_inventory_sha256": selection["inventory_digest"],
            "source_archive_sha256": archive_hash,
            "pinned_dependency_receipt_sha256": DEPENDENCY_RECEIPT_SHA256,
            "pinned_dependency_inventory_sha256": DEPENDENCY_INVENTORY_SHA256,
            "code_only_native_target": target,
            "planned_source_files": len(prepared["runtime"]),
            "planned_dependency_files": len(prepared["dependencies"]),
            "planned_native_files": len(prepared["names"]),
            "planned_native_directories": len(prepared["directories"])+1,
            "planned_native_bytes": prepared["total"],
            **counts,
            "selected_r17_unchanged": True,
            "original_financial_roots_untouched": True,
            "immutable_release_installed": False,
            "new_release_selected": False,
            "new_operator_install_approved": False,
            "financial_issuer_accepted": False,
            "native_paper_accounts_incepted": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
        (REVIEW / "source-only-review.json").write_text(
            json.dumps(record, indent=2, sort_keys=True),
            encoding="utf-8")
        return record
    except BaseException:  # noqa: TRY203 -- preserve original failure and partial review
        # Preserve a possibly partial review; do not adopt/retry it.
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--execute-source-only", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect:
        selection, counts, _dependencies, target = inspect()
        result = {
            "schema": SCHEMA,
            "status": "TRACKED_CODE_ONLY_PLAN_NOT_PACKAGED",
            "source_commit": selection["source_commit"],
            "inventory_sha256": selection["inventory_digest"],
            "target": target,
            **counts,
            "release_installed": False,
            "selected_r17_unchanged": True,
            "financial_authority": False,
            "paper_start_authorized": False,
        }
    else:
        result = execute_source_only()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
