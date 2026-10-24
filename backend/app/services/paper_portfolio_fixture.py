"""Versioned read-only disposable account summary/presentation;no API registration.

Independent arithmetic checks local declared fixture sources,not authenticated
archives or protected storage. No account consolidation or unrealized valuation.
"""
import sqlite3
from decimal import Decimal

from app.services.paper_epoch_fixture import digest, number, strict
from app.services.paper_strategy_fixture import NativeProjectionFixture
from app.services.paper_summary_contract import (
    portfolio_payload_fixture,
    render_portfolio_fixture,
)

__all__ = ["account_summary_fixture", "portfolio_payload_fixture", "render_portfolio_fixture"]

METRICS = ("reconciled_cash", "realized_gross", "trading_costs", "realized_net")


def _audit(store, snapshot):
    """Independent financial recomputation,not EpochFixture._apply reuse."""
    positions, gross, costs = {}, Decimal(0), Decimal(0)
    cash = number(store.manifest["opening_cash"])
    spot = store.manifest["strategy"] == "QUALITY_DIPS"
    with store.connect(readonly=True) as db:
        db.execute("BEGIN")
        verified, head, operations = store._load(db)  # Structural/receipt integrity is still required.
        if digest(verified) != digest({k: snapshot[k] for k in verified}):
            raise ValueError("Source changed during summary read")
        for raw, ack in db.execute("SELECT body,receipt FROM events ORDER BY revision"):
            c, receipt = strict(raw), strict(ack)
            if c["kind"] == "ENTRY":
                ident = receipt["position_id"]
                if ident in positions:
                    raise ValueError("Duplicate independent original inventory")
                qty, price = number(c["quantity"]), number(c["quote"]["price"])
                positions[ident] = {"quantity": qty, "remaining": qty, "entry": price, "side": c["side"], "net": Decimal(0)}
                if spot:
                    cash -= qty * price
            else:
                p = positions[c["position_id"]]
                qty, price = number(c["quantity"]), number(c["quote"]["price"])
                p["remaining"] -= qty
                if p["remaining"] < 0:
                    raise ValueError("Independent over-close")
                gain = (price - p["entry"]) * qty * (1 if p["side"] == "LONG" else -1)
                cost = p["entry"] * qty * (number(store.manifest["fees_bps"]) + number(store.manifest["slippage_bps"])) / 5000
                gross += gain
                costs += cost
                p["net"] += gain - cost
                cash += price * qty - cost if spot else gain - cost
    if (set(positions) != set(snapshot["positions"]) or cash != number(snapshot["cash"])
            or gross != number(snapshot["gross"]) or costs != number(snapshot["costs"])
            or gross - costs != number(snapshot["net"])):
        raise ValueError("Independent cash/inventory reconciliation mismatch")
    for ident, p in positions.items():
        s = snapshot["positions"][ident]
        if any(p[k] != number(s[k]) for k in ("quantity", "remaining", "entry")) or p["net"] != number(s["realized_net"]):
            raise ValueError("Independent position reconciliation mismatch")
    return head, any(receipt["projection_required"] for _, receipt in operations.values())


def account_summary_fixture(store, *, now, max_age, reader=None):
    """Collect fresh local reads;event age is not market-quote freshness."""
    if type(now) is not int or type(max_age) is not int or max_age < 0:
        raise ValueError("Explicit bounded fixture clock/freshness contract required")
    result = {"schema": "PAPER_ACCOUNT_SUMMARY_FIXTURE_V1", "strategy": store.manifest["strategy"],
              "epoch": store.manifest["epoch"], "currency": store.manifest["currency"],
              "simulated_opening_cash": store.manifest["opening_cash"], "observed_at": now,
              "max_event_age_seconds": max_age,
              "source_revision": None, "source_head": None, "state": "UNKNOWN", "remaining_positions": None,
              "freshness": {"status": "UNKNOWN", "event_at": None, "age_seconds": None,
                            "basis": "FINANCIAL_EVENT_NOT_MARKET_QUOTE"},
              "unavailable_metrics": ["total_equity", "unrealized_pnl", "market_data_freshness"],
              "total_equity": None, "unrealized_pnl": None, "reason_codes": [],
              "reconciliation": "UNVERIFIED", "startup_authorized": False, "shutdown_authorized": False}
    result.update(dict.fromkeys(METRICS))
    try:
        snapshot = (reader or store).snapshot()
        if snapshot["pending_projections"]:
            raise ValueError("Pending projection")
        head, needs_native = _audit(store, snapshot)
        if needs_native and (not isinstance(reader, NativeProjectionFixture) or reader.store is not store):
            raise ValueError("Required native projection verification absent")
        if (reader or store).snapshot() != snapshot:
            raise ValueError("Source/projection changed during summary read")
        age = now - snapshot["last_clock"]
        if age < 0:
            raise ValueError("Future financial evidence")
        remaining = [{"position_id": ident, "symbol": p["symbol"], "side": p["side"],
                      "quantity": p["remaining"], "position_revision": p["revision"]}
                     for ident, p in sorted(snapshot["positions"].items()) if number(p["remaining"]) > 0]
        result.update(reconciled_cash=snapshot["cash"], realized_gross=snapshot["gross"], trading_costs=snapshot["costs"],
                      realized_net=snapshot["net"], source_revision=snapshot["revision"], source_head=head,
                      remaining_positions=remaining, reconciliation="INDEPENDENT_FIXTURE_ARITHMETIC",
                      state="INCOMPLETE" if remaining or age > max_age else "RECONCILED_FIXTURE_ONLY")
        result["freshness"].update(status="STALE" if age > max_age else "FRESH", event_at=snapshot["last_clock"], age_seconds=age)
        result["reason_codes"] = (["OPEN_POSITIONS"] if remaining else []) + (["FINANCIAL_EVENT_AGE_LIMIT"] if age > max_age else [])
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError, sqlite3.Error):
        result["reason_codes"] = ["SOURCE_OR_PROJECTION_UNVERIFIED"]
    return result
