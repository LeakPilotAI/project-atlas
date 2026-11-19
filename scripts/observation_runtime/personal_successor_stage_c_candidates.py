"""Fresh successor C-stage account candidates for interrupted R26 PAPER epochs.

Memory-only and explicitly reviewed; never creates journal, activation,
account, provider connection, source entitlement, order, or PAPER session.
New issuer authority is separately gated by native original D/E/F approval.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from app.services.paper_financial_replay import body, digest, strict, validate_manifest
from app.services.personal_paper_runtime import validate_policy
from app.services.quality_dips_autonomous_enrollment import WRITERS as QD_WRITERS
from app.services.perp_operational_contract import WRITERS as HL_WRITERS
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.personal_native_original_self_job import (
    NativeOriginalSelfJob, NativeFinancialReleaseAdmission,
)
from scripts.observation_runtime.personal_release_identity import NativePersonalReleaseIdentity
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock, require_version_safe_release_digest,
)
from scripts.observation_runtime.personal_successor_native_root_scope import (
    NativeSelectedSuccessorEpochRoots, LANES, ROLES,
)
from scripts.observation_runtime.personal_successor_account_terms_review import (
    SCHEMA as REVIEW_SCHEMA, ORIGINAL_ACCOUNTS, ORIGINAL_ECONOMIC_DIGESTS,
    ORIGINAL_ENROLLMENT_DIGESTS, ORIGINAL_MANIFEST_DIGESTS,
)
from scripts.observation_runtime.personal_paper_inception import validate_personal_inception
from scripts.observation_runtime.quality_dips_read_service import observe_self

SCHEMA="ATLAS_R27_POSTR26_REVIEWED_SUCCESSOR_STAGE_C_V1"
WRITERS={"QUALITY_DIPS":QD_WRITERS,"HYPERLIQUID":HL_WRITERS}


def _reviewed_in_memory_terms(review, plan, release_digest):
    if (type(review) is not dict or review.get("schema")!=REVIEW_SCHEMA
            or review.get("status")!="EXACT_NEW_EPOCH_TERMS_FOR_OPERATOR_REVIEW_ONLY"
            or review.get("source")!="TWO_VERIFIED_ORIGINAL_R26_JOURNAL_MANIFESTS"
            or review.get("successor_release")!=plan["successor_release"]
            or review.get("epoch_nonce")!=plan["epoch_nonce"]
            or review.get("successor_artifact_digest")!=release_digest
            or review.get("old_approval_transferred") is not False
            or review.get("new_operator_approval_issued") is not False
            or review.get("new_journal_or_account_created") is not False
            or review.get("original_R26_immutable") is not True
            or review.get("paper_start_authorized") is not False
            or review.get("live_money_trading_authorized") is not False
            or type(review.get("accounts")) is not dict
            or set(review["accounts"])!=set(LANES)):
        raise ValueError("R27_STAGE_C_EXACT_UNAPPROVED_SUCCESSOR_REVIEW_REQUIRED")
    for lane in LANES:
        value=review["accounts"][lane]
        if (type(value) is not dict or value.get("lane")!=lane
                or value.get("new_epoch")!=plan["lanes"][lane]["epoch"]
                or value.get("new_account_id")!=ORIGINAL_ACCOUNTS[lane]+"-recovery-"+plan["epoch_nonce"]
                or value.get("new_release_digest")!=release_digest
                or value.get("old_original_enrollment_digest")!=ORIGINAL_ENROLLMENT_DIGESTS[lane]
                or value.get("old_original_manifest_digest")!=ORIGINAL_MANIFEST_DIGESTS[lane]
                or value.get("economic_terms_digest")!=ORIGINAL_ECONOMIC_DIGESTS[lane]
                or digest(value.get("exact_economic_terms"))!=ORIGINAL_ECONOMIC_DIGESTS[lane]
                or value.get("prospective_paths")!=plan["lanes"][lane]["roots"]
                or value.get("opening_timestamp_pending_independent_native_UTC") is not True
                or value.get("new_native_resource_ids_pending") is not True
                or value.get("new_windows_process_writer_roster_pending") is not True
                or value.get("new_local_operator_financial_review_required") is not True
                or value.get("account_initialized") is not False):
            raise ValueError("R27_STAGE_C_ORIGINAL_PINNED_ECONOMICS_OR_ACCOUNT_CHANGED")
    return True


def prepare_fresh_successor_account_candidates(
        *, self_job, release, clock, runtime_id, successor_root_scope,
        reviewed_successor_terms, personal_policy,
        operator_acceptance_ids, approved_unstamped_manifest_digests):
    """Return reviewed C-only candidates with retained new self-Job admission.

    Both EXACT new epoch/financial scope digests must come from a separate
    locally reviewed decision. This function never creates that approval.
    A historical R26 approval is explicitly rejected for new account IDs.
    """
    if (type(self_job) is not NativeOriginalSelfJob
            or type(release) is not NativePersonalReleaseIdentity
            or type(clock) is not NativeVersionSafePaperOperatorClock
            or type(successor_root_scope) is not NativeSelectedSuccessorEpochRoots
            or type(runtime_id) is not str or not runtime_id
            or type(operator_acceptance_ids) is not dict
            or set(operator_acceptance_ids)!=set(LANES)
            or type(approved_unstamped_manifest_digests) is not dict
            or set(approved_unstamped_manifest_digests)!=set(LANES)):
        raise ValueError("R27_STAGE_C_GENUINE_SELECTED_SUCCESSOR_INPUTS_REQUIRED")
    from scripts.observation_runtime.personal_successor_root_provision_once import (
        _attempt_paths, SCHEMA as PROVISION_SCHEMA,
    )
    plan=successor_root_scope.plan
    guard=successor_root_scope.historical_guard
    if (guard.release is not release
            or plan["successor_release"]!=release.root.name
            or Path(__file__).absolute()!=release.root/
               "scripts/observation_runtime/personal_successor_stage_c_candidates.py"
            or self_job.verify() is not True
            or self_job.identity!=observe_self()
            or any(type(v) is not str or not v.startswith("R27_REVIEWED_")
                   for v in operator_acceptance_ids.values())
            or len(set(operator_acceptance_ids.values()))!=2
            or any(type(v) is not str or len(v)!=64
                   or any(c not in "0123456789abcdef" for c in v)
                   for v in approved_unstamped_manifest_digests.values())):
        raise ValueError("R27_STAGE_C_NEW_RELEASE_OPERATOR_AND_PROCESS_BINDING_REQUIRED")
    original=guard.capture()
    if (original.get("original_journals_verified")!=2
            or original.get("original_financial_account_publications")!=0
            or original.get("historical_writer_adoption_authorized") is not False):
        raise ValueError("R27_STAGE_C_HISTORICAL_R26_JOURNALS_NOT_VERIFIED")
    _reviewed_in_memory_terms(reviewed_successor_terms,plan,release.artifact_digest)
    receipt_path, success_path=_attempt_paths(plan)
    if not receipt_path.is_file() or not success_path.is_file():
        raise ValueError("R27_STAGE_C_NATIVE_ROOT_PROVISION_SUCCESS_REQUIRED")
    from scripts.observation_runtime.personal_successor_root_provision_once import SCOPE as ROOT_SCOPE
    import json, hashlib
    raw_intent=receipt_path.read_bytes()
    receipt=strict(success_path.read_bytes())
    if (receipt.get("schema")!=PROVISION_SCHEMA
            or receipt.get("status")!=
               "TWELVE_NEW_EMPTY_ROOTS_NATIVE_ID_VERIFIED_NOT_FINANCIAL_AUTHORITY"
            or receipt.get("intent_sha256")!=hashlib.sha256(raw_intent).hexdigest()
            or receipt.get("scope",{}).get("scope")!=ROOT_SCOPE
            or receipt["scope"].get("terms_review_digest")!=digest(reviewed_successor_terms)
            or receipt["scope"].get("successor_release_digest")!=release.artifact_digest
            or receipt.get("new_financial_directories_created")!=14
            or receipt.get("new_accounts_opened")!=0
            or receipt.get("new_journals_created")!=0
            or receipt.get("paper_start_authorized") is not False
            or receipt.get("live_money_trading_authorized") is not False):
        raise ValueError("R27_STAGE_C_ORIGINAL_NATIVE_ROOT_PROVISION_RECEIPT_REQUIRED")
    from scripts.volume_inspector.windows_output import current_sid
    intent=strict(raw_intent)
    if (intent.get("status")!="CREATE_ONLY_NATIVE_DIRECTORY_ATTEMPT_STARTED"
            or intent.get("operator_sid")!=current_sid()
            or intent.get("scope")!=receipt.get("scope")):
        raise ValueError("R27_STAGE_C_PROVISIONING_OPERATOR_SID_OR_SCOPE_CHANGED")
    roots=successor_root_scope.inspect()
    if (roots["native_root_ids_verified"]!=12
            or roots["all_twelve_distinct_and_empty"] is not True
            or roots["lanes"]!=receipt["native_12_roots"]["lanes"]):
        raise ValueError("R27_STAGE_C_SUCCESSOR_NATIVE_ROOTS_CHANGED")
    if require_version_safe_release_digest(
        clock=clock,runtime_id=runtime_id,release_digest=release.artifact_digest
    ) is not True:
        raise ValueError("R27_STAGE_C_INDEPENDENT_UTC_AND_RELEASE_REQUIRED")
    policy=validate_policy(personal_policy)
    admission=NativeFinancialReleaseAdmission(release=release)
    if admission.verify(release_digest=release.artifact_digest) is None:
        raise ValueError("R27_STAGE_C_GENUINE_NATIVE_SUCCESSOR_ADMISSION_REQUIRED")
    identity={"schema":"QD_OP_PROCESS_ID_V1",**self_job.identity}
    # Recompute and match both approved unstamped manifests BEFORE starting
    # the strict five-second original-account commissioning clock.
    proposals={}
    for lane in LANES:
        terms=reviewed_successor_terms["accounts"][lane]
        m=deepcopy(terms["exact_economic_terms"])
        m["release"]=release.artifact_digest
        m["epoch"]=terms["new_epoch"]
        unstamped=digest(m)
        if approved_unstamped_manifest_digests[lane]!=unstamped:
            raise ValueError("R27_STAGE_C_FRESH_ECONOMIC_TERMS_REQUIRE_NEW_APPROVAL")
        proposals[lane]=m
    clock.require_operational(runtime_id)
    opened=clock()
    if type(opened) is not int or opened<=0:
        raise ValueError("R27_STAGE_C_NATIVE_INTEGER_UTC_REQUIRED")
    result={}
    for lane in LANES:
        terms=reviewed_successor_terms["accounts"][lane]
        manifest=proposals[lane]
        manifest["opened_at"]=opened
        validate_manifest(manifest)
        historical=guard.old_enrollments[lane]
        if (digest(historical)!=ORIGINAL_ENROLLMENT_DIGESTS[lane]
                or historical["release_digest"]==release.artifact_digest
                or operator_acceptance_ids[lane]==historical["acceptance_id"]):
            raise ValueError("R27_STAGE_C_OLD_R26_ACCOUNT_OWNER_OR_APPROVAL_REUSE")
        enrollment=deepcopy(historical)
        enrollment["epoch"]=terms["new_epoch"]
        enrollment["account_id"]=terms["new_account_id"]
        enrollment["release_digest"]=release.artifact_digest
        enrollment["inception_digest"]=digest(manifest)
        enrollment["writers"]={role:deepcopy(identity) for role in WRITERS[lane]}
        enrollment["clock_source"]=SOURCE
        enrollment["acceptance_id"]=operator_acceptance_ids[lane]
        enrollment["resources"]={
            role:{"path":roots["lanes"][lane]["roots"][role]["path"],
                  "native_id":roots["lanes"][lane]["roots"][role]["native_id"]}
            for role in ROLES
        }
        report={
            "schema":"FS3_QD_REPORT_SCOPE_V2" if lane=="QUALITY_DIPS"
                     else "FS3_PERP_REPORT_SCOPE_V3",
            "account_id":enrollment["account_id"],
            "epoch":enrollment["epoch"],"policy_digest":digest(manifest),
            "timezone":manifest["timezone"],
            "session_reporting_policy":"ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1"}
        if lane=="HYPERLIQUID":
            report["funding_reporting_policy"]="POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1"
        entry={"profile":"PERSONAL_PAPER_ONLY_V1","lane":lane,
               "personal_policy":deepcopy(policy),"native_enrollment":enrollment,
               "parameters":manifest,"report_scope":report}
        real_lane,e,m=validate_personal_inception(entry)
        if real_lane!=lane or e!=enrollment or m!=manifest:
            raise ValueError("R27_STAGE_C_NEW_ACCOUNT_INCEPTION_SHAPE_REFUSED")
        result[lane]=entry
    if (clock()-opened>2 or self_job.verify() is not True
            or successor_root_scope.inspect()!=roots):
        raise ValueError("R27_STAGE_C_SUCCESSOR_FRESH_NATIVE_STATE_EXPIRED")
    return strict(body(result)),admission
