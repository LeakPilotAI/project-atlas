"""Independent fixture exit audit; does not call execution/accounting producers."""
import hashlib
import json
import sqlite3
from decimal import Decimal
from pathlib import Path


def audit_fixture_exits(path, *, expected_positions=None):
    def number(value):
        value = Decimal(str(value))
        if not value.is_finite():
            raise ValueError("Nonfinite audit input")
        return value

    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        positions = {ident: json.loads(body) for ident, body in db.execute("SELECT id,body FROM positions")}
        if expected_positions is not None:
            if type(expected_positions) is not dict:
                raise ValueError("Explicit trusted fixture position inventory required")
            actual = {ident: hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
                      for ident, row in positions.items()}
            if actual != expected_positions:
                raise ValueError("Missing, changed or unexpected original position")
        exits = {ident: json.loads(body) for ident, body in db.execute("SELECT id,body FROM exits")}
        fills = {}
        for ident, trade, body in db.execute("SELECT id,trade,body FROM partial_fills ORDER BY rowid"):
            row = json.loads(body)
            if trade not in positions or row["trade_id"] != trade or row["fill_id"] != ident:
                raise ValueError("Orphan or conflicting fill identity")
            fills.setdefault(trade, []).append(row)
        if set(exits) - set(positions):
            raise ValueError("Orphan exit")
        unresolved, totals = [], {}
        for ident, p in positions.items():
            quantity, entry, risk = (number(p[k]) for k in ("quantity", "actual_entry_price", "risk_price"))
            if min(quantity, entry, risk) <= 0 or p["side"] not in ("LONG", "SHORT"):
                raise ValueError("Invalid position")
            remaining, net, gross_total = quantity, Decimal(0), Decimal(0)
            fee, slip = number(p["fees_bps"]), number(p["slippage_bps"])
            rates = fee + slip
            if min(fee, slip) < 0:
                raise ValueError("Invalid costs")
            last = p.get("opened_at", -1)
            for fill in fills.get(ident, []):
                amount, price = number(fill["quantity"]), number(fill["price"])
                if not 0 < amount <= remaining or price <= 0 or fill["timestamp"] < last:
                    raise ValueError("Invalid committed fill quantity/clock")
                last = fill["timestamp"]
                gross = (price - entry) * amount * (1 if p["side"] == "LONG" else -1)
                gross_total += gross
                net += gross - 2 * entry * amount * rates / 10000
                remaining -= amount
            closed = exits.get(ident)
            if closed:
                if closed.get("trade_id") != ident:
                    raise ValueError("Exit identity mismatch")
                if closed.get("reason") == "RECORDED_PARTIAL_FILLS_COMPLETE":
                    if remaining != 0:
                        raise ValueError("Premature finalization")
                else:
                    price = number(closed["reference_price"])
                    if remaining <= 0 or price <= 0 or closed["exit_timestamp"] < last:
                        raise ValueError("Invalid final exit")
                    recorded = closed["currency_accounting"]
                    if number(recorded.get("shutdown_quantity", recorded["quantity"])) != remaining:
                        raise ValueError("Shutdown quantity mismatch")
                    gross = (price - entry) * remaining * (1 if p["side"] == "LONG" else -1)
                    gross_total += gross
                    net += gross - 2 * entry * remaining * rates / 10000
                    if number(recorded["gross"]) != gross_total:
                        raise ValueError("Exit gross mismatch")
                    for key, rate in (("entry_fee", fee), ("exit_fee", fee), ("entry_slippage", slip), ("exit_slippage", slip)):
                        if number(recorded[key]) != entry * remaining * rate / 10000:
                            raise ValueError("Exit fee/slippage component mismatch")
                if number(closed["currency_accounting"]["net"]) != net or number(closed["net_pnl_r"]) != net / (risk * quantity):
                    raise ValueError("Exit P&L mismatch")
                totals[p["currency"]] = totals.get(p["currency"], Decimal(0)) + net
            else:
                unresolved.append(ident)
        return {"scope": "INDEPENDENT_LOCAL_RECOMPUTATION", "unresolved": sorted(unresolved),
                "source_inventory_matched": expected_positions is not None,
                "source_completeness_independently_proven": False,
                "reconciled": not unresolved, "closed_n": len(exits),
                "currency_totals": {k: str(v) for k, v in sorted(totals.items())},
                "production_authorized": False}
