"""R17 current selected two-account PAPER original-draft review — no writers.

This is NOT an enrollment issuer, reservation, financial inception, activation,
market-data rights, account balance, or authority. Historical review-only V5
opening timestamps and fees MUST be freshly approved at actual inception.
No files written and no account/financial process started.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from app.services.paper_daily_report import validate_scope
from app.services.paper_financial_replay import digest, validate_manifest
from app.services.perp_operational_contract import (
    validate_enrollment as hl_validate,
)
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as qd_validate,
)

from scripts import release_selection as selection
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE as CLOCK
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    ARTIFACT as R15_ARTIFACT,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    RECEIPT as R15_RECEIPT,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    RECEIPT_SHA as R15_RECEIPT_SHA,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTED_HEAD as R15_HEAD,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTED_SHA as R15_SHA,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTOR_NATIVE_ID,
)
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    LEGACY_SHA,
    legacy_proposal,
)
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    build_handoff as r15_handoff,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    R16_HEAD,
)
from scripts.observation_runtime.atlas_r16_two_account_enrollment_handoff import (
    HISTORICAL_R15_HANDOFF_DIGEST,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    ARTIFACT,
    HEAD,
    PREDECESSOR,
    SOURCE,
    require_selected_r17_nonfinancial,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES,
    inspect_two_lane_native_roots,
)
from scripts.release_selection_store import NativeSelectionStore

SCHEMA = "ATLAS_R17_CURRENT_UNACCEPTED_TWO_ACCOUNT_INCEPTION_HANDOFF_V1"
LANES = ("QUALITY_DIPS", "HYPERLIQUID")


def historical_r15_ref():
    """Verify actual rev14 / rev15 / rev16 original Windows selection chain."""
    current = require_selected_r17_nonfinancial()
    store = NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection", native_root=SELECTOR_NATIVE_ID,
    )
    try:
        with store.locked():
            rows = store.records()
        if (len(rows) != 16
                or [row.get("revision") for row in rows] != list(range(1,17))
                or selection.digest(rows[13]) != R15_HEAD
                or selection.digest(rows[14]) != R16_HEAD
                or selection.digest(rows[15]) != HEAD
                or rows[15].get("previous") != PREDECESSOR
                or rows[13].get("action") != "SELECT"
                or rows[13].get("restores") is not None):
            raise ValueError("R17_DRAFT_ORIGINAL_R15_R16_R17_SELECTION_CHAIN_REFUSED")
        historic = selection.validate_spec(rows[13]["selected"], "WINDOWS_LOCAL")
        if (historic["release"] != "2c79a8d846d6b33669008114732ae5896153812a"
                or historic["artifact_digest"] != R15_ARTIFACT
                or historic["receipt_sha256"] != R15_RECEIPT_SHA
                or historic["receipt"] != str(R15_RECEIPT)
                or current["release"] != SOURCE
                or current["artifact_digest"] != ARTIFACT):
            raise ValueError("R17_DRAFT_PINNED_HISTORIC_SELECTION_REFUSED")
    finally:
        store.close()
    if (not R15_RECEIPT.is_file()
            or R15_RECEIPT.is_symlink() or R15_RECEIPT.is_junction()
            or hashlib.sha256(R15_RECEIPT.read_bytes()).hexdigest()
               != R15_RECEIPT_SHA):
        raise ValueError("R17_DRAFT_HISTORICAL_IMMUTABLE_R15_RECEIPT_REFUSED")
    data = json.loads(R15_RECEIPT.read_bytes())
    if (data.get("artifact_digest") != R15_ARTIFACT
            or any(data.get(k) is not False for k in (
                "selected", "financial_effects",
                "provider_connections", "operational_acceptance"))):
        raise ValueError("R17_DRAFT_HISTORICAL_R15_CODE_ONLY_RECEIPT_REQUIRED")
    return {
        "revision":14,
        "selected_release":historic["release"],
        "selected_native_head":R15_HEAD,
        "selected_native_record_sha256":R15_SHA,
        "installed_receipt_sha256":R15_RECEIPT_SHA,
        "financial_authority":False,
        "independent_live_financial_clock_lease_accepted":False,
    }


def rebind(*, original, selected, roots):
    """Pure current R17 structural manifest; all true financial gates false."""
    if (type(selected) is not dict
            or selected.get("release") != SOURCE
            or selected.get("artifact_digest") != ARTIFACT
            or type(original) is not dict
            or original.get("schema") !=
                "ATLAS_R15_TWO_ACCOUNT_UNAPPROVED_REBIND_HANDOFF_V1"
            or original.get("status") !=
                "TWO_LANE_R15_STRUCTURAL_REBIND_ONLY_NEVER_ACCEPTED"
            or digest(original) != HISTORICAL_R15_HANDOFF_DIGEST
            or original.get("historical_unapproved_source_sha256") != LEGACY_SHA
            or original.get("selected_native_head") != R15_HEAD
            or set(original.get("accounts",{})) != set(LANES)
            or type(roots) is not dict
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("existing_empty_root_namespaces") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or set(roots.get("lanes",{})) != set(LANES)
            or any(original.get(k) is not False for k in (
                "account_enrollment_accepted", "both_financial_inceptions_published",
                "native_operator_activation_present",
                "native_current_quality_dips_source_accepted",
                "native_current_hyperliquid_source_accepted",
                "paper_start_authorized", "live_trading_authorized"))
            or original.get("financial_operating_gates_accepted") != 0
            or any(roots.get(k) is not False for k in (
                "operator_account_enrollment_verified", "writer_ownership_verified",
                "financial_inception_verified", "paper_start_authorized",
                "live_trading_authorized"))):
        raise ValueError("R17_DRAFT_EXACT_UNAPPROVED_NATIVE_PREINCEPTION_REQUIRED")
    seen_roots = set()
    accounts, epochs, output = set(), set(), {}
    for lane in LANES:
        previous = original["accounts"][lane]
        if (type(previous) is not dict
                or previous.get("real_enrollment_accepted") is not False
                or previous.get("writer_process_observed_and_leased") is not False
                or previous.get("financial_inception_published") is not False
                or previous.get("operational_source_rights_accepted") is not False
                or previous.get("account_fee_entitlement_verified") is not False
                or previous.get("opened_at_is_historical_stale_not_new_inception") is not True):
            raise ValueError("R17_DRAFT_HISTORIC_ACCOUNT_AUTHORITY_NOT_UNACCEPTED")
        params = deepcopy(previous["provisional_r15_parameters"])
        enrollment = deepcopy(previous["provisional_r15_native_enrollment_unaccepted"])
        scope = deepcopy(previous["provisional_report_scope_unaccepted"])
        if (params.get("release") != R15_ARTIFACT
                or enrollment.get("release_digest") != R15_ARTIFACT
                or enrollment.get("writers") is not None
                or enrollment.get("acceptance_id") is not None
                or enrollment.get("clock_source") != CLOCK
                or params.get("opening_cash") != "1000"
                or digest(params) != previous.get("provisional_inception_digest")
                or enrollment.get("inception_digest") != digest(params)
                or scope.get("policy_digest") != digest(params)
                or enrollment.get("account_id") != scope.get("account_id")
                or enrollment.get("epoch") != scope.get("epoch")
                or enrollment["account_id"] in accounts
                or enrollment["epoch"] in epochs
                or set(enrollment.get("resources",{})) != set(ROLES)
                or set(roots["lanes"][lane].get("roots",{})) != set(ROLES)
                or roots["lanes"][lane].get("epoch") != enrollment.get("epoch")):
            raise ValueError("R17_DRAFT_HISTORIC_MANIFEST_SCOPE_CHANGED")
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
                    or tuple(got["native_id"]) in seen_roots):
                raise ValueError("R17_DRAFT_ORIGINAL_NATIVE_ROOT_IDENTITY_DRIFT")
            seen_roots.add(tuple(got["native_id"]))
        params["release"] = ARTIFACT
        validate_manifest(params)
        enrollment["release_digest"] = ARTIFACT
        enrollment["inception_digest"] = digest(params)
        scope["policy_digest"] = digest(params)
        validate_scope(scope, params)
        validator = qd_validate if lane == "QUALITY_DIPS" else hl_validate
        try:
            validator(enrollment)
        except (ValueError, KeyError, TypeError):
            pass
        else:
            raise ValueError("R17_DRAFT_UNACCEPTED_ENROLLMENT_BECAME_ACCEPTED")
        output[lane] = {
            "provisional_parameters_historical_open_time":params,
            "provisional_manifest_digest":digest(params),
            "provisional_enrollment_unaccepted":enrollment,
            "provisional_report_scope_unaccepted":scope,
            "native_existing_original_root_identities_verified":True,
            "fees_historical_not_currently_accepted":True,
            "opening_time_historical_not_currently_accepted":True,
            "writer_process_unbound":True,
            "operator_account_approval_unissued":True,
            "account_fs1_fs3_not_published":True,
            "market_source_rights_unaccepted":True,
        }
    if len(seen_roots) != 12:
        raise ValueError("R17_DRAFT_NOT_TWELVE_INDEPENDENT_NATIVE_ROOTS")
    return {
        "schema":SCHEMA,
        "status":"TWO_R17_ACCOUNT_DRAFTS_ONLY_NOT_ACCEPTED_OR_INCEPTED",
        "selected_source_commit":SOURCE,
        "selected_release_digest":ARTIFACT,
        "native_revision":16,
        "native_head":HEAD,
        "original_historical_unaccepted_v5_sha256":LEGACY_SHA,
        "original_r15_handoff_digest":HISTORICAL_R15_HANDOFF_DIGEST,
        "original_root_count":12,
        "accounts":output,
        "financial_writer_enrollments_accepted":0,
        "native_account_fs1_fs3_inceptions_published":0,
        "provider_rights_accepted":False,
        "financial_issuer_present":False,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
        "filesystem_writes":0,
        "network_requests":0,
    }


def inspect():
    selected = require_selected_r17_nonfinancial()
    roots = inspect_two_lane_native_roots()
    before = deepcopy(roots)
    historical = r15_handoff(
        legacy_proposal(), selected=historical_r15_ref(), roots=roots)
    if roots != before:
        raise ValueError("R17_DRAFT_ROOTS_CHANGED")
    result = rebind(original=historical,selected=selected,roots=roots)
    if inspect_two_lane_native_roots() != before:
        raise ValueError("R17_DRAFT_ORIGINAL_NATIVE_ROOTS_DRIFTED")
    return result


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True, indent=2))
