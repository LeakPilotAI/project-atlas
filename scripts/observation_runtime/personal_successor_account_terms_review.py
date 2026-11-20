"""Review-only original R26 -> fresh successor financial account manifest proposal.

No directory creation, enrollment, timestamp authority, user approval, provider,
financial publication, account, trading, or PAPER Start. Immutable ORIGINAL
manifest input must have a separately verified native historical journal readback.
The new selected release will need an independently reviewed exact proposal.
"""
from __future__ import annotations

from app.services.paper_financial_replay import body, digest, strict, validate_manifest
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as validate_qd,
)
from app.services.perp_operational_contract import (
    validate_enrollment as validate_hl,
)
from scripts.observation_runtime.personal_paper_inception import (
    validate_personal_inception,
)
from scripts.observation_runtime.personal_successor_native_root_scope import (
    LANES, successor_root_plan,
)
from scripts.observation_runtime.personal_r26_postjournal_historical_guard import (
    R26_DIGEST,
)

SCHEMA="ATLAS_R27_SUCCESSOR_REVIEWABLE_TWO_SIMULATED_ACCOUNT_TERMS_V1"
HASH_KEYS=("QUALITY_DIPS","HYPERLIQUID")
FRESH_FIELDS=frozenset(("release","epoch","opened_at"))
ORIGINAL_EPOCHS={
    "QUALITY_DIPS":"qd-paper-20261024-b2cbd50cfe59475fa3726549365cc253",
    "HYPERLIQUID":"hl-paper-20261108-de437abe-v1",
}
ORIGINAL_ACCOUNTS={
    "QUALITY_DIPS":"atlas-personal-quality-dips",
    "HYPERLIQUID":"atlas-personal-hyperliquid",
}
# Pinned to the independent original native revision-one R26 readback and
# original explicit journal approval. Synthetic lookalike R26 enrollments
# are never a source for carry-forward financial review.
ORIGINAL_ENROLLMENT_DIGESTS={
    "QUALITY_DIPS":"af37e01dd10bbb3e7f7c609d6f2e667e0adcdfd4800e4fc9f223c7762f6e1874",
    "HYPERLIQUID":"d8a555d2ae7736695f6f8ce8126b2d0a3eaa33c17630d1dfe913ce7d3ac8cda0",
}
ORIGINAL_MANIFEST_DIGESTS={
    "QUALITY_DIPS":"d78ff2b23e1e37538be1bfe54f46b10b3a96a60174ab565ba2aa747eb445e044",
    "HYPERLIQUID":"c34a1523af837e80310cbd4e8cd9a0d3051cd226ffba39bd50b6ea99fb55603a",
}
ORIGINAL_ECONOMIC_DIGESTS={
    "QUALITY_DIPS":"8be8ca63eeb253ae3d83b1b9d0694443354a0cc0dee15bcdf9a2e83fdd69ecbe",
    "HYPERLIQUID":"03db50f7a112a105ed1ed38bed200fe25967ec78ccd5f0cbd18d33d28a18ce43",
}


def _report_scope(lane, enrollment, manifest):
    value={
        "schema":"FS3_QD_REPORT_SCOPE_V2" if lane=="QUALITY_DIPS"
                 else "FS3_PERP_REPORT_SCOPE_V3",
        "account_id":enrollment["account_id"],
        "epoch":manifest["epoch"],
        "policy_digest":digest(manifest),
        "timezone":manifest["timezone"],
        "session_reporting_policy":"ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1",
    }
    if lane=="HYPERLIQUID":
        value["funding_reporting_policy"]="POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1"
    return value


def economic_terms(manifest):
    """Immutable financial terms excluding only original epoch identities/time."""
    if type(manifest) is not dict or not FRESH_FIELDS<=set(manifest):
        raise ValueError("SUCCESSOR_ECONOMIC_TERMS_EXACT_ORIGINAL_MANIFEST_REQUIRED")
    return strict(body({key:value for key,value in manifest.items()
                        if key not in FRESH_FIELDS}))


