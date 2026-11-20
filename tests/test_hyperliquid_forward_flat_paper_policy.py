"""Proposed intrahour PAPER-only funding avoidance, never a grant or fill."""
from datetime import UTC, datetime

import pytest
from app.services import hyperliquid_forward_flat_paper_policy as flat

BASE = int(datetime(2026, 11, 13, 15, 0, tzinfo=UTC).timestamp())


def plan(minutes, *, hold=1200, uncertainty=139, positions=0,
         unresolved=False, symbol="BTC"):
    return flat.plan_new_entry(
        now_utc_seconds=BASE + minutes * 60,
        uncertainty_ms=uncertainty,
        symbol=symbol,
        intended_hold_seconds=hold,
        native_unverified_positions=positions,
        native_unresolved_close=unresolved,
    )


def test_original_market_session_entry_window_is_only_proposal():
    r = plan(31, symbol="ETH")
    assert r["entry_window_structurally_eligible"] is True
    assert r["next_funding_at_utc"] == BASE + 3600
    assert r["mandatory_flat_by_utc"] == BASE + 3300
    assert r["latest_proposed_close_at_utc"] == BASE + 31 * 60 + 1200
    assert r["result"] == "CANDIDATE_WINDOW_ONLY_AWAIT_NATIVE_FINANCIAL_AUTHORITY"
    assert all(r[key] is False for key in (
        "simulated_paper_financial_order_authorized",
        "live_money_order_authorized", "native_ledger_proof_verified",
        "original_historical_oracle_evidence_accepted",
        "actual_fee_schedule_verified", "assumed_funding_cost_zero",
    ))


@pytest.mark.parametrize("minute,holding,eligible", (
    (0, 30, False), (1, 1200, True), (34, 1200, True),
    (35, 1200, False), (54, 1, False), (55, 1, False),
    (59, 1, False),
))
def test_only_the_proven_intrahour_window_can_be_proposed(
    minute, holding, eligible,
):
    assert plan(minute, hold=holding)["entry_window_structurally_eligible"] is eligible


@pytest.mark.parametrize("positions,unresolved", (
    (1, False), (3, False), (0, True), (1, True),
))
def test_unresolved_native_positions_forbid_all_new_entries(
    positions, unresolved,
):
    r = plan(15, positions=positions, unresolved=unresolved)
    assert r["entry_window_structurally_eligible"] is False
    assert r["result"] == "FLATTEN_OR_RECONCILE_UNVERIFIED_NATIVE_POSITION"


@pytest.mark.parametrize("clock", (0, 139, 1000))
def test_clock_uncertainty_is_reserved_at_boundaries(clock):
    hour_start = BASE + 3600
    assert flat.next_funding_hour(hour_start) == BASE + 7200
    assert plan(0, uncertainty=clock)["entry_window_structurally_eligible"] is False
    assert plan(1, uncertainty=clock)["entry_window_structurally_eligible"] is True


@pytest.mark.parametrize("args", (
    {"now_utc_seconds": "fake"},
    {"uncertainty_ms": True},
    {"uncertainty_ms": -1},
    {"uncertainty_ms": 1001},
    {"symbol": "FAKE"},
    {"symbol": True},
    {"intended_hold_seconds": True},
    {"intended_hold_seconds": 0},
    {"intended_hold_seconds": 1201},
    {"native_unverified_positions": -1},
    {"native_unverified_positions": True},
    {"native_unverified_positions": 4},
    {"native_unresolved_close": 0},
))
def test_invalid_clock_account_or_proposal_input_never_allows_entry(args):
    original = {
        "now_utc_seconds": BASE + 60 * 10,
        "uncertainty_ms": 139, "symbol": "BTC",
        "intended_hold_seconds": 1200,
        "native_unverified_positions": 0,
        "native_unresolved_close": False,
    }
    original.update(args)
    with pytest.raises(ValueError):
        flat.plan_new_entry(**original)


@pytest.mark.parametrize("opened,closed,accepted", (
    (1, 5, True),
    (30, 45, True),
    (34, 54, True),
    (34, 55, False),
    (35, 55, False),
    (55, 59, False),
    (59, 61, False),
    (0, 2, False),
    (30, 50, True),
))
def test_only_completed_safe_intrahour_intervals_are_structurally_valid(
    opened, closed, accepted,
):
    kwargs = {
        "opened_at_utc": BASE + opened * 60,
        "closed_at_utc": BASE + closed * 60,
        "uncertainty_ms": 139,
    }
    if not accepted:
        with pytest.raises(ValueError):
            flat.audit_closed_interval(**kwargs)
    else:
        r = flat.audit_closed_interval(**kwargs)
        assert r["status"] == "CLOSED_INTERVAL_OUTSIDE_HOURLY_FUNDING_PROPOSED_ONLY"
        assert r["original_native_fill_and_flat_ack_verified"] is False
        assert r["provider_settlement_oracle_verified"] is False
        assert r["financial_funding_accrual_waived"] is False
        assert r["paper_start_authorized"] is False


