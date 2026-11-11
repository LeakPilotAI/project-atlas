"""R16 pinned SOURCE-ONLY native install proposal; no installation or grant.

Uses the real currently selected immutable R15 native 14-record chain,
the frozen 983-file R16 source candidate, and an independently inventoried
9,566-file Python dependency receipt. Never creates a native release, selection,
account, process or order; never reads credentials or makes provider requests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts.atlas_r14_low_impact_installer import (
    DEPENDENCY, DEPENDENCY_RECEIPT_SHA256, DEPENDENCY_INVENTORY_SHA256,
)
from scripts.build_release_candidate import source_bytes
from scripts.native_install_plan import prepare_install_inputs
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    selected_code as selected_r15_code, SELECTED_HEAD, SELECTED_SHA,
)

ROOT = Path("D:/Work/Project Atlas")
SOURCE_COMMIT = "cadb3b5a163b31f9ee7bda32453a5983e809ccc0"
ARCHIVE_SHA = "397f6722feb2c2483c3f262e87fae6110d9ba3c8d3f990c62162f090a70afd0a"
INVENTORY_SHA = "c4b72c58867cbb0a49a2126bae5527ed9b004807bb46cda272c75219c321e341"
ARCHIVE = ROOT / "logs/diagnostics/atlas-r16-source-only-20261111-r01/package/atlas-source.zip"
FREEZE = ROOT / "logs/diagnostics/atlas-r16-source-only-20261111-r01/source-freeze-review.json"
TARGET = Path("D:/AtlasRuntime/releases") / SOURCE_COMMIT
RECEIPT = ROOT / "logs/diagnostics" / ("qd-unselected-release-" + SOURCE_COMMIT + ".json")
SELECTED_R15_RELEASE = "2c79a8d846d6b33669008114732ae5896153812a"
EXPECTED_RUNTIME = 983
EXPECTED_DEPENDENCIES = 9566
EXPECTED_FILES = 10549
EXPECTED_DIRECTORIES = 912
EXPECTED_BYTES = 263892205


def require_new_native_target(path=TARGET):
    """Create-only namespace and ancestor check; never repair a failed copy."""
    if path != TARGET:
        raise ValueError("R16_EXACT_CREATE_ONLY_TARGET_REQUIRED")
    for item in (TARGET, RECEIPT, RECEIPT.with_suffix(".pending.jsonl")):
        if os.path.lexists(item):
            raise ValueError("R16_NATIVE_TARGET_OR_RECEIPT_ALREADY_OCCUPIED")
        for ancestor in item.parents:
            if ancestor.exists() and (
                not ancestor.is_dir() or ancestor.is_symlink()
                or ancestor.is_junction()):
                raise ValueError("R16_NATIVE_TARGET_ANCESTOR_REFUSED")
    if not TARGET.parent.is_dir():
        raise ValueError("R16_NATIVE_RELEASE_PARENT_REQUIRED")
    return True


def validate_selected_r15(selected):
    if (type(selected) is not dict
            or selected.get("revision") != 14
            or selected.get("selected_release") != SELECTED_R15_RELEASE
            or selected.get("selected_native_head") != SELECTED_HEAD
            or selected.get("selected_native_record_sha256") != SELECTED_SHA
            or selected.get("native_clock_own_release_source_admitted") is not True
            or selected.get("independent_live_financial_clock_lease_accepted") is not False
            or selected.get("financial_authority") is not False):
        raise ValueError("R16_GENUINE_NATIVE_SELECTED_R15_ANCHOR_REQUIRED")
    return True


def evaluate(*, selected, prepared, freeze):
    validate_selected_r15(selected)
    if (type(freeze) is not dict
            or freeze.get("schema") != "ATLAS_R16_FROZEN_CODE_ONLY_SOURCE_CANDIDATE_V1"
            or freeze.get("status") !=
                "TRACKED_SOURCE_AND_DEPENDENCY_PLAN_VERIFIED_NOT_INSTALL_OR_SELECTION_AUTHORIZATION"
            or freeze.get("source_commit") != SOURCE_COMMIT
            or freeze.get("source_archive_sha256") != ARCHIVE_SHA
            or freeze.get("selected_source_inventory_sha256") != INVENTORY_SHA
            or freeze.get("original_source_paths_preserved") != 960
            or freeze.get("new_tracked_runtime_paths_added") != 23
            or freeze.get("source_files") != EXPECTED_RUNTIME
            or freeze.get("dependency_files") != EXPECTED_DEPENDENCIES
            or freeze.get("native_files_planned") != EXPECTED_FILES
            or freeze.get("native_directories_planned") != EXPECTED_DIRECTORIES
            or freeze.get("native_bytes_planned") != EXPECTED_BYTES
            or freeze.get("proposed_create_only_target") != str(TARGET)
            or freeze.get("selected_r15_selection_record_sha256") != SELECTED_SHA
            or freeze.get("selected_r15_unchanged") is not True
            or freeze.get("dependency_receipt_sha256") != DEPENDENCY_RECEIPT_SHA256
            or freeze.get("dependency_file_inventory_sha256") != DEPENDENCY_INVENTORY_SHA256
            or freeze.get("financial_operating_gates_accepted") != 0
            or any(freeze.get(key) is not False for key in (
                "source_installation_authorized", "native_installation_executed",
                "native_release_selection_authorized", "financial_authority",
                "operator_account_inception", "paper_orders_authorized",
                "live_trading_authorized", "market_data_provider_requested"))):
        raise ValueError("R16_PINNED_SOURCE_FREEZE_REVIEW_REQUIRED")
    if (type(prepared) is not dict
            or prepared.get("selected_digest") != INVENTORY_SHA
            or prepared.get("verified", {}).get("source_files") != EXPECTED_RUNTIME
            or prepared.get("verified", {}).get("activation_approved") is not False
            or prepared.get("verified", {}).get("installation_verified") is not False
            or len(prepared.get("runtime", {})) != EXPECTED_RUNTIME
            or len(prepared.get("dependencies", {})) != EXPECTED_DEPENDENCIES
            or len(prepared.get("names", [])) != EXPECTED_FILES
            or len(prepared.get("directories", [])) + 1 != EXPECTED_DIRECTORIES
            or prepared.get("total") != EXPECTED_BYTES):
        raise ValueError("R16_EXACT_BOUNDED_NATIVE_INSTALL_PLAN_REFUSED")
    return {
        "schema": "ATLAS_R16_SOURCE_ONLY_NATIVE_INSTALL_PROPOSAL_V1",
        "status": "SOURCE_AND_DEPENDENCY_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION",
        "decision": "REVIEW_REQUIRED",
        "source_commit": SOURCE_COMMIT,
        "source_archive_sha256": ARCHIVE_SHA,
        "selected_source_inventory_sha256": INVENTORY_SHA,
        "dependency_receipt_sha256": DEPENDENCY_RECEIPT_SHA256,
        "dependency_file_inventory_sha256": DEPENDENCY_INVENTORY_SHA256,
        "native_selected_predecessor": SELECTED_R15_RELEASE,
        "native_selected_predecessor_head": SELECTED_HEAD,
        "new_create_only_release_target": str(TARGET),
        "future_exact_native_install_receipt": str(RECEIPT),
        "planned_runtime_source_files": EXPECTED_RUNTIME,
        "planned_dependency_files": EXPECTED_DEPENDENCIES,
        "planned_native_files": EXPECTED_FILES,
        "planned_native_directories": EXPECTED_DIRECTORIES,
        "planned_native_bytes": EXPECTED_BYTES,
        "independent_two_peer_clock_required_for_future_install": True,
        "bounded_idle_priority_install_required": True,
        "separate_exact_one_shot_code_install_authorization_required": True,
        "separate_exact_one_shot_code_selection_authorization_required": True,
        "native_installation_executed": False,
        "native_installation_authorized": False,
        "source_authenticated_by_native_install": False,
        "native_selection_changed": False,
        "financial_writer_enrolled": False,
        "provider_connection_opened": False,
        "financial_paper_start_authorized": False,
        "paper_orders_authorized": False,
        "live_trading_authorized": False,
        "financial_operating_gates_accepted": 0,
    }


def inspect():
    """Fresh source/selector/dep readback, NO native mutations or network."""
    selected = selected_r15_code()
    require_new_native_target()
    review_bytes = source_bytes(ROOT, FREEZE.relative_to(ROOT).as_posix(), maximum_bytes=16384)
    freeze = json.loads(review_bytes)
    dependency_raw = source_bytes(ROOT, DEPENDENCY.relative_to(ROOT).as_posix(),
                                  maximum_bytes=16*1024*1024)
    if hashlib.sha256(dependency_raw).hexdigest() != DEPENDENCY_RECEIPT_SHA256:
        raise ValueError("R16_DEPENDENCY_RECEIPT_CHANGED")
    dependency = json.loads(dependency_raw)
    prepared = prepare_install_inputs(
        archive=ARCHIVE, archive_sha256=ARCHIVE_SHA, source_commit=SOURCE_COMMIT,
        inventory_digest=INVENTORY_SHA, dependency_receipt=dependency,
        dependency_digest=DEPENDENCY_INVENTORY_SHA256, require_tracked=True)
    require_new_native_target()
    return evaluate(selected=selected, prepared=prepared, freeze=freeze)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", required=True)
    parser.parse_args(argv)
    print(json.dumps(inspect(), sort_keys=True, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
