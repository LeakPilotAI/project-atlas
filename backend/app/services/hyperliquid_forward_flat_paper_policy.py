"""Forward-only local Hyperliquid PAPER alternative: flat BEFORE every funding hour.

This is a PROPOSED policy with no original financial issuer integration.
A verified original Stop/flatten owner must enforce a zero-position ledger
before every UTC hour. If that proof is missing, this policy never assumes
zero funding or a successful close. It never authorizes orders, simulated
account inception, data rights, existing original oracle-rule bypass, or live
trading. Fee/slippage examples are conservative unverified simulation costs.
"""
from __future__ import annotations

from decimal import Decimal

SCHEMA = "ATLAS_HL_FORWARD_FLAT_PRE_FUNDING_PAPER_PROPOSAL_V1"
HOUR = 3600
GUARD_BEFORE_FUNDING_SECONDS = 300
GUARD_AFTER_FUNDING_SECONDS = 30
MAX_SIMULATED_HOLD_SECONDS = 1200
MAX_NTP_UNCERTAINTY_MS = 1000
SYMBOLS = frozenset(("BTC", "ETH", "SOL"))
# The real maker/taker schedule is NOT authenticated by this module. For
# proposed synthetic accounting only, each side reserves larger charges.
ASSUMED_TAKER_FEE_BPS_EACH_SIDE = "10"
ASSUMED_SLIPPAGE_BPS_EACH_SIDE = "5"


def _second(value):
    if type(value) is not int or value < 1_600_000_000:
        raise ValueError("HL_FLAT_ONLY_BOUNDED_UTC_SECONDS_REQUIRED")
    return value


def _uncertainty(value):
    if type(value) is not int or not 0 <= value <= MAX_NTP_UNCERTAINTY_MS:
        raise ValueError("HL_FLAT_ONLY_INDEPENDENT_CLOCK_BOUND_REQUIRED")
    # The planning clock is an INTEGER UTC second. Reserve both its missing
    # fractional second and the independent NTP uncertainty. This is a
    # proposal only, never a financial timing/flatness authority.
    return 1 + (value + 999) // 1000