@pytest.mark.parametrize("bad", (
    "-1", "0", "101", "1e100", "NaN", "Infinity", "abc", "",
    100, None, True,
))
def test_cost_assumptions_refuse_unbounded_and_non_decimal_notional(bad):
    with pytest.raises(ValueError):
        flat.conservative_round_trip_cost_usdc(bad)


def _operational_pilot():
    from copy import deepcopy
    from test_perp_financial_v2 import manifest as perp_manifest
    m = deepcopy(perp_manifest())
    m.update(
        schema="PAPER_EPOCH_PERP_OPERATIONAL_V1",
        release="a" * 64,
        provenance="ACCEPTED_PERP_PAPER_PARAMETERS_V1",
        opening_cash="1000",
    )
    m["perp_policy"].update(
        symbols=["BTC", "ETH", "SOL"], max_notional="100",
        maker_bps="1.5", taker_bps="10", slippage_bps="5",
        fee_schedule_id="ATLAS_CONSERVATIVE_SIMULATED_NO_WALLET_FEE_V1",
    )
    cut = {"manifest": deepcopy(m), "state": {"positions": {}}}
    sample = {"schema": "QD_AUTO_NATIVE_CLOCK_V4",
              "utc": BASE + 10 * 60, "uncertainty_ms": 139}
    return m, cut, sample


def _historical_unapproved_hl():
    m, _, _ = _operational_pilot()
    m["perp_policy"].update(
        taker_bps="4.5", slippage_bps="2",
        fee_schedule_id="PENDING_E1_VERIFIED_FEE_SCHEDULE",
    )
    return m


def test_reviewed_historical_original_fee_amendment_is_copy_only_not_permission():
    from copy import deepcopy
    old = _historical_unapproved_hl()
    unchanged = deepcopy(old)
    amended = flat.derive_reviewable_conservative_hl_manifest(old)
    assert old == unchanged
    assert amended["perp_policy"]["taker_bps"] == "10"
    assert amended["perp_policy"]["slippage_bps"] == "5"
    assert amended["perp_policy"]["maker_bps"] == "1.5"
    assert (amended["perp_policy"]["fee_schedule_id"]
            == flat.CONSERVATIVE_LOCAL_FEE_POLICY_ID)
    for unchanged_key in (
        "instrument_cut", "market_source", "funding_source",
        "risk_limit", "maintenance_rate", "symbols",
        "max_notional", "max_positions", "max_leverage",
    ):
        assert (amended["perp_policy"][unchanged_key]
                == old["perp_policy"][unchanged_key])
    for unchanged_key in (
        "epoch", "release", "opening_cash", "opened_at",
        "currency", "provenance", "timezone",
    ):
        assert amended[unchanged_key] == old[unchanged_key]


@pytest.mark.parametrize("damage", [
    "already_amended", "foreign_fee", "foreign_cost", "unknown_fee",
    "lower_notional", "wrong_symbols", "wrong_currency", "wrong_schema",
    "wrong_provenance",
])
def test_historical_fee_overlay_rejects_nonoriginal_or_changed_terms(damage):
    m = _historical_unapproved_hl()
    p = m["perp_policy"]
    if damage == "already_amended":
        p["taker_bps"] = "10"
    elif damage == "foreign_fee":
        p["taker_bps"] = "3"
    elif damage == "foreign_cost":
        p["slippage_bps"] = "4"
    elif damage == "unknown_fee":
        p["fee_schedule_id"] = "PROVIDER_TIER_NOT_VERIFIED"
    elif damage == "lower_notional":
        p["max_notional"] = "90"
    elif damage == "wrong_symbols":
        p["symbols"] = ["BTC"]
    elif damage == "wrong_currency":
        m["currency"] = "USD"
    elif damage == "wrong_schema":
        m["schema"] = "PAPER_EPOCH_PERP_FIXTURE_V2"
    else:
        m["provenance"] = "FOREIGN"
    with pytest.raises(ValueError):
        flat.derive_reviewable_conservative_hl_manifest(m)


