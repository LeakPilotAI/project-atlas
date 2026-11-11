"""R15 actual installed technical milestones versus distinct PAPER financial gates.

Read-only observer, NOT financial readiness authority. R15 legacy offline NO_GO
report intentionally has zero accepted financial gates by construction. This
separate report tracks verifiable Windows prerequisites by *re-running* actual
selected native release, held-root/handle and suspended Job probes. No saved
receipt alone promotes a gate, no provider connection, no financial file write,
no persistent writer or automatic startup.
"""
import json
from pathlib import Path

from scripts.observation_runtime import atlas_r15_paper_offline_commissioning as r15
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    inspect as handoff_inspect,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    inspect_two_lane_native_root_handles,
)
from scripts.observation_runtime.atlas_r15_native_job_admission_preflight import (
    inspect as real_job_inspect,
)

SCHEMA = "ATLAS_R15_ACTUAL_WINDOWS_TECHNICAL_MILESTONES_V1"
TECHNICAL_NAMES = (
    "IMMUTABLE_SELECTED_R15_RELEASE",
    "EXACT_INSTALLED_FINANCIAL_SOURCE_PORTS",
    "BOTH_LANES_EXISTING_NATIVE_ROOT_IDENTITIES",
    "TWO_PROVISIONAL_R15_ACCOUNT_MANIFESTS",
    "INSTALLED_R15_HELD_NATIVE_ROOT_HANDLE_CONTINUITY",
    "SUSPENDED_R15_WINDOWS_JOB_ADMISSION_AND_OWNED_TERMINATION",
)
PENDING = (
    "INDEPENDENT_PROVIDER_RIGHTS_AND_CURRENT_MARKET_SOURCES",
    "ACCEPTED_BOTH_LANE_ACTUAL_WRITER_OWNERSHIP_AND_ENROLLMENT",
    "FRESH_ACCEPTED_FINANCIAL_CLOCK_AND_OPERATOR_ACTIVATION",
    "TWO_FINANCIAL_INCEPTIONS_AND_DURABLE_ACCOUNT_LEDGERS",
    "SUPERVISED_BOTH_LANE_PAPER_STOP_FLAT_RESTART_AND_RECONCILIATION",
    "EXTENDED_PAPER_SOAK_ACCEPTANCE",
)


