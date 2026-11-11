"""Actual selected R16 two-account FS1/FS3 financial arithmetic only.

Runs genuine in-memory financial replay and independent auditors on exact
native READ-ONLY selected R16 draft/root evidence. It never commissions
accounts, requests market quotes, creates a native ledger or issues orders.
"""
from __future__ import annotations

import copy
import json
from datetime import UTC, datetime

import pytest

from app.services.paper_financial_replay import digest
from scripts.observation_runtime import atlas_r16_two_account_financial_arithmetic as audit
from scripts.observation_runtime.atlas_r16_two_account_enrollment_handoff import inspect as proposal_inspect
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

# Entirely deterministic OBSERVATION-only UTC; never an accepted financial clock.
OBSERVED = int(datetime(2026, 11, 11, 20, tzinfo=UTC).timestamp())


@pytest.fixture(scope="module")
def grounded():
    proposal=proposal_inspect()
    roots=inspect_two_lane_native_roots()
    policy=json.loads(audit.POLICY_PATH.read_text(encoding="utf-8-sig"))
    values=audit.evaluate(
        proposal=proposal, roots=roots, observed_at=OBSERVED,
        personal_policy=policy)
    return proposal, roots, policy, values


def test_selected_r16_two_distinct_account_fs1_fs3_are_audited_without_native_inception(grounded):
    proposal,roots,policy,observed=grounded
    assert observed["schema"]==audit.SCHEMA
    assert observed["status"]=="R16_SELECTED_TWO_LANE_FS1_FS3_ARITHMETIC_PREVIEW_ONLY"
    assert observed["selected_native_revision"]==15
    assert observed["selected_native_head"]==audit.R16_HEAD
    assert observed["unaccepted_r16_source_draft_digest"]==audit.DRAFT_DIGEST
    assert observed["opening_cash_kept_separate_in_usd_and_usdc"] is True
    assert observed["usd_to_usdc_conversion_or_netting_performed"] is False
    assert observed["required_real_writer_roles_unenrolled"]==12
    assert observed["unpublished_initial_daily_reports"]==2
    assert observed["historical_inception_timestamps_must_be_replaced"] is True
    assert observed["operator_financial_authority_accepted"] is False
    assert observed["independent_financial_clock_lease_accepted"] is False
    assert observed["provider_market_rights_accepted"] is False
    assert observed["native_financial_accounts_incepted"] is False
    assert observed["paper_start_authorized"] is False
    assert observed["live_trading_authorized"] is False
    assert observed["native_financial_account_files_written"]==0
    assert observed["network_provider_requests"]==0
    assert observed["paper_orders_created"]==0
    assert set(observed["accounts"])=={"QUALITY_DIPS","HYPERLIQUID"}
    assert roots["native_root_total"]==12
    assert roots["all_twelve_distinct_and_empty"] is True
    assert digest(proposal)==audit.DRAFT_DIGEST
    assert digest(policy)==audit.POLICY_DIGEST


def test_two_lane_cash_silos_and_native_source_heads_bound_to_current_r16(grounded):
    proposal,_,_,v=grounded
    cash_by_lane={"QUALITY_DIPS":("USD","America/New_York",5),
                  "HYPERLIQUID":("USDC","UTC",7)}
    original={key:x.copy() for key,x in v["accounts"].items()}
    for lane,(currency,timezone,roles) in cash_by_lane.items():
        item=v["accounts"][lane]
        original_manifest=proposal["accounts"][lane]["provisional_r16_parameters"]
        assert item["account_id"]==proposal["accounts"][lane][
            "provisional_r16_enrollment_unaccepted"]["account_id"]
        assert item["epoch"]==original_manifest["epoch"]
        assert item["currency"]==currency
        assert item["opening_cash"]==item["in_memory_initial_cash"]=="1000"
        assert item["in_memory_initial_positions"]==0
        assert item["initial_financial_source_events"]==0
        assert item["reporting_timezone"]==timezone
        assert item["observed_reporting_day"]=="2026-11-11"
        assert item["fs1_empty_replay_and_independent_audit_passed"] is True
        assert item["fs3_daily_report_and_independent_audit_passed"] is True
        assert item["fs3_unpublished_report_status"]=="INCOMPLETE"
        assert item["source_head_hypothetical_only"]==item["manifest_digest_provisional"]
        assert item["manifest_digest_provisional"]==audit.MANIFEST_DIGESTS[lane]
        assert item["historical_opened_at_is_not_current_financial_inception"] is True
        assert item["registered_native_writer_roles"]==0
        assert len(item["required_writer_roles"])==roles
        assert item["native_fs1_inception_bound"] is False
        assert item["native_fs3_report_bound"] is False
        assert item["financial_account_inception_accepted"] is False
        assert item["operator_activation_accepted"] is False
        assert item["paper_order_authorized"] is False
    assert v["accounts"]==original
    assert v["accounts"]["QUALITY_DIPS"]["account_id"]!=v["accounts"]["HYPERLIQUID"]["account_id"]
    assert v["accounts"]["QUALITY_DIPS"]["epoch"]!=v["accounts"]["HYPERLIQUID"]["epoch"]


