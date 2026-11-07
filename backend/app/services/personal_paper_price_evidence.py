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
    if quote.get("timestamp_basis") != "PROVIDER_EVENT_TIMESTAMP":
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

def preview_quality_dips_execution(
    observation: dict[str, Any], quote: dict[str, Any], *, now: datetime,
) -> dict[str, Any]:
    """Join frozen V3 research with quote evidence; never create a fill."""
    if type(observation) is not dict or observation.get("strategy") != "QUALITY_DIPS_V3":
        raise PriceEvidenceRejected("QUALITY_DIPS_OBSERVATION_REQUIRED")
    symbol = observation.get("symbol")
    if type(symbol) is not str or not symbol:
        raise PriceEvidenceRejected("OBSERVATION_SYMBOL_MISSING")
    raw_blockers = observation.get("blockers", [])
    if type(raw_blockers) is not list or any(type(item) is not str or not item for item in raw_blockers):
        raise PriceEvidenceRejected("INVALID_STRATEGY_BLOCKERS")
    blockers = list(raw_blockers)
    evidence = None
    try:
        evidence = validate_stock_iex_quote(quote, symbol=symbol, now=now)
    except PriceEvidenceRejected as exc:
        blockers.append(str(exc))
    plan = observation.get("strategy_result")
    ladder = plan.get("entry_ladder") if type(plan) is dict else None
    if type(ladder) is not dict or ladder.get("ready") is not True:
        blockers.append("QUALITY_DIPS_ENTRY_LADDER_NOT_READY")
    if observation.get("paper_execution_eligible") is not True:
        blockers.append("STRATEGY_OBSERVATION_NOT_EXECUTION_ELIGIBLE")
    return {
        "schema": "ATLAS_PERSONAL_PAPER_QUALITY_DIPS_EXECUTION_PREVIEW_V1",
        "symbol": symbol,
        "observation_id": observation.get("observation_id"),
        "quote_evidence": evidence,
        "blockers": list(dict.fromkeys(blockers)),
        "paper_execution_eligible": False,
        "paper_fill_authorized": False,
        "live_order_authorized": False,
    }

def preview_stock_execution_side(evidence: dict[str, Any], *, side: str, quantity: str) -> dict[str, Any]:
    """Pure conservative bid/ask reference for a proposed PAPER trade; never fills."""
    if type(evidence) is not dict or evidence.get("schema") != "ATLAS_PERSONAL_PAPER_PRICE_EVIDENCE_V1":
        raise PriceEvidenceRejected("VALIDATED_QUOTE_EVIDENCE_REQUIRED")
    if evidence.get("paper_fill_authorized") is not False or evidence.get("live_order_authorized") is not False:
        raise PriceEvidenceRejected("QUOTE_EVIDENCE_AUTHORITY_MISMATCH")
    if side not in ("BUY", "SELL"):
        raise PriceEvidenceRejected("EXECUTION_SIDE_UNSUPPORTED")
    try:
        qty = Decimal(quantity)
        bid = Decimal(evidence["bid"])
        ask = Decimal(evidence["ask"])
    except (KeyError, TypeError, InvalidOperation, ValueError) as exc:
        raise PriceEvidenceRejected("EXECUTION_PRICE_OR_QUANTITY_INVALID") from exc
    if not qty.is_finite() or qty <= 0 or not bid.is_finite() or not ask.is_finite() or not 0 < bid <= ask:
        raise PriceEvidenceRejected("EXECUTION_PRICE_OR_QUANTITY_INVALID")
    reference = ask if side == "BUY" else bid
    return {
        "schema": "ATLAS_PERSONAL_PAPER_EXECUTION_SIDE_PREVIEW_V1",
        "symbol": evidence.get("symbol"), "side": side, "quantity": str(qty),
        "reference_price": str(reference), "reference_notional": str(qty * reference),
        "price_basis": "ASK_FOR_BUY_BID_FOR_SELL", "paper_fill_authorized": False,
        "live_order_authorized": False,
    }