def evaluate(*, selected, ports, roots, handoff, held, job, financial):
    """No authority is derived from any single report; exact cross-check only."""
    required_pins = set(r15.CODE_PINS) | set(r15.PORTS)
    if (type(selected) is not dict
            or selected.get("revision") != 14
            or selected.get("selected_release") != r15.RELEASE.name
            or selected.get("selected_native_head") != r15.SELECTED_HEAD
            or selected.get("selected_native_record_sha256") != r15.SELECTED_SHA
            or selected.get("installed_receipt_sha256") != r15.RECEIPT_SHA
            or selected.get("financial_authority") is not False
            or selected.get("independent_live_financial_clock_lease_accepted") is not False
            or selected.get("native_clock_own_release_source_admitted") is not True
            or type(ports) is not dict or set(ports) != required_pins
            or any(type(row) is not dict
                   or row.get("native_installed_source_present") is not True
                   or type(row.get("native_sha256")) is not str
                   or len(row["native_sha256"]) != 64
                   or any(ch not in "0123456789abcdef" for ch in row["native_sha256"])
                   for row in ports.values())
            or any(ports[p]["native_sha256"] != digest
                   for p,digest in r15.CODE_PINS.items())):
        raise ValueError("R15_MILESTONES_SELECTED_RELEASE_OR_NATIVE_CODE_REFUSED")
    if (type(roots) is not dict
            or type(roots.get("lanes")) is not dict
            or set(roots["lanes"]) != {"HYPERLIQUID", "QUALITY_DIPS"}
            or roots.get("schema") !=
                "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("existing_empty_root_namespaces") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or any(roots.get(flag) is not False for flag in (
                "operator_account_enrollment_verified",
                "writer_ownership_verified",
                "native_activation_record_verified",
                "financial_inception_verified",
                "paper_start_authorized",
                "live_trading_authorized"))):
        raise ValueError("R15_MILESTONES_BOTH_LANE_ROOT_IDENTITIES_REFUSED")
    from scripts.observation_runtime.personal_existing_native_resource_evidence import ROLES
    for lane in ("HYPERLIQUID", "QUALITY_DIPS"):
        role_root = roots["lanes"][lane]
        if (type(role_root) is not dict
                or type(role_root.get("roots")) is not dict
                or set(role_root["roots"]) != set(ROLES)):
            raise ValueError("R15_MILESTONES_EXACT_TWO_LANE_ROOT_ROLES_REFUSED")
        for role in ROLES:
            original = role_root["roots"][role]
            if (type(original) is not dict
                    or type(original.get("native_id")) is not list
                    or len(original["native_id"]) != 3
                    or original.get("native_identity_verified") is not True
                    or original.get("existing_empty_namespace_verified") is not True):
                raise ValueError("R15_MILESTONES_EXACT_NATIVE_ROLE_ID_REFUSED")
    if (type(handoff) is not dict
            or handoff.get("schema") !=
                "ATLAS_R15_TWO_ACCOUNT_UNAPPROVED_REBIND_HANDOFF_V1"
            or handoff.get("status") !=
                "TWO_LANE_R15_STRUCTURAL_REBIND_ONLY_NEVER_ACCEPTED"
            or handoff.get("native_root_count_handle_verified") != 12
            or handoff.get("selected_native_head") != r15.SELECTED_HEAD
            or handoff.get("selected_r15_artifact_digest") != r15.ARTIFACT
            or handoff.get("selected_r15_record_sha256") != r15.SELECTED_SHA
            or set(handoff.get("accounts",{})) != {"HYPERLIQUID","QUALITY_DIPS"}
            or handoff.get("financial_operating_gates_accepted") != 0
            or any(handoff.get(flag) is not False for flag in (
                "account_enrollment_accepted",
                "both_financial_inceptions_published",
                "native_operator_activation_present",
                "native_current_hyperliquid_source_accepted",
                "native_current_quality_dips_source_accepted",
                "paper_start_authorized",
                "live_trading_authorized"))
            or any(item.get("existing_native_root_identity_matched") is not True
                   or item.get("real_enrollment_accepted") is not False
                   or item.get("writer_process_observed_and_leased") is not False
                   or item.get("financial_inception_published") is not False
                   for item in handoff["accounts"].values())):
        raise ValueError("R15_MILESTONES_BOTH_ACCOUNTS_STILL_PROVISIONAL_REQUIRED")
    for lane in ("HYPERLIQUID", "QUALITY_DIPS"):
        account = handoff["accounts"][lane]
        original = roots["lanes"][lane]
        native = account["provisional_r15_native_enrollment_unaccepted"]
        if (native.get("epoch") != original.get("epoch")
                or native.get("release_digest") != r15.ARTIFACT
                or set(native.get("resources",{})) != set(ROLES)):
            raise ValueError("R15_MILESTONES_NATIVE_ACCOUNT_ROOT_SCOPE_REFUSED")
        for role in ROLES:
            a = native["resources"][role]
            b = original["roots"][role]
            if (a.get("path") != b.get("path")
                    or a.get("native_id") != b.get("native_id")):
                raise ValueError("R15_MILESTONES_CROSS_CHECK_ACCOUNT_ROOT_REFUSED")
    if (type(held) is not dict
            or held.get("schema") !=
                "ATLAS_R15_TWO_LANE_SHORT_LIVED_ROOT_HANDLE_PROOF_V1"
            or held.get("status") !=
                "INSTALLED_NATIVE_R15_TWELVE_READ_ONLY_ROOT_HANDLES_RECHECKED"
            or held.get("selected_native_head") != r15.SELECTED_HEAD
            or held.get("native_selected_release") != str(r15.RELEASE)
            or held.get("actual_existing_native_roots_verified") != 12
            or held.get("sample_count_while_process_alive") != 3
            or held.get("child_exited_and_handles_closed") is not True
            or held.get("all_twelve_root_ids_unchanged_after_exit") is not True
            or any(held.get(flag) is not False for flag in (
                "financial_writer_process_enrolled",
                "financial_writer_lease_active",
                "native_paper_account_inception",
                "paper_start_authorized",
                "real_money_order_authorized"))
            or held.get("native_financial_files_written") != 0
            or held.get("market_provider_requests") != 0):
        raise ValueError("R15_MILESTONES_LIVE_NATIVE_HANDLES_REFUSED")
    if (type(job) is not dict
            or job.get("schema") !=
                "ATLAS_R15_REAL_SUSPENDED_JOB_CONTAINMENT_NONFINANCIAL_V1"
            or job.get("selected_native_head") != r15.SELECTED_HEAD
            or job.get("selected_release") != str(r15.RELEASE)
            or job.get("status") != "REAL_SUSPENDED_R15_JOB_CONTAINMENT_REHEARSAL_PASS"
            or job.get("active_children_after_check") != 0
            or any(job.get(k) != 0 for k in (
                "new_financial_accounts", "native_financial_writes",
                "network_requests"))
            or any(job.get(k) is not False for k in (
                "persistent_writer_enrolled",
                "paper_start_authorized", "real_money_orders_authorized"))
            or type(job.get("runs")) is not list or len(job["runs"]) != 2
            or [r.get("mode") for r in job["runs"]] != [
                "NORMAL_EXIT", "OWNED_JOB_STOP"]
            or [r.get("exit_code") for r in job["runs"]] != [0,1]
            or any(r.get("owned_job_active_processes_after_exit") != 0
                   or r.get("assigned_to_real_job_before_resume") is not True
                   or r.get("suspended_identity_checked_before_resume") is not True
                   or r.get("job_kill_on_close_configured") is not True
                   for r in job["runs"])):
        raise ValueError("R15_MILESTONES_REAL_SUSPENDED_JOB_PROOF_REFUSED")
    if (type(financial) is not dict
            or financial.get("schema") !=
                "ATLAS_SELECTED_R15_OFFLINE_FINANCIAL_COMMISSIONING_V1"
            or financial.get("selected_native_release") != "R15"
            or financial.get("selected_code_identity") != selected
            or financial.get("selected_native_financial_port_sources") != ports
            or financial.get("decision") != "NO_GO"
            or financial.get("financial_operating_gates_independently_accepted") != 0
            or financial.get("financial_operating_gates_total") != len(r15.GATES)
            or [g.get("gate") for g in financial.get("gates", [])] != list(r15.GATES)
            or any(g.get("accepted") is not False
                   or g.get("status") != "NOT_INDEPENDENTLY_ACCEPTED"
                   for g in financial["gates"])
            or any(financial.get(k) is not False for k in (
                "native_personal_activation_verified",
                "native_qd_forward_writer_enrolled",
                "native_hyperliquid_forward_writer_enrolled",
                "native_financial_ledger_accepted",
                "native_financial_stop_and_flat_accepted",
                "current_iex_equity_quotes_verified",
                "current_hyperliquid_public_book_verified",
                "paper_start_authorized",
                "live_trading_authorized"))):
        raise ValueError("R15_MILESTONES_LEGACY_OFFLINE_FINANCIAL_NO_GO_REQUIRED")
    return {
        "schema": SCHEMA,
        "decision": "TECHNICAL_PREREQUISITES_VERIFIED_FINANCIAL_NO_GO",
        "installed_release": "R15",
        "installed_selected_head": r15.SELECTED_HEAD,
        "technical_checks": [
            {"name": name, "verified": True, "status": "INDEPENDENT_READ_ONLY_RUNTIME_PROOF"}
            for name in TECHNICAL_NAMES
        ],
        "technical_prerequisites_verified": len(TECHNICAL_NAMES),
        "technical_prerequisites_total": len(TECHNICAL_NAMES),
        "financial_operating_gates_from_legacy_offline_inspector": [
            {"gate":g, "accepted":False, "status":"NOT_INDEPENDENTLY_ACCEPTED"}
            for g in r15.GATES
        ],
        "financial_operating_gates_accepted": 0,
        "financial_operating_gates_total":len(r15.GATES),
        "financial_gate_acceptance_evaluator_installed":False,
        "financial_percent_complete_estimate_available":False,
        "unmet_financial_requirements":list(PENDING),
        "technical_prechecks_not_financial_gate_promotions":True,
        "native_financial_account_files_written":0,
        "provider_requests":0,
        "paper_orders_created":0,
        "real_money_orders_created":0,
        "persistent_paper_writer_enrolled":False,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
    }


def inspect():
    # Each runtime-dependent check is rerun from genuine Windows native
    # identity/handle measurements; cached JSON receipts are not trusted.
    selected = r15.selected_code()
    ports = r15.selected_ports()
    roots = inspect_two_lane_native_roots()
    handoff = handoff_inspect()
    held = inspect_two_lane_native_root_handles()
    job = real_job_inspect()
    financial = r15.inspect()
    return evaluate(selected=selected, ports=ports, roots=roots,
                    handoff=handoff, held=held, job=job,
                    financial=financial)


if __name__ == "__main__":
    print(json.dumps(inspect(),sort_keys=True,indent=2))
