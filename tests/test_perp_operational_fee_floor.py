"""No unverified low-fee assumptions in an operational Hyperliquid PAPER epoch.

Pure admission + disposable transition; no provider, wallet or real financial trade.
Existing disposable fixture economics deliberately remain unchanged.
"""
import copy
from decimal import Decimal

import pytest

from app.services.paper_financial_replay import apply_event, initial_state, validate_manifest
from app.services.paper_perp_transition import (
    require_operational_fee_policy,
    validate_manifest as validate_perp_manifest,
)
from test_perp_financial_v2 import manifest as fixture_manifest

BASE_MAKER_BPS="1.5"
BASE_TAKER_BPS="4.5"
BASE_FEE_ID="HYPERLIQUID_PUBLIC_VALIDATOR_PERP_BASE_UNDISCOUNTED_REVIEW_ONLY_V1"


def operational():
    m=copy.deepcopy(fixture_manifest())
    m.update(schema="PAPER_EPOCH_PERP_OPERATIONAL_V1",
             release="a"*64,provenance="ACCEPTED_PERP_PAPER_PARAMETERS_V1")
    m["perp_policy"].update(
        maker_bps=BASE_MAKER_BPS,taker_bps=BASE_TAKER_BPS,
        fee_schedule_id=BASE_FEE_ID)
    return m


def test_base_tier_operational_manifest_can_be_validated_but_is_not_a_grant():
    m=operational()
    assert validate_manifest(m) is None
    assert validate_perp_manifest(m) is None
    assert require_operational_fee_policy(m) is None
    assert m["strategy"]=="HYPERLIQUID_PAPER" and m["currency"]=="USDC"
    assert m["perp_policy"]["symbols"]==["BTC","ETH","SOL"]
    # Validation only checks declared policy, not authenticated public rights.
    assert m["perp_policy"]["fee_schedule_id"]==BASE_FEE_ID


@pytest.mark.parametrize("maker,taker,fee_id",[
    ("1","2","PENDING_E1_VERIFIED_FEE_SCHEDULE"),
    ("1","4.5",BASE_FEE_ID),
    ("1.49","4.5",BASE_FEE_ID),
    ("1.5","4.49",BASE_FEE_ID),
    ("1.5","0",BASE_FEE_ID),
    ("0","4.5",BASE_FEE_ID),
    ("1.5","4.5","PENDING_E1_VERIFIED_FEE_SCHEDULE"),
    ("1.5","4.5","PENDING_FAKE_ACCOUNT_TIER"),
])
def test_operational_missing_or_discounted_without_tier_proof_refuses(
    maker,taker,fee_id,
):
    m=operational()
    m["perp_policy"].update(
        maker_bps=maker,taker_bps=taker,fee_schedule_id=fee_id)
    from test_perp_financial_v2 import entry
    before=copy.deepcopy(m)
    state=initial_state(m)
    original_state=copy.deepcopy(state)
    # Retained historical drafts stay parsable, but applying any simulated
    # financial effect with their placeholder fees refuses before mutation.
    validate_manifest(m)
    with pytest.raises(ValueError,match="fee schedule"):
        apply_event(m,state,entry())
    assert m==before and state==original_state


@pytest.mark.parametrize("maker,taker",[
    ("1.5","4.5"),("2.0","5.0"),("10","20"),
])
def test_higher_explicit_assumptions_are_not_silently_reduced(maker,taker):
    m=operational()
    m["perp_policy"]["maker_bps"]=maker
    m["perp_policy"]["taker_bps"]=taker
    validate_manifest(m)
    require_operational_fee_policy(m)
    assert (m["perp_policy"]["maker_bps"],m["perp_policy"]["taker_bps"])==(maker,taker)


def test_fixture_v2_legacy_ledger_rates_not_rewritten():
    old=fixture_manifest()
    before=copy.deepcopy(old)
    validate_manifest(old)
    assert old==before
    assert old["perp_policy"]["maker_bps"]=="1"
    assert old["perp_policy"]["taker_bps"]=="2"
    assert old["schema"]=="PAPER_EPOCH_PERP_FIXTURE_V2"


def test_initial_legacy_draft_still_refused_as_operational_without_fake_upgrade():
    m=fixture_manifest()
    m.update(schema="PAPER_EPOCH_PERP_OPERATIONAL_V1",
             release="a"*64,provenance="ACCEPTED_PERP_PAPER_PARAMETERS_V1")
    validate_manifest(m)
    with pytest.raises(ValueError,match="fee schedule"):
        require_operational_fee_policy(m)


def test_accepted_model_fee_changes_simulated_entry_cash_without_live_order():
    from test_perp_financial_v2 import entry
    m=operational()
    original=initial_state(m)
    cmd=entry()
    cmd["evidence"]["fee_schedule_id"]=BASE_FEE_ID
    new, receipt=apply_event(m,original,cmd)
    assert Decimal(new["cash"])==Decimal("999.9675")
    assert Decimal(new["fees"])==Decimal("0.0225")
    assert Decimal(new["slippage"])==Decimal("0.01")
    assert receipt["production_authorized"] is False
    assert receipt["startup_authorized"] is False
    assert Decimal(original["cash"])==1000


def test_fee_notional_arithmetic_exposes_real_cost_gap_without_any_order():
    usd_notional=Decimal("100")
    legacy=usd_notional*Decimal("2")*Decimal("2")/Decimal("10000")
    conservative=usd_notional*Decimal("2")*Decimal(BASE_TAKER_BPS)/Decimal("10000")
    assert legacy==Decimal("0.04")
    assert conservative==Decimal("0.09")
    assert conservative-legacy==Decimal("0.05")


def test_operational_base_fee_partial_funding_exit_cash_path_matches_native_fixture():
    from test_perp_financial_v2 import (
        entry, exit_command, funding,
    )
    m=operational()
    state=initial_state(m)

    class Memory:
        manifest=m

        def snapshot(self):
            return state

    memory=Memory()
    cmd=entry()
    cmd["evidence"]["fee_schedule_id"]=BASE_FEE_ID
    state,_=apply_event(m,state,cmd)

    part=exit_command(memory,"0.2",3603,"partial","102")
    part["evidence"]["fee_schedule_id"]=BASE_FEE_ID
    state,_=apply_event(m,state,part)

    state,_=apply_event(m,state,funding(memory))

    final=exit_command(memory,"0.3",7202,"final","104")
    final["evidence"]["fee_schedule_id"]=BASE_FEE_ID
    state,_=apply_event(m,state,final)

    assert Decimal(state["cash"])==Decimal("1001.50396")
    assert Decimal(state["reserved_margin"])==Decimal("0")
    assert Decimal(state["funding"])==Decimal("-0.03")
    assert state["valuation_state"] in ("CURRENT_SYNTHETIC_MARK", "UNAVAILABLE")