def test_pure_audit_is_repeatable_and_does_not_mutate_native_input(grounded):
    proposal,roots,policy,v=grounded
    snapshot=copy.deepcopy((proposal,roots,policy))
    for _ in range(3):
        assert audit.evaluate(
            proposal=proposal,roots=roots,
            personal_policy=policy,observed_at=OBSERVED)==v
    assert (proposal,roots,policy)==snapshot
    assert audit.inspect(observed_at=OBSERVED)==v


@pytest.mark.parametrize("path,value",[
    ("selected_native_revision",14),
    ("selected_native_head","0"*64),
    ("selected_r16_artifact_digest","f"*64),
    ("financial_paper_start_authorized",True),
    ("actual_financial_writer_roles_enrolled",12),
    ("native_financial_inceptions_published",2),
    ("accepted_financial_operating_gates",9),
    ("provider_requests",1),
    ("live_trading_authorized",True),
])
def test_wrong_r16_source_or_financial_promotion_refused(grounded,path,value):
    proposal,roots,policy,_=grounded
    changed=copy.deepcopy(proposal)
    changed[path]=value
    with pytest.raises((ValueError,TypeError,KeyError)):
        audit.evaluate(proposal=changed,roots=roots,personal_policy=policy,
                       observed_at=OBSERVED)


@pytest.mark.parametrize("lane,field,value",[
    ("QUALITY_DIPS","opening_cash","10000"),
    ("HYPERLIQUID","opening_cash","2000"),
    ("QUALITY_DIPS","fees_bps","0"),
    ("QUALITY_DIPS","slippage_bps","0"),
    ("HYPERLIQUID","currency","USD"),
    ("QUALITY_DIPS","currency","USDC"),
    ("QUALITY_DIPS","initial_net_r","5"),
    ("HYPERLIQUID","initial_net_r","5"),
    ("QUALITY_DIPS","timezone","UTC"),
    ("HYPERLIQUID","timezone","America/Chicago"),
    ("QUALITY_DIPS","opened_at",OBSERVED+1000),
    ("HYPERLIQUID","opened_at",OBSERVED+1000),
])
def test_wrong_cash_fees_initial_pnl_currency_or_calendar_refused(grounded,lane,field,value):
    proposal,roots,policy,_=grounded
    p=copy.deepcopy(proposal)
    p["accounts"][lane]["provisional_r16_parameters"][field]=value
    with pytest.raises((ValueError,TypeError,KeyError)):
        audit.evaluate(proposal=p,roots=roots,personal_policy=policy,observed_at=OBSERVED)


@pytest.mark.parametrize("lane,where,field,value",[
    ("QUALITY_DIPS","provisional_r16_enrollment_unaccepted","writers",{"source":{"pid":123}}),
    ("HYPERLIQUID","provisional_r16_enrollment_unaccepted","acceptance_id","FAKE"),
    ("QUALITY_DIPS","provisional_r16_report_scope_unaccepted","timezone","UTC"),
    ("HYPERLIQUID","provisional_r16_enrollment_unaccepted","account_id","FOREIGN"),
])
def test_foreign_writer_account_or_report_scope_refused(grounded,lane,where,field,value):
    proposal,roots,policy,_=grounded
    p=copy.deepcopy(proposal)
    p["accounts"][lane][where][field]=value
    with pytest.raises((ValueError,TypeError,KeyError)):
        audit.evaluate(proposal=p,roots=roots,personal_policy=policy,observed_at=OBSERVED)