def test_actual_operational_manifest_costs_and_funding_window_preflight_only():
    m, cut, clock = _operational_pilot()
    receipt = flat.require_conservative_original_paper_preflight(
        manifest=m, verified_native_cut=cut, issued_utc_sample=clock)
    assert receipt["status"] == "NATIVE_POLICY_AND_HOURLY_TIME_WINDOW_ONLY"
    assert receipt["next_utc_hour"] == BASE + 3600
    assert receipt["mandatory_flat_by_utc"] == BASE + 3300
    assert receipt["paper_cost_model"]["taker_fee_bps_per_side"] == "10"
    assert receipt["paper_cost_model"]["slippage_bps_per_side"] == "5"
    assert all(receipt[key] is False for key in (
        "actual_wallet_fee_tier_verified",
        "historical_settlement_oracle_verified",
        "independent_source_rights_accepted",
        "financial_paper_start_authorized",
        "live_trading_authorized",
    ))


@pytest.mark.parametrize("damage", [
    "cheap_fee", "cheap_slip", "pending_fee_id", "over_notional",
    "wrong_symbol", "prior_position", "changed_manifest", "late_start",
    "hour_edge", "uncertain_ntp", "not_operational", "foreign_clock",
])
def test_flat_pilot_refuses_cheaper_or_unsafe_native_finance_before_start(
        damage):
    m, cut, clock = _operational_pilot()
    if damage == "cheap_fee":
        m["perp_policy"]["taker_bps"] = "4.5"
    elif damage == "cheap_slip":
        m["perp_policy"]["slippage_bps"] = "4.999"
    elif damage == "pending_fee_id":
        m["perp_policy"]["fee_schedule_id"] = "PENDING_E1_FEE"
    elif damage == "over_notional":
        m["perp_policy"]["max_notional"] = "101"
    elif damage == "wrong_symbol":
        m["perp_policy"]["symbols"] = ["BTC", "ETH"]
    elif damage == "prior_position":
        cut["state"]["positions"]["synthetic"] = {"remaining": "0.1"}
    elif damage == "changed_manifest":
        cut["manifest"]["opening_cash"] = "999"
    elif damage == "late_start":
        clock["utc"] = BASE + 35 * 60
    elif damage == "hour_edge":
        clock["utc"] = BASE
    elif damage == "uncertain_ntp":
        clock["uncertainty_ms"] = 1001
    elif damage == "not_operational":
        m["schema"] = "PAPER_EPOCH_PERP_FIXTURE_V2"
    else:
        clock["schema"] = "FAKE_CLOCK"
    with pytest.raises(ValueError):
        flat.require_conservative_original_paper_preflight(
            manifest=m, verified_native_cut=cut, issued_utc_sample=clock)


def test_assumed_fee_and_slippage_are_labelled_not_real_entitlements():
    r = flat.conservative_round_trip_cost_usdc("100")
    assert r["conservative_round_trip_cost_usdc"] == "0.3"
    assert r["assumed_fee_bps_per_side"] == "10"
    assert r["assumed_slippage_bps_per_side"] == "5"
    assert r["observed_actual_user_fee_verified"] is False
    assert r["paper_start_authorized"] is False
    assert r["live_trading_authorized"] is False


def test_original_financial_oracle_gate_is_not_changed_by_new_proposal():
    from app.services.hyperliquid_consensus_settlement import (
        require_consensus_settlement_oracle,
    )

    with pytest.raises(ValueError, match="ORIGINAL_CONSENSUS_SETTLEMENT_ORACLE"):
        require_consensus_settlement_oracle(
            None, symbol="BTC", at=BASE + 3600,
            funding_record={"hourly_rate": "0.001"},
        )



def test_latest_possible_entry_reserves_whole_second_plus_ntp_uncertainty():
    kw = {
        "uncertainty_ms": 1000,
        "symbol": "SOL",
        "intended_hold_seconds": 1,
        "native_unverified_positions": 0,
        "native_unresolved_close": False,
    }
    safe = flat.plan_new_entry(
        now_utc_seconds=BASE + 34 * 60 + 57, **kw,
    )
    too_late = flat.plan_new_entry(
        now_utc_seconds=BASE + 34 * 60 + 58, **kw,
    )
    assert safe["entry_window_structurally_eligible"] is True
    assert too_late["entry_window_structurally_eligible"] is False
    assert too_late["result"] == "HOURLY_FUNDING_FLAT_DEADLINE_GUARD"
    assert too_late["simulated_paper_financial_order_authorized"] is False


def test_unverified_close_second_cannot_be_rounded_to_funding_safe():
    # At 15:54:59 the timestamp can actually be after 15:55:00 when
    # rounded or the NTP authority has a nonzero uncertainty.
    with pytest.raises(ValueError, match="SETTLEMENT_PROOF_STILL_REQUIRED"):
        flat.audit_closed_interval(
            opened_at_utc=BASE + 34 * 60 + 59,
            closed_at_utc=BASE + 54 * 60 + 59,
            uncertainty_ms=1000,
        )
