"""R23 code-only source inventory, directly succeeding genuine selected R21.

No installer, operator approval, selector publication, PAPER/financial write,
provider session or live trading. All new source, tests, docs and temporary
data stay in the sole D:/Work/Project Atlas project folder. The immutable
selected R21 original source+native installed release are independently
checked before packaging; all 12 financial original roots must be empty.
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
from scripts.atlas_r21_code_only_install import SOURCE as R21_SOURCE
from scripts.atlas_r21_source_review import (
    ALLOWED_EXTENSIONS,
    ROOT,
    git,
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

SCHEMA = "ATLAS_R23_SELECTED_R21_CODE_ONLY_SOURCE_REVIEW_V1"
DIAG = ROOT / "logs/diagnostics"
REVIEW = DIAG / "atlas-r23-source-only-20261113-r01"
PACKAGE = REVIEW / "package"
BASELINE = DIAG / "atlas-r21-source-only-20261113-r01/package/atlas-source.zip"
R21_ARCHIVE_SHA = "bb58601ac09de2f0e638ecc1aaf72d39179b295f227f09cdbd4bb1b75cf53e3b"
R21_RECEIPT_SHA = "b097b8f84945d49490bcb31cf330abf4a660651e0fc509fa92890ba9e8e24fcf"
R21_ARTIFACT = "02c5705e586f92415612c70309bd7051ad76629278f6c22905b056558b602b27"
R21_NATIVE_REVISION = 20
REQUIRED_NEW_MODULES = frozenset((
    "scripts/observation_runtime/atlas_independent_ntp_clock.py",
    "scripts/observation_runtime/personal_version_safe_release_clock.py",
    "scripts/observation_runtime/atlas_r20_native_iex_latest_readonly.py",
    "scripts/observation_runtime/atlas_r22_precise_live_ntp_readonly.py",
    "backend/app/services/hyperliquid_forward_flat_paper_policy.py",
    "backend/app/services/hyperliquid_intrahour_stop_supervisor.py",
    "backend/app/services/unified_paper_runtime.py",
    "backend/app/services/personal_installed_stop_owner.py",
))
MISSING_OPERATOR_SCOPE = "R23_SEPARATE_EXPLICIT_APPROVAL_NOT_CREATED"


def selected_r21():
    store = NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection",
        native_root=list(SELECTOR_NATIVE),
    )
    try:
        with store.locked():
            records = store.records()
            if (
                len(records) != R21_NATIVE_REVISION
                or records[-1].get("revision") != R21_NATIVE_REVISION
                or records[-1].get("action") != "SELECT"
            ):
                raise ValueError("R23_SELECTED_ORIGINAL_R21_REVISION20_REQUIRED")
            spec = release_selection.validate_spec(
                records[-1].get("selected"), "WINDOWS_LOCAL",
            )
            if (
                spec.get("release") != R21_SOURCE
                or spec.get("receipt_sha256") != R21_RECEIPT_SHA
                or spec.get("artifact_digest") != R21_ARTIFACT
            ):
                raise ValueError("R23_EXACT_RECOVERED_R21_INSTALL_RECEIPT_REQUIRED")
            with NativeInstalledReleaseVerifier().open(spec) as readback:
                if (
                    readback.get("source_commit") != R21_SOURCE
                    or readback.get("artifact_digest") != R21_ARTIFACT
                    or any(readback.get(key) is not False for key in (
                        "selected", "financial_effects",
                        "provider_connections", "operational_acceptance",
                    ))
                ):
                    raise ValueError("R23_IMMUTABLE_SELECTED_R21_INSTALLED_READBACK")
    finally:
        store.close()
    roots = inspect_two_lane_native_roots()
    if (
        roots.get("native_root_total") != 12
        or roots.get("native_root_ids_verified") != 12
        or roots.get("existing_empty_root_namespaces") != 12
        or roots.get("all_twelve_distinct_and_empty") is not True
    ):
        raise ValueError("R23_ORIGINAL_EMPTY_FINANCIAL_ROOTS_REQUIRED")
    return spec


def source_baseline():
    original = verify_candidate(BASELINE, expected_sha256=R21_ARCHIVE_SHA)
    with zipfile.ZipFile(BASELINE) as archive:
        manifest = json.loads(archive.read("release-manifest.json"))
    if (
        manifest.get("head") != R21_SOURCE
        or manifest.get("contract") != "R7E46O_SOURCE_V1"
        or type(manifest.get("files")) is not list
        or not 1100 <= len(manifest["files"]) <= 2048
        or any(row.get("git_status") != "tracked"
               for row in manifest["files"])
        or original.get("source_authenticated") is not False
    ):
        raise ValueError("R23_ORIGINAL_PINNED_R21_SOURCE_REQUIRED")
    return {row["path"] for row in manifest["files"]}


def review_selection():
    predecessor = selected_r21()
    baseline = source_baseline()
    head = git("rev-parse", "HEAD")[0]
    if (
        not re.fullmatch(r"[0-9a-f]{40}", head)
        or head == R21_SOURCE
        or git("status", "--porcelain", "--untracked-files=no")
    ):
        raise ValueError("R23_CLEAN_NEW_TRACKED_COMMIT_REQUIRED")
    subprocess.check_call(
        ["git", "merge-base", "--is-ancestor", R21_SOURCE, head],
        cwd=ROOT, stdout=subprocess.DEVNULL,
    )
    changed = set(git(
        "diff", "--name-only", R21_SOURCE, head, "--",
        "backend/app/", "scripts/", "tests/", "docs/", "frontend/offline/",
    ))
    tracked = set(git(
        "ls-files", "--",
        "backend/app/", "scripts/", "tests/", "docs/", "frontend/offline/",
    ))
    merged = baseline | changed | REQUIRED_NEW_MODULES
    if (
        not REQUIRED_NEW_MODULES <= tracked
        or not merged <= tracked
        or len(changed) < 10
        or any(not p.startswith(ROOTS) for p in merged)
        or any(Path(p).suffix.lower() not in ALLOWED_EXTENSIONS
               for p in changed - baseline)
    ):
        raise ValueError("R23_EXACT_TRACKED_ORIGINAL_SOURCE_ONLY_REQUIRED")
    closure = required_runtime_documents(
        ROOT, selected={p for p in merged if p.startswith(SOURCE_ROOTS)},
        tracked=tracked,
    )
    if (
        closure["missing_independent_operator_approval_input"]
        != [EXPLICIT_UNAVAILABLE_OPERATOR_INPUT]
        or closure["missing_operator_input_must_not_be_packaged"] is not True
        or not 20 <= closure["tracked_runtime_document_count"] <= 100
    ):
        raise ValueError("R23_ORIGINAL_RUNTIME_DOCS_AND_MISSING_APPROVAL_REQUIRED")
    names = sorted(merged | set(closure["tracked_runtime_document_paths"]))
    if not 1100 <= len(names) <= 2048:
        raise ValueError("R23_BOUNDED_SOURCE_FILE_COUNT_REQUIRED")
    windows_namespace(names)
    rows, total = [], 0
    for name in names:
        source_path(ROOT, name)
        content = source_bytes(ROOT, name, maximum_bytes=16*1024*1024)
        total += len(content)
        if total > 128*1024*1024:
            raise ValueError("R23_SOURCE_BYTE_CAPACITY")
        rows.append({
            "path": name, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    digest = hashlib.sha256(json.dumps(
        rows, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    selection = {
        "schema": "ATLAS_SOURCE_SELECTION_V1",
        "source_commit": head,
        "inventory_digest": digest,
        "files": rows,
    }
    summary = {
        "selected_predecessor": R21_SOURCE,
        "selected_predecessor_artifact_digest": predecessor["artifact_digest"],
        "selected_predecessor_revision": R21_NATIVE_REVISION,
        "source_files": len(rows),
        "source_bytes": total,
        "new_or_changed_tracked_paths": len(changed),
        "runtime_document_count": closure["tracked_runtime_document_count"],
        "pinned_runtime_documents": closure["tracked_runtime_document_paths"],
    }
    return selection, summary


def inspect():
    if (
        os.path.lexists(REVIEW)
        or not DIAG.is_dir()
        or DIAG.is_symlink()
        or DIAG.is_junction()
    ):
        raise ValueError("R23_FRESH_D_ONLY_REVIEW_REQUIRED")
    selection, summary = review_selection()
    target = Path("D:/AtlasRuntime/releases") / selection["source_commit"]
    if os.path.lexists(target):
        raise ValueError("R23_CREATE_ONLY_NATIVE_TARGET_EXISTS")
    raw = source_bytes(
        ROOT, DEPENDENCY.relative_to(ROOT).as_posix(),
        maximum_bytes=16*1024*1024,
    )
    if hashlib.sha256(raw).hexdigest() != DEPENDENCY_RECEIPT_SHA256:
        raise ValueError("R23_PINNED_ORIGINAL_PYTHON_DEPENDENCIES_REQUIRED")
    return selection, summary, json.loads(raw), target


def execute_source_only():
    selection, summary, dependencies, target = inspect()
    REVIEW.mkdir(parents=False, exist_ok=False)
    (REVIEW / "selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    archive_sha = build_selected(
        PACKAGE, selection=selection,
        expected_inventory_sha256=selection["inventory_digest"],
    )
    prepared = prepare_install_inputs(
        archive=PACKAGE / "atlas-source.zip",
        archive_sha256=archive_sha,
        source_commit=selection["source_commit"],
        inventory_digest=selection["inventory_digest"],
        dependency_receipt=dependencies,
        dependency_digest=DEPENDENCY_INVENTORY_SHA256,
        require_tracked=True,
    )
    if (
        len(prepared["runtime"]) != summary["source_files"]
        or len(prepared["dependencies"]) != 9566
        or not REQUIRED_NEW_MODULES <= set(prepared["runtime"])
        or prepared["verified"].get("activation_approved") is not False
        or len(prepared["names"]) >= 12000
        or prepared["total"] > 512*1024*1024
    ):
        raise ValueError("R23_FULL_CODE_ONLY_PACKAGE_REFUSED")
    review = {
        "schema": SCHEMA,
        "status": "AUDITED_R23_SOURCE_ONLY_NOT_INSTALLED",
        "source_commit": selection["source_commit"],
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
        "required_operator_approval": MISSING_OPERATOR_SCOPE,
        **summary,
        "selected_r21_unchanged": True,
        "original_native_financial_roots_untouched": True,
        "native_code_installed": False,
        "new_release_selected": False,
        "original_operator_activation": False,
        "source_rights_accepted": False,
        "financial_inception_verified": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }
    (REVIEW / "source-only-review.json").write_text(
        json.dumps(review, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return review


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--execute-source-only", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect:
        selection, summary, _, target = inspect()
        result = {
            "schema": SCHEMA,
            "status": "EXACT_R23_SOURCE_ONLY_PLAN_NOT_INSTALLED",
            "source_commit": selection["source_commit"],
            "source_inventory_sha256": selection["inventory_digest"],
            "target": str(target),
            **summary,
            "paper_start_authorized": False,
        }
    else:
        result = execute_source_only()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
