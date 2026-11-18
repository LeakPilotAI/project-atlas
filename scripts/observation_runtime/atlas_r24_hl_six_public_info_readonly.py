"""Strict original six Hyperliquid INFO POST evidence parser, data only.

Exactly 6 PUBLIC HTTPS POST /info observations: metaAndAssetCtxs, two
predictedFundings samples >=10 seconds apart, and BTC/ETH/SOL l2Book.
The original HL native book admission parser validates the three books.
Stale HlPerp nextFundingTime is a terminal refusal, NEVER inferred/corrected.
No credentials, accounts, financial sources, publisher, PAPER or live authority.
Network acquisition and original Windows operator consent are SEPARATE.
"""
from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation

from app.adapters.hyperliquid import _paper_execution_observation
from app.investment.free_research_transport import decode

SCHEMA = "ATLAS_R24_HL_ORIGINAL_SIX_PUBLIC_INFO_REVIEW_V1"
SOURCE = "https://api.hyperliquid.xyz/info"
HOUR_MS = 3_600_000
SYMBOLS = ("BTC", "ETH", "SOL")
KINDS = (
    ("metaAndAssetCtxs", None),
    ("predictedFundings", None),
    ("l2Book", "BTC"),
    ("l2Book", "ETH"),
    ("l2Book", "SOL"),
    ("predictedFundings", None),
)
MAX_BYTES = 524_288
MAX_WALL_MS = 75_000
MAX_UTC_UNCERTAINTY_MS = 1000
MIN_FORECAST_SPACING_MS = 10_000
MAX_REQUEST_MS = 5000
MAX_WEIGHT = 66  # 20 + 20 + (2*3) + 20, as official public INFO rate rules.
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _decode_frame(row, request, *, previous_observed_ms=None):
    if (type(row) is not dict
            or set(row) != {"type", "coin", "started_ms", "observed_ms",
                             "raw_json", "raw_sha256"}
            or (row["type"], row["coin"]) != request
            or type(row["started_ms"]) is not int
            or type(row["observed_ms"]) is not int
            or row["started_ms"] < 1_700_000_000_000
            or not 0 <= row["observed_ms"]-row["started_ms"] <= MAX_REQUEST_MS
            or (previous_observed_ms is not None
                and row["started_ms"] < previous_observed_ms)
            or type(row["raw_json"]) is not str
            or type(row["raw_sha256"]) is not str
            or _SHA.fullmatch(row["raw_sha256"]) is None):
        raise ValueError("HL_R24_ORIGINAL_SIX_FRAME_ENVELOPE_REFUSED")
    raw = row["raw_json"].encode("utf-8")
    if (not 0 < len(raw) <= MAX_BYTES
            or hashlib.sha256(raw).hexdigest() != row["raw_sha256"]):
        raise ValueError("HL_R24_ORIGINAL_SIX_FRAME_BYTES_REFUSED")
    return decode(raw)


