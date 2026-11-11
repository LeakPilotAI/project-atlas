"""R15 real FS1/FS3 financial accounting pre-inception, never native approval."""
import copy
from datetime import UTC,datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.paper_daily_report import validate_scope
from app.services.paper_financial_replay import digest
from scripts.observation_runtime import atlas_r15_two_account_preinception_audit as audit
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    inspect as inspect_handoff, legacy_proposal,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)


@pytest.fixture(scope="module")
def witnesses():
    p=inspect_handoff()
    r=inspect_two_lane_native_roots()
    return {"proposal":p,"roots":r}


def _timestamp():
    return int(datetime.now(UTC).timestamp())


def test_r15_provisional_qd_account_calendar_is_america_new_york(witnesses):
    original=legacy_proposal()
    old=original["accounts"]["QUALITY_DIPS"]
    assert old["parameters"]["timezone"]=="America/Chicago"
    assert old["report_scope_draft"]["timezone"]=="America/Chicago"
    new=witnesses["proposal"]["accounts"]["QUALITY_DIPS"]
    m=new["provisional_r15_parameters"]
    scope=new["provisional_report_scope_unaccepted"]
    assert m["timezone"]==scope["timezone"]=="America/New_York"
    assert scope["policy_digest"]==digest(m)==new["provisional_inception_digest"]
    assert new["provisional_r15_native_enrollment_unaccepted"]["inception_digest"]==digest(m)
    assert new["historical_draft_reporting_timezone"]=="America/Chicago"
    assert new["provisional_fs3_calendar_validated_without_publication"] is True
    validate_scope(scope,m)
    perp=witnesses["proposal"]["accounts"]["HYPERLIQUID"]
    assert perp["provisional_r15_parameters"]["timezone"]=="UTC"
    assert perp["provisional_report_scope_unaccepted"]["timezone"]=="UTC"
    assert perp["historical_draft_reporting_timezone"]=="UTC"
    validate_scope(perp["provisional_report_scope_unaccepted"],
                   perp["provisional_r15_parameters"])


def test_actual_unpublished_both_account_fs1_fs3_arithmetic_separates_currencies(witnesses):
    original=copy.deepcopy(witnesses)
    r=audit.evaluate(**witnesses,observed_at=_timestamp())
    assert witnesses==original
    assert r["status"]=="TWO_LANE_PREINCEPTION_FS1_FS3_ARITHMETIC_VERIFIED_ONLY"
    assert r["hypothetical_unpublished_report_count"]==2
    assert r["separate_simulated_usd_and_usdc_balances"] is True
    assert r["cash_netting_or_exchange_conversion_performed"] is False
    assert r["unapproved_historical_inception_timestamps_must_be_replaced"] is True
    assert set(r["accounts"])=={"QUALITY_DIPS","HYPERLIQUID"}
    assert r["accounts"]["QUALITY_DIPS"]["currency"]=="USD"
    assert r["accounts"]["QUALITY_DIPS"]["report_calendar"]=="America/New_York"
    assert r["accounts"]["HYPERLIQUID"]["currency"]=="USDC"
    assert r["accounts"]["HYPERLIQUID"]["report_calendar"]=="UTC"
    for lane in ("QUALITY_DIPS","HYPERLIQUID"):
        a=r["accounts"][lane]
        assert a["opening_cash"]=="1000" and a["initial_cash_state"]=="1000"
        assert a["fs1_empty_initial_state_audited"] is True
        assert a["fs3_unpublished_initial_daily_report_arithmetic_audited"] is True
        assert a["initial_open_positions"]==0 and a["source_events"]==0
        assert a["unpublished_report_status"]=="INCOMPLETE"
        assert a["opened_at_is_historical_not_authorized"] is True
        assert a["report_is_native_bound"] is False
        assert a["financial_account_inception_published"] is False
        assert a["native_initial_financial_ledger_accepted"] is False
        assert a["paper_order_authorized"] is False
    for key in ("operator_activation_accepted",
                "current_provider_rights_accepted",
                "writer_enrollment_accepted",
                "native_financial_accounts_incepted",
                "financial_ledger_publication_authorized",
                "paper_start_authorized","real_money_trading_authorized"):
        assert r[key] is False
    for key in ("native_account_file_writes","external_provider_requests",
                "paper_orders_created"):
        assert r[key]==0


