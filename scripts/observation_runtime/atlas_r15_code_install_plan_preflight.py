"""R15 source-candidate native install PLAN only; no installation or authority.

Validates the already-frozen tracked 960-source archive plus the previous
9,566-file Python dependency receipt and pinned selected R14 predecessor.
Never creates a native directory, installs, opens external NTP, connects
providers, reads private credentials, or selects a new release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts.atlas_r14_low_impact_installer import (
    DEPENDENCY,
    DEPENDENCY_INVENTORY_SHA256,
    DEPENDENCY_RECEIPT_SHA256,
)
from scripts.build_release_candidate import source_bytes
from scripts.native_install_plan import prepare_install_inputs
from scripts.observation_runtime.atlas_r14_selected_paper_readiness import (
    collect_selected_reference,
)

ROOT = Path("D:/Work/Project Atlas")
SOURCE_COMMIT = "2c79a8d846d6b33669008114732ae5896153812a"
ARCHIVE_SHA = "f6cb597a53373efee929c306ae42537e16abcbcf6e57f7bd23ee92e8570160c0"
INVENTORY_SHA = "31df928fd182f4508ff84d4342eff5dc4ce6acb5cea68adc9f20265b23a8bb82"
ARCHIVE = ROOT / "logs/diagnostics/atlas-r15-source-only-20261110-r01/package/atlas-source.zip"
FREEZE = ROOT / "logs/diagnostics/atlas-r15-source-only-20261110-r01/source-freeze-readonly-result.json"
TARGET = Path("D:/AtlasRuntime/releases") / SOURCE_COMMIT
RECEIPT = ROOT / "logs/diagnostics" / (
    "qd-unselected-release-" + SOURCE_COMMIT + ".json")
R14_HEAD = "3fd8e1972b559a5de90627a303fc663b11928f8b43e84621a6796e9f3dbe9383"
REQUIRED_SELECTED_RELEASE = "7ff9d3dba2eabe110f843c13efac49464805de2a"
EXPECTED_RUNTIME = 960
EXPECTED_DEPENDENCIES = 9566
EXPECTED_FILES = 10526
EXPECTED_DIRECTORIES = 912
EXPECTED_BYTES = 263545933


def require_new_native_target(path: Path):
    """Read filesystem attributes, never create/reuse an installation."""
    if path != TARGET:
        raise ValueError("R15_EXACT_CREATE_ONLY_TARGET_REQUIRED")
    for target in (TARGET, RECEIPT, RECEIPT.with_suffix(".pending.jsonl")):
        if os.path.lexists(target):
            raise ValueError("R15_NATIVE_TARGET_OR_RECEIPT_ALREADY_OCCUPIED")
        for ancestor in target.parents:
            if ancestor.exists() and (
                    not ancestor.is_dir()
                    or ancestor.is_symlink()
                    or ancestor.is_junction()):
                raise ValueError("R15_NATIVE_TARGET_ANCESTOR_REFUSED")
    if not TARGET.parent.is_dir():
        raise ValueError("R15_NATIVE_RELEASE_PARENT_REQUIRED")
    return True


def evaluate(*, selected: dict, prepared: dict, freeze: dict):
    if (type(selected) is not dict or selected.get("revision") != 13
            or selected.get("selected_release") != REQUIRED_SELECTED_RELEASE
            or selected.get("native_selection_head") != R14_HEAD
            or selected.get("native_selection_record_verified") is not True
            or selected.get("financial_authority") is not False):
        raise ValueError("R15_GENUINE_SELECTED_R14_PREDECESSOR_REQUIRED")
    if (type(freeze) is not dict
            or freeze.get("schema") != "ATLAS_R15_SOURCE_ONLY_FROZEN_CANDIDATE_V1"
            or freeze.get("status") != "ARCHIVE_SOURCE_BYTES_VERIFIED_NO_INSTALL_OR_SELECTION"
            or freeze.get("source_commit") != SOURCE_COMMIT
            or freeze.get("selected_native_predecessor") != REQUIRED_SELECTED_RELEASE
            or freeze.get("source_files") != EXPECTED_RUNTIME
            or freeze.get("inventory_sha256") != INVENTORY_SHA
            or freeze.get("archive_sha256") != ARCHIVE_SHA
            or freeze.get("native_release_installed") is not False
            or freeze.get("native_installation_authorized") is not False
            or freeze.get("release_selection_authorized") is not False
            or freeze.get("financial_paper_authorized") is not False):
        raise ValueError("R15_FROZEN_SOURCE_NONFINANCIAL_EVIDENCE_REQUIRED")
    if (type(prepared) is not dict
            or prepared.get("selected_digest") != INVENTORY_SHA
            or prepared.get("verified", {}).get("source_files") != EXPECTED_RUNTIME
            or prepared["verified"].get("activation_approved") is not False
            or prepared["verified"].get("installation_verified") is not False
            or len(prepared.get("runtime", {})) != EXPECTED_RUNTIME
            or len(prepared.get("dependencies", {})) != EXPECTED_DEPENDENCIES
            or len(prepared.get("names", [])) != EXPECTED_FILES
            or len(prepared.get("directories", [])) + 1 != EXPECTED_DIRECTORIES
            or prepared.get("total") != EXPECTED_BYTES):
        raise ValueError("R15_EXACT_BOUNDED_NATIVE_INSTALL_PLAN_REFUSED")
    return {
        "schema":"ATLAS_R15_SOURCE_ONLY_NATIVE_INSTALL_PROPOSAL_V1",
        "status":"SOURCE_AND_DEPENDENCY_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION",
        "decision":"REVIEW_REQUIRED",
        "source_commit":SOURCE_COMMIT,
        "source_archive_sha256":ARCHIVE_SHA,
        "inventory_sha256":INVENTORY_SHA,
        "dependency_receipt_sha256":DEPENDENCY_RECEIPT_SHA256,
        "dependency_file_inventory_sha256":DEPENDENCY_INVENTORY_SHA256,
        "native_selected_predecessor":REQUIRED_SELECTED_RELEASE,
        "native_selected_predecessor_head":R14_HEAD,
        "new_create_only_release_target":str(TARGET),
        "future_exact_native_install_receipt":str(RECEIPT),
        "planned_runtime_source_files":EXPECTED_RUNTIME,
        "planned_dependency_files":EXPECTED_DEPENDENCIES,
        "planned_native_files":EXPECTED_FILES,
        "planned_native_directories":EXPECTED_DIRECTORIES,
        "planned_native_bytes":EXPECTED_BYTES,
        "independent_two_peer_clock_required_for_future_install":True,
        "bounded_idle_priority_install_required":True,
        "separate_exact_one_shot_code_install_authorization_required":True,
        "separate_exact_one_shot_code_selection_authorization_required":True,
        "native_installation_executed":False,
        "native_installation_authorized":False,
        "source_authenticated_by_native_install":False,
        "native_selection_changed":False,
        "financial_writer_enrolled":False,
        "provider_connection_opened":False,
        "financial_paper_start_authorized":False,
        "paper_orders_authorized":False,
        "live_trading_authorized":False,
        "financial_operating_gates_accepted":0,
    }


def inspect():
    selected = collect_selected_reference()
    require_new_native_target(TARGET)
    data = source_bytes(
        ROOT, str(FREEZE.relative_to(ROOT)).replace("\\", "/"), maximum_bytes=16384)
    freeze = json.loads(data)
    dep_bytes = source_bytes(
        ROOT, str(DEPENDENCY.relative_to(ROOT)).replace("\\", "/"),
        maximum_bytes=16*1024*1024)
    if hashlib.sha256(dep_bytes).hexdigest() != DEPENDENCY_RECEIPT_SHA256:
        raise ValueError("R15_DEPENDENCY_RECEIPT_CHANGED")
    dependency = json.loads(dep_bytes)
    prepared = prepare_install_inputs(
        archive=ARCHIVE, archive_sha256=ARCHIVE_SHA, source_commit=SOURCE_COMMIT,
        inventory_digest=INVENTORY_SHA, dependency_receipt=dependency,
        dependency_digest=DEPENDENCY_INVENTORY_SHA256, require_tracked=True)
    require_new_native_target(TARGET)
    return evaluate(selected=selected, prepared=prepared, freeze=freeze)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", required=True)
    parser.parse_args(argv)
    print(json.dumps(inspect(), sort_keys=True, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
