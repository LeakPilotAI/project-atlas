"""Versioned offline fill replay; no fill generation, persistence or authority."""
from decimal import Decimal


def _decimal(value):
    if type(value) not in (str, int):
        raise ValueError("Explicit exact decimal required")
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError("Nonfinite accounting")
    return number


def replay_partial_fills(position, fills):
    if position.get("schema") != "PAPER_PARTIAL_POSITION_V1":
        raise ValueError("Explicit versioned position required")
    quantity, entry, risk = (_decimal(position[k]) for k in ("quantity", "entry", "risk_price"))
    fee, slip = (_decimal(position[k]) for k in ("fees_bps", "slippage_bps"))
    if min(quantity, entry, risk) <= 0 or min(fee, slip) < 0 or position["side"] not in ("LONG", "SHORT"):
        raise ValueError("Invalid position")
    if not position.get("currency") or type(position.get("opened_at")) is not int:
        raise ValueError("Missing currency/clock")
    seen, remaining, net, gross_total, costs = {}, quantity, Decimal(0), Decimal(0), Decimal(0)
    last = position["opened_at"]
    for fill in fills:
        ident = fill.get("fill_id")
        if type(ident) is not str or not ident:
            raise ValueError("Missing fill identity")
        if ident in seen:
            if seen[ident] != fill:
                raise ValueError("Conflicting fill replay")
            continue
        if fill.get("trade_id") != position["trade_id"] or fill.get("schema") != "PAPER_PARTIAL_FILL_V1":
            raise ValueError("Fill identity/schema mismatch")
        clock = fill.get("timestamp")
        if type(clock) is not int or clock < last:
            raise ValueError("Fill chronology mismatch")
        amount, price = (_decimal(fill[k]) for k in ("quantity", "price"))
        if not 0 < amount <= remaining or price <= 0:
            raise ValueError("Over-close or invalid fill")
        # Legacy entry-notional cost convention; allocate entry costs per closed unit.
        gross = (price - entry) * amount * (1 if position["side"] == "LONG" else -1)
        cost = 2 * entry * amount * (fee + slip) / Decimal(10000)
        remaining -= amount
        gross_total += gross
        costs += cost
        net += gross - cost
        last, seen[ident] = clock, dict(fill)
    return {"schema": "PAPER_PARTIAL_ACCOUNTING_V1", "trade_id": position["trade_id"],
            "remaining_quantity": str(remaining), "closed_quantity": str(quantity - remaining),
            "gross_currency": str(gross_total), "cost_currency": str(costs), "net_currency": str(net),
            "currency": position["currency"], "net_r_original_risk": str(net / (risk * quantity)),
            "unique_fill_n": len(seen), "complete": remaining == 0,
            "cost_policy": "LEGACY_ENTRY_NOTIONAL_ALLOCATED_PER_CLOSED_UNIT", "production_authorized": False}