@pytest.mark.parametrize("damage",[
    "qd_old_calendar","qd_scope_old_calendar","qd_wrong_manifest_digest",
    "qd_wrong_inception_digest","qd_unexpected_cash","qd_misplaced_usdc",
    "qd_account_identity_changed","qd_observed_writer",
    "qd_forged_operator_acceptance","qd_fake_reporting_certification",
    "qd_wrong_native_source_handle","qd_root_path_alias",
    "hl_wrong_usd","hl_not_utc","hl_oversized_cash","hl_forged_fee_approval",
    "hl_pretend_native_inception","hl_unmatched_epoch","hl_wrong_report_scope",
    "full_proposal_forged_start","full_proposal_forged_financial_release",
    "full_proposal_missing_lane","physical_root_disappeared","physical_root_occupied",
    "physical_root_modified_id","physical_extra_lane",
])
def test_r15_preinception_fs1_fs3_refuses_wrong_financial_source_or_approval(
        witnesses,damage):
    inputs=copy.deepcopy(witnesses)
    p=inputs["proposal"]
    q=p["accounts"]["QUALITY_DIPS"]
    h=p["accounts"]["HYPERLIQUID"]
    if damage=="qd_old_calendar":
        q["provisional_r15_parameters"]["timezone"]="America/Chicago"
    elif damage=="qd_scope_old_calendar":
        q["provisional_report_scope_unaccepted"]["timezone"]="America/Chicago"
    elif damage=="qd_wrong_manifest_digest":
        q["provisional_inception_digest"]="0"*64
    elif damage=="qd_wrong_inception_digest":
        q["provisional_r15_native_enrollment_unaccepted"]["inception_digest"]="0"*64
    elif damage=="qd_unexpected_cash":
        q["provisional_r15_parameters"]["opening_cash"]="2000"
    elif damage=="qd_misplaced_usdc":
        q["provisional_r15_parameters"]["currency"]="USDC"
    elif damage=="qd_account_identity_changed":
        q["provisional_report_scope_unaccepted"]["account_id"]="SOMEONE_ELSE"
    elif damage=="qd_observed_writer":
        q["provisional_r15_native_enrollment_unaccepted"]["writers"]={"decision":{"pid":111}}
    elif damage=="qd_forged_operator_acceptance":
        q["provisional_r15_native_enrollment_unaccepted"]["acceptance_id"]="FAKE"
    elif damage=="qd_fake_reporting_certification":
        q["provisional_fs3_calendar_validated_without_publication"]=False
    elif damage=="qd_wrong_native_source_handle":
        q["provisional_r15_native_enrollment_unaccepted"]["resources"]["source"]["native_id"]=[1,2,3]
    elif damage=="qd_root_path_alias":
        q["provisional_r15_native_enrollment_unaccepted"]["resources"]["source"]["path"]="D:\\OTHER"
    elif damage=="hl_wrong_usd":
        h["provisional_r15_parameters"]["currency"]="USD"
    elif damage=="hl_not_utc":
        h["provisional_r15_parameters"]["timezone"]="America/New_York"
    elif damage=="hl_oversized_cash":
        h["provisional_r15_parameters"]["opening_cash"]="2000"
    elif damage=="hl_forged_fee_approval":
        h["account_fee_entitlement_verified"]=True
    elif damage=="hl_pretend_native_inception":
        h["financial_inception_published"]=True
    elif damage=="hl_unmatched_epoch":
        h["provisional_report_scope_unaccepted"]["epoch"]="foreign"
    elif damage=="hl_wrong_report_scope":
        h["provisional_report_scope_unaccepted"]["policy_digest"]="0"*64
    elif damage=="full_proposal_forged_start":
        p["paper_start_authorized"]=True
    elif damage=="full_proposal_forged_financial_release":
        p["selected_r15_artifact_digest"]="0"*64
    elif damage=="full_proposal_missing_lane":
        p["accounts"].pop("HYPERLIQUID")
    elif damage=="physical_root_disappeared":
        inputs["roots"]["native_root_ids_verified"]=11
    elif damage=="physical_root_occupied":
        inputs["roots"]["existing_empty_root_namespaces"]=11
    elif damage=="physical_root_modified_id":
        inputs["roots"]["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"]=[1,2,3]
    elif damage=="physical_extra_lane":
        inputs["roots"]["lanes"]["OTHER"]={"epoch":"OTHER","roots":{}}
    with pytest.raises((ValueError,TypeError,KeyError)):
        audit.evaluate(**inputs,observed_at=_timestamp())


@pytest.mark.parametrize("offset",[-3600,0])
def test_r15_preinception_historical_inception_time_not_a_new_financial_inception(
        witnesses,offset):
    past=witnesses["proposal"]["accounts"]["QUALITY_DIPS"]["provisional_r15_parameters"]["opened_at"]
    with pytest.raises(ValueError):
        audit.evaluate(**witnesses,observed_at=past+offset)


def test_r15_real_native_preinception_inspection_does_not_publish_any_account():
    r=audit.inspect()
    assert r["hypothetical_unpublished_report_count"]==2
    assert r["accounts"]["HYPERLIQUID"]["report_is_native_bound"] is False
    assert r["accounts"]["QUALITY_DIPS"]["report_is_native_bound"] is False
    assert r["native_account_file_writes"]==0
    assert r["paper_start_authorized"] is False
