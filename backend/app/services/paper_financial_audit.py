"""Independent arithmetic over structurally verified event streams; no storage.

This does not call the transition/replay engine or authenticate source origin.
Caller must establish complete source/receipt/projection evidence separately.
"""
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from app.services.paper_financial_replay import digest, number, strict, validate_manifest


def audit_financial_events(manifest, records, snapshot):
    validate_manifest(manifest)
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        return _audit(manifest, records, snapshot)


def _audit(manifest, records, snapshot, *, record_schema="PAPER_EVENT_STREAM_RECORD_V1"):
    positions, origins, operations = {}, set(), set()
    gross, costs, revision = Decimal(0), Decimal(0), 0
    net_r, cash = number(manifest["initial_net_r"]), number(manifest["opening_cash"])
    spot, projection_required = manifest["strategy"] == "QUALITY_DIPS", False
    for row in records:
        if type(row) is not dict or row.get("schema") != record_schema:
            raise ValueError("Versioned verified source stream required")
        c, receipt = strict(row["command"]), strict(row["receipt"])
        revision += 1
        ident = receipt["position_id"]
        if (type(row["revision"]) is not int or type(c["expected_source_revision"]) is not int
                or type(receipt["source_revision"]) is not int or type(receipt["position_revision"]) is not int
                or row["revision"] != revision or c["expected_source_revision"] != revision - 1
                or c["epoch"] != manifest["epoch"] or receipt["epoch"] != manifest["epoch"]
                or row["operation_id"] in operations or row["operation_id"] != c["operation_id"]
                or receipt["operation_id"] != c["operation_id"] or receipt["source_revision"] != revision
                or receipt["payload_digest"] != digest(c) or type(receipt["projection_required"]) is not bool):
            raise ValueError("Independent operation/revision binding mismatch")
        operations.add(row["operation_id"])
        projection_required |= receipt["projection_required"]
        qty, price = number(c["quantity"]), number(c["quote"]["price"])
        if min(qty, price) <= 0:
            raise ValueError("Independent positive quantity/price required")
        if c["kind"] == "ENTRY":
            if ident in positions or c["origin_ref"] in origins or not ident.startswith(manifest["epoch"] + ":"):
                raise ValueError("Duplicate/foreign independent original inventory")
            origins.add(c["origin_ref"])
            positions[ident] = {"quantity": qty, "remaining": qty, "entry": price, "side": c["side"],
                                "symbol": c["symbol"], "revision": 1, "net": Decimal(0), "risk_price": c["risk_price"]}
            if spot: cash -= qty * price
        elif c["kind"] == "EXIT":
            p = positions.get(ident)
            if (p is None or c["position_id"] != ident or c["expected_position_revision"] != p["revision"]
                    or c["quote"]["symbol"] != p["symbol"] or qty > p["remaining"]):
                raise ValueError("Independent orphan/over-close/revision mismatch")
            p["remaining"] -= qty
            p["revision"] += 1
            gain = (price - p["entry"]) * qty * (1 if p["side"] == "LONG" else -1)
            cost = p["entry"] * qty * (number(manifest["fees_bps"]) + number(manifest["slippage_bps"])) / 5000
            gross, costs = gross + gain, costs + cost
            p["net"] += gain - cost
            cash += price * qty - cost if spot else gain - cost
            if p["risk_price"] is not None:
                net_r += (gain - cost) / (number(p["risk_price"]) * p["quantity"])
        else:
            raise ValueError("Unknown financial event")
        if receipt["position_revision"] != positions[ident]["revision"]:
            raise ValueError("Independent receipt position revision mismatch")
    if (type(snapshot["revision"]) is not int or set(positions) != set(snapshot["positions"]) or revision != snapshot["revision"]
            or cash != number(snapshot["cash"]) or gross != number(snapshot["gross"])
            or costs != number(snapshot["costs"]) or gross - costs != number(snapshot["net"])
            or net_r != number(snapshot["net_r"])):
        raise ValueError("Independent cash/inventory/revision reconciliation mismatch")
    for ident, p in positions.items():
        s = snapshot["positions"][ident]
        if (any(p[k] != number(s[k]) for k in ("quantity", "remaining", "entry"))
                or type(s["revision"]) is not int or p["net"] != number(s["realized_net"]) or p["revision"] != s["revision"]
                or p["symbol"] != s["symbol"] or p["side"] != s["side"]):
            raise ValueError("Independent position reconciliation mismatch")
    return {"schema": "PAPER_ARITHMETIC_AUDIT_V1", "source_revision": revision,
            "position_count": len(positions), "projection_required": projection_required,
            "production_authorized": False, "startup_authorized": False}
