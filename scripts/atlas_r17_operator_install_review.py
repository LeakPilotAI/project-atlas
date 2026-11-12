"""Read-only R17-r06 operator decision review; never grants installation.

Resolves the exact selected R16 predecessor, frozen R17 archive and native
destination, host CPU guard, code-only authority limits, and a SID fingerprint.
No approval JSON is generated or signed, no APPROVAL_SHA256 is changed, no
clock qualification/network is attempted, and no financial operating gates
are marked accepted. The actual native installer requires a fresh operator
decision pinned independently after review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

from scripts import atlas_r17_code_only_installer as installer
from scripts import atlas_r17_code_only_selection_publisher as selector

SCHEMA = "ATLAS_R17_CODE_ONLY_OPERATOR_DECISION_REVIEW_PACKET_V1"


def operator_review():
    from scripts.volume_inspector.windows_output import current_sid

    approved_code = installer.inspect()
    selected = installer.require_selected_r16()
    original_roots = installer.require_original_financial_roots_untouched()
    pinned_cpu_guard = installer.require_cpu_budget_pinned()
    if (selected is not True or original_roots is not True
            or pinned_cpu_guard is not True
            or approved_code["status"] !=
               "FROZEN_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION"
            or approved_code["installed"] is not False
            or approved_code["separate_approval_pinned"] is not False
            or installer.APPROVAL_SHA256 is not None
            or selector.APPROVAL_SHA256 is not None
            or os.path.lexists(selector.handoff.SELECTION_ROOT / "r0016.json")
            or os.path.lexists(selector.handoff.SELECTION_ROOT / "r0016.pending")
            or approved_code["source_commit"] != installer.SOURCE
            or approved_code["archive_sha256"] != installer.ARCHIVE_SHA
            or approved_code["native_target"] != str(installer.TARGET)
            or approved_code["planned_native_files"] != 10610
            or approved_code["planned_bytes"] != 264583312):
        raise ValueError("R17_CODE_ONLY_OPERATOR_REVIEW_PRECONDITIONS_REFUSED")
    sid = current_sid()
    if type(sid) is not str or not sid.startswith("S-1-"):
        raise ValueError("R17_CODE_ONLY_LOCAL_WINDOWS_SID_REQUIRED")
    try:
        from scripts.observation_runtime.atlas_r16_nine_gate_evidence_inventory import (
            inspect as financial_gate_inspect,
        )
        financial = financial_gate_inspect()
    except (OSError, ValueError, KeyError):
        raise ValueError("R17_CODE_ONLY_FINANCIAL_GATE_STATUS_UNKNOWN") from None
    if (financial["source_release"] != "R16"
            or financial["selected_revision"] != 15
            or financial["independently_accepted_gate_count"] != 0
            or financial["financial_gate_issuer_present"] is not False
            or financial["paper_start_authorized"] is not False):
        raise ValueError("R17_CODE_ONLY_OPERATOR_REVIEW_FINANCIAL_STATUS_CHANGED")
    return {
        "schema": SCHEMA,
        "status": "PREPARED_FOR_DISTINCT_OPERATOR_DECISION_NOT_APPROVED",
        "exact_operation": installer.OPERATION,
        "exact_scope": installer.SCOPE,
        "source_commit": installer.SOURCE,
        "archive_sha256": installer.ARCHIVE_SHA,
        "source_inventory_sha256": installer.INVENTORY_SHA,
        "dependency_inventory_sha256": installer.DEPENDENCY_INVENTORY_SHA256,
        "installer_source_sha256": installer.source_digest_for_approval(),
        "cpu_guard_sha256": installer.CPU_GUARD_SHA256,
        "windows_operator_sid_fingerprint_sha256":
            hashlib.sha256(sid.encode("utf-8")).hexdigest(),
        "selected_native_predecessor": "R16",
        "selected_predecessor_head": installer.PREDECESSOR_HEAD,
        "selected_predecessor_record_sha256": installer.PREDECESSOR_RECORD_SHA,
        "selected_predecessor_artifact_digest": installer.PREDECESSOR_ARTIFACT,
        "proposed_unselected_native_target": str(installer.TARGET),
        "proposed_installation_receipt": str(installer.RECEIPT),
        "source_files": approved_code["planned_source_files"],
        "planned_native_files": approved_code["planned_native_files"],
        "planned_bytes": approved_code["planned_bytes"],
        "installer_max_logical_processors": 2,
        "host_busy_threshold_percent": 70,
        "code_only_create_and_verify": True,
        "native_release_selection_requested": False,
        "operator_one_shot_authorization_present": False,
        "new_native_release_installed": False,
        "financial_authority": False,
        "account_creation_or_mutation": False,
        "provider_or_broker_connections": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "native_financial_operating_gates_accepted": 0,
        "next_step_requires_distinct_explicit_operator_action": True,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inspect", action="store_true", required=True)
    p.parse_args(argv)
    print(json.dumps(operator_review(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
