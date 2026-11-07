"""Pure bounded fill-subset comparison; never repairs or authorizes a PAPER book."""
from __future__ import annotations

import hashlib
import json
from collections import Counter

from app.investment.offline_research import aware, number, symbol_identity


class PaperBookAuditRefused(ValueError):
    """Explicit pinned evidence could not be compared safely."""


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise PaperBookAuditRefused("Duplicate JSON field")
        result[key] = value
    return result


def _constant(_value):
    raise PaperBookAuditRefused("Nonfinite JSON evidence")


def _decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise PaperBookAuditRefused("Malformed PAPER evidence") from error


def _pin(raw, expected):
    if type(raw) is not bytes or len(raw) > 5_000_000:
        raise PaperBookAuditRefused("Bounded explicit bytes required")
    digest = hashlib.sha256(raw).hexdigest()
    if type(expected) is not str or digest != expected:
        raise PaperBookAuditRefused("Caller evidence commitment mismatch")
    return digest


def _fill_key(row):
    if not isinstance(row, dict):
        raise PaperBookAuditRefused("Malformed recorded fill")
    try:
        if symbol_identity(row["symbol"]) != row["symbol"]:
            raise ValueError("Noncanonical symbol")
        aware(row["at"], "fill time")
        number(row["shares"], "fill shares")
        number(row["price"], "fill price")
        if row.get("session") not in {"RESEARCH_PAPER", "MARKET_OPEN"}:
            raise ValueError("Unknown fill session")
        raw = json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (KeyError, TypeError, ValueError, RecursionError) as error:
        raise PaperBookAuditRefused("Malformed recorded fill") from error
    return hashlib.sha256(raw).hexdigest()


def audit_fill_subset(snapshot, ledger, *, expected_snapshot_sha256, expected_ledger_sha256):
    """Compare exact recorded payloads, not inferred fills or full book accounting.

    Caller pins bind the supplied bytes only; they are not independent provenance,
    transaction boundaries, tail-loss witnesses or proof that files share ownership.
    Numeric representation changes can be reported as unmatched: no silent coercion.
    """
    state_hash = _pin(snapshot, expected_snapshot_sha256)
    ledger_hash = _pin(ledger, expected_ledger_sha256)
    state = _decode(snapshot)
    if not isinstance(state, dict) or type(state.get("fills")) is not list or len(state["fills"]) > 10000:
        raise PaperBookAuditRefused("Bounded explicit snapshot fills required")
    state_fills = Counter(_fill_key(row) for row in state["fills"])
    lines = ledger.splitlines()
    if len(lines) > 20000:
        raise PaperBookAuditRefused("Bounded ledger required")
    recorded = Counter()
    unexamined = Counter()
    for line in lines:
        event = _decode(line)
        if not isinstance(event, dict) or type(event.get("kind")) is not str:
            raise PaperBookAuditRefused("Explicit ledger event kind required")
        if event["kind"] in {"research_buy", "fill"}:
            recorded[_fill_key({k: v for k, v in event.items() if k != "kind"})] += 1
        else:
            kind = event["kind"] if event["kind"] in {"order", "cancel"} else "UNKNOWN_KIND"
            unexamined[kind] += 1
    missing_state = recorded - state_fills
    missing_ledger = state_fills - recorded
    repeated_ledger = sum(n - 1 for n in recorded.values() if n > 1)
    repeated_state = sum(n - 1 for n in state_fills.values() if n > 1)
    issue = bool(missing_state or missing_ledger or repeated_ledger or repeated_state)
    return {"schema": "ATLAS_PAPER_BOOK_FILL_AUDIT_V1",
            "status": "REQUIRES_RECONCILIATION" if issue else
                      "MATCHED_RECORDED_FILL_SUBSET" if recorded else "INSUFFICIENT_EVIDENCE",
            "snapshot_sha256": state_hash, "ledger_sha256": ledger_hash,
            "snapshot_fill_n": sum(state_fills.values()), "ledger_fill_n": sum(recorded.values()),
            "ledger_payloads_missing_from_snapshot": sum(missing_state.values()),
            "snapshot_payloads_missing_from_ledger": sum(missing_ledger.values()),
            "repeated_ledger_payload_n": repeated_ledger, "repeated_snapshot_payload_n": repeated_state,
            "unexamined_event_kinds": dict(sorted(unexamined.items())),
            "full_book_consistency_established": False, "source_ownership_established": False,
            "startup_authorized": False, "recovery_authorized": False, "paper_trading_authorized": False,
            "live_trading_authorized": False, "repair_performed": False}