def derive_reviewable_successor_terms(*, plan, old_enrollments, old_manifests,
                                       personal_policy, successor_artifact_digest):
    """Build review packet, not a future approval or a publishable account."""
    if (type(plan) is not dict
            or plan!=successor_root_plan(
                successor_release=plan.get("successor_release"),
                epoch_nonce=plan.get("epoch_nonce"))
            or type(old_enrollments) is not dict
            or type(old_manifests) is not dict
            or set(old_enrollments)!=set(LANES)
            or set(old_manifests)!=set(LANES)
            or type(successor_artifact_digest) is not str
            or len(successor_artifact_digest)!=64
            or any(c not in "0123456789abcdef"
                   for c in successor_artifact_digest)
            or successor_artifact_digest==R26_DIGEST):
        raise ValueError("SUCCESSOR_REVIEW_EXACT_RELEASE_AND_HISTORICAL_INPUTS_REQUIRED")
    from app.services.personal_paper_runtime import validate_policy
    validated_policy=validate_policy(personal_policy)
    preview={}
    for lane in LANES:
        raw_enrollment=old_enrollments[lane]
        old=(validate_qd(raw_enrollment) if lane=="QUALITY_DIPS"
             else validate_hl(raw_enrollment))
        manifest=strict(body(old_manifests[lane]))
        if (old["release_digest"]!=R26_DIGEST
                or manifest["release"]!=R26_DIGEST
                or not (old["epoch"]==manifest["epoch"]==ORIGINAL_EPOCHS[lane])
                or old["account_id"]!=ORIGINAL_ACCOUNTS[lane]
                or digest(old)!=ORIGINAL_ENROLLMENT_DIGESTS[lane]
                or digest(manifest)!=ORIGINAL_MANIFEST_DIGESTS[lane]
                or old["inception_digest"]!=digest(manifest)
                or old["policy_digest"]!=digest(
                    manifest["autonomous_policy"] if lane=="QUALITY_DIPS"
                    else manifest["perp_policy"])
                or type(manifest["opened_at"]) is not int
                or manifest["opened_at"]<=0):
            raise ValueError("SUCCESSOR_REVIEW_ORIGINAL_R26_EPOCH_OR_MANIFEST_MISMATCH")
        # Validate the complete historic economic/identity contract before
        # deriving a review for a new, independently authorized account.
        historical={
            "profile":"PERSONAL_PAPER_ONLY_V1",
            "lane":lane, "personal_policy":validated_policy,
            "native_enrollment":old,
            "parameters":manifest,
            "report_scope":_report_scope(lane,old,manifest),
        }
        if validate_personal_inception(historical)[0]!=lane:
            raise ValueError("SUCCESSOR_REVIEW_HISTORICAL_INCEPTION_REFUSED")
        terms=economic_terms(manifest)
        if digest(terms)!=ORIGINAL_ECONOMIC_DIGESTS[lane]:
            raise ValueError('SUCCESSOR_REVIEW_ORIGINAL_APPROVED_ECONOMICS_CHANGED')
        validate_manifest(manifest)
        future_epoch=plan["lanes"][lane]["epoch"]
        future_account=old["account_id"]+"-recovery-"+plan["epoch_nonce"]
        if (future_epoch==old["epoch"] or future_account==old["account_id"]
                or len(future_account)>256):
            raise ValueError("SUCCESSOR_REVIEW_ORIGINAL_ACCOUNT_IDENTITY_REUSE_REFUSED")
        proposal={
            "lane":lane, "new_epoch":future_epoch,
            "new_account_id":future_account,
            "new_release_digest":successor_artifact_digest,
            "old_original_enrollment_digest":digest(old),
            "old_original_manifest_digest":digest(manifest),
            "economic_terms_digest":digest(terms),
            "exact_economic_terms":terms,
            "prospective_paths":strict(body(plan["lanes"][lane]["roots"])),
            "opening_timestamp_pending_independent_native_UTC":True,
            "new_native_resource_ids_pending":True,
            "new_windows_process_writer_roster_pending":True,
            "future_manifest_must_be_revalidated":True,
            "new_local_operator_financial_review_required":True,
            "account_initialized":False,
        }
        preview[lane]=proposal
    if (preview[LANES[0]]["new_account_id"]==
            preview[LANES[1]]["new_account_id"]
            or preview[LANES[0]]["new_epoch"]==preview[LANES[1]]["new_epoch"]):
        raise ValueError("SUCCESSOR_REVIEW_NEW_ACCOUNT_IDENTITY_ALIAS")
    return strict(body({
        "schema":SCHEMA,
        "status":"EXACT_NEW_EPOCH_TERMS_FOR_OPERATOR_REVIEW_ONLY",
        "source":"TWO_VERIFIED_ORIGINAL_R26_JOURNAL_MANIFESTS",
        "successor_release":plan["successor_release"],
        "successor_artifact_digest":successor_artifact_digest,
        "epoch_nonce":plan["epoch_nonce"],
        "accounts":preview,
        "old_approval_transferred":False,
        "new_operator_approval_issued":False,
        "new_journal_or_account_created":False,
        "original_R26_immutable":True,
        "paper_start_authorized":False,
        "live_money_trading_authorized":False,
    }))
