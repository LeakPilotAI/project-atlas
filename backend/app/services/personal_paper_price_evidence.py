"""Fail-closed executable-price evidence validation for future PAPER fills.

This is a pure validator. It cannot authorize trading or call a provider.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class PriceEvidenceRejected(ValueError):
    """Evidence cannot support a contemporaneous simulated execution."""


def validate_stock_iex_quote(
    quote: dict[str, Any], *, symbol: str, now: datetime,
    max_age_seconds: float = 15.0, max_spread_bps: float = 100.0,
) -> dict[str, Any]:
    """Validate an already captured Alpaca IEX quote, without granting fill authority."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise PriceEvidenceRejected("CLOCK_NOT_TIMEZONE_AWARE")
    if type(quote) is not dict or quote.get("symbol") != symbol:
        raise PriceEvidenceRejected("QUOTE_SYMBOL_MISMATCH")
    if quote.get("state") != "FRESH":
        raise PriceEvidenceRejected("QUOTE_NOT_FRESH")
    if quote.get("timestamp_basis") not in (None, "PROVIDER_EVENT_TIMESTAMP"):
        raise PriceEvidenceRejected("UNTRUSTED_TIMESTAMP_BASIS")
    raw_time = quote.get("timestamp")
    if not isinstance(raw_time, str):
        raise PriceEvidenceRejected("PROVIDER_TIMESTAMP_MISSING")
    try:
        source = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PriceEvidenceRejected("PROVIDER_TIMESTAMP_INVALID") from exc
    if source.tzinfo is None or source.utcoffset() is None:
        raise PriceEvidenceRejected("PROVIDER_TIMESTAMP_NOT_TIMEZONE_AWARE")
    age = (now.astimezone(UTC) - source.astimezone(UTC)).total_seconds()
    if not 0 <= age <= max_age_seconds:
        raise PriceEvidenceRejected("PROVIDER_QUOTE_STALE_OR_FUTURE")
    try:
        bid = Decimal(str(quote["bid"]))
        ask = Decimal(str(quote["ask"]))
    except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
        raise PriceEvidenceRejected("BID_ASK_UNAVAILABLE") from exc
    if not bid.is_finite() or not ask.is_finite() or not 0 < bid <= ask:
        raise PriceEvidenceRejected("BID_ASK_INVALID")
    spread_bps = (ask - bid) / ask * 10000
    if spread_bps > Decimal(str(max_spread_bps)):
        raise PriceEvidenceRejected("BID_ASK_SPREAD_EXCESSIVE")
    if any(type(quote.get(key)) is not int or quote[key] <= 0 for key in ("bid_lots", "ask_lots")):
        raise PriceEvidenceRejected("BID_ASK_SIZE_UNAVAILABLE")
    return {
        "schema": "ATLAS_PERSONAL_PAPER_PRICE_EVIDENCE_V1",
        "symbol": symbol,
        "source": "ALPACA_IEX_PROVIDER_QUOTE",
        "provider_timestamp": source.astimezone(UTC).isoformat(),
        "age_seconds": round(age, 6),
        "bid": str(bid),
        "ask": str(ask),
        "spread_bps": float(spread_bps),
        "paper_fill_authorized": False,
        "live_order_authorized": False,
    }