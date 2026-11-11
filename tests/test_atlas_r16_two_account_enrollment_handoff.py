"""Actual selected R16 two-account financial draft rebind, READ ONLY.

These are explicitly UNACCEPTED PAPER account proposals, not balances held
in actual financial native files. All negative cases use in-memory copies.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.services.paper_financial_replay import digest, validate_manifest
from app.services.paper_daily_report import validate_scope
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as qd_validate,
)
from app.services.perp_operational_contract import (
    validate_enrollment as hl_validate,
)
from scripts.observation_runtime import atlas_r16_two_account_enrollment_handoff as r16
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    build_handoff as r15_build, legacy_proposal,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import selected_code
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)


@pytest.fixture(scope="module")
def actual():
    roots=inspect_two_lane_native_roots()
    before=copy.deepcopy(roots)
    historic=r15_build(
        legacy_proposal(),selected=r16.historical_r15_reference(),roots=roots)
    current=selected_code()
    proposal=r16.rebind(
        historic_r15=historic,selected_r16=current,roots=roots)
    assert roots == before
    return historic,current,roots,proposal


def test_actual_selected_r16_preinception_two_account_proposal_is_genuine_and_unapproved(actual):
    historical,current,roots,proposal=actual
    assert proposal["schema"]==r16.SCHEMA
    assert proposal["status"]=="R16_TWO_LANE_CURRENT_CODE_PROPOSAL_ONLY_UNACCEPTED"
    assert proposal["selected_r16_source_commit"]==r16.R16_SOURCE
    assert proposal["selected_r16_artifact_digest"]==r16.R16_ARTIFACT
    assert proposal["selected_native_revision"]==15
    assert proposal["selected_native_head"]==r16.R16_HEAD
    assert proposal["selected_native_record_sha256"]==r16.R16_RECORD_SHA
    assert proposal["historical_r15_rebind_digest"]==digest(historical)
    assert proposal["original_historical_v5_proposal_sha256"]==r16.LEGACY_SHA
    assert proposal["native_original_empty_root_count_verified"]==12
    assert proposal["account_count"]==2
    assert proposal["actual_financial_writer_roles_enrolled"]==0
    assert proposal["native_financial_inceptions_published"]==0
    assert proposal["accepted_financial_operating_gates"]==0
    assert proposal["financial_paper_start_authorized"] is False
    assert proposal["live_trading_authorized"] is False
    assert proposal["filesystem_mutations"]==0
    assert proposal["provider_requests"]==0
    assert set(proposal["accounts"])==set(r16.LANES)
    assert current["selected_revision"]==15
    assert roots["all_twelve_distinct_and_empty"] is True


def test_frozen_real_r16_manifest_digest_scope_and_native_roots_unchanged(actual):
    historical,current,roots,proposal=actual
    pinned = {
        "QUALITY_DIPS": "778380e25decdfd63f913754c160146b0134bcc966864b52a2250d4530769067",
        "HYPERLIQUID": "ce4cd1dc55c5a51ea32e93f17c99ec8adabb1ff5d289a454472a2a8f2faaefbb",
    }
    original=legacy_proposal()
    for lane in r16.LANES:
        item=proposal["accounts"][lane]
        previous=historical["accounts"][lane]
        params=item["provisional_r16_parameters"]
        enrollment=item["provisional_r16_enrollment_unaccepted"]
        scope=item["provisional_r16_report_scope_unaccepted"]
        assert params["opening_cash"]=="1000"
        assert params["timezone"]==("America/New_York" if lane=="QUALITY_DIPS" else "UTC")
        assert params["release"]==enrollment["release_digest"]==r16.R16_ARTIFACT
        assert enrollment["inception_digest"]==digest(params)==pinned[lane]
        assert item["provisional_r16_manifest_digest"]==pinned[lane]
        assert scope["policy_digest"]==digest(params)
        assert scope["timezone"]==params["timezone"]
        assert enrollment["writers"] is None
        assert enrollment["acceptance_id"] is None
        assert enrollment["account_id"]==previous[
            "provisional_r15_native_enrollment_unaccepted"]["account_id"]
        assert enrollment["epoch"]==previous[
            "provisional_r15_native_enrollment_unaccepted"]["epoch"]
        assert params["opened_at"]==original["accounts"][lane]["parameters"]["opened_at"]
        assert item["opening_timestamp_historical_not_current"] is True
        assert item["real_writer_roster_present"] is False
        assert item["accepted_operator_inception"] is False
        assert item["financial_inception_published"] is False
        assert item["provider_source_rights_accepted"] is False
        assert item["fee_policy_historical_review_only"] is True
        assert len(item["required_live_inputs"])==6
        assert enrollment["resources"]==previous[
            "provisional_r15_native_enrollment_unaccepted"]["resources"]
        assert set(enrollment["resources"])==set(r16.ROLES)
        for role in r16.ROLES:
            real=roots["lanes"][lane]["roots"][role]
            assert enrollment["resources"][role]["path"]==real["path"]
            assert enrollment["resources"][role]["native_id"]==real["native_id"]
        validate_manifest(params)
        validate_scope(scope,params)
        with pytest.raises(ValueError):
            (qd_validate if lane=="QUALITY_DIPS" else hl_validate)(enrollment)


def test_current_original_selected_r16_and_historical_native_r15_both_read_back(actual):
    historical,current,roots,proposal=actual
    ref=r16.historical_r15_reference()
    assert ref["revision"]==14
    assert ref["selected_native_head"]==r16.R15_HEAD
    assert ref["installed_receipt_sha256"]==r16.R15_RECEIPT_SHA
    assert ref["financial_authority"] is False
    assert current["selected_native_head"]==r16.R16_HEAD
    assert current["financial_writer_operational_accepted"] is False
    assert historical["selected_r15_artifact_digest"]==r16.R15_ARTIFACT


def test_pure_rebinding_never_mutates_input_and_is_reproducible(actual):
    historical,current,roots,proposal=actual
    saved=copy.deepcopy((historical,current,roots))
    first=r16.rebind(historic_r15=historical,selected_r16=current,roots=roots)
    second=r16.rebind(historic_r15=historical,selected_r16=current,roots=roots)
    assert first==second==proposal
    assert (historical,current,roots)==saved


@pytest.mark.parametrize("which", [
    "wrong_selected_revision","wrong_native_head","wrong_artifact",
    "fake_paper_start","fake_provider","fake_writer_operational",
    "invalid_native_chain","invalid_source_commit",
    "historic_source_digest","historic_enrollment_claim",
    "historic_inception_claim","historic_wrong_release",
    "historic_wrong_native_head","historic_financial_gates",
    "historic_qd_writer_invented","historic_hl_acceptance_invented",
    "historic_qd_release_mismatch","historic_hl_manifest_digest",
    "historic_qd_cash_changed","historic_qd_timezone_changed",
    "historic_hl_timezone_changed","historic_qd_scope_digest",
    "historic_hl_account_clash","historic_epochs_clash",
    "historic_qd_root_identity_changed","historic_hl_path_changed",
    "historic_duplicate_native_root","historic_qd_real_accepted",
    "root_no_longer_empty","root_occupancy_counter",
    "root_identity_lost","root_provider_grant_claim",
    "root_unknown_lane","root_alias",
])
def test_current_unapproved_r16_draft_refuses_tampered_evidence(actual,which):
    historical,current,roots,_=actual
    h,s,n=copy.deepcopy((historical,current,roots))
    qd=h["accounts"]["QUALITY_DIPS"]
    hl=h["accounts"]["HYPERLIQUID"]
    qdp=qd["provisional_r15_parameters"]
    hlp=hl["provisional_r15_parameters"]
    qde=qd["provisional_r15_native_enrollment_unaccepted"]
    hle=hl["provisional_r15_native_enrollment_unaccepted"]
    if which=="wrong_selected_revision":s["selected_revision"]=14
    elif which=="wrong_native_head":s["selected_native_head"]="0"*64
    elif which=="wrong_artifact":s["installed_artifact_digest"]="0"*64
    elif which=="fake_paper_start":s["paper_start_authorized"]=True
    elif which=="fake_provider":s["provider_source_operational_accepted"]=True
    elif which=="fake_writer_operational":s["financial_writer_operational_accepted"]=True
    elif which=="invalid_native_chain":s["native_selection_append_only_chain_verified"]=False
    elif which=="invalid_source_commit":s["selected_release"]="f"*40
    elif which=="historic_source_digest":h["historical_unapproved_source_sha256"]="0"*64
    elif which=="historic_enrollment_claim":h["account_enrollment_accepted"]=True
    elif which=="historic_inception_claim":h["both_financial_inceptions_published"]=True
    elif which=="historic_wrong_release":h["selected_r15_artifact_digest"]="0"*64
    elif which=="historic_wrong_native_head":h["selected_native_head"]="0"*64
    elif which=="historic_financial_gates":h["financial_operating_gates_accepted"]=1
    elif which=="historic_qd_writer_invented":qde["writers"]={"source":{"pid":99}}
    elif which=="historic_hl_acceptance_invented":hle["acceptance_id"]="FAKE"
    elif which=="historic_qd_release_mismatch":qdp["release"]="f"*64
    elif which=="historic_hl_manifest_digest":hl["provisional_inception_digest"]="0"*64
    elif which=="historic_qd_cash_changed":qdp["opening_cash"]="10000"
    elif which=="historic_qd_timezone_changed":qdp["timezone"]="America/Chicago"
    elif which=="historic_hl_timezone_changed":hlp["timezone"]="America/Chicago"
    elif which=="historic_qd_scope_digest":qd["provisional_report_scope_unaccepted"]["policy_digest"]="0"*64
    elif which=="historic_hl_account_clash":hle["account_id"]=qde["account_id"]
    elif which=="historic_epochs_clash":hle["epoch"]=qde["epoch"]
    elif which=="historic_qd_root_identity_changed":qde["resources"]["source"]["native_id"]=[0,0,0]
    elif which=="historic_hl_path_changed":hle["resources"]["source"]["path"]=r"D:\FOREIGN"
    elif which=="historic_duplicate_native_root":
        hle["resources"]["source"]["native_id"]=qde["resources"]["source"]["native_id"]
    elif which=="historic_qd_real_accepted":qd["real_enrollment_accepted"]=True
    elif which=="root_no_longer_empty":n["all_twelve_distinct_and_empty"]=False
    elif which=="root_occupancy_counter":n["existing_empty_root_namespaces"]=11
    elif which=="root_identity_lost":n["native_root_ids_verified"]=11
    elif which=="root_provider_grant_claim":n["writer_ownership_verified"]=True
    elif which=="root_unknown_lane":n["lanes"].pop("QUALITY_DIPS")
    elif which=="root_alias":
        n["lanes"]["HYPERLIQUID"]["roots"]["source"]["native_id"]=n[
            "lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"]
    with pytest.raises((ValueError,TypeError,KeyError)):
        r16.rebind(historic_r15=h,selected_r16=s,roots=n)


def test_full_real_read_only_inspect_matches_pure_verified_handoff(actual):
    historical,current,roots,proposal=actual
    result=r16.inspect()
    assert result==proposal
    assert result["filesystem_mutations"]==0
    assert result["provider_requests"]==0
    assert not Path(r16.__file__).is_symlink()


def test_recomputed_nested_manifest_digests_cannot_rewrite_pinned_historical_account(actual):
    historical,current,roots,_=actual
    changed=copy.deepcopy(historical)
    qd=changed["accounts"]["QUALITY_DIPS"]
    params=qd["provisional_r15_parameters"]
    # Even a self-consistent new digest for a changed historical timestamp
    # cannot impersonate the original real/native R15 review-only bundle.
    opened=params["opened_at"]
    params["opened_at"] = opened+1 if type(opened) is int else str(opened)+"_FORGED"
    recalculated=digest(params)
    qd["provisional_inception_digest"]=recalculated
    qd["provisional_r15_native_enrollment_unaccepted"]["inception_digest"]=recalculated
    qd["provisional_report_scope_unaccepted"]["policy_digest"]=recalculated
    with pytest.raises(ValueError,match="R16_DRAFT_VERIFIED_UNAPPROVED_HISTORICAL_R15_INPUT_REQUIRED"):
        r16.rebind(historic_r15=changed,selected_r16=current,roots=roots)


def test_history_outer_draft_fields_cannot_be_relabelled_without_original_digest(actual):
    historical,current,roots,_=actual
    changed=copy.deepcopy(historical)
    changed["accounts"]["HYPERLIQUID"][
        "historical_draft_reporting_timezone"]="Europe/London"
    with pytest.raises(ValueError,match="R16_DRAFT_VERIFIED_UNAPPROVED_HISTORICAL_R15_INPUT_REQUIRED"):
        r16.rebind(historic_r15=changed,selected_r16=current,roots=roots)


def test_current_revision_15_historical_14_digest_pins_are_exact(actual):
    historical,current,roots,proposal=actual
    assert digest(historical)==r16.HISTORICAL_R15_HANDOFF_DIGEST
    assert proposal["historical_r15_rebind_digest"]==r16.HISTORICAL_R15_HANDOFF_DIGEST
    assert digest(proposal)==(
        "57c3dc502cb5a5e70885bf016364ea1746b47a6f5b2027169d8ee77e066678db")
