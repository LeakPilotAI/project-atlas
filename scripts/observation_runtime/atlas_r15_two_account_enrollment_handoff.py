"""R15 two-lane enrollment draft rebinder: source-only, no permissions.

Consumes a pinned historical V5 proposal, the genuinely selected immutable
R15 native release and actual existing Windows root-handle evidence. The
rebinding is a *provisional planning artifact*, never an enrolled account,
financial manifest inception, trusted clock lease, writer roster or operator
activation. No native file, credential, network, provider or financial writer.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from app.services.paper_financial_replay import digest, validate_manifest
from app.services.paper_daily_report import validate_scope
from app.services.quality_dips_autonomous_enrollment import validate_enrollment as qd_enrollment
from app.services.perp_operational_contract import validate_enrollment as perp_enrollment
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    ARTIFACT, SELECTED_HEAD, SELECTED_SHA, RECEIPT_SHA, selected_code,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "docs/ATLAS_TWO_ACCOUNT_V5_BASE_FEE_UNAPPROVED_ENROLLMENT_BUNDLE_2026-11-08.json"
LEGACY_SHA = "d4b439d8b7c4ea8d51cd3a003f1cf68cc22f008b500b4c58acdf357af0cf6800"
SCHEMA = "ATLAS_R15_TWO_ACCOUNT_UNAPPROVED_REBIND_HANDOFF_V1"
LANES = ("HYPERLIQUID", "QUALITY_DIPS")
ROLES = ("source", "projection", "report", "control", "coordination", "custody")


def legacy_proposal(path=LEGACY):
    path = Path(path)
    if (not path.is_file() or path.is_symlink() or path.is_junction()
            or not 1000 <= path.stat().st_size < 30_000):
        raise ValueError("R15_HANDOFF_PINNED_HISTORICAL_DRAFT_REQUIRED")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEGACY_SHA:
        raise ValueError("R15_HANDOFF_ORIGINAL_PROPOSAL_DIGEST_CHANGED")
    return json.loads(raw.decode("utf-8-sig"))


def build_handoff(original, *, selected, roots, original_sha=LEGACY_SHA):
    """Pure strictly scoped V5->R15 prototype; financial authorizations FALSE."""
    if (type(original) is not dict
            or original.get("schema") != "ATLAS_PERSONAL_TWO_ACCOUNT_OFFLINE_DRAFT_BUNDLE_V1"
            or original.get("status") != "V5_PUBLIC_BASE_PERPS_FEES_REVIEW_ONLY_NOT_ACCEPTED_OR_AUTHORIZED"
            or original.get("profile") != "PERSONAL_PAPER_ONLY_V1"
            or set(original.get("accounts", {})) != set(LANES)
            or original.get("selected_release_artifact_digest") == ARTIFACT
            or any(original.get(flag) is not False for flag in (
                "account_inception_authorized", "creation_authorized",
                "enrollment_accepted", "live_order_authorized",
                "paper_start_authorized", "provider_check_authorized"))
            or original_sha != LEGACY_SHA):
        raise ValueError("R15_HANDOFF_UNAPPROVED_V5_SOURCE_REQUIRED")
    if (type(selected) is not dict
            or selected.get("revision") != 14
            or selected.get("selected_release") != "2c79a8d846d6b33669008114732ae5896153812a"
            or selected.get("selected_native_head") != SELECTED_HEAD
            or selected.get("selected_native_record_sha256") != SELECTED_SHA
            or selected.get("installed_receipt_sha256") != RECEIPT_SHA
            or selected.get("financial_authority") is not False
            or selected.get("independent_live_financial_clock_lease_accepted") is not False):
        raise ValueError("R15_HANDOFF_EXACT_SELECTED_NONFINANCIAL_R15_REQUIRED")
    if (type(roots) is not dict
            or roots.get("schema") != "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("existing_empty_root_namespaces") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or set(roots.get("lanes", {})) != set(LANES)
            or any(roots.get(k) is not False for k in (
                "operator_account_enrollment_verified",
                "writer_ownership_verified", "native_activation_record_verified",
                "financial_inception_verified", "paper_start_authorized",
                "live_trading_authorized"))):
        raise ValueError("R15_HANDOFF_GENUINE_EMPTY_NATIVE_ROOT_PRECONDITION_REQUIRED")
    output = {}
    epoch_ids = set()
    account_ids = set()
    all_ids = set()
    original_release = original["selected_release_artifact_digest"]
    for lane in LANES:
        item = original["accounts"][lane]
        if (type(item) is not dict
                or item.get("enrollment_schema_validated") is not False
                or item.get("native_financial_inception_published") is not False
                or item.get("parameters_schema_validated") is not True
                or item.get("report_scope_validated_against_manifest") is not True
                or type(item.get("parameters")) is not dict
                or type(item.get("native_enrollment_draft")) is not dict
                or type(item.get("report_scope_draft")) is not dict):
            raise ValueError("R15_HANDOFF_HISTORICAL_FINANCIAL_DRAFT_SCOPE_REFUSED")
        params = deepcopy(item["parameters"])
        enrollment = deepcopy(item["native_enrollment_draft"])
        scope = deepcopy(item["report_scope_draft"])
        if (params.get("release") != original_release
                or enrollment.get("release_digest") != original_release
                or enrollment.get("inception_digest") != item.get("parameters_digest")
                or digest(params) != item.get("parameters_digest")
                or scope.get("policy_digest") != digest(params)
                or enrollment.get("acceptance_id") is not None
                or enrollment.get("writers") is not None
                or enrollment.get("profile") != "AUTONOMOUS_PAPER_ONLY_V1"
                or enrollment.get("account_id") != scope.get("account_id")
                or enrollment.get("epoch") != params.get("epoch")
                or enrollment["account_id"] in account_ids
                or enrollment["epoch"] in epoch_ids
                or type(enrollment.get("resources")) is not dict
                or set(enrollment["resources"]) != set(ROLES)
                or set(roots["lanes"][lane]["roots"]) != set(ROLES)
                or roots["lanes"][lane]["epoch"] != enrollment["epoch"]
                or item.get("identity_requirements_pending") != [
                    "ACTUAL_WRITER_PID_AND_CREATION_FILETIME",
                    "ACCEPTANCE_ID",
                    "E1_PROVIDER_SOURCE_ENTITLEMENT",
                    "OPERATOR_FINANCIAL_INCEPTION_AUTHORIZATION"]):
            raise ValueError("R15_HANDOFF_UNACCEPTED_OR_STALE_ACCOUNT_DRAFT_REFUSED")
        account_ids.add(enrollment["account_id"])
        epoch_ids.add(enrollment["epoch"])
        original_params = deepcopy(params)
        validate_manifest(original_params)
        expected_schema = ("QD_AUTO_NATIVE_ROOT_V4" if lane == "QUALITY_DIPS"
                           else "PERP_AUTO_NATIVE_ROOT_V1")
        for role, resource in enrollment["resources"].items():
            actual = roots["lanes"][lane]["roots"][role]
            if (resource.get("schema") != expected_schema
                    or resource.get("path") != actual.get("path")
                    or resource.get("native_id") != actual.get("native_id")
                    or actual.get("native_identity_verified") is not True
                    or actual.get("existing_empty_namespace_verified") is not True
                    or tuple(resource["native_id"]) in all_ids):
                raise ValueError("R15_HANDOFF_EXISTING_NATIVE_HANDLE_OR_ROLE_MISMATCH")
            all_ids.add(tuple(resource["native_id"]))
        # Historical opened_at is NOT the future native financial inception.
        # Keep that conspicuous; never manufacture an operator-approved time.
        params["release"] = ARTIFACT
        # The historical QD proposal was in the operator's Chicago timezone,
        # but the actual FS3 financial daily reporter REQUIRES exchange-local
        # America/New_York for a Quality Dips inception. Do not change the
        # pinned historical proposal; explicitly rebind the unapproved R15
        # prospective policy+report pair together, including their digest.
        historical_timezone = params["timezone"]
        if lane == "QUALITY_DIPS":
            if historical_timezone != "America/Chicago" or scope.get("timezone") != historical_timezone:
                raise ValueError("R15_HANDOFF_HISTORICAL_QD_REPORT_CALENDAR_UNEXPECTED")
            params["timezone"] = "America/New_York"
        elif historical_timezone != "UTC" or scope.get("timezone") != historical_timezone:
            raise ValueError("R15_HANDOFF_HISTORICAL_PERP_REPORT_CALENDAR_UNEXPECTED")
        validate_manifest(params)  # Structural only, not financial acceptance.
        enrollment["release_digest"] = ARTIFACT
        enrollment["inception_digest"] = digest(params)
        enrollment["clock_source"] = SOURCE
        scope["policy_digest"] = digest(params)
        scope["timezone"] = params["timezone"]
        validate_scope(scope, params)  # Real FS3 accounting contract, no file writes.
        for key in ("account_id", "epoch"):
            if scope.get(key) != enrollment[key]:
                raise ValueError("R15_HANDOFF_REPORT_SCOPE_ACCOUNT_CHANGED")
        if enrollment.get("policy_digest") != digest(
                params["autonomous_policy" if lane == "QUALITY_DIPS" else "perp_policy"]):
            raise ValueError("R15_HANDOFF_POLICY_NOT_BOUND_TO_ORIGINAL_PARAMETERS")
        # It must remain UNACCEPTABLE to the real native enrollment validator.
        validator = qd_enrollment if lane == "QUALITY_DIPS" else perp_enrollment
        try:
            validator(enrollment)
        except (ValueError, TypeError, KeyError):
            pass
        else:
            raise ValueError("R15_HANDOFF_REAL_ENROLLMENT_UNEXPECTEDLY_ACCEPTED")
        output[lane] = {
            "provisional_r15_parameters": params,
            "provisional_inception_digest": digest(params),
            "provisional_r15_native_enrollment_unaccepted": enrollment,
            "provisional_report_scope_unaccepted": scope,
            "existing_native_root_identity_matched": True,
            "parameters_structurally_valid_not_current": True,
            "historical_draft_reporting_timezone": historical_timezone,
            "provisional_fs3_reporting_timezone": params["timezone"],
            "provisional_fs3_calendar_validated_without_publication": True,
            "real_enrollment_accepted": False,
            "writer_process_observed_and_leased": False,
            "opened_at_is_historical_stale_not_new_inception": True,
            "account_fee_entitlement_verified": False,
            "operational_source_rights_accepted": False,
            "financial_inception_published": False,
            "required_live_commissioning_inputs": [
                "TRUE_FINANCIAL_INCEPTION_TIME_AND_RECOMPUTED_DIGEST",
                "ACTUAL_INSTALLED_R15_WRITER_PID_CREATION_FILETIME",
                "INDEPENDENT_OPERATOR_ACCOUNT_AND_WRITER_ACCEPTANCE",
                "C1_D1_E1_SOURCE_RIGHTS_AND_RUNTIME_CLOCK_LEASE",
                "NATIVE_ACTIVATION_AND_DUAL_ACCOUNT_FINANCIAL_READBACK"],
        }
    if len(all_ids) != 12:
        raise ValueError("R15_HANDOFF_TWO_DISTINCT_NATIVE_LANES_REQUIRED")
    return {
        "schema": SCHEMA,
        "status": "TWO_LANE_R15_STRUCTURAL_REBIND_ONLY_NEVER_ACCEPTED",
        "historical_unapproved_source_sha256": original_sha,
        "selected_r15_artifact_digest": ARTIFACT,
        "selected_native_head": SELECTED_HEAD,
        "selected_r15_record_sha256": SELECTED_SHA,
        "original_historical_release_digest": original_release,
        "native_root_count_handle_verified": 12,
        "no_existing_native_root_modified": True,
        "accounts": output,
        "account_enrollment_accepted": False,
        "both_financial_inceptions_published": False,
        "native_operator_activation_present": False,
        "native_current_quality_dips_source_accepted": False,
        "native_current_hyperliquid_source_accepted": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "financial_operating_gates_accepted": 0,
        "filesystem_mutations": 0,
        "network_requests": 0,
    }


def inspect():
    return build_handoff(
        legacy_proposal(), selected=selected_code(),
        roots=inspect_two_lane_native_roots(),
    )


if __name__ == "__main__":
    result = inspect()
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
