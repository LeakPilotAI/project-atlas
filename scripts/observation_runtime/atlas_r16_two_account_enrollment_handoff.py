"""R16 current-selected two-account PAPER draft rebinder: READ ONLY.

Recover the original V5 unapproved QD and Hyperliquid manifests through
the ACTUAL historical R15 revision-14 native selection, then rebind their
existing root IDs, policy/report scopes and manifest digests to the CURRENT
genuine selected R16 revision-15 artifact. Never invent a current opened_at,
PID, writer lease, operator acceptance, market data right, account file or
financial action. These two drafts MUST remain invalid for real enrollment.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from app.services.paper_financial_replay import digest, validate_manifest
from app.services.paper_daily_report import validate_scope
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as validate_qd,
)
from app.services.perp_operational_contract import (
    validate_enrollment as validate_hl,
)
from scripts import release_selection as selection
from scripts.release_selection_store import NativeSelectionStore
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE as CLOCK_SOURCE
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    ARTIFACT as R15_ARTIFACT,
    SELECTED_HEAD as R15_HEAD, SELECTED_SHA as R15_SHA,
    RECEIPT as R15_RECEIPT, RECEIPT_SHA as R15_RECEIPT_SHA,
    SELECTOR_NATIVE_ID,
)
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    build_handoff as build_original_r15_handoff,
    legacy_proposal,
    LEGACY_SHA,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    ARTIFACT_DIGEST as R16_ARTIFACT,
    R16_HEAD, R16_RECORD_SHA, RECEIPT_SHA as R16_RECEIPT_SHA,
    SOURCE as R16_SOURCE,
    selected_code,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)

SCHEMA = "ATLAS_R16_TWO_ACCOUNT_PROVISIONAL_NATIVE_DRAFT_REBIND_V1"
# The *whole* historical review-only R15 handoff, independently derived from
# the original byte-pinned V5 input and actual r0014 native selection. Never
# accept an attacker-edited fee, risk, opened_at, scope or parameter bundle
# merely because its individual nested digests were recomputed.
HISTORICAL_R15_HANDOFF_DIGEST = (
    "a1e65008a965aec36a261cadcdb0c0da2d9d4b9a09ebf165e35e80c154be0506"
)
LANES = ("QUALITY_DIPS", "HYPERLIQUID")
SELECTION_ROOT = Path("D:/AtlasRuntime/selection")


def historical_r15_reference():
    """Prior selection from genuine 15-record native chain, NEVER current R15."""
    store = NativeSelectionStore(
        root=str(SELECTION_ROOT), native_root=SELECTOR_NATIVE_ID)
    try:
        with store.locked():
            records = store.records()
            if (len(records) != 15
                    or [row.get("revision") for row in records] != list(range(1,16))
                    or selection.digest(records[-2]) != R15_HEAD
                    or selection.digest(records[-1]) != R16_HEAD):
                raise ValueError("R16_DRAFT_ORIGINAL_R15_R16_NATIVE_CHAIN_REQUIRED")
            historic = records[-2]
            if (historic.get("action") != "SELECT"
                    or historic.get("previous") is None
                    or historic.get("restores") is not None):
                raise ValueError("R16_DRAFT_GENUINE_HISTORICAL_R15_SELECTION_REQUIRED")
            ref = selection.validate_spec(historic.get("selected"), "WINDOWS_LOCAL")
            if (ref["release"] != "2c79a8d846d6b33669008114732ae5896153812a"
                    or ref["artifact_digest"] != R15_ARTIFACT
                    or ref["receipt_sha256"] != R15_RECEIPT_SHA
                    or ref["receipt"] != str(R15_RECEIPT)):
                raise ValueError("R16_DRAFT_PINNED_PREDECESSOR_R15_RECEIPT_REQUIRED")
    finally:
        store.close()
    if (not R15_RECEIPT.is_file() or R15_RECEIPT.is_symlink()
            or R15_RECEIPT.is_junction()
            or hashlib.sha256(R15_RECEIPT.read_bytes()).hexdigest() !=
               R15_RECEIPT_SHA):
        raise ValueError("R16_DRAFT_HISTORIC_NATIVE_R15_RECEIPT_SHA_REFUSED")
    original_receipt = json.loads(R15_RECEIPT.read_bytes())
    if (original_receipt.get("artifact_digest") != R15_ARTIFACT
            or any(original_receipt.get(field) is not False for field in (
                "selected", "financial_effects", "provider_connections",
                "operational_acceptance"))):
        raise ValueError("R16_DRAFT_HISTORIC_CODE_ONLY_RECEIPT_NOT_FINANCIAL")
    return {
        "revision": 14,
        "selected_release": ref["release"],
        "selected_native_head": R15_HEAD,
        "selected_native_record_sha256": R15_SHA,
        "installed_receipt_sha256": R15_RECEIPT_SHA,
        # Historical R15 CODE-ONLY selection grants neither authority.
        "financial_authority": False,
        "independent_live_financial_clock_lease_accepted": False,
    }


def _require_current_r16(selected):
    if (type(selected) is not dict
            or selected.get("schema") !=
                "ATLAS_R16_SELECTED_NONFINANCIAL_NATIVE_CODE_READBACK_V1"
            or selected.get("selected_revision") != 15
            or selected.get("selected_release") != R16_SOURCE
            or selected.get("selected_native_head") != R16_HEAD
            or selected.get("selected_native_record_sha256") != R16_RECORD_SHA
            or selected.get("installed_receipt_sha256") != R16_RECEIPT_SHA
            or selected.get("installed_artifact_digest") != R16_ARTIFACT
            or selected.get("native_selection_append_only_chain_verified") is not True
            or selected.get("native_receipt_and_install_ack_verified") is not True
            or selected.get("code_selection_accepted") is not True
            or any(selected.get(field) is not False for field in (
                "financial_clock_operational_accepted",
                "provider_source_operational_accepted",
                "financial_writer_operational_accepted",
                "paper_start_authorized", "live_trading_authorized"))):
        raise ValueError("R16_DRAFT_EXACT_NONFINANCIAL_SELECTED_R16_REQUIRED")


def rebind(*, historic_r15, selected_r16, roots):
    """Pure original R15 draft -> R16 draft, preserving all unaccepted gates."""
    _require_current_r16(selected_r16)
    if (type(historic_r15) is not dict
            or historic_r15.get("schema") !=
                "ATLAS_R15_TWO_ACCOUNT_UNAPPROVED_REBIND_HANDOFF_V1"
            or historic_r15.get("status") !=
                "TWO_LANE_R15_STRUCTURAL_REBIND_ONLY_NEVER_ACCEPTED"
            or digest(historic_r15) != HISTORICAL_R15_HANDOFF_DIGEST
            or historic_r15.get("historical_unapproved_source_sha256") != LEGACY_SHA
            or historic_r15.get("selected_r15_artifact_digest") != R15_ARTIFACT
            or historic_r15.get("selected_native_head") != R15_HEAD
            or historic_r15.get("selected_r15_record_sha256") != R15_SHA
            or historic_r15.get("native_root_count_handle_verified") != 12
            or historic_r15.get("no_existing_native_root_modified") is not True
            or set(historic_r15.get("accounts", {})) != set(LANES)
            or any(historic_r15.get(k) is not False for k in (
                "account_enrollment_accepted", "both_financial_inceptions_published",
                "native_operator_activation_present",
                "native_current_quality_dips_source_accepted",
                "native_current_hyperliquid_source_accepted",
                "paper_start_authorized", "live_trading_authorized"))
            or historic_r15.get("financial_operating_gates_accepted") != 0
            or historic_r15.get("filesystem_mutations") != 0
            or historic_r15.get("network_requests") != 0):
        raise ValueError("R16_DRAFT_VERIFIED_UNAPPROVED_HISTORICAL_R15_INPUT_REQUIRED")
    if (type(roots) is not dict
            or roots.get("schema") !=
                "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("existing_empty_root_namespaces") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or set(roots.get("lanes", {})) != set(LANES)
            or any(roots.get(k) is not False for k in (
                "operator_account_enrollment_verified",
                "writer_ownership_verified", "native_activation_record_verified",
                "financial_inception_verified", "paper_start_authorized",
                "live_trading_authorized"))
            or roots.get("filesystem_writes") != 0
            or roots.get("network_requests") != 0):
        raise ValueError("R16_DRAFT_REAL_TWELVE_EMPTY_NATIVE_ROOTS_REQUIRED")
    output = {}
    used_ids = set()
    accounts = set()
    epochs = set()
    for lane in LANES:
        old = historic_r15["accounts"][lane]
        if (type(old) is not dict
                or old.get("real_enrollment_accepted") is not False
                or old.get("writer_process_observed_and_leased") is not False
                or old.get("financial_inception_published") is not False
                or old.get("operational_source_rights_accepted") is not False
                or old.get("account_fee_entitlement_verified") is not False
                or old.get("opened_at_is_historical_stale_not_new_inception") is not True
                or old.get("existing_native_root_identity_matched") is not True
                or old.get("parameters_structurally_valid_not_current") is not True):
            raise ValueError("R16_DRAFT_PREVIOUS_FINANCIAL_DRAFT_NOT_REVIEW_ONLY")
        params = deepcopy(old["provisional_r15_parameters"])
        enrollment = deepcopy(old["provisional_r15_native_enrollment_unaccepted"])
        scope = deepcopy(old["provisional_report_scope_unaccepted"])
        if (type(params) is not dict or type(enrollment) is not dict
                or type(scope) is not dict
                or params.get("release") != R15_ARTIFACT
                or enrollment.get("release_digest") != R15_ARTIFACT
                or enrollment.get("writers") is not None
                or enrollment.get("acceptance_id") is not None
                or enrollment.get("clock_source") != CLOCK_SOURCE
                or params.get("opening_cash") != "1000"
                or digest(params) != old.get("provisional_inception_digest")
                or enrollment.get("inception_digest") != digest(params)
                or scope.get("policy_digest") != digest(params)
                or enrollment.get("account_id") != scope.get("account_id")
                or enrollment.get("epoch") != scope.get("epoch")
                or enrollment["account_id"] in accounts
                or enrollment["epoch"] in epochs
                or set(enrollment.get("resources", {})) != set(ROLES)
                or set(roots["lanes"][lane].get("roots", {})) != set(ROLES)
                or roots["lanes"][lane].get("epoch") != enrollment.get("epoch")
                or params.get("timezone") != (
                    "America/New_York" if lane == "QUALITY_DIPS" else "UTC")
                or scope.get("timezone") != params.get("timezone")):
            raise ValueError("R16_DRAFT_PREDECESSOR_MANIFEST_OR_LANE_BINDING_CHANGED")
        validate_manifest(params)
        validate_scope(scope, params)
        accounts.add(enrollment["account_id"])
        epochs.add(enrollment["epoch"])
        for role in ROLES:
            expected = roots["lanes"][lane]["roots"][role]
            got = enrollment["resources"][role]
            if (got.get("path") != expected.get("path")
                    or got.get("native_id") != expected.get("native_id")
                    or expected.get("native_identity_verified") is not True
                    or expected.get("existing_empty_namespace_verified") is not True
                    or tuple(got["native_id"]) in used_ids):
                raise ValueError("R16_DRAFT_EXISTING_ORIGINAL_NATIVE_ROOT_IDENTITY_DRIFT")
            used_ids.add(tuple(got["native_id"]))
        params["release"] = R16_ARTIFACT
        validate_manifest(params)
        enrollment["release_digest"] = R16_ARTIFACT
        enrollment["inception_digest"] = digest(params)
        scope["policy_digest"] = digest(params)
        validate_scope(scope, params)
        validator = validate_qd if lane == "QUALITY_DIPS" else validate_hl
        # No writer pid, acceptance or current inception stamp may be fabricated.
        try:
            validator(enrollment)
        except (ValueError, TypeError, KeyError):
            pass
        else:
            raise ValueError("R16_DRAFT_UNACCEPTED_ENROLLMENT_SUDDENLY_ACCEPTED")
        output[lane] = {
            "provisional_r16_parameters": params,
            "provisional_r16_manifest_digest": digest(params),
            "provisional_r16_enrollment_unaccepted": enrollment,
            "provisional_r16_report_scope_unaccepted": scope,
            "existing_native_roots_original_handles_matched": True,
            "fs3_reporting_scope_structurally_valid": True,
            "opening_timestamp_historical_not_current": True,
            "fee_policy_historical_review_only": True,
            "real_writer_roster_present": False,
            "accepted_operator_inception": False,
            "financial_inception_published": False,
            "provider_source_rights_accepted": False,
            "required_live_inputs": [
                "CURRENT_TRUSTED_FINANCIAL_INCEPTION_TIME_AND_NEW_DIGEST",
                "GENUINE_RETAINED_R16_OWNER_PLUS_FINANCIAL_WRITER_LEASE",
                "CURRENT_OPERATOR_SID_BOUND_FINANCIAL_AUTHORITY",
                "QUALITY_DIPS_AND_HYPERLIQUID_PROVIDER_RIGHTS",
                "ACTUAL_ACCOUNT_INCEPTION_FS1_FS3_READBACK",
                "SUPERVISED_FINANCIAL_STOP_AND_RESTART_SOAK",
            ],
        }
    if len(used_ids) != 12:
        raise ValueError("R16_DRAFT_TWELVE_DISTINCT_EXISTING_ROOTS_REQUIRED")
    return {
        "schema": SCHEMA,
        "status": "R16_TWO_LANE_CURRENT_CODE_PROPOSAL_ONLY_UNACCEPTED",
        "selected_r16_source_commit": R16_SOURCE,
        "selected_r16_artifact_digest": R16_ARTIFACT,
        "selected_native_revision": 15,
        "selected_native_head": R16_HEAD,
        "selected_native_record_sha256": R16_RECORD_SHA,
        "historical_r15_rebind_digest": HISTORICAL_R15_HANDOFF_DIGEST,
        "original_historical_v5_proposal_sha256": LEGACY_SHA,
        "native_original_empty_root_count_verified": 12,
        "account_count": 2,
        "accounts": output,
        "actual_financial_writer_roles_enrolled": 0,
        "native_financial_inceptions_published": 0,
        "accepted_financial_operating_gates": 0,
        "financial_paper_start_authorized": False,
        "live_trading_authorized": False,
        "filesystem_mutations": 0,
        "provider_requests": 0,
    }


def inspect(*, verify_installed_handles=False):
    """Existing-only R16+R15 native selection and original 12-root readback."""
    selected = selected_code(
        verify_original_installed_handles=verify_installed_handles)
    history = build_original_r15_handoff(
        legacy_proposal(), selected=historical_r15_reference(),
        roots=inspect_two_lane_native_roots())
    return rebind(
        historic_r15=history, selected_r16=selected,
        roots=inspect_two_lane_native_roots())


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True, indent=2))
