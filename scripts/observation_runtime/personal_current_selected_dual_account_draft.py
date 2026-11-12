"""Version-safe SELECTED original two-account structural handoff, read-only.

Never a financial enrollment, operator signature, market source entitlement,
simulated-account inception, Stop authority, or PAPER startup approval. It
preserves the pinned V5/R15 history while rebinding account PLAN parameters to
the real currently selected immutable R18+ release artifact, all 12 original
empty Windows-root identities, and the unchanged historic opening timestamps.

Unlike the historical R17-only review, this relies on a genuine append-only
selected release plus original installed-file handle verification, not a
revision-16 assertion that can become stale after selecting an R18 successor.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from app.services.paper_daily_report import validate_scope
from app.services.paper_financial_replay import digest, validate_manifest
from app.services.perp_operational_contract import (
    validate_enrollment as validate_hl,
)
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as validate_qd,
)

from scripts import release_selection as selection
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
    build_handoff as r15_build,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    R16_HEAD,
)
from scripts.observation_runtime.atlas_r16_two_account_enrollment_handoff import (
    HISTORICAL_R15_HANDOFF_DIGEST,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    ARTIFACT as R17_ARTIFACT,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    HEAD as R17_HEAD,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    SOURCE as R17_RELEASE,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES,
    inspect_two_lane_native_roots,
)
from scripts.release_selection import NativeInstalledReleaseVerifier
from scripts.release_selection_store import NativeSelectionStore

SCHEMA = "ATLAS_CURRENT_SELECTED_R18_PLUS_TWO_UNACCEPTED_ACCOUNT_DRAFT_V1"
LANES = ("QUALITY_DIPS", "HYPERLIQUID")
MIN_RELEASE_REVISION = 17
OPERATOR_INPUTS_NOT_YET_ACCEPTED = (
    "INDEPENDENTLY_ACCEPTED_ISSUER_AND_CURRENT_WINDOWS_OPERATOR_APPROVAL",
    "ORIGINAL_ONE_PROCESS_TWELVE_FINANCIAL_WRITER_ROLE_BINDINGS",
    "FRESH_TRUE_OPENING_TIME_AND_NEW_NATIVE_DIGESTS",
    "REVIEWED_CURRENT_FEE_AND_SLIPPAGE_POLICY",
    "PERMITTED_CONTINUOUS_IEX_AND_HYPERLIQUID_FEEDS",
    "NATIVE_INITIAL_JOURNALS_AND_DUAL_FS1_FS3_ACCOUNT_OPENINGS",
    "FINANCIAL_STOP_FLATNESS_AND_MULTI_SESSION_PAPER_SOAK",
)


def selected_and_historical():
    """True native selected store and installed release, not a supplied JSON."""
    store = NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection",
        native_root=list(SELECTOR_NATIVE_ID))
    try:
        with store.locked():
            records = store.records()
            if (len(records) < MIN_RELEASE_REVISION
                    or len(records) > 64
                    or any(type(row) is not dict or row.get("revision") != n
                           for n, row in enumerate(records, 1))
                    or selection.digest(records[13]) != R15_HEAD
                    or selection.digest(records[14]) != R16_HEAD
                    or selection.digest(records[15]) != R17_HEAD
                    or records[15].get("selected", {}).get("release") != R17_RELEASE
                    or records[15]["selected"]["artifact_digest"] != R17_ARTIFACT):
                raise ValueError("CURRENT_DUAL_HISTORIC_R15_R16_R17_CHAIN_REQUIRED")
            for n in range(16, len(records)):
                row = records[n]
                prior = records[n-1]
                if (row.get("previous") != selection.digest(prior)
                        or row.get("action") != "SELECT"
                        or row.get("restores") is not None):
                    raise ValueError("CURRENT_DUAL_ONLY_FORWARD_SELECTED_RELEASES_ALLOWED")
                selection.validate_spec(row.get("selected"), "WINDOWS_LOCAL")
            last = records[-1]
            spec = selection.validate_spec(last.get("selected"), "WINDOWS_LOCAL")
            with NativeInstalledReleaseVerifier().open(spec) as installed:
                if (installed.get("source_commit") != spec["release"]
                        or installed.get("artifact_digest") != spec["artifact_digest"]
                        or any(installed.get(k) is not False for k in (
                            "selected", "financial_effects",
                            "provider_connections", "operational_acceptance"))):
                    raise ValueError("CURRENT_DUAL_GENUINE_INSTALLED_RELEASE_REQUIRED")
            historic = selection.validate_spec(
                records[13].get("selected"), "WINDOWS_LOCAL")
        if (historic["release"] !=
                "2c79a8d846d6b33669008114732ae5896153812a"
                or historic["artifact_digest"] != R15_ARTIFACT
                or historic["receipt_sha256"] != R15_RECEIPT_SHA
                or historic["receipt"] != str(R15_RECEIPT)):
            raise ValueError("CURRENT_DUAL_IMMUTABLE_R15_HISTORIC_SPEC_REFUSED")
    finally:
        store.close()
    if (not R15_RECEIPT.is_file()
            or R15_RECEIPT.is_symlink() or R15_RECEIPT.is_junction()
            or hashlib.sha256(R15_RECEIPT.read_bytes()).hexdigest()
               != R15_RECEIPT_SHA):
        raise ValueError("CURRENT_DUAL_HISTORIC_R15_RECEIPT_CHANGED")
    historic_data = json.loads(R15_RECEIPT.read_bytes())
    if (historic_data.get("artifact_digest") != R15_ARTIFACT
            or any(historic_data.get(flag) is not False for flag in (
                "selected", "financial_effects",
                "provider_connections", "operational_acceptance"))):
        raise ValueError("CURRENT_DUAL_ORIGINAL_R15_CODE_ONLY_RECEIPT_REQUIRED")
    historical = {
        "revision": 14,
        "selected_release": historic["release"],
        "selected_native_head": R15_HEAD,
        "selected_native_record_sha256": R15_SHA,
        "installed_receipt_sha256": R15_RECEIPT_SHA,
        "financial_authority": False,
        "independent_live_financial_clock_lease_accepted": False,
    }
    return spec, last, historical


def rebind(*, original, selected, head, roots):
    """Copy historical UNAPPROVED manifests; no defaults, authorizations."""
    if (type(selected) is not dict
            or selected.get("schema") != "QD_INSTALLED_RELEASE_REFERENCE_V1"
            or selected.get("domain") != "WINDOWS_LOCAL"
            or selected.get("release") in (R17_RELEASE,)
            or type(head) is not dict or head.get("revision") < MIN_RELEASE_REVISION
            or head.get("selected") != selected
            or type(original) is not dict
            or original.get("schema") !=
                "ATLAS_R15_TWO_ACCOUNT_UNAPPROVED_REBIND_HANDOFF_V1"
            or original.get("status") !=
                "TWO_LANE_R15_STRUCTURAL_REBIND_ONLY_NEVER_ACCEPTED"
            or digest(original) != HISTORICAL_R15_HANDOFF_DIGEST
            or original.get("selected_r15_artifact_digest") != R15_ARTIFACT
            or original.get("original_historical_release_digest") is None
            or original.get("historical_unapproved_source_sha256") != LEGACY_SHA
            or original.get("account_enrollment_accepted") is not False
            or original.get("both_financial_inceptions_published") is not False
            or original.get("paper_start_authorized") is not False
            or type(roots) is not dict
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12
            or roots.get("existing_empty_root_namespaces") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True
            or set(original.get("accounts", {})) != set(LANES)
            or set(roots.get("lanes", {})) != set(LANES)):
        raise ValueError("CURRENT_DUAL_GENUINE_HISTORICAL_UNACCEPTED_PLAN_REQUIRED")
    selected_digest = selected["artifact_digest"]
    used_native_ids = set()
    output = {}
    epochs = set()
    ids = set()
    for lane in LANES:
        prior = original["accounts"][lane]
        if (type(prior) is not dict
                or prior.get("real_enrollment_accepted") is not False
                or prior.get("financial_inception_published") is not False
                or prior.get("operational_source_rights_accepted") is not False
                or prior.get("account_fee_entitlement_verified") is not False
                or prior.get("opened_at_is_historical_stale_not_new_inception") is not True):
            raise ValueError("CURRENT_DUAL_HISTORIC_ACCOUNT_STILL_UNACCEPTED_REQUIRED")
        manifest = deepcopy(prior["provisional_r15_parameters"])
        enrollment = deepcopy(prior["provisional_r15_native_enrollment_unaccepted"])
        scope = deepcopy(prior["provisional_report_scope_unaccepted"])
        old_manifest = deepcopy(manifest)
        validate_manifest(old_manifest)
        # The old POLICY and timestamp are not fresh approval, but they must
        # still exactly match the independently pinned historical R15 cut.
        # Otherwise a caller could alter a plausible historical fee/risk
        # assumption and have its checksum silently recomputed on rebinding.
        historical_policy = ("autonomous_policy" if lane == "QUALITY_DIPS"
                             else "perp_policy")
        if (digest(old_manifest) != prior.get("provisional_inception_digest")
                or enrollment.get("policy_digest") !=
                    digest(old_manifest[historical_policy])
                or enrollment.get("release_digest") != R15_ARTIFACT
                or manifest.get("release") != R15_ARTIFACT
                or enrollment.get("inception_digest") != digest(manifest)
                or scope.get("policy_digest") != digest(manifest)
                or enrollment.get("writers") is not None
                or enrollment.get("acceptance_id") is not None
                or enrollment.get("account_id") != scope.get("account_id")
                or enrollment.get("epoch") != manifest.get("epoch")
                or manifest.get("opening_cash") != "1000"
                or manifest.get("currency") != (
                    "USD" if lane == "QUALITY_DIPS" else "USDC")
                or manifest.get("timezone") !=
                    ("America/New_York" if lane == "QUALITY_DIPS" else "UTC")
                or enrollment.get("epoch") in epochs
                or enrollment.get("account_id") in ids
                or set(enrollment.get("resources", {})) != set(ROLES)
                or roots["lanes"][lane]["epoch"] != enrollment.get("epoch")):
            raise ValueError("CURRENT_DUAL_HISTORIC_NATIVE_PARAMETERS_INVALID")
        # A historic dual-account draft may have the SAME proposal timestamp;
        # uniqueness belongs to account identities and epochs, not clock time.
        epochs.add(enrollment["epoch"])
        ids.add(enrollment["account_id"])
        validate_scope(scope, manifest)
        for role in ROLES:
            actual = roots["lanes"][lane]["roots"][role]
            old = enrollment["resources"][role]
            if (old.get("path") != actual.get("path")
                    or old.get("native_id") != actual.get("native_id")
                    or actual.get("native_identity_verified") is not True
                    or actual.get("existing_empty_namespace_verified") is not True
                    or tuple(actual["native_id"]) in used_native_ids):
                raise ValueError("CURRENT_DUAL_ORIGINAL_NATIVE_ROOTS_CHANGED")
            used_native_ids.add(tuple(actual["native_id"]))
        manifest["release"] = selected_digest
        validate_manifest(manifest)
        enrollment["release_digest"] = selected_digest
        enrollment["inception_digest"] = digest(manifest)
        scope["policy_digest"] = digest(manifest)
        validate_scope(scope, manifest)
        validate = validate_qd if lane == "QUALITY_DIPS" else validate_hl
        try:
            validate(enrollment)
        except (ValueError, KeyError, TypeError):
            pass
        else:
            raise ValueError("CURRENT_DUAL_UNAPPROVED_DRAFT_WAS_FINANCIALLY_ACCEPTED")
        output[lane] = {
            "unaccepted_historical_parameters": manifest,
            "unaccepted_historical_enrollment": enrollment,
            "unaccepted_historical_report_scope": scope,
            "original_root_identity_verified": True,
            "writer_process_not_accepted": True,
            "operator_approval_unissued": True,
            "fee_rights_unreviewed": True,
            "opening_timestamp_historical_stale": True,
            "fs1_fs3_not_published": True,
            "operational_market_rights_unaccepted": True,
        }
    if len(used_native_ids) != 12:
        raise ValueError("CURRENT_DUAL_TWELVE_DISTINCT_NATIVE_DIR_IDENTITIES_REQUIRED")
    return {
        "schema": SCHEMA,
        "status": "TWO_CURRENT_RELEASE_ACCOUNT_DRAFTS_UNACCEPTED_NO_FINANCE",
        "native_revision": head["revision"],
        "selected_source_commit": selected["release"],
        "selected_artifact_digest": selected_digest,
        "selected_native_head": selection.digest(head),
        "historical_source_digest": LEGACY_SHA,
        "historical_r15_handoff_digest": HISTORICAL_R15_HANDOFF_DIGEST,
        "two_simulated_account_opening_balances": {
            "QUALITY_DIPS": "1000 USD",
            "HYPERLIQUID": "1000 USDC",
        },
        "accounts": output,
        "missing_real_financial_prerequisites":
            list(OPERATOR_INPUTS_NOT_YET_ACCEPTED),
        "original_native_root_count": 12,
        "native_account_inceptions_published": 0,
        "operator_financial_approval_accepted": False,
        "provider_rights_accepted": False,
        "financial_issuer_present": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "filesystem_writes": 0,
        "network_requests": 0,
    }


def inspect():
    selected, head, historic = selected_and_historical()
    original_roots = inspect_two_lane_native_roots()
    before = deepcopy(original_roots)
    historical = r15_build(
        legacy_proposal(), selected=historic, roots=original_roots)
    result = rebind(
        original=historical, selected=selected,
        head=head, roots=original_roots)
    if inspect_two_lane_native_roots() != before:
        raise ValueError("CURRENT_DUAL_NATIVE_ACCOUNT_ROOTS_CHANGED_DURING_REVIEW")
    return result


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
