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


def preview_current_stock_order(
    quote: dict[str, Any], *, symbol: str, now: datetime, side: str,
    quantity: str, max_notional: str,
) -> dict[str, Any]:
    """Revalidate provider event at decision time and cap proposed PAPER notional.

    No caller-supplied evidence object is trusted and no simulated fill is made.
    """
    evidence = validate_stock_iex_quote(quote, symbol=symbol, now=now)
    proposal = preview_stock_execution_side(evidence, side=side, quantity=quantity)
    try:
        cap = Decimal(max_notional)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PriceEvidenceRejected("PAPER_NOTIONAL_CAP_INVALID") from exc
    if not cap.is_finite() or cap <= 0:
        raise PriceEvidenceRejected("PAPER_NOTIONAL_CAP_INVALID")
    if Decimal(proposal["reference_notional"]) > cap:
        raise PriceEvidenceRejected("PAPER_NOTIONAL_CAP_EXCEEDED")
    return {**proposal, "quote_evidence": evidence, "max_notional": str(cap)}


def preview_quality_dips_order(
    observation: dict[str, Any], quote: dict[str, Any], *, now: datetime,
    quantity: str, max_notional: str,
) -> dict[str, Any]:
    """Join strategy and decision-time BUY quote into one non-executable proposal."""
    strategy = preview_quality_dips_execution(observation, quote, now=now)
    if strategy["blockers"]:
        raise PriceEvidenceRejected("QUALITY_DIPS_STRATEGY_BLOCKED:" + ",".join(strategy["blockers"]))
    # Even a blocker-free observation is not an execution grant: the public
    # observation pipeline currently does not produce executable observations.
    if observation.get("paper_execution_eligible") is not True:
        raise PriceEvidenceRejected("QUALITY_DIPS_EXECUTION_ELIGIBILITY_REQUIRED")
    proposal = preview_current_stock_order(
        quote, symbol=strategy["symbol"], now=now, side="BUY",
        quantity=quantity, max_notional=max_notional,
    )
    return {**proposal, "observation_id": strategy["observation_id"],
            "strategy": "QUALITY_DIPS_V3", "paper_fill_authorized": False}


def preview_quality_dips_account_capacity(
    proposal: dict[str, Any], *, journal_events: list[dict[str, Any]],
    account_id: str,
) -> dict[str, Any]:
    """Check a simulated journal's cash/position limits without writing a fill.

    This is a diagnostic only: caller-supplied proposals and journal events do
    not establish authority or exclusive writer ownership.
    """
    from app.investment.quality_dips_paper import accounting_snapshot

    if (type(proposal) is not dict or proposal.get("schema") != "ATLAS_PERSONAL_PAPER_EXECUTION_SIDE_PREVIEW_V1"
            or proposal.get("side") != "BUY" or proposal.get("paper_fill_authorized") is not False
            or proposal.get("live_order_authorized") is not False
            or type(journal_events) is not list or type(account_id) is not str or not account_id):
        raise PriceEvidenceRejected("PAPER_ACCOUNT_PREVIEW_INPUT_INVALID")
    try:
        snapshot = accounting_snapshot(journal_events, account_id=account_id)
        notional = Decimal(proposal["reference_notional"])
    except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
        raise PriceEvidenceRejected("PAPER_ACCOUNT_JOURNAL_INVALID") from exc
    if snapshot is None or snapshot.get("data_provenance") != "FORWARD_COLLECTION":
        raise PriceEvidenceRejected("FORWARD_PAPER_ACCOUNT_REQUIRED")
    if not notional.is_finite() or notional <= 0:
        raise PriceEvidenceRejected("PAPER_NOTIONAL_INVALID")
    fee = notional * Decimal(str(snapshot["fee_bps_per_side"])) / Decimal("10000")
    blockers = []
    if notional > Decimal(str(snapshot.get("max_entry_notional", 0))):
        blockers.append("PAPER_ENTRY_NOTIONAL_LIMIT")
    if snapshot["open_positions"] >= snapshot["max_open_positions"]:
        blockers.append("PAPER_POSITION_LIMIT")
    if notional + fee > Decimal(str(snapshot["available_cash"])):
        blockers.append("PAPER_INSUFFICIENT_SIMULATED_CASH")
    return {"schema": "ATLAS_PERSONAL_PAPER_ACCOUNT_CAPACITY_PREVIEW_V1",
            "account_id": account_id, "blockers": blockers,
            "reference_notional": str(notional), "estimated_fee": str(fee),
            "paper_fill_authorized": False, "live_order_authorized": False}


def preview_quality_dips_forward_capacity(
    observation: dict[str, Any], quote: dict[str, Any], *, now: datetime,
    quantity: str, max_notional: str, journal_events: list[dict[str, Any]],
    account_id: str,
) -> dict[str, Any]:
    """Full read-only strategy/quote/account diagnostic, never an execution grant."""
    proposal = preview_quality_dips_order(
        observation, quote, now=now, quantity=quantity, max_notional=max_notional,
    )
    capacity = preview_quality_dips_account_capacity(
        proposal, journal_events=journal_events, account_id=account_id,
    )
    return {"schema": "ATLAS_PERSONAL_PAPER_FORWARD_CAPACITY_DIAGNOSTIC_V1",
            "proposal": proposal, "capacity": capacity,
            "blockers": capacity["blockers"], "paper_fill_authorized": False,
            "live_order_authorized": False}


def check_forward_paper_write_authority(*, installation: Any, request: dict[str, Any],
                                        components: Any) -> dict[str, Any]:
    """Require the installed personal local-operator lease before any future writer.

    Returns a diagnostic only. The actual writer must keep this lease open and
    recheck it immediately before and after its durable mutation.
    """
    from app.services.personal_paper_runtime import checked_personal_installation

    if installation is None or type(request) is not dict:
        raise PriceEvidenceRejected("PERSONAL_OPERATOR_INSTALLATION_REQUIRED")
    try:
        with installation.lease(request) as lease:
            checked_personal_installation(lease, request)
            if lease.check_components(components) is not True:
                raise PriceEvidenceRejected("PERSONAL_WRITER_COMPONENTS_CHANGED")
    except PriceEvidenceRejected:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise PriceEvidenceRejected("PERSONAL_OPERATOR_LEASE_REFUSED") from exc
    return {"schema": "ATLAS_PERSONAL_PAPER_WRITE_AUTHORITY_DIAGNOSTIC_V1",
            "lease_checked": True, "paper_fill_authorized": False,
            "live_order_authorized": False}
