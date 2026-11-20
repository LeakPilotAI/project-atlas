"""Current SELECTED R16 nine-gate commissioning inventory; read-only NO-GO.

This is the R16 replacement for the historic R15-only nine-gate viewer.
It consumes genuine current native selected-R16 and two-lane draft readers,
real original Windows 12-root identities, existing source custody/readiness,
and the installed desktop safety inspector. It NEVER infers an operational
acceptance from directory/file existence, review-only drafts, parked Jobs,
an HTTP probe or a user-supplied JSON claim.

Gate ACCEPTED can only come from independent, future *financial* issuers and
operational account/Stop/source readers. None exists in this viewer.
No clock/NTP network request, provider call, account publication or order.
"""
from __future__ import annotations

import argparse
import json

from app.services.paper_financial_replay import digest, validate_manifest
from app.services.paper_daily_report import validate_scope
from scripts.observation_runtime.atlas_r15_nine_gate_evidence_inventory import (
    REQUIREMENTS,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    ARTIFACT_DIGEST, RECEIPT_SHA, R16_HEAD, R16_RECORD_SHA, SOURCE,
    GATES, ROOT, selected_code, inspect as selected_inspect,
)
from scripts.observation_runtime.atlas_r16_two_account_enrollment_handoff import (
    SCHEMA as DRAFT_SCHEMA, HISTORICAL_R15_HANDOFF_DIGEST,
    inspect as draft_inspect,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_commissioning_inventory import (
    inspect as personal_inspect,
)
from scripts.observation_runtime.quality_dips_source_inventory import (
    inspect as quality_source_inspect,
)
from scripts.observation_runtime.hyperliquid_native_preflight import (
    inspect as hyperliquid_inspect,
)
from scripts.windows.atlas_paper_readiness_check import (
    inspect as desktop_inspect,
)

SCHEMA = "ATLAS_R16_CURRENT_SELECTED_NINE_FINANCIAL_GATE_REQUIREMENTS_V1"
SCREENED = (
    "CURRENT_R16_NATIVE_SELECTED_CODE",
    "EXISTING_TWO_LANE_EMPTY_NATIVE_ROOTS",
    "R16_TWO_REBOUND_PROVISIONAL_ACCOUNT_MANIFESTS",
    "QD_SOURCE_CUSTODY_PARENT_PRESENT",
    "PERSONAL_ACTIVATION_FILE_CANDIDATE_PRESENT",
    "ACTUAL_NATIVE_ACTIVATION_ACCEPTED",
    "CURRENT_QD_OPERATIONAL_SOURCE_ACCEPTED",
    "CURRENT_HL_PROVIDER_RIGHTS_ACCEPTED",
    "FINANCIAL_LEDGER_AND_OWNED_STOP_ACCEPTED",
    "DESKTOP_FINANCIAL_START_STOP_CERTIFIED",
)
PINNED_PROPOSAL_DIGEST = (
    "57c3dc502cb5a5e70885bf016364ea1746b47a6f5b2027169d8ee77e066678db"
)
PINNED_MANIFESTS = {
    "QUALITY_DIPS": "778380e25decdfd63f913754c160146b0134bcc966864b52a2250d4530769067",
    "HYPERLIQUID": "ce4cd1dc55c5a51ea32e93f17c99ec8adabb1ff5d289a454472a2a8f2faaefbb",
}


def evaluate(*, selected, readiness, draft, roots, personal, qd, hl, desktop):
    """Fail closed for contradictory or 'promoted' review-only evidence."""
    if (type(selected) is not dict
            or selected.get("schema") !=
                "ATLAS_R16_SELECTED_NONFINANCIAL_NATIVE_CODE_READBACK_V1"
            or selected.get("selected_revision") != 15
            or selected.get("selected_release") != SOURCE
            or selected.get("selected_native_head") != R16_HEAD
            or selected.get("selected_native_record_sha256") != R16_RECORD_SHA
            or selected.get("installed_receipt_sha256") != RECEIPT_SHA
            or selected.get("installed_artifact_digest") != ARTIFACT_DIGEST
            or selected.get("native_selection_append_only_chain_verified") is not True
            or selected.get("native_receipt_and_install_ack_verified") is not True
            or selected.get("code_selection_accepted") is not True
            or any(selected.get(k) is not False for k in (
                "financial_clock_operational_accepted",
                "provider_source_operational_accepted",
                "financial_writer_operational_accepted",
                "paper_start_authorized", "live_trading_authorized"))):
        raise ValueError("R16_GATE_SELECTED_NONFINANCIAL_NATIVE_CODE_REQUIRED")
    if (type(readiness) is not dict
            or readiness.get("schema") !=
                "ATLAS_R16_CODE_SELECTED_PAPER_OFFLINE_READINESS_V1"
            or readiness.get("selected_code") != selected
            or readiness.get("decision") != "NO_GO"
            or readiness.get("native_existing_root_total") != 12
            or readiness.get("financial_operating_gates_total") != len(GATES)
            or readiness.get("financial_operating_gates") != list(GATES)
            or readiness.get("financial_operating_gates_independently_accepted") != 0
            or readiness.get("financial_writer_roles_enrolled") != 0
            or readiness.get("financial_writer_roles_required") != 12
            or any(readiness.get(k) is not False for k in (
                "native_financial_account_inception_accepted",
                "independent_current_provider_rights_accepted",
                "supervised_paper_session_accepted", "months_long_soak_accepted",
                "paper_start_authorized", "live_trading_authorized"))):
        raise ValueError("R16_GATE_CURRENT_SELECTED_OFFLINE_NO_GO_REQUIRED")
    if (type(draft) is not dict
            or digest(draft) != PINNED_PROPOSAL_DIGEST
            or draft.get("schema") != DRAFT_SCHEMA
            or draft.get("status") !=
                "R16_TWO_LANE_CURRENT_CODE_PROPOSAL_ONLY_UNACCEPTED"
            or draft.get("selected_r16_source_commit") != SOURCE
            or draft.get("selected_r16_artifact_digest") != ARTIFACT_DIGEST
            or draft.get("selected_native_revision") != 15
            or draft.get("selected_native_head") != R16_HEAD
            or draft.get("selected_native_record_sha256") != R16_RECORD_SHA
            or draft.get("historical_r15_rebind_digest") !=
                HISTORICAL_R15_HANDOFF_DIGEST
            or draft.get("native_original_empty_root_count_verified") != 12
            or draft.get("account_count") != 2
            or set(draft.get("accounts", {})) != set(PINNED_MANIFESTS)
            or draft.get("actual_financial_writer_roles_enrolled") != 0
            or draft.get("native_financial_inceptions_published") != 0
            or draft.get("accepted_financial_operating_gates") != 0
            or draft.get("filesystem_mutations") != 0
            or draft.get("provider_requests") != 0
            or draft.get("financial_paper_start_authorized") is not False
            or draft.get("live_trading_authorized") is not False):
        raise ValueError("R16_GATE_CURRENT_R16_TWO_ACCOUNT_UNACCEPTED_DRAFT_REQUIRED")
    if (type(roots) is not dict
            or roots.get("schema") !=
                "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("existing_empty_root_namespaces") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or roots.get("filesystem_writes") != 0
            or roots.get("network_requests") != 0
            or set(roots.get("lanes", {})) != set(PINNED_MANIFESTS)
            or any(roots.get(k) is not False for k in (
                "operator_account_enrollment_verified", "writer_ownership_verified",
                "native_activation_record_verified", "financial_inception_verified",
                "paper_start_authorized", "live_trading_authorized"))):
        raise ValueError("R16_GATE_TWELVE_ORIGINAL_EMPTY_NATIVE_ROOTS_REQUIRED")
    identities = set()
    for lane, pinned in PINNED_MANIFESTS.items():
        account = draft["accounts"][lane]
        manifest = account["provisional_r16_parameters"]
        enrollment = account["provisional_r16_enrollment_unaccepted"]
        report = account["provisional_r16_report_scope_unaccepted"]
        if (account.get("provisional_r16_manifest_digest") != pinned
                or digest(manifest) != pinned
                or enrollment.get("release_digest") != ARTIFACT_DIGEST
                or enrollment.get("inception_digest") != pinned
                or enrollment.get("writers") is not None
                or enrollment.get("acceptance_id") is not None
                or manifest.get("opening_cash") != "1000"
                or manifest.get("timezone") != (
                    "America/New_York" if lane == "QUALITY_DIPS" else "UTC")
                or account.get("real_writer_roster_present") is not False
                or account.get("accepted_operator_inception") is not False
                or account.get("financial_inception_published") is not False
                or account.get("provider_source_rights_accepted") is not False
                or account.get("opening_timestamp_historical_not_current") is not True
                or set(enrollment.get("resources", {})) != set(ROLES)
                or set(roots["lanes"][lane].get("roots", {})) != set(ROLES)
                or enrollment.get("epoch") != roots["lanes"][lane].get("epoch")
                or report.get("policy_digest") != pinned):
            raise ValueError("R16_GATE_UNACCEPTED_NATIVE_ACCOUNT_SCOPE_REQUIRED")
        validate_manifest(manifest)
        validate_scope(report, manifest)
        for role in ROLES:
            actual = roots["lanes"][lane]["roots"][role]
            expected = enrollment["resources"][role]
            if (expected.get("native_id") != actual.get("native_id")
                    or expected.get("path") != actual.get("path")
                    or actual.get("native_identity_verified") is not True
                    or actual.get("existing_empty_namespace_verified") is not True
                    or tuple(actual["native_id"]) in identities):
                raise ValueError("R16_GATE_ORIGINAL_NATIVE_ROOT_IDENTITY_DRIFT")
            identities.add(tuple(actual["native_id"]))
    if len(identities) != 12:
        raise ValueError("R16_GATE_TWELVE_DISTINCT_NATIVE_HANDLES_REQUIRED")
    if (type(personal) is not dict
            or personal.get("schema") !=
                "ATLAS_PERSONAL_NATIVE_COMMISSIONING_INVENTORY_V1"
            or personal.get("personal_parent_present") is not True
            or type(personal.get("ordinary_activation_file_candidates")) is not list
            or any(type(x) is not str for x in
                   personal["ordinary_activation_file_candidates"])
            or any(personal.get(k) is not False for k in (
                "native_activation_verified", "account_enrollment_verified",
                "financial_inception_authorized", "paper_start_authorized"))):
        raise ValueError("R16_GATE_NATIVE_OPERATOR_ACTIVATION_UNVERIFIED")
    if (type(qd) is not dict
            or qd.get("schema") != "ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1"
            or qd.get("operational_publication_verified") is not False
            or type(hl) is not dict
            or hl.get("schema") != "ATLAS_HYPERLIQUID_NATIVE_PREFLIGHT_V1"
            or hl.get("provider_rights_and_current_market_data") !=
               "NOT_INDEPENDENTLY_VERIFIED"
            or hl.get("native_writer_ownership") !=
               "NOT_INDEPENDENTLY_VERIFIED"
            or hl.get("hyperliquid_native_account_inception") !=
               "NOT_INDEPENDENTLY_VERIFIED"
            or hl.get("paper_startup_authorized") is not False
            or hl.get("live_trading_authorized") is not False
            or type(desktop) is not dict
            or desktop.get("schema") != "ATLAS_PAPER_DESKTOP_READINESS_V1"
            or desktop.get("decision") != "NO_GO"
            or desktop.get("unverified_gate_count") != 9
            or desktop.get("paper_startup_authorized") is not False
            or desktop.get("live_trading_authorized") is not False
            or set(desktop.get("acceptance", {})) != set(GATES)
            or any(value != "NOT_INDEPENDENTLY_VERIFIED"
                   for value in desktop["acceptance"].values())):
        raise ValueError("R16_GATE_SOURCE_HL_OR_DESKTOP_UNACCEPTED_READBACK_REQUIRED")

    screen = {
        "CURRENT_R16_NATIVE_SELECTED_CODE": True,
        "EXISTING_TWO_LANE_EMPTY_NATIVE_ROOTS": True,
        "R16_TWO_REBOUND_PROVISIONAL_ACCOUNT_MANIFESTS": True,
        "QD_SOURCE_CUSTODY_PARENT_PRESENT": qd.get("source_parent_present") is True,
        "PERSONAL_ACTIVATION_FILE_CANDIDATE_PRESENT":
            bool(personal["ordinary_activation_file_candidates"]),
        "ACTUAL_NATIVE_ACTIVATION_ACCEPTED": False,
        "CURRENT_QD_OPERATIONAL_SOURCE_ACCEPTED": False,
        "CURRENT_HL_PROVIDER_RIGHTS_ACCEPTED": False,
        "FINANCIAL_LEDGER_AND_OWNED_STOP_ACCEPTED": False,
        "DESKTOP_FINANCIAL_START_STOP_CERTIFIED": False,
    }
    assert set(screen) == set(SCREENED)
    gates = [{
        "gate": gate,
        "status": "BLOCKED_INDEPENDENT_FINANCIAL_ACCEPTANCE_MISSING",
        "accepted": False,
        "required_independent_readbacks": list(REQUIREMENTS[gate]),
        "independent_readbacks_accepted": 0,
        "code_or_review_only_draft_is_not_operational_acceptance": True,
    } for gate in GATES]
    return {
        "schema": SCHEMA,
        "decision": "NO_GO",
        "source_release": "R16",
        "selected_revision": 15,
        "selected_native_head": R16_HEAD,
        "selected_record_sha256": R16_RECORD_SHA,
        "selected_release_artifact_digest": ARTIFACT_DIGEST,
        "historical_r15_readback_used_for_current_selection": False,
        "unaccepted_two_account_draft_digest": PINNED_PROPOSAL_DIGEST,
        "native_original_empty_roots_verified": 12,
        "candidate_screen": screen,
        "candidate_preconditions_present": sum(screen.values()),
        "candidate_screen_count": len(screen),
        "financial_gates": gates,
        "independently_accepted_gate_count": 0,
        "independently_accepted_gate_total": len(GATES),
        "missing_independent_financial_readbacks": [
            token for gate in GATES for token in REQUIREMENTS[gate]],
        "missing_independent_financial_readback_count":
            sum(len(REQUIREMENTS[gate]) for gate in GATES),
        "financial_gate_issuer_present": False,
        "unsigned_operator_or_provider_json_can_authorize": False,
        "paper_start_authorized": False,
        "real_money_trading_authorized": False,
        "native_financial_account_writes": 0,
        "provider_requests": 0,
    }


def inspect(*, verify_installed_handles=False):
    """Genuine current selected R16 and source/desktop readers, no network."""
    selected = selected_code(
        verify_original_installed_handles=verify_installed_handles)
    readiness = selected_inspect()
    roots = inspect_two_lane_native_roots()
    draft = draft_inspect()
    return evaluate(
        selected=selected, readiness=readiness, draft=draft, roots=roots,
        personal=personal_inspect(), qd=quality_source_inspect(),
        hl=hyperliquid_inspect(), desktop=desktop_inspect(root=ROOT),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", required=True)
    parser.add_argument("--verify-installed-file-handles", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(inspect(
        verify_installed_handles=args.verify_installed_file_handles),
        indent=2, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