def _forecast(body, *, observed_ms, uncertainty_ms):
    """Inspect ONLY the exact original HlPerp row for BTC/ETH/SOL."""
    if type(body) is not list or not 3 <= len(body) <= 1000:
        raise ValueError("HL_R24_ORIGINAL_PREDICTION_ENVELOPE_REFUSED")
    found = {}
    for row in body:
        if (type(row) is not list or len(row) != 2 or type(row[0]) is not str
                or type(row[1]) is not list):
            raise ValueError("HL_R24_ORIGINAL_PREDICTION_ROW_REFUSED")
        coin, venues = row
        if coin not in SYMBOLS:
            continue
        if coin in found or not 1 <= len(venues) <= 20:
            raise ValueError("HL_R24_ORIGINAL_PREDICTION_DUPLICATE_COIN")
        hits = [p[1] for p in venues if
                type(p) is list and len(p) == 2 and p[0] == "HlPerp"]
        if len(hits) != 1:
            raise ValueError("HL_R24_ORIGINAL_HLPERP_FORECAST_MISSING_OR_DUPLICATE")
        value = hits[0]
        if (type(value) is not dict or set(value) != {
                "fundingRate", "nextFundingTime"}
                or type(value["fundingRate"]) is not str
                or type(value["nextFundingTime"]) is not int):
            raise ValueError("HL_R24_ORIGINAL_HLPERP_FUNDING_SCHEMA_REFUSED")
        try:
            rate = Decimal(value["fundingRate"])
        except InvalidOperation:
            raise ValueError("HL_R24_ORIGINAL_HLPERP_RATE_REFUSED") from None
        if not rate.is_finite() or abs(rate) > Decimal("0.04"):
            raise ValueError("HL_R24_ORIGINAL_HLPERP_RATE_REFUSED")
        next_utc_hour = (observed_ms // HOUR_MS + 1) * HOUR_MS
        published = value["nextFundingTime"]
        if (published != next_utc_hour
                or published <= observed_ms + uncertainty_ms
                or published % HOUR_MS != 0):
            raise ValueError("HL_R24_ORIGINAL_HLPERP_NEXT_FUNDING_STALE_OR_INCONSISTENT")
        found[coin] = {"next_funding_ms":published,
                       "rate":str(rate)}
    if set(found) != set(SYMBOLS):
        raise ValueError("HL_R24_ORIGINAL_HLPERP_THREE_REQUIRED")
    return found


def inspect_exact_six(*, frames, ntp_uncertainty_ms):
    """Pure review of original raw data; financial authorization always FALSE."""
    if (type(frames) is not list or len(frames) != 6
            or type(ntp_uncertainty_ms) is not int
            or not 0 <= ntp_uncertainty_ms <= MAX_UTC_UNCERTAINTY_MS):
        raise ValueError("HL_R24_SIX_FRAMES_AND_TWO_PEER_UTC_REQUIRED")
    packets = []
    previous = None
    for row, req in zip(frames, KINDS, strict=True):
        packets.append(_decode_frame(
            row, req, previous_observed_ms=previous))
        previous = row["observed_ms"]
    if frames[-1]["observed_ms"]-frames[0]["started_ms"] > MAX_WALL_MS:
        raise ValueError("HL_R24_SIX_FRAME_GLOBAL_DEADLINE_REFUSED")
    if frames[5]["started_ms"] - frames[1]["observed_ms"] < MIN_FORECAST_SPACING_MS:
        raise ValueError("HL_R24_SECOND_PREDICTION_SAMPLE_TOO_SOON")
    first = _forecast(packets[1],
                      observed_ms=frames[1]["observed_ms"],
                      uncertainty_ms=ntp_uncertainty_ms)
    second = _forecast(packets[5],
                       observed_ms=frames[5]["observed_ms"],
                       uncertainty_ms=ntp_uncertainty_ms)
    expected_hours = {first[s]["next_funding_ms"] for s in SYMBOLS}
    if (first != second or len(expected_hours) != 1):
        # Rates can change between samples; only same clock-hour required.
        if any(first[s]["next_funding_ms"] != second[s]["next_funding_ms"]
               for s in SYMBOLS):
            raise ValueError("HL_R24_PROVIDER_FUNDING_HOUR_CHANGED_OR_CONFLICTED")
    # The original native public execution parser validates the actual
    # metadata+3 contemporaneous public orderbook envelopes, without orders.
    books = {}
    for index, coin in enumerate(SYMBOLS, 2):
        result = _paper_execution_observation(
            coin, packets[0], packets[index],
            frames[0]["started_ms"], frames[index]["observed_ms"])
        if (result["market_book_validated"] is not True
                or result["financial_execution_authorized"] is not False
                or result["startup_authorized"] is not False
                or result["historical_settlement_oracle"] is not None
                or result["fee_schedule"] is not None):
            raise ValueError("HL_R24_ORIGINAL_BOOK_FINANCIAL_AUTHORITY_REFUSED")
        books[coin] = {"book_time_ms":result["book_timestamp_ms"],
                       "bid":result["bid"],"ask":result["ask"]}
    return {
        "schema":SCHEMA,
        "status":"SIX_GENUINE_PUBLIC_INFO_RAW_OBSERVATIONS_STRUCTURALLY_VALID_ONLY",
        "source_url":SOURCE,
        "symbols":list(SYMBOLS),
        "real_public_info_requests":6,
        "reserved_max_info_weight":MAX_WEIGHT,
        "max_verified_ntp_uncertainty_ms":ntp_uncertainty_ms,
        "first_funding":first, "second_funding":second,
        "books":books,
        "all_raw_receipts_sha256":[r["raw_sha256"] for r in frames],
        "two_forecast_samples_separated_at_least_ten_seconds":True,
        "historical_settlement_oracle_accepted":False,
        "account_fee_tier_accepted":False,
        "provider_data_rights_accepted":False,
        "ongoing_source_continuity_proven":False,
        "original_source_issuer_commissioned":False,
        "financial_accounts_initialized":False,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
    }
