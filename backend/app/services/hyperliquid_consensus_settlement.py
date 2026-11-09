"""Operational Hyperliquid funding oracle must be tied to settlement consensus.

The public fundingHistory rate alone does not include the oracle price applied
at settlement. Current metaAndAssetCtxs oraclePx is not historical proof.
This validates *shape and relative event ordering only*: separate existing
financial authorities must authenticate the original consensus actions, their
completeness, and publisher custody. No external provider or financial I/O.
"""
from __future__ import annotations

import re

from app.services.paper_financial_replay import number, text

SCHEMA = "HL_CONSENSUS_SETTLEMENT_ORACLE_V1"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = {
    "schema", "venue", "symbol", "settlement_at", "price",
    "source_id", "revision", "price_block", "settlement_block",
    "price_event_at_ms", "settlement_event_at_ms", "funding_rate",
    "oracle_action_digest", "funding_action_digest",
}


def require_consensus_settlement_oracle(oracle, *, symbol, at, funding_record):
    """Refuse stale/current oracle substitution before PAPER funding admission.

    Does not establish source authenticity. The existing authority verifier
    must independently validate both original consensus actions and that this
    was the LAST oracle in force when the settlement applied.
    """
    if (type(oracle) is not dict or set(oracle) != _FIELDS
            or oracle.get("schema") != SCHEMA
            or oracle.get("venue") != "HYPERCORE_NATIVE_PERPS"
            or type(symbol) is not str or symbol not in ("BTC", "ETH", "SOL")
            or type(at) is not int or at <= 0 or at % 3600
            or oracle.get("symbol") != symbol or oracle.get("settlement_at") != at
            or type(oracle.get("revision")) is not int or oracle["revision"] < 1
            or any(type(oracle.get(k)) is not int or oracle[k] <= 0 for k in
                   ("price_block", "settlement_block", "price_event_at_ms",
                    "settlement_event_at_ms"))):
        raise ValueError("HL_ORIGINAL_CONSENSUS_SETTLEMENT_ORACLE_REQUIRED")
    text(oracle["source_id"])
    for key in ("oracle_action_digest", "funding_action_digest"):
        if type(oracle.get(key)) is not str or not _HEX.fullmatch(oracle[key]):
            raise ValueError("HL_CONSENSUS_ACTION_DIGEST_REQUIRED")
    if (type(funding_record) is not dict
            or funding_record.get("settlement_at_ms") != at * 1000
            or type(funding_record.get("provider_event_at_ms")) is not int
            or funding_record["provider_event_at_ms"] < at * 1000
            or funding_record["provider_event_at_ms"] > (at * 1000 + 30_000)
            or funding_record.get("settlement_oracle") is not None):
        raise ValueError("HL_FUNDING_RATE_IS_NOT_ORACLE_SOURCE")
    if (oracle["price_block"] > oracle["settlement_block"]
            or oracle["price_event_at_ms"] > oracle["settlement_event_at_ms"]
            or oracle["price_event_at_ms"] < at * 1000 - 60_000
            or not at * 1000 <= oracle["settlement_event_at_ms"] <= at * 1000 + 30_000):
        raise ValueError("HL_CONSENSUS_ORACLE_EVENT_ORDER_OR_AGE_REFUSED")
    if (number(oracle["price"]) <= 0
            or number(oracle["funding_rate"]) != number(funding_record["hourly_rate"])
            or abs(number(oracle["funding_rate"])) > number("0.04")):
        raise ValueError("HL_CONSENSUS_ORACLE_RATE_OR_PRICE_MISMATCH")
    return None