@pytest.mark.parametrize("field,value",[
    ("all_twelve_distinct_and_empty",False),
    ("native_root_ids_verified",11),
    ("existing_empty_root_namespaces",11),
    ("financial_inception_verified",True),
    ("writer_ownership_verified",True),
    ("paper_start_authorized",True),
])
def test_original_native_account_root_claims_never_promote_a_financial_cut(grounded,field,value):
    proposal,roots,policy,_=grounded
    r=copy.deepcopy(roots)
    r[field]=value
    with pytest.raises((ValueError,TypeError,KeyError)):
        audit.evaluate(proposal=proposal,roots=r,personal_policy=policy,
                       observed_at=OBSERVED)


def test_native_root_alias_and_process_scope_cannot_be_rewritten(grounded):
    proposal,roots,policy,_=grounded
    r=copy.deepcopy(roots)
    r["lanes"]["HYPERLIQUID"]["roots"]["source"]["native_id"]=r[
        "lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"][:]
    with pytest.raises(ValueError):
        audit.evaluate(proposal=proposal,roots=r,personal_policy=policy,
                       observed_at=OBSERVED)


@pytest.mark.parametrize("lane,change",[
    ("QUALITY_DIPS","opening_balance"),
    ("HYPERLIQUID","max_open_positions"),
    ("HYPERLIQUID","universe"),
    ("QUALITY_DIPS","fee_bps_per_side"),
    ("QUALITY_DIPS","slippage_bps_per_side"),
])
def test_changed_original_operator_financial_policy_refused(grounded,lane,change):
    proposal,roots,policy,_=grounded
    p=copy.deepcopy(policy)
    field=p["accounts"][lane][change]
    p["accounts"][lane][change] = (
        ["BTC"] if type(field) is list else "99999")
    with pytest.raises((ValueError,TypeError,KeyError)):
        audit.evaluate(proposal=proposal,roots=roots,personal_policy=p,
                       observed_at=OBSERVED)


@pytest.mark.parametrize("bad",[None,False,True,0,-5,"2026-11-11",OBSERVED//2])
def test_non_integral_or_stale_reporting_observation_is_refused(grounded,bad):
    proposal,roots,policy,_=grounded
    with pytest.raises((ValueError,TypeError,KeyError)):
        audit.evaluate(proposal=proposal,roots=roots,personal_policy=policy,
                       observed_at=bad)


def test_new_utc_report_midnight_exact_boundary_is_not_a_false_day_period(grounded):
    proposal,roots,policy,_=grounded
    exactly_midnight=int(datetime(2026,11,12,0,tzinfo=UTC).timestamp())
    with pytest.raises(ValueError,match="No report period after authenticated inception"):
        audit.evaluate(proposal=proposal,roots=roots,personal_policy=policy,
                       observed_at=exactly_midnight)
    # A full minute into the next UTC day is a valid INCOMPLETE report for
    # both accounts, not a published account or completed financial day.
    one_minute_later=exactly_midnight+60
    result=audit.evaluate(proposal=proposal,roots=roots,personal_policy=policy,
                          observed_at=one_minute_later)
    assert result["accounts"]["HYPERLIQUID"]["observed_reporting_day"]=="2026-11-12"
    assert result["accounts"]["QUALITY_DIPS"]["observed_reporting_day"]=="2026-11-11"
    assert all(x["fs3_unpublished_report_status"]=="INCOMPLETE"
               for x in result["accounts"].values())


def test_existing_personal_paper_policy_file_sha_and_no_network_requirement(grounded):
    import hashlib
    assert audit.POLICY_PATH.is_file()
    assert hashlib.sha256(audit.POLICY_PATH.read_bytes()).hexdigest()==audit.POLICY_SHA256
    assert audit.inspect(observed_at=OBSERVED)["paper_start_authorized"] is False