def next_funding_hour(now_utc_seconds):
    now = _second(now_utc_seconds)
    return ((now // HOUR) + 1) * HOUR


def plan_new_entry(
    *, now_utc_seconds, uncertainty_ms, symbol, intended_hold_seconds,
    native_unverified_positions, native_unresolved_close,
):
    """Propose only; no native clock, ledger, issuer, fill or financial grant."""
    now = _second(now_utc_seconds)
    slack = _uncertainty(uncertainty_ms)
    if (type(symbol) is not str or symbol not in SYMBOLS
            or type(intended_hold_seconds) is not int
            or not 1 <= intended_hold_seconds <= MAX_SIMULATED_HOLD_SECONDS
            or type(native_unverified_positions) is not int
            or not 0 <= native_unverified_positions <= 3
            or type(native_unresolved_close) is not bool):
        raise ValueError("HL_FLAT_ONLY_STRICT_PROPOSAL_INPUT_REQUIRED")
    current_hour = (now // HOUR) * HOUR
    next_hour = current_hour + HOUR
    hard_deadline = next_hour - GUARD_BEFORE_FUNDING_SECONDS
    # A floor-second sample and measured peer uncertainty may straddle the
    # UTC hour; don't open until well inside the *current* funded period.
    after_boundary = now - slack >= current_hour + GUARD_AFTER_FUNDING_SECONDS
    # Always reserve the entire bounded maximum hold for a newly opened
    # position. A caller may request a one-second hold, but the exchange
    # simulator cannot guarantee an immediate fill or a successful exit.
    # No new entry may start in the last 25 minutes of a funding hour.
    expiry_ok = now + slack + MAX_SIMULATED_HOLD_SECONDS < hard_deadline
    no_uncertain_ledger = (
        native_unverified_positions == 0 and not native_unresolved_close
    )
    eligible_window = after_boundary and expiry_ok and no_uncertain_ledger
    if not no_uncertain_ledger:
        reason = "FLATTEN_OR_RECONCILE_UNVERIFIED_NATIVE_POSITION"
    elif not after_boundary:
        reason = "HOURLY_FUNDING_START_GUARD"
    elif not expiry_ok:
        reason = "HOURLY_FUNDING_FLAT_DEADLINE_GUARD"
    else:
        reason = "CANDIDATE_WINDOW_ONLY_AWAIT_NATIVE_FINANCIAL_AUTHORITY"
    return {
        "schema": SCHEMA,
        "symbol": symbol,
        "next_funding_at_utc": next_hour,
        "mandatory_flat_by_utc": hard_deadline,
        "guard_before_funding_seconds": GUARD_BEFORE_FUNDING_SECONDS,
        "guard_after_funding_seconds": GUARD_AFTER_FUNDING_SECONDS,
        "latest_proposed_close_at_utc": now + intended_hold_seconds,
        "entry_window_structurally_eligible": eligible_window,
        "result": reason,
        "native_ledger_proof_verified": False,
        "assumed_funding_cost_zero": False,
        "original_historical_oracle_evidence_accepted": False,
        "actual_fee_schedule_verified": False,
        "real_provider_data_rights_accepted": False,
        "simulated_paper_financial_order_authorized": False,
        "live_money_order_authorized": False,
    }


def audit_closed_interval(*, opened_at_utc, closed_at_utc, uncertainty_ms):
    """Reject crossing a funding hour; never infer an externally settled close.

    A closed interval is only a proposed bookkeeping claim. A financial owner
    MUST authenticate durable native fill/flat ACKs independently.
    """
    opened = _second(opened_at_utc)
    slack = _uncertainty(uncertainty_ms)
    if (type(closed_at_utc) is not int
            or closed_at_utc < opened
            or closed_at_utc > opened + MAX_SIMULATED_HOLD_SECONDS):
        raise ValueError("HL_FLAT_ONLY_CLOSE_INTERVAL_REQUIRED")
    next_hour = next_funding_hour(opened)
    flat_deadline = next_hour - GUARD_BEFORE_FUNDING_SECONDS
    safe_window = (
        opened - slack >= (opened // HOUR) * HOUR
        + GUARD_AFTER_FUNDING_SECONDS
        and opened + slack + MAX_SIMULATED_HOLD_SECONDS < flat_deadline
        and closed_at_utc + slack < flat_deadline
    )
    if not safe_window:
        raise ValueError("HL_FLAT_ONLY_ORIGINAL_SETTLEMENT_PROOF_STILL_REQUIRED")
    return {
        "schema": SCHEMA,
        "status": "CLOSED_INTERVAL_OUTSIDE_HOURLY_FUNDING_PROPOSED_ONLY",
        "opened_at_utc": opened,
        "closed_at_utc": closed_at_utc,
        "next_funding_at_utc": next_hour,
        "original_native_fill_and_flat_ack_verified": False,
        "provider_settlement_oracle_verified": False,
        "financial_funding_accrual_waived": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def require_conservative_original_paper_preflight(
        *, manifest, verified_native_cut, issued_utc_sample):
    """Admission-only PAPER fee/funding check on the actual financial cut.

    The caller must have independently verified the original native writer
    and sample with its own Windows/NTP owner. This pure checker grants no
    source rights and cannot substitute for a simulated account or Stop.
    """
    from app.services.paper_financial_replay import body, number, strict
    from app.services.paper_perp_transition import (
        require_operational_fee_policy, validate_manifest,
    )

    if (type(manifest) is not dict
            or manifest.get("schema") != "PAPER_EPOCH_PERP_OPERATIONAL_V1"
            or type(verified_native_cut) is not dict
            or verified_native_cut.get("manifest") != manifest
            or type(issued_utc_sample) is not dict
            or issued_utc_sample.get("schema") != "QD_AUTO_NATIVE_CLOCK_V4"
            or type(issued_utc_sample.get("utc")) is not int
            or type(issued_utc_sample.get("uncertainty_ms")) is not int):
        raise ValueError("HL_FLAT_PILOT_ORIGINAL_NATIVE_MANIFEST_AND_CLOCK_REQUIRED")
    manifest = strict(body(manifest))
    validate_manifest(manifest)
    require_operational_fee_policy(manifest)
    p = manifest["perp_policy"]
    # These are deliberately more expensive than the published undiscounted
    # base and are declared LOCAL SIMULATION assumptions, not wallet rates.
    if (number(p["taker_bps"]) < Decimal(ASSUMED_TAKER_FEE_BPS_EACH_SIDE)
            or number(p["slippage_bps"]) < Decimal(ASSUMED_SLIPPAGE_BPS_EACH_SIDE)
            or number(p["max_notional"]) > Decimal("100")
            or p["symbols"] != ["BTC", "ETH", "SOL"]
            or type(verified_native_cut.get("state")) is not dict
            or type(verified_native_cut["state"].get("positions")) is not dict):
        raise ValueError("HL_FLAT_PILOT_CONSERVATIVE_NATIVE_POLICY_REQUIRED")
    positions = verified_native_cut["state"]["positions"]
    if any(type(row) is not dict or number(row["remaining"]) > 0
           for row in positions.values()):
        raise ValueError("HL_FLAT_PILOT_PRIOR_NATIVE_POSITION_RECONCILIATION_REQUIRED")
    sample = issued_utc_sample
    candidate = plan_new_entry(
        now_utc_seconds=sample["utc"],
        uncertainty_ms=sample["uncertainty_ms"],
        symbol="BTC", intended_hold_seconds=MAX_SIMULATED_HOLD_SECONDS,
        native_unverified_positions=0, native_unresolved_close=False,
    )
    if candidate["entry_window_structurally_eligible"] is not True:
        raise ValueError("HL_FLAT_PILOT_PRE_FUNDING_START_WINDOW_REFUSED")
    return {
        "schema": "ATLAS_HL_CONSERVATIVE_ORIGINAL_PRESTART_V1",
        "status": "NATIVE_POLICY_AND_HOURLY_TIME_WINDOW_ONLY",
        "utc_sample": sample["utc"],
        "next_utc_hour": candidate["next_funding_at_utc"],
        "mandatory_flat_by_utc": candidate["mandatory_flat_by_utc"],
        "native_no_open_positions_observed": True,
        "paper_cost_model": {
            "taker_fee_bps_per_side": p["taker_bps"],
            "slippage_bps_per_side": p["slippage_bps"],
            "fee_schedule_id": p["fee_schedule_id"],
        },
        "actual_wallet_fee_tier_verified": False,
        "historical_settlement_oracle_verified": False,
        "independent_source_rights_accepted": False,
        "financial_paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def conservative_round_trip_cost_usdc(notional_usdc):
    """Non-authoritative illustrative fees; never provider/account claims."""
    if type(notional_usdc) is not str or len(notional_usdc) > 35:
        raise ValueError("HL_FLAT_ONLY_FIXED_NOTIONAL_STRING_REQUIRED")
    try:
        amount = Decimal(notional_usdc)
    except (ArithmeticError, ValueError) as exc:
        raise ValueError("HL_FLAT_ONLY_FIXED_NOTIONAL_REFUSED") from exc
    if not amount.is_finite() or not Decimal(0) < amount <= Decimal(100):
        raise ValueError("HL_FLAT_ONLY_PAPER_MAX_NOTIONAL_EXCEEDED")
    each_side = (
        Decimal(ASSUMED_TAKER_FEE_BPS_EACH_SIDE)
        + Decimal(ASSUMED_SLIPPAGE_BPS_EACH_SIDE)
    )
    return {
        "schema": SCHEMA,
        "hypothetical_notional_usdc": str(amount),
        "assumed_fee_bps_per_side": ASSUMED_TAKER_FEE_BPS_EACH_SIDE,
        "assumed_slippage_bps_per_side": ASSUMED_SLIPPAGE_BPS_EACH_SIDE,
        "conservative_round_trip_cost_usdc": str(amount * each_side * 2
                                                / Decimal(10000)),
        "observed_actual_user_fee_verified": False,
        "original_historical_settlement_verified": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }
