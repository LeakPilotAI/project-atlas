"""Independent arithmetic over structurally verified event streams; no storage.

This does not call the transition/replay engine or authenticate source origin.
Caller must establish complete source/receipt/projection evidence separately.
"""
from decimal import ROUND_HALF_EVEN, Context, Decimal, Inexact, localcontext
from fractions import Fraction

from app.services.paper_financial_replay import digest, number, strict, validate_manifest


def _audit_maintenance(m, p):
    value = p["mark"] * p["remaining"]
    if "margin_policy" not in p:
        return value * number(m["perp_policy"]["maintenance_rate"])
    policy = p["margin_policy"]
    rate, deduction, last = Fraction(0), Fraction(0), None
    chosen = Fraction(0)
    for tier in policy["tiers"]:
        lower = number(tier["lower_bound"])
        next_rate = Fraction(1, 2 * tier["max_leverage"])
        if last is not None: deduction += Fraction(lower) * (next_rate - rate)
        rate, last = next_rate, lower
        if value >= lower: chosen = Fraction(value) * rate - deduction
    q = number(policy["maintenance_quantum"])
    units = chosen / Fraction(q)
    return q * ((units.numerator + units.denominator - 1) // units.denominator)


def audit_financial_events(manifest, records, snapshot):
    validate_manifest(manifest)
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as context:
        if manifest.get("schema") == "PAPER_EPOCH_PERP_FIXTURE_V2":
            context.traps[Inexact] = True
            try:
                return _audit_perp(manifest, records, snapshot)
            except Inexact as exc:
                raise ValueError("Independent perpetual precision refusal") from exc
        return _audit(manifest, records, snapshot)


def _audit_perp(m, records, snapshot):
    """Separate cash-flow derivation; never calls the financial transition."""
    positions, operations, liquidity, funding_events, maker_orders = {}, set(), {}, [], {}
    cash = number(m["opening_cash"])
    gross = fees = slip = funding = liquidation_fees = Decimal(0)
    risk_ratio = Fraction(0)
    parent, revision, clock = digest(m), 0, m["opened_at"]
    required = False
    for row in records:
        if (type(row) is not dict or set(row) != {"schema", "revision", "operation_id", "command", "parent", "digest", "receipt"}
                or row["schema"] != "PAPER_EVENT_STREAM_RECORD_V1"):
            raise ValueError("Independent perpetual envelope mismatch")
        c, r = strict(row["command"]), strict(row["receipt"])
        revision += 1
        ident = r["position_id"]
        recovery = c["schema"] == "PAPER_PERP_FUNDING_RECOVERY_V1"
        maker = c["schema"] == "PAPER_PERP_MAKER_FILL_V1"
        if (c["schema"] not in ("PAPER_PERP_COMMAND_V2", "PAPER_PERP_FUNDING_RECOVERY_V1", "PAPER_PERP_MARGIN_ENTRY_V1", "PAPER_PERP_MARGIN_MARK_V1", "PAPER_PERP_IOC_ENTRY_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1", "PAPER_PERP_LIQUIDATION_V1", "PAPER_PERP_MAKER_FILL_V1") or r["schema"] != "PAPER_PERP_RECEIPT_V2"
                or any(type(v) is not int for v in (row["revision"], c["expected_source_revision"], r["source_revision"], r["position_revision"], c["timestamp"]))
                or row["revision"] != revision or c["expected_source_revision"] != revision - 1
                or r["source_revision"] != revision or c["timestamp"] < clock
                or row["operation_id"] in operations or row["operation_id"] != c["operation_id"]
                or r["operation_id"] != c["operation_id"] or c["epoch"] != m["epoch"] or r["epoch"] != m["epoch"]
                or r["payload_digest"] != digest(c) or row["parent"] != parent
                or row["digest"] != digest([parent, c, r]) or type(r["projection_required"]) is not bool
                or r["execution"] != "SIMULATED" or r["startup_authorized"] is not False
                or r["production_authorized"] is not False):
            raise ValueError("Independent perpetual operation lineage mismatch")
        operations.add(c["operation_id"])
        required |= r["projection_required"]
        parent, clock = row["digest"], c["timestamp"]
        kind, e = c["kind"], c["evidence"]
        if kind == "ENTRY":
            if (ident != m["epoch"] + ":" + digest([m["epoch"], c["operation_id"]]) or ident in positions
                    or any(p["origin"] == c["origin_ref"] for p in positions.values())):
                raise ValueError("Independent original position mismatch")
            price = number(e["ask" if c["side"] == "LONG" else "bid"])
            if maker: price = number(e["maker_execution"]["limit_price"])
            qty, lev = number(c["quantity"]), number(c["leverage"])
            positions[ident] = {"quantity": qty, "remaining": qty, "entry": price, "leverage": lev,
                                   "side": c["side"], "symbol": c["symbol"], "revision": 0, "margin": qty * price / lev,
                                   "risk": number(c["risk_price"]), "net": Decimal(0), "funding": Decimal(0), "remaining_funding": Decimal(0),
                                   "fees": Decimal(0), "slippage": Decimal(0), "next_funding": (clock // 3600 + 1) * 3600,
                                   "mark": number(e["mark"]), "mark_at": clock, "origin": c["origin_ref"]}
            if c["schema"] in ("PAPER_PERP_MARGIN_ENTRY_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1"):
                positions[ident]["margin_policy"] = e["margin_policy"]
            if maker or "margin_policy" in positions[ident]:
                positions[ident]["margin_basis_price"] = max(price, number(e["mark"]))
                positions[ident]["margin"] = qty * positions[ident]["margin_basis_price"] / lev
            if c["schema"] in ("PAPER_PERP_IOC_ENTRY_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1"):
                proof = e["ioc"]
                field = "ask" if c["side"] == "LONG" else "bid"
                requested, step = number(proof["requested_quantity"]), number(proof["quantity_step"])
                capacity = min(requested, number(e[field + "_size"]) * number(m["perp_policy"]["participation"]))
                units = Fraction(capacity) / Fraction(step)
                if (qty != step * (units.numerator // units.denominator) or number(proof["filled_quantity"]) != qty
                        or number(proof["cancelled_quantity"]) != requested - qty):
                    raise ValueError("Independent IOC fill/cancel mismatch")
                positions[ident]["ioc"] = proof
        if ident not in positions:
            raise ValueError("Independent orphan position")
        p = positions[ident]
        if kind != "ENTRY" and (c["position_id"] != ident or type(c["expected_position_revision"]) is not int
                                or c["expected_position_revision"] != p["revision"] or p["remaining"] <= 0):
            raise ValueError("Independent position revision mismatch")
        change = Decimal(0)
        if kind in ("ENTRY", "EXIT"):
            qty = number(c["quantity"])
            buy = (p["side"] == "LONG") == (kind == "ENTRY")
            field = "ask" if buy else "bid"
            price = number(e[field])
            if maker: price = number(e["maker_execution"]["limit_price"])
            if (not 0 < qty <= p["remaining"] or clock % 3600 == 0
                    or (kind == "EXIT" and p["next_funding"] <= clock)):
                raise ValueError("Independent quantity/funding ordering mismatch")
            key = digest([p["symbol"], e["sequence"], field])
            capacity = number(e[field + "_size"]) * number(m["perp_policy"]["participation"])
            if maker:
                proof = e["maker_execution"]
                key = digest([p["symbol"], "MAKER_TRADE", proof["source_ref"]])
                capacity = (number(proof["traded_quantity"]) - number(proof["queue_ahead"])) * number(m["perp_policy"]["participation"])
                if proof["order_id"] in maker_orders or qty != number(proof["filled_quantity"]) or number(proof["requested_quantity"]) != qty + number(proof["cancelled_quantity"]):
                    raise ValueError("Independent maker order/fill mismatch")
                maker_orders[proof["order_id"]] = digest(c)
            used = liquidity.get(key, {"digest": digest(e), "quantity": "0"})
            total = number(used["quantity"]) + qty
            if used["digest"] != digest(e) or total > capacity:
                raise ValueError("Independent reused liquidity")
            liquidity[key] = {"digest": digest(e), "quantity": str(total)}
            f = qty * price * number(m["perp_policy"]["maker_bps"] if maker else m["perp_policy"]["taker_bps"]) / 10000
            if c["schema"] == "PAPER_PERP_LIQUIDATION_V1":
                proof = e["liquidation"]
                trigger = number(proof["trigger_mark"])
                observed_equity = p["margin"] + p["remaining_funding"] + (trigger - p["entry"]) * p["remaining"] * (1 if p["side"] == "LONG" else -1)
                required = _audit_maintenance(m, {**p, "mark": trigger})
                if number(proof["maintenance"]) != required or number(proof["equity"]) != observed_equity or observed_equity > required:
                    raise ValueError("Independent liquidation trigger mismatch")
                penalty = qty * price * number(proof["fee_bps"]) / 10000
                f += penalty
                liquidation_fees += penalty
                p["liquidation_fees"] = p.get("liquidation_fees", Decimal(0)) + penalty
            sl = qty * price * number(m["perp_policy"]["slippage_bps"]) / 10000
            gain = Decimal(0)
            if kind == "EXIT":
                gain = (price - p["entry"]) * qty * (1 if p["side"] == "LONG" else -1)
                p["margin"] -= p["margin"] if qty == p["remaining"] else qty * p.get("margin_basis_price", p["entry"]) / p["leverage"]
                p["remaining_funding"] = Decimal(0) if qty == p["remaining"] else p["remaining_funding"] * (p["remaining"] - qty) / p["remaining"]
                p["remaining"] -= qty
            change = gain - f - sl
            gross += gain
            fees += f
            slip += sl
            p["fees"] += f
            p["slippage"] += sl
            p.update(mark=number(e["mark"]), mark_at=clock)
        elif kind == "FUNDING":
            if (e["settlement_at"] != p["next_funding"] or e["interval_seconds"] != 3600
                    or not e["settlement_at"] <= clock or not recovery and clock > e["settlement_at"] + 30):
                raise ValueError("Independent funding cut mismatch")
            if recovery and (number(c["recovery"]["quantity"]) != p["remaining"]
                             or c["recovery"]["evidence_digest"] != digest(e)
                             or c["recovery"]["accepted_at"] != clock):
                raise ValueError("Independent recovery quantity/evidence mismatch")
            change = p["remaining"] * number(e["oracle"]) * number(e["rate"]) * (-1 if p["side"] == "LONG" else 1)
            funding_events.append({"position_id": ident, "settlement_at": e["settlement_at"],
                                   "posted_at": clock, "cash": str(change)})
            funding += change
            p["funding"] += change
            p["remaining_funding"] += change
            p["next_funding"] += 3600
        elif kind == "MARK":
            p.update(mark=number(e["mark"]), mark_at=clock)
            if c["schema"] == "PAPER_PERP_MARGIN_MARK_V1": p["margin_policy"] = e["margin_policy"]
        else:
            raise ValueError("Independent unknown perpetual event")
        p["revision"] += 1
        p["net"] += change
        cash += change
        risk_ratio += Fraction(change) / Fraction(p["risk"] * p["quantity"])
        if r["position_revision"] != p["revision"]:
            raise ValueError("Independent perpetual receipt revision mismatch")
    margin = sum((p["margin"] for p in positions.values()), Decimal(0))
    with localcontext() as display:
        display.traps[Inexact] = False
        net_r = Decimal(risk_ratio.numerator) / Decimal(risk_ratio.denominator)
    expected = {"cash": cash, "gross": gross, "fees": fees, "slippage": slip, "costs": fees + slip,
                    "funding": funding, "net": gross + funding - fees - slip, "net_r": net_r,
                    "reserved_margin": margin, "available_cash": cash - margin}
    if any("liquidation_fees" in p for p in positions.values()): expected["liquidation_fees"] = liquidation_fees
    if snapshot is None:
        # Reporting auditor consumes independently derived facts, never the
        # transition state or a report's asserted balances.
        return {"totals": expected, "positions": positions, "funding_events": funding_events}
    if snapshot.get("maker_orders", {}) != maker_orders:
        raise ValueError("Independent maker order inventory mismatch")
    if (snapshot["net_r_fraction"] != {"numerator": str(risk_ratio.numerator), "denominator": str(risk_ratio.denominator)}
            or snapshot["net_r_display_only"] is not True):
        raise ValueError("Independent exact risk fraction mismatch")
    if (type(snapshot["revision"]) is not int or snapshot["revision"] != revision
            or set(snapshot["positions"]) != set(positions) or snapshot["liquidity_consumption"] != liquidity
            or snapshot["last_clock"] != clock or any(number(snapshot[k]) != v for k, v in expected.items())):
        raise ValueError("Independent perpetual cash/margin/source conservation mismatch")
    live = [p for p in positions.values() if p["remaining"] > 0]
    current = all(p["mark_at"] == clock for p in live)
    unrealized = sum(((p["mark"] - p["entry"]) * p["remaining"] * (1 if p["side"] == "LONG" else -1) for p in live), Decimal(0))
    maintenance = sum((_audit_maintenance(m, p) for p in live), Decimal(0))
    values = {"unrealized": unrealized, "maintenance_margin": maintenance, "margin_equity": cash + unrealized}
    if any((snapshot[k] is not None if not current else number(snapshot[k]) != v) for k, v in values.items()):
        raise ValueError("Independent perpetual valuation mismatch")
    warning = any(p["margin"] + p["remaining_funding"] + (p["mark"] - p["entry"]) * p["remaining"] * (1 if p["side"] == "LONG" else -1)
                  <= _audit_maintenance(m, p) for p in live)
    if (snapshot["margin_warning"] is not (warning if current else None)
            or snapshot["valuation_state"] != ("CURRENT_SYNTHETIC_MARK" if current else "UNAVAILABLE")):
        raise ValueError("Independent margin warning mismatch")
    for ident, p in positions.items():
        actual = snapshot["positions"][ident]
        if actual.get("margin_policy") != p.get("margin_policy"):
            raise ValueError("Independent margin policy substitution")
        if actual.get("ioc") != p.get("ioc"):
            raise ValueError("Independent IOC remainder substitution")
        if ("margin_basis_price" in p) != ("margin_basis_price" in actual) or "margin_basis_price" in p and number(actual["margin_basis_price"]) != p["margin_basis_price"]:
            raise ValueError("Independent initial margin basis mismatch")
        if ("liquidation_fees" in p) != ("liquidation_fees" in actual) or "liquidation_fees" in p and number(actual["liquidation_fees"]) != p["liquidation_fees"]:
            raise ValueError("Independent liquidation fee mismatch")
        fields = {"quantity": p["quantity"], "remaining": p["remaining"], "entry": p["entry"], "margin": p["margin"],
                      "leverage": p["leverage"], "entry_notional": p["quantity"] * p["entry"], "risk_price": p["risk"],
                      "realized_net": p["net"], "funding": p["funding"], "remaining_funding": p["remaining_funding"], "fees": p["fees"], "slippage": p["slippage"], "mark": p["mark"]}
        if (any(number(actual[k]) != v for k, v in fields.items())
                or any(type(actual[k]) is not int for k in ("revision", "next_funding", "mark_at"))
                or actual["revision"] != p["revision"]
                or actual["next_funding"] != p["next_funding"] or actual["mark_at"] != p["mark_at"]
                or actual["side"] != p["side"] or actual["symbol"] != p["symbol"] or actual["origin_ref"] != p["origin"]):
            raise ValueError("Independent perpetual position conservation mismatch")
        fresh = p["remaining"] == 0 or p["mark_at"] == clock
        gain = (p["mark"] - p["entry"]) * p["remaining"] * (1 if p["side"] == "LONG" else -1)
        values = {"marked_notional": p["mark"] * p["remaining"],
                  "margin_equity": p["margin"] + p["remaining_funding"] + gain,
                  "maintenance_margin": _audit_maintenance(m, p)}
        if any((actual[k] is not None if not fresh else number(actual[k]) != v) for k, v in values.items()):
            raise ValueError("Independent position mark/risk mismatch")
    return {"schema": "PAPER_PERP_ARITHMETIC_AUDIT_V2", "source_revision": revision, "position_count": len(positions),
                "projection_required": required, "production_authorized": False, "startup_authorized": False}


def _audit(manifest, records, snapshot, *, record_schema="PAPER_EVENT_STREAM_RECORD_V1"):
    autonomous = manifest.get("schema") == "PAPER_EPOCH_AUTONOMOUS_QD_V1"
    consumed = {}
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
            if autonomous:
                entry_cost = qty * price * (number(manifest["fees_bps"]) + number(manifest["slippage_bps"])) / 10000
                cash -= entry_cost
                positions[ident].update(entry_costs=entry_cost, remaining_entry_costs=entry_cost)
        elif c["kind"] == "EXIT":
            p = positions.get(ident)
            if (p is None or c["position_id"] != ident or c["expected_position_revision"] != p["revision"]
                    or c["quote"]["symbol"] != p["symbol"] or qty > p["remaining"]):
                raise ValueError("Independent orphan/over-close/revision mismatch")
            p["remaining"] -= qty
            p["revision"] += 1
            gain = (price - p["entry"]) * qty * (1 if p["side"] == "LONG" else -1)
            cost = p["entry"] * qty * (number(manifest["fees_bps"]) + number(manifest["slippage_bps"])) / 5000
            if autonomous:
                allocated = p["remaining_entry_costs"] if p["remaining"] == 0 else p["entry_costs"] * qty / p["quantity"]
                exit_cost = price * qty * (number(manifest["fees_bps"]) + number(manifest["slippage_bps"])) / 10000
                cost = allocated + exit_cost
                p["remaining_entry_costs"] -= allocated
            gross, costs = gross + gain, costs + cost
            p["net"] += gain - cost
            cash += price * qty - (exit_cost if autonomous else cost) if spot else gain - cost
            if p["risk_price"] is not None:
                net_r += (gain - cost) / (number(p["risk_price"]) * p["quantity"])
        else:
            raise ValueError("Unknown financial event")
        if autonomous:
            packet = c["evidence"]["l1"]; key = digest([packet["provider_id"], packet["feed_id"], packet["instrument_id"], packet["sequence"], c["kind"]])
            prior = consumed.get(key, {"quantity": "0", "packet_digest": digest(packet)})
            if prior["packet_digest"] != digest(packet):
                raise ValueError("Independent quote sequence conflict")
            total = number(prior["quantity"]) + qty
            size = number(packet["ask_size" if c["kind"] == "ENTRY" else "bid_size"])
            if total > size * number(manifest["autonomous_policy"]["participation"]):
                raise ValueError("Independent reused liquidity")
            consumed[key] = {"quantity": str(total), "packet_digest": digest(packet)}
        if receipt["position_revision"] != positions[ident]["revision"]:
            raise ValueError("Independent receipt position revision mismatch")
    if (type(snapshot["revision"]) is not int or set(positions) != set(snapshot["positions"]) or revision != snapshot["revision"]
            or cash != number(snapshot["cash"]) or gross != number(snapshot["gross"])
            or costs != number(snapshot["costs"]) or gross - costs != number(snapshot["net"])
            or net_r != number(snapshot["net_r"])):
        raise ValueError("Independent cash/inventory/revision reconciliation mismatch")
    if autonomous and snapshot["l1_consumption"] != consumed:
        raise ValueError("Independent liquidity inventory mismatch")
    for ident, p in positions.items():
        s = snapshot["positions"][ident]
        if autonomous and any(p[k] != number(s[k]) for k in ("entry_costs", "remaining_entry_costs")):
            raise ValueError("Independent deferred entry cost mismatch")
        if (any(p[k] != number(s[k]) for k in ("quantity", "remaining", "entry"))
                or type(s["revision"]) is not int or p["net"] != number(s["realized_net"]) or p["revision"] != s["revision"]
                or p["symbol"] != s["symbol"] or p["side"] != s["side"]):
            raise ValueError("Independent position reconciliation mismatch")
    return {"schema": "PAPER_ARITHMETIC_AUDIT_V1", "source_revision": revision,
            "position_count": len(positions), "projection_required": projection_required,
            "production_authorized": False, "startup_authorized": False}
