"""Exact R27-to-successor code-only financial-root carry-forward evidence.

Read-only; does NOT transfer financial account approvals. The one previously
authorized, EMPTY R27 successor epoch may be bound by newer selected code only
when immutable R27 review, root provisioning, operator SID, old R26 journals,
and same 12 protected NTFS identities remain independently authenticated.
Never use R26 original roots, arbitrary historical epochs, or a new mkdir.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.paper_financial_replay import digest,strict,body
from scripts.observation_runtime.personal_successor_native_root_scope import (
    successor_root_plan,
)
from scripts.volume_inspector.windows_output import current_sid

R27_SOURCE="f528398fa73bcb51011f3aa2fad7b78e1bab5623"
R27_ARTIFACT="1c11c293ee006745955f828c89842ead7dca824bb61e1f068ad67f9d59f400a6"
EPOCH_NONCE="0123456789abcdef01234567"
PROVISION_ROOT=Path(r"D:\Work\Project Atlas\logs\diagnostics")
REVIEW=PROVISION_ROOT/"atlas-r27-selected-successor-simulated-account-review-20261119-r01.json"
REVIEW_SHA="78aa6218c2d195ef06e7e4e5772a06ef5b07d4de49b21e807c1668215d0f568d"
TOKEN=R27_SOURCE[:12]+"-"+EPOCH_NONCE
ATTEMPT=PROVISION_ROOT/("atlas-r27-successor-root-provision-attempt-"+TOKEN+".json")
ATTEMPT_SHA="82833680f930318046ac16a90aaee7592764069125e1d1ade0218d41d2f7cf44"
SUCCESS=PROVISION_ROOT/("atlas-r27-successor-root-provision-success-"+TOKEN+".json")
SUCCESS_SHA="95d53b5790503c12344d3f483dcdfd88265f9f2a77c056b8035598b5efe134aa"
SELECTED_R27=Path(r"D:\AtlasRuntime\selection\r0027.json")
SELECTED_R27_SHA="833534fca0da802046445c1d6225f743a8010db66bedc42fe6e1cb25d599ec20"
CARRIED_SCHEMA="ATLAS_R27_EXACT_APPROVED_EMPTY_ROOTS_CODE_ONLY_CARRYFORWARD_V1"


def _read_exact(path,checksum):
    if (not path.is_file() or path.is_symlink() or path.is_junction()
            or len(checksum)!=64):
        raise ValueError("R27_CARRYFORWARD_PINNED_NATIVE_RECORD_MISSING")
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=checksum:
        raise ValueError("R27_CARRYFORWARD_PINNED_NATIVE_RECORD_CHANGED")
    return strict(raw)


def verified_carried_r27_roots(*, plan, selected_code_release,
                                selected_code_digest):
    """Return exact old permission provenance; no new operator financial grant.

    Source transition is code-only: the financially approved 12 empty roots
    remain owned by R27's original directory decision. New release must be a
    DIFFERENT genuinely selected code and create its OWN economic review,
    operator approval, and financial account journals.
    """
    if (type(plan) is not dict
            or plan!=successor_root_plan(
                successor_release=R27_SOURCE,epoch_nonce=EPOCH_NONCE)
            or type(selected_code_release) is not str
            or len(selected_code_release)!=40
            or any(x not in "0123456789abcdef" for x in selected_code_release)
            or selected_code_release==R27_SOURCE
            or type(selected_code_digest) is not str
            or len(selected_code_digest)!=64
            or any(x not in "0123456789abcdef" for x in selected_code_digest)
            or selected_code_digest==R27_ARTIFACT):
        raise ValueError("R27_CARRYFORWARD_EXACT_OLD_EPOCH_AND_NEW_RELEASE_REQUIRED")
    sealed_selector=_read_exact(SELECTED_R27,SELECTED_R27_SHA)
    r27_selector=sealed_selector.get("record",{})
    if (r27_selector.get("revision")!=27
            or r27_selector.get("selected",{}).get("release")!=R27_SOURCE
            or r27_selector["selected"].get("artifact_digest")!=R27_ARTIFACT
            or type(sealed_selector.get("native_id")) is not list
            or len(sealed_selector["native_id"])!=3):
        raise ValueError("R27_CARRYFORWARD_GENUINE_PREDECESSOR_RELEASE_REQUIRED")
    review=_read_exact(REVIEW,REVIEW_SHA)
    intent=_read_exact(ATTEMPT,ATTEMPT_SHA)
    success=_read_exact(SUCCESS,SUCCESS_SHA)
    from scripts.observation_runtime.personal_successor_root_provision_once import (
        SCHEMA as ROOT_SCHEMA,SCOPE as ROOT_SCOPE,
    )
    if (review.get("selected_release")!=R27_SOURCE
            or review.get("selected_artifact_digest")!=R27_ARTIFACT
            or review.get("plan")!=plan
            or review.get("new_operator_financial_review_completed") is not False
            or review.get("new_financial_journals_created")!=0
            or review.get("simulated_accounts_initialized")!=0
            or review.get("successor_terms_review_digest")!=digest(
                review.get("successor_terms_review"))
            or intent.get("status")!="CREATE_ONLY_NATIVE_DIRECTORY_ATTEMPT_STARTED"
            or intent.get("operator_sid")!=current_sid()
            or success.get("schema")!=ROOT_SCHEMA
            or success.get("status")!=
               "TWELVE_NEW_EMPTY_ROOTS_NATIVE_ID_VERIFIED_NOT_FINANCIAL_AUTHORITY"
            or success.get("intent_sha256")!=ATTEMPT_SHA
            or success.get("scope")!=intent.get("scope")
            or success.get("scope",{}).get("scope")!=ROOT_SCOPE
            or success["scope"].get("successor_release")!=R27_SOURCE
            or success["scope"].get("successor_release_digest")!=R27_ARTIFACT
            or success["scope"].get("terms_review_digest")!=
               review["successor_terms_review_digest"]
            or success["scope"].get("plan_digest")!=digest(plan)
            or success.get("new_financial_directories_created")!=14
            or success.get("new_journals_created")!=0
            or success.get("new_accounts_opened")!=0
            or success.get("paper_start_authorized") is not False
            or success.get("live_money_trading_authorized") is not False
            or success.get("native_12_roots",{}).get("native_root_ids_verified")!=12
            or success["native_12_roots"].get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R27_CARRYFORWARD_EXACT_ROOT_APPROVAL_PROVENANCE_REQUIRED")
    result={
        "schema":CARRIED_SCHEMA,
        "status":"ORIGINAL_R27_PROTECTED_EMPTY_ROOTS_REVIEWED_CODE_ONLY_CARRY_NO_ACCOUNTS",
        "R27_provisioning_success_sha256":SUCCESS_SHA,
        "R27_provisioning_intent_sha256":ATTEMPT_SHA,
        "R27_terms_review_sha256":REVIEW_SHA,
        "R27_operator_sid":intent["operator_sid"],
        "plan_digest":digest(plan),
        "original_R27_terms_digest":review["successor_terms_review_digest"],
        "original_R27_artifact_digest":R27_ARTIFACT,
        "selected_code_release":selected_code_release,
        "selected_code_artifact_digest":selected_code_digest,
        "original_R26_accounts_adopted":False,
        "new_financial_account_approval_issued":False,
        "new_financial_journal_creation_authorized":False,
        "paper_start_authorized":False,
        "live_money_trading_authorized":False,
    }
    return strict(body(result)),success["native_12_roots"]
