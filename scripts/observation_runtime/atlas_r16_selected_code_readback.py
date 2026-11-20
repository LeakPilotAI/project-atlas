"""Read-only R16 selected native CODE verification after actual revision 15.

Never use R15-only selected_code() after r0015 has been published. This
independent code identity proof does NOT issue financial clock, provider,
native account, PAPER writer, stop-drain or order authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts import release_selection as sel
from scripts.release_selection_store import NativeSelectionStore
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTED_HEAD as R15_HEAD, SELECTED_SHA as R15_SHA,
    SELECTOR_NATIVE_ID, GATES,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

ROOT = Path("D:/Work/Project Atlas")
SELECTION = Path("D:/AtlasRuntime/selection")
SOURCE = "cadb3b5a163b31f9ee7bda32453a5983e809ccc0"
RELEASE = Path("D:/AtlasRuntime/releases") / SOURCE
RECEIPT = ROOT / "logs/diagnostics" / ("qd-unselected-release-" + SOURCE + ".json")
JOURNAL = RECEIPT.with_suffix(".pending.jsonl")
R16_HEAD = "1244c614ccc9e89e436d90df77cebb6e44a57edcb44972660940ed29ebfcd593"
R16_RECORD_SHA = "d8ea7097008019426d64f96ca717878082644d3ec7592d26ce0428607988cc6f"
RECEIPT_SHA = "bee5534c894959f70ddcea75b9c7c419274029fedb8c275169fbd4567bf9516e"
JOURNAL_SHA = "6ee6dc4ea34605f38b3d855d6cbdb2a329f36f5034a43ee2b1ea8ca7fe1612a7"
ARTIFACT_DIGEST = "48c8192aa378526a319c3d2808f35f7e4662e47e69cde4daafbd4ba4115a8bd9"


def _pin(path: Path, sha: str, *, maximum: int):
    if (not path.is_file() or path.is_symlink() or path.is_junction()
            or not 0 < path.stat().st_size <= maximum):
        raise ValueError("R16_SELECTED_CODE_NATIVE_RECEIPT_OR_RECORD_REQUIRED")
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError("R16_SELECTED_CODE_NATIVE_HASH_CHANGED")
    return True


def selected_code(*, verify_original_installed_handles=False):
    """Exact 15 native selector records; original file handles optional/read-only."""
    if os.name != "nt":
        raise ValueError("R16_SELECTED_CODE_NATIVE_WINDOWS_REQUIRED")
    if type(verify_original_installed_handles) is not bool:
        raise ValueError("R16_SELECTED_CODE_EXPLICIT_READBACK_SCOPE_REQUIRED")
    store = NativeSelectionStore(root=str(SELECTION), native_root=SELECTOR_NATIVE_ID)
    try:
        with store.locked():
            rows = store.records()
            if (len(rows) != 15
                    or [r.get("revision") for r in rows] != list(range(1,16))
                    or sel.digest(rows[-2]) != R15_HEAD
                    or sel.digest(rows[-1]) != R16_HEAD
                    or rows[-1].get("schema") != "QD_RELEASE_SELECTION_RECEIPT_V1"
                    or rows[-1].get("domain") != "WINDOWS_LOCAL"
                    or rows[-1].get("revision") != 15
                    or rows[-1].get("action") != "SELECT"
                    or rows[-1].get("previous") != R15_HEAD
                    or rows[-1].get("restores") is not None):
                raise ValueError("R16_SELECTED_CODE_ORIGINAL_15_RECORD_NATIVE_CHAIN_REQUIRED")
            spec = sel.validate_spec(rows[-1].get("selected"), "WINDOWS_LOCAL")
            if (spec["release"] != SOURCE or spec["root"] != str(RELEASE)
                    or spec["receipt"] != str(RECEIPT)
                    or spec["receipt_sha256"] != RECEIPT_SHA
                    or spec["artifact_digest"] != ARTIFACT_DIGEST):
                raise ValueError("R16_SELECTED_CODE_EXACT_NONFINANCIAL_RELEASE_REQUIRED")
    finally:
        store.close()
    for path, digest, limit in (
        (SELECTION/"r0014.json", R15_SHA, 65536),
        (SELECTION/"r0014.pending", R15_SHA, 65536),
        (SELECTION/"r0015.json", R16_RECORD_SHA, 65536),
        (SELECTION/"r0015.pending", R16_RECORD_SHA, 65536),
        (RECEIPT, RECEIPT_SHA, 4*1024*1024),
        (JOURNAL, JOURNAL_SHA, 8192),
    ):
        _pin(path,digest,maximum=limit)
    if (not RELEASE.is_dir() or RELEASE.is_symlink() or RELEASE.is_junction()
            or not (RELEASE/"python/python.exe").is_file()):
        raise ValueError("R16_SELECTED_CODE_INSTALLED_RELEASE_REQUIRED")
    if verify_original_installed_handles:
        from scripts.release_selection import NativeInstalledReleaseVerifier
        with NativeInstalledReleaseVerifier().open(spec) as native:
            if (native.get("source_commit") != SOURCE
                    or native.get("artifact_digest") != ARTIFACT_DIGEST
                    or len(native.get("files", [])) != 10549
                    or len(native.get("directories", [])) != 912
                    or any(native.get(k) is not False for k in (
                        "selected", "financial_effects",
                        "provider_connections", "operational_acceptance"))):
                raise ValueError("R16_SELECTED_CODE_NATIVE_ORIGINAL_HANDLE_READBACK_REFUSED")
    return {
        "schema": "ATLAS_R16_SELECTED_NONFINANCIAL_NATIVE_CODE_READBACK_V1",
        "selected_revision": 15,
        "selected_release": SOURCE,
        "selected_native_head": R16_HEAD,
        "selected_native_record_sha256": R16_RECORD_SHA,
        "installed_receipt_sha256": RECEIPT_SHA,
        "installed_artifact_digest": ARTIFACT_DIGEST,
        "native_selection_append_only_chain_verified": True,
        "native_receipt_and_install_ack_verified": True,
        "installed_original_handles_reverified_in_this_call": verify_original_installed_handles,
        "code_selection_accepted": True,
        "financial_clock_operational_accepted": False,
        "provider_source_operational_accepted": False,
        "financial_writer_operational_accepted": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def inspect(*, verify_original_installed_handles=False):
    """Fail-closed PAPER readiness: release-code selection alone is insufficient."""
    code = selected_code(
        verify_original_installed_handles=verify_original_installed_handles)
    roots = inspect_two_lane_native_roots()
    if (roots.get("native_root_total") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or roots.get("financial_inception_verified") is not False
            or roots.get("paper_start_authorized") is not False
            or roots.get("live_trading_authorized") is not False):
        raise ValueError("R16_SELECTED_CODE_PREINCEPTION_NATIVE_ROOTS_CHANGED")
    return {
        "schema": "ATLAS_R16_CODE_SELECTED_PAPER_OFFLINE_READINESS_V1",
        "decision": "NO_GO",
        "selected_code": code,
        "native_existing_root_total": 12,
        "native_financial_account_inception_accepted": False,
        "financial_operating_gates_independently_accepted": 0,
        "financial_operating_gates_total": len(GATES),
        "financial_operating_gates": list(GATES),
        "financial_writer_roles_enrolled": 0,
        "financial_writer_roles_required": 12,
        "independent_current_provider_rights_accepted": False,
        "supervised_paper_session_accepted": False,
        "months_long_soak_accepted": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", required=True)
    parser.add_argument("--verify-all-installed-handles", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(inspect(
        verify_original_installed_handles=args.verify_all_installed_handles),
        sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
