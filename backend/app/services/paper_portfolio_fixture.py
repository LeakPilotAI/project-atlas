"""Versioned read-only disposable account summary/presentation;no API registration.

Independent arithmetic checks local declared fixture sources,not authenticated
archives or protected storage. No account consolidation or unrealized valuation.
"""
import sqlite3
from decimal import Decimal
from html import escape

from app.services.paper_epoch_fixture import body, digest, number, strict
from app.services.paper_strategy_fixture import NativeProjectionFixture

METRICS = ("reconciled_cash", "realized_gross", "trading_costs", "realized_net")
ACCOUNT_FIELDS = {"schema", "strategy", "epoch", "currency", "simulated_opening_cash", "observed_at",
                  "max_event_age_seconds", "source_revision", "source_head", "state", "remaining_positions",
                  "freshness", "unavailable_metrics", "total_equity", "unrealized_pnl", "reason_codes",
                  "reconciliation", "startup_authorized", "shutdown_authorized", *METRICS}


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


def portfolio_payload_fixture(accounts):
    """Validated deterministic API-shaped payload,no totals,no registered route."""
    seen, epochs, rows = set(), set(), []
    for row in accounts:
        if type(row) is not dict or set(row) != ACCOUNT_FIELDS:
            raise ValueError("Exact versioned account summary required")
        if type(row["strategy"]) is not str or type(row["epoch"]) is not str:
            raise ValueError("String strategy/epoch identities required")
        identity = row["strategy"], row["epoch"]
        if identity in seen or row["epoch"] in epochs or row.get("schema") != "PAPER_ACCOUNT_SUMMARY_FIXTURE_V1":
            raise ValueError("Duplicate/unsupported account summary")
        seen.add(identity)
        epochs.add(row["epoch"])
        if (row.get("startup_authorized") is not False or row.get("shutdown_authorized") is not False
                or row.get("state") not in ("UNKNOWN", "INCOMPLETE", "RECONCILED_FIXTURE_ONLY")
                or row.get("total_equity") is not None or row.get("unrealized_pnl") is not None):
            raise ValueError("Invalid authority/state or fabricated equity")
        if (row["strategy"] not in ("QUALITY_DIPS", "HYPERLIQUID_MANUAL") or row["currency"] != "USD"
                or type(row["epoch"]) is not str or not row["epoch"]
                or type(row["observed_at"]) is not int or type(row["max_event_age_seconds"]) is not int
                or row["max_event_age_seconds"] < 0 or number(row["simulated_opening_cash"]) <= 0):
            raise ValueError("Malformed account identity/clock/capital")
        for key in METRICS:
            if row[key] is not None:
                number(row[key])
        number(row["simulated_opening_cash"])
        if row["state"] != "UNKNOWN" and (any(row[k] is None for k in METRICS)
                or type(row.get("source_revision")) is not int or row["source_revision"] < 0
                or row.get("reconciliation") != "INDEPENDENT_FIXTURE_ARITHMETIC"
                or type(row["remaining_positions"]) is not list):
            raise ValueError("Missing reconciled source evidence")
        if row["state"] == "UNKNOWN" and any(row[k] is not None for k in METRICS):
            raise ValueError("Unknown evidence cannot publish balances")
        if row["state"] != "UNKNOWN":
            position_ids = set()
            for p in row["remaining_positions"]:
                if (type(p) is not dict or set(p) != {"position_id", "symbol", "side", "quantity", "position_revision"}
                        or type(p["position_id"]) is not str or not p["position_id"].startswith(row["epoch"] + ":")
                        or p["position_id"] in position_ids or type(p["symbol"]) is not str or not p["symbol"]
                        or p["side"] not in ("LONG", "SHORT") or number(p["quantity"]) <= 0
                        or type(p["position_revision"]) is not int or p["position_revision"] < 1):
                    raise ValueError("Malformed remaining-position inventory")
                position_ids.add(p["position_id"])
            if number(row["realized_gross"]) - number(row["trading_costs"]) != number(row["realized_net"]):
                raise ValueError("Gross/cost/net contradiction")
            freshness = row["freshness"]
            if (type(freshness) is not dict or set(freshness) != {"status", "event_at", "age_seconds", "basis"}
                    or freshness["basis"] != "FINANCIAL_EVENT_NOT_MARKET_QUOTE"
                    or type(freshness["event_at"]) is not int or type(freshness["age_seconds"]) is not int
                    or freshness["age_seconds"] != row["observed_at"] - freshness["event_at"]
                    or freshness["age_seconds"] < 0
                    or freshness["status"] != ("STALE" if freshness["age_seconds"] > row["max_event_age_seconds"] else "FRESH")):
                raise ValueError("Malformed freshness evidence")
            if row["state"] == "RECONCILED_FIXTURE_ONLY" and (row["remaining_positions"] or freshness["status"] != "FRESH"):
                raise ValueError("Open/stale account cannot appear complete")
        elif row["remaining_positions"] is not None or row["source_revision"] is not None or row["source_head"] is not None:
            raise ValueError("UNKNOWN cannot invent verified source inventory")
        rows.append(strict(body(row)))
    return {"schema": "PAPER_PORTFOLIO_FIXTURE_V1", "accounts": sorted(rows, key=lambda r: (r["strategy"], r["epoch"])),
            "portfolio_totals": None, "consolidation": "NOT_AUTHORIZED", "startup_authorized": False}


def render_portfolio_fixture(payload):
    """Inert escaped presentation fragment,not a connected dashboard."""
    if payload != portfolio_payload_fixture(payload["accounts"]):
        raise ValueError("Malformed portfolio presentation contract")
    lines = ["<table><thead><tr><th>Strategy / epoch</th><th>State</th><th>Reconciled cash</th><th>Realized net</th></tr></thead><tbody>"]
    for r in payload["accounts"]:
        cells = [r["strategy"] + " / " + r["epoch"], r["state"], r["reconciled_cash"], r["realized_net"]]
        lines.append("<tr>" + "".join("<td>" + escape("Unavailable" if v is None else v) + "</td>" for v in cells) + "</tr>")
    return "".join(lines) + "</tbody></table><p>Separate simulated accounts. No combined equity or trading authority.</p>"
