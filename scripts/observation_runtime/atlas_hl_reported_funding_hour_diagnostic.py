"""Strict NONFINANCIAL explanation of reported Hyperliquid funding-hour labels.

A past-dated HlPerp nextFundingTime can be consistent with the running
hour's boundary. This does NOT assert exchange semantics or change the
immutable original selected R24 forecast acceptance / settlement oracle.

Never derive an executable next-funding time or a financial funding rate.
No market requests, credentials, account, publisher, wallet, or order calls.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

HOUR_MS = 3_600_000
MIN_UNIX_MS = 1_700_000_000_000
ALLOWED_COINS = frozenset(("BTC", "ETH", "SOL"))
OBSERVATION_ONLY = "REPORTED_RUNNING_HOUR_START_PATTERN_NONFINANCIAL_ONLY"


def classify_reported_hl_hour_label(
    *, coin, reported_next_funding_time_ms, observed_utc_ms,
    funding_interval_hours, funding_rate,
):
    """Classify a received raw field, not a settlement time.

    Raises on invalid schema, future/previous-hour timestamps, fabricated
    time, or nonhourly intervals. Reports ONLY an observed pattern, never
    a future timestamp. Immutable native financial issuer remains a refusal.
    """
    if type(coin) is not str or coin not in ALLOWED_COINS:
        raise ValueError("HL_REPORTED_HOUR_SYMBOL_REFUSED")
    if (type(reported_next_funding_time_ms) is not int
            or type(observed_utc_ms) is not int
            or observed_utc_ms < MIN_UNIX_MS
            or type(funding_interval_hours) is not int
            or funding_interval_hours != 1):
        raise ValueError("HL_REPORTED_HOUR_SCHEMA_REFUSED")
    if type(funding_rate) is not str:
        raise ValueError("HL_REPORTED_HOUR_RATE_REFUSED")
    try:
        rate = Decimal(funding_rate)
    except InvalidOperation:
        raise ValueError("HL_REPORTED_HOUR_RATE_REFUSED") from None
    if not rate.is_finite() or abs(rate) > Decimal("0.04"):
        raise ValueError("HL_REPORTED_HOUR_RATE_REFUSED")
    expected_running_hour = (observed_utc_ms // HOUR_MS) * HOUR_MS
    if (reported_next_funding_time_ms != expected_running_hour
            or not 0 <= observed_utc_ms - reported_next_funding_time_ms < HOUR_MS):
        raise ValueError("HL_REPORTED_HOUR_NOT_CURRENT_HOUR_PATTERN")
    return {
        "schema": "ATLAS_HL_REPORTED_RUNNING_HOUR_NONFINANCIAL_V1",
        "status": OBSERVATION_ONLY,
        "coin": coin,
        "received_field_name": "HlPerp.nextFundingTime",
        "received_raw_time_ms": reported_next_funding_time_ms,
        "observation_utc_ms": observed_utc_ms,
        "field_lag_ms": observed_utc_ms - reported_next_funding_time_ms,
        "received_funding_interval_hours": funding_interval_hours,
        "provider_rate_preserved_as_nonfinancial_string": str(rate),
        "declares_provider_semantics_authoritative": False,
        "relabels_field_as_verified_next_settlement": False,
        "inferred_future_next_funding_ms": None,
        "historical_settlement_oracle_verified": False,
        "financial_position_flat_verified": False,
        "actual_account_fee_tier_verified": False,
        "financial_source_rights_accepted": False,
        "paper_start_authorized": False,
        "live_money_authorized": False,
    }
