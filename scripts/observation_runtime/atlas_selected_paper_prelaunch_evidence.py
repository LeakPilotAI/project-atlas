"""Read-only ORIGINAL selected R20 PAPER prelaunch evidence, not a Start issuer.

Runs with the EXACT selected original installed Windows Python and modules
from that release. A newer workspace source file cannot be adopted as an
installed operational issuer. The original 9-gate desktop checker is a
deliberately constant NO_GO sentinel, not a 0..9 progress counter.

No journals, activation, PAPER account, workspace installation, API keys, NTP
network calls, financial leases, trading orders, or direct HTML/UI scraping.
"""
from __future__ import annotations

import json
import ntpath
import os
import re
import sys
from pathlib import Path

from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_financial_release_origin import (
    require_selected_native_origin,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    SELECTOR_NATIVE,
)
from scripts.release_selection import validate_spec
from scripts.release_selection_store import NativeSelectionStore

SCHEMA = "ATLAS_SELECTED_NATIVE_REAL_PAPER_PRELAUNCH_READONLY_V1"
SELECTOR = r"D:\AtlasRuntime\selection"
ROOT = Path("D:/AtlasRuntime/releases")
LATEST_QD_WATCH = "scripts/observation_runtime/personal_selected_qd_sec_watch_issuer.py"
QDSOURCE = "scripts/observation_runtime/personal_source_epoch_readback.py"
ORIGINAL_GATE_COUNT = 9


def _classify(*, origin, roots, newer_watch, newer_epoch):
    """Explanation only. No caller-provided assertion can grant financial use."""
    if (
        type(origin) is not dict
        or origin.get("schema")
        != "ATLAS_NATIVE_SELECTED_FINANCIAL_ACTIVATION_SOURCE_BINDING_V1"
        or origin.get("installed_source_and_process_path_bound") is not True
        or origin.get("selected_artifact_digest_bound") is not True
        or type(roots) is not dict
        or roots.get("native_root_total") != 12
        or roots.get("native_root_ids_verified") != 12
        or type(roots.get("existing_empty_root_namespaces")) is not int
        or not 0 <= roots["existing_empty_root_namespaces"] <= 12
        or type(newer_watch) is not bool
        or type(newer_epoch) is not bool
    ):
        raise ValueError("PRELAUNCH_EXACT_NATIVE_EVIDENCE_REQUIRED")
    remaining_empty = roots["existing_empty_root_namespaces"]
    clean = roots.get("all_twelve_distinct_and_empty") is True and remaining_empty == 12
    state = (
        "PREINCEPTION_EMPTY_NO_FINANCIAL_COMMISSIONING"
        if clean else "NONEMPTY_OR_UNKNOWN_REQUIRES_INDEPENDENT_NATIVE_RECONCILIATION"
    )
    return {
        "schema": SCHEMA,
        "source_origin_native_verified": True,
        "native_original_root_count": 12,
        "native_empty_root_count": remaining_empty,
        "native_roots_preinception_empty": clean,
        "native_financial_state": state,
        "native_original_preinception_journals_verified": False,
        "native_simulated_account_inceptions_verified": False,
        "postinception_operator_activation_verified": False,
        "new_watch_only_source_module_installed": newer_watch,
        "new_source_epoch_readback_module_installed": newer_epoch,
        "new_watch_source_is_not_executable_market_issuer": True,
        "new_source_epoch_readback_is_not_financial_reader_switch": True,
        "quality_dips_127_publication_rollover_operationally_accepted": False,
        "hyperliquid_signed_settlement_oracle_accepted": False,
        "original_stop_first_financial_acceptance_verified": False,
        "legacy_nine_gate_checker_is_constant_no_go_sentinel": True,
        "legacy_checker_gate_count": ORIGINAL_GATE_COUNT,
        "legacy_checker_is_a_progress_percentage": False,
        "ready_to_issue_financial_first_journals": False,
        "financial_journals_created_by_this_report": False,
        "paper_startup_authorized": False,
        "live_trading_authorized": False,
        "first_safe_commissioning_work": (
            "ACCEPT_FREE_DATA_POLICY_VALUATION_ORIGINAL_ISSUER_AND_AUDITED_NEXT_CODE_RELEASE"
            if clean else
            "EXACT_NATIVE_READBACK_RECONCILIATION_REQUIRED_NO_CREATE_ONLY_RETRY"
        ),
    }


def inspect():
    if os.name != "nt":
        raise ValueError("PRELAUNCH_NATIVE_WINDOWS_ONLY")
    store = NativeSelectionStore(
        root=SELECTOR, native_root=list(SELECTOR_NATIVE),
    )
    try:
        with store.locked():
            records = store.records()
            if type(records) is not list or not records:
                raise ValueError("PRELAUNCH_ORIGINAL_SELECTION_REQUIRED")
            spec = validate_spec(records[-1].get("selected"), "WINDOWS_LOCAL")
            release = Path(spec["root"])
            expected = release / "python/python.exe"
            if (
                release.parent != ROOT
                or not re.fullmatch(r"[0-9a-f]{40}", release.name)
                or ntpath.normcase(ntpath.normpath(str(sys.executable)))
                != ntpath.normcase(ntpath.normpath(str(expected)))
            ):
                raise ValueError("PRELAUNCH_SELECTED_INSTALLED_INTERPRETER_REQUIRED")
            from scripts.release_selection import NativeInstalledReleaseVerifier

            with NativeInstalledReleaseVerifier().open(spec) as proof:
                if (
                    proof.get("source_commit") != release.name
                    or proof.get("artifact_digest") != spec["artifact_digest"]
                ):
                    raise ValueError("PRELAUNCH_ORIGINAL_RELEASE_CONTENT_REFUSED")
            artifact = spec["artifact_digest"]
    finally:
        store.close()
    origin = require_selected_native_origin(release_digest=artifact)
    roots = inspect_two_lane_native_roots()
    # An untracked workspace copy is not an installed native source. The
    # installed-release readback above pins every declared original file.
    watch_path = release / LATEST_QD_WATCH
    epoch_path = release / QDSOURCE
    result = _classify(
        origin=origin,
        roots=roots,
        newer_watch=watch_path.is_file() and not watch_path.is_symlink(),
        newer_epoch=epoch_path.is_file() and not epoch_path.is_symlink(),
    )
    result["selected_original_code_release"] = release.name
    result["selected_original_artifact_digest"] = artifact
    result["original_selected_code_is_complete_current_workspace"] = False
    return result


def main():
    try:
        result = inspect()
    except (OSError, ValueError, KeyError, TypeError):
        result = {
            "schema": SCHEMA,
            "status": "ORIGINAL_NATIVE_READBACK_REFUSED",
            "paper_startup_authorized": False,
            "live_trading_authorized": False,
            "financial_journals_created_by_this_report": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
