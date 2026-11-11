"""R15 nine-gate financial acceptance evidence inventory, read-only and NO-GO.

Actual financial acceptance is not a source-code feature flag. The selected
R15 offline report has fixed NO_GO/0-of-9 by construction; this independent
diagnostic records the *specific upstream proof readers* still missing for each
gate. Only independently accepted native/operator/provider/financial readers
may ever promote a gate in a separate future runtime controller.

All inputs originate from actual installed Windows/native readbacks. This module
deliberately cannot promote a gate from injected summaries, unsigned JSON,
historical research or disposable process tests. No account files are opened
for writing, no NTP/provider access, paper orders or installed release writes.
"""
import json

from scripts.observation_runtime import atlas_r15_paper_offline_commissioning as r15
from scripts.observation_runtime.personal_native_commissioning_inventory import (
    inspect as native_inventory,
)
from scripts.observation_runtime.quality_dips_source_inventory import (
    inspect as qd_source_inventory,
)
from scripts.observation_runtime.hyperliquid_native_preflight import (
    inspect as hl_inventory,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.windows.atlas_paper_readiness_check import inspect as desktop_inspect

SCHEMA = "ATLAS_R15_NINE_FINANCIAL_GATE_SOURCE_REQUIREMENTS_V1"
# Each token is an independently verified *operational* readback that must be
# implemented/accepted upstream; it cannot be supplied as a caller Boolean.
REQUIREMENTS = {
    "B1_HISTORICAL_COMPLETENESS_OR_EPOCH": (
        "ACCEPTED_COMPLETE_SOURCE_HISTORY_OR_NEW_INCEPTION_EPOCH",
    ),
    "C1_OWNERSHIP_AND_FINANCIAL_DRAIN": (
        "TWO_LIVE_INSTALLED_WRITER_HANDLE_AND_LEASE_READBACKS",
        "CORRELATED_BOTH_ACCOUNT_FINANCIAL_STOP_AND_DRAIN",
    ),
    "D1_TRUSTED_STORAGE_AUTHORITY_CLOCK": (
        "EXACT_NATIVE_BOTH_ACCOUNT_ENROLLMENTS",
        "VALID_CURRENT_OPERATOR_ACTIVATION_AND_LEASE",
        "CONTINUOUS_SELECTED_RELEASE_FINANCIAL_UTC",
        "NATIVE_DURABLE_CUSTODY_AND_LEDGER_ACCEPTANCE",
    ),
    "E1_PROVIDER_RIGHTS_AND_SUPERVISED_SESSION": (
        "ACCOUNT_SPECIFIC_PERMITTED_ALPACA_IEX_AND_HYPERLIQUID_FEEDS",
        "SUPERVISED_CURRENT_MARKET_SOURCE_PUBLISHER",
    ),
    "DESKTOP_OWNED_START_STOP": (
        "CERTIFIED_INSTALLED_DESKTOP_START_AND_STOP_TARGETS",
        "OWNED_QD_AND_HL_FLAT_ACKNOWLEDGED_SHUTDOWN",
    ),
    "MARKET_AND_ACCOUNT_COVERAGE": (
        "PERMITTED_FULL_EQUITY_ETF_DISCOVERY_AND_CURRENT_QUOTES",
        "HYPERLIQUID_PAPER_PERPETUAL_COVERAGE",
        "TWO_ACCEPTED_SIMULATED_ACCOUNT_IDENTITIES",
    ),
    "RESTART_AND_RECONCILIATION": (
        "NATIVE_BOTH_ACCOUNT_LEDGER_COLD_RESTART_REPLAY",
        "DURABLE_STOP_RECEIPT_AND_ZERO_UNSETTLED_ENTRIES",
    ),
    "SUPERVISED_END_TO_END": (
        "ACCEPTED_SIMULATED_ORDERS_RISK_LEDGER_AND_FLATTEN",
        "TWO_LANE_SUPERVISED_SESSION_INDEPENDENT_AUDIT",
    ),
    "EXTENDED_SOAK_ACCEPTANCE": (
        "MULTI_SESSION_PAPER_RUNTIME_AND_RESOURCE_SOAK",
        "INDEPENDENT_COMPLETE_DAILY_PAPER_RECONCILIATION",
    ),
}

# Physical existence / code-only prerequisites are reported separately.
# These facts are NEVER substituted for any item in REQUIREMENTS.
SCREENED = (
    "SELECTED_R15_NATIVE_CODE",
    "EXISTING_TWO_LANE_NATIVE_STORAGE",
    "TWO_PROVISIONAL_REBOUND_ACCOUNT_MANIFESTS",
    "QD_SOURCE_CUSTODY_DIRECTORY_PRESENT",
    "PERSONAL_ACTIVATION_FILE_CANDIDATE_PRESENT",
    "ACTUAL_NATIVE_ACTIVATION_ACCEPTED",
    "QUALITY_DIPS_CURRENT_PUBLICATION_ACCEPTED",
    "HYPERLIQUID_CURRENT_SOURCE_RIGHTS_ACCEPTED",
    "FINANCIAL_LEDGER_AND_STOP_ACCEPTED",
    "DESKTOP_FINANCIAL_START_STOP_CERTIFIED",
)


def evaluate(*, selected, financial, roots, personal, qd, hl, desktop, handoff):
    """Strict snapshot, never dynamically treat source presence as acceptance."""
    if (type(selected) is not dict or selected.get("revision") != 14
            or selected.get("selected_native_head") != r15.SELECTED_HEAD
            or selected.get("selected_native_record_sha256") != r15.SELECTED_SHA
            or selected.get("installed_receipt_sha256") != r15.RECEIPT_SHA
            or selected.get("financial_authority") is not False
            or type(financial) is not dict
            or financial.get("selected_code_identity") != selected
            or financial.get("selected_native_release") != "R15"
            or financial.get("decision") != "NO_GO"
            or financial.get("paper_start_authorized") is not False
            or financial.get("financial_operating_gates_independently_accepted") != 0
            or financial.get("financial_operating_gates_total") != 9
            or len(financial.get("gates",[])) != 9
            or [g.get("gate") for g in financial["gates"]] != list(REQUIREMENTS)
            or any(g.get("status") != "NOT_INDEPENDENTLY_ACCEPTED"
                   or g.get("accepted") is not False
                   for g in financial["gates"])):
        raise ValueError("R15_FINANCIAL_INVENTORY_SELECTED_NO_GO_PROOF_REQUIRED")
    if (type(roots) is not dict
            or roots.get("schema") != "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("existing_empty_root_namespaces") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or roots.get("operator_account_enrollment_verified") is not False
            or roots.get("writer_ownership_verified") is not False
            or roots.get("native_activation_record_verified") is not False):
        raise ValueError("R15_FINANCIAL_INVENTORY_EXISTING_NATIVE_ROLLUP_REFUSED")
    if (type(personal) is not dict
            or personal.get("schema") != "ATLAS_PERSONAL_NATIVE_COMMISSIONING_INVENTORY_V1"
            or personal.get("native_activation_verified") is not False
            or personal.get("account_enrollment_verified") is not False
            or personal.get("paper_start_authorized") is not False
            or type(personal.get("ordinary_activation_file_candidates")) is not list
            or not all(type(name) is str for name in personal["ordinary_activation_file_candidates"])
            or personal.get("personal_parent_present") is not True):
        raise ValueError("R15_FINANCIAL_INVENTORY_PERSONAL_ACTIVATION_REFUSED")
    if (type(qd) is not dict
            or qd.get("schema") != "ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1"
            or qd.get("operational_publication_verified") is not False
            or type(hl) is not dict
            or hl.get("schema") != "ATLAS_HYPERLIQUID_NATIVE_PREFLIGHT_V1"
            or hl.get("native_writer_ownership") != "NOT_INDEPENDENTLY_VERIFIED"
            or hl.get("provider_rights_and_current_market_data") != "NOT_INDEPENDENTLY_VERIFIED"
            or hl.get("paper_startup_authorized") is not False
            or type(desktop) is not dict
            or desktop.get("schema") != "ATLAS_PAPER_DESKTOP_READINESS_V1"
            or desktop.get("decision") != "NO_GO"
            or desktop.get("paper_startup_authorized") is not False
            or type(desktop.get("desktop")) is not dict
            or type(handoff) is not dict
            or handoff.get("schema") !=
                "ATLAS_R15_TWO_ACCOUNT_UNAPPROVED_REBIND_HANDOFF_V1"
            or handoff.get("selected_r15_artifact_digest") != r15.ARTIFACT
            or handoff.get("native_root_count_handle_verified") != 12
            or handoff.get("account_enrollment_accepted") is not False
            or handoff.get("both_financial_inceptions_published") is not False
            or handoff.get("paper_start_authorized") is not False):
        raise ValueError("R15_FINANCIAL_INVENTORY_CURRENT_SOURCE_DESKTOP_OR_DRAFT_REFUSED")
    from scripts.observation_runtime.personal_existing_native_resource_evidence import ROLES
    if (set(roots.get("lanes", {})) != {"QUALITY_DIPS", "HYPERLIQUID"}
            or set(handoff.get("accounts",{})) != {"QUALITY_DIPS", "HYPERLIQUID"}):
        raise ValueError("R15_FINANCIAL_INVENTORY_EXACT_TWO_LANE_SCOPE_REQUIRED")
    for lane in ("QUALITY_DIPS","HYPERLIQUID"):
        observed = roots["lanes"][lane]["roots"]
        enrolled = handoff["accounts"][lane]["provisional_r15_native_enrollment_unaccepted"]
        if (set(observed) != set(ROLES)
                or set(enrolled.get("resources",{})) != set(ROLES)
                or enrolled.get("writers") is not None
                or enrolled.get("acceptance_id") is not None
                or enrolled.get("release_digest") != r15.ARTIFACT):
            raise ValueError("R15_FINANCIAL_INVENTORY_NATIVE_ENROLLMENT_NOT_YET_ACCEPTED")
        for role in ROLES:
            if (enrolled["resources"][role].get("native_id") != observed[role].get("native_id")
                    or enrolled["resources"][role].get("path") != observed[role].get("path")
                    or observed[role].get("native_identity_verified") is not True):
                raise ValueError("R15_FINANCIAL_INVENTORY_ROOT_HANDLE_MISMATCH")

    screened = {
        "SELECTED_R15_NATIVE_CODE":True,
        "EXISTING_TWO_LANE_NATIVE_STORAGE":True,
        "TWO_PROVISIONAL_REBOUND_ACCOUNT_MANIFESTS":True,
        "QD_SOURCE_CUSTODY_DIRECTORY_PRESENT":qd.get("source_parent_present") is True,
        "PERSONAL_ACTIVATION_FILE_CANDIDATE_PRESENT":
            bool(personal["ordinary_activation_file_candidates"]),
        "ACTUAL_NATIVE_ACTIVATION_ACCEPTED":False,
        "QUALITY_DIPS_CURRENT_PUBLICATION_ACCEPTED":False,
        "HYPERLIQUID_CURRENT_SOURCE_RIGHTS_ACCEPTED":False,
        "FINANCIAL_LEDGER_AND_STOP_ACCEPTED":False,
        "DESKTOP_FINANCIAL_START_STOP_CERTIFIED":False,
    }
    assert set(screened) == set(SCREENED)
    gates = [{
        "gate":name,
        "status":"BLOCKED_INDEPENDENT_NATIVE_FINANCIAL_ACCEPTANCE_MISSING",
        "accepted":False,
        "required_independent_readbacks":list(requirements),
        "independent_readbacks_accepted":0,
        "technical_implementation_or_directory_presence_is_not_acceptance":True,
    } for name,requirements in REQUIREMENTS.items()]
    return {
        "schema":SCHEMA,
        "decision":"NO_GO",
        "source_release":"R15",
        "selected_native_head":r15.SELECTED_HEAD,
        "current_native_candidate_screen":screened,
        "native_candidate_preconditions_present":sum(screened.values()),
        "native_candidate_screen_count":len(screened),
        "unaccepted_financial_gate_readbacks":[
            token for values in REQUIREMENTS.values() for token in values],
        "financial_gate_acceptance_authority_installed":False,
        "financial_gates":gates,
        "independently_accepted_gate_count":0,
        "independently_accepted_gate_total":len(REQUIREMENTS),
        "financial_gate_evidence_can_be_supplied_as_unsigned_json":False,
        "paper_start_authorized":False,
        "real_money_trading_authorized":False,
        "financial_writes":0,
        "provider_requests":0,
    }


def inspect():
    from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
        inspect as inspect_handoff,
    )
    # No document or operator-provided witness can force PASS: every port is
    # an independent read-only implementation in the current source tree.
    return evaluate(
        selected=r15.selected_code(),
        financial=r15.inspect(),
        roots=inspect_two_lane_native_roots(),
        personal=native_inventory(),
        qd=qd_source_inventory(),
        hl=hl_inventory(),
        desktop=desktop_inspect(root=r15.ROOT),
        handoff=inspect_handoff(),
    )


if __name__ == "__main__":
    print(json.dumps(inspect(),sort_keys=True,indent=2))
