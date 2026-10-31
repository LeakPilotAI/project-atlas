"""Pure versioned read-only PAPER presentation contracts. No stores, routes or authority."""
import json
from decimal import Decimal, InvalidOperation
from html import escape


def number(value):
    if type(value) is not str:
        raise ValueError("Explicit decimal string required")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Malformed decimal") from error
    if not result.is_finite():
        raise ValueError("Finite decimal required")
    return result


def body(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate presentation field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


METRICS = ("reconciled_cash", "realized_gross", "trading_costs", "realized_net")
ACCOUNT_FIELDS = {"schema", "strategy", "epoch", "currency", "simulated_opening_cash", "observed_at",
                  "max_event_age_seconds", "source_revision", "source_head", "state", "remaining_positions",
                  "freshness", "unavailable_metrics", "total_equity", "unrealized_pnl", "reason_codes",
                  "reconciliation", "startup_authorized", "shutdown_authorized", *METRICS}


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
