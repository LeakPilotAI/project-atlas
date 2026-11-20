"""Pure disposable-source audit, not account inception or runtime authority.

No file access, clocks, singleton or financial writes. The caller's digest pins
fixture bytes only; it does not authenticate a custodian or complete archive.
Native Quality Dips V1 has gross lot returns, not a fee/cash accounting contract.
"""
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate source field")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("Nonfinite source value: " + value)


def _number(value, *, positive=False):
    try:
        if isinstance(value, bool):
            raise TypeError("Boolean financial value")
        result = Decimal(str(value))
        if not result.is_finite() or (positive and result <= 0):
            raise ValueError("Invalid financial value")
        return result
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid financial value") from exc


def audit_quality_fixture(raw, *, expected_sha256):
    """Validate a pinned native V1 fixture before deriving gross-only totals.

    Reject ambiguous history instead of inheriting the legacy view's dict-based
    duplicate collapsing/orphan omission. Partial exits need a separate approved
    version; they cannot be represented as a native V1 full lot close.
    """
    if type(raw) is not bytes or not raw or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Exact nonempty fixture source required")
    opens, closed, event_ids, clocks = {}, {}, set(), {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        if (type(row) is not dict or type(row.get("schema_version")) is not int
                or row["schema_version"] != 1 or row.get("execution") != "PAPER_ONLY"
                or row.get("live_capital_allowed") is not False
                or row.get("automatic_real_money_execution") is not False):
            raise ValueError("Unsupported fixture source contract")
        ident = row.get("event_id")
        if type(ident) is not str or not ident or ident in event_ids:
            raise ValueError("Missing or duplicate source event")
        event_ids.add(ident)
        stamp = datetime.fromisoformat(row["timestamp"])
        if stamp.tzinfo is None:
            raise ValueError("Explicit source timezone required")
        kind = row.get("event")
        if kind == "decision":
            continue
        lot = row.get("lot_id")
        if type(lot) is not str or not lot or not row.get("symbol"):
            raise ValueError("Missing lot identity")
        if kind == "open_lot":
            if (lot in opens or row.get("side") != "LONG" or row.get("status") != "OPEN"
                    or row.get("strategy_version") != "QUALITY_DIPS_V3"
                    or row.get("paper_policy_version") != "QUALITY_DIPS_PAPER_V1"):
                raise ValueError("Duplicate or unsupported opening lot")
            price = _number(row.get("fill_price"), positive=True)
            qty = _number(row.get("quantity_shares"), positive=True)
            notional = _number(row.get("paper_notional_dollars"), positive=True)
            if abs(qty * price - notional) > Decimal("0.0000001"):
                raise ValueError("Opening quantity/notional mismatch")
            opens[lot] = row
        else:
            if lot not in opens or lot in closed or row["symbol"] != opens[lot]["symbol"]:
                raise ValueError("Orphan, repeated close or conflicting lot identity")
            if stamp < clocks[lot]:
                raise ValueError("Reversed lot history")
            opening = opens[lot]
            qty = _number(opening["quantity_shares"], positive=True)
            entry = _number(opening["fill_price"], positive=True)
            if kind == "mark_lot":
                _number(row.get("market_price"), positive=True)
            elif kind == "close_lot":
                price = _number(row.get("exit_price"), positive=True)
                if (_number(row.get("quantity_shares"), positive=True) != qty
                        or row.get("status") != "CLOSED"
                        or abs(_number(row.get("realized_pnl")) - (price - entry) * qty) > Decimal("0.00000001")):
                    raise ValueError("Full-close quantity/gross P&L mismatch")
                closed[lot] = row
            else:
                raise ValueError("Unsupported lot event; partial exits cannot imply full close")
        clocks[lot] = stamp
    if not opens:
        raise ValueError("No complete opening inventory")
    gross = sum((_number(r["realized_pnl"]) for r in closed.values()), Decimal(0))
    return {"schema": "QUALITY_DIPS_FIXTURE_HANDOFF_V1", "source_sha256": expected_sha256,
            "source_event_count": len(event_ids), "original_lot_count": len(opens),
            "closed_lot_count": len(closed), "remaining_lot_ids": sorted(set(opens) - set(closed)),
            "realized_gross_currency": str(gross), "realized_net_currency": None, "currency": None,
            "opening_cash": None, "closing_cash": None, "equity": None,
            "report_state": "INCOMPLETE", "reason_codes": ["NO_ACCEPTED_CASH_SOURCE", "NO_COST_CONTRACT", "NO_CURRENCY_CONTRACT"],
            "source_completeness_authenticated": False, "shutdown_authorized": False,
            "startup_authorized": False, "production_authorized": False}
