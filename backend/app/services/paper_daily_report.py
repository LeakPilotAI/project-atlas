"""FS3 pure deterministic daily reports; source authentication is caller-owned.

The report auditor independently derives daily arithmetic without invoking the
financial transition/replay or the report builder. No stores/services/providers.
"""
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from zoneinfo import ZoneInfo

from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    body,
    digest,
    number,
    replay_verified_events,
    strict,
    validate_manifest,
)


def validate_scope(scope, manifest):
    validate_manifest(manifest)
    if (type(scope) is not dict or set(scope) != {"schema", "account_id", "epoch", "policy_digest", "timezone"}
            or scope["schema"] != "FS3_REPORT_SCOPE_V1" or type(scope["account_id"]) is not str
            or not 1 <= len(scope["account_id"]) <= 96 or scope["epoch"] != manifest["epoch"]
            or scope["policy_digest"] != digest(manifest) or scope["timezone"] != manifest["timezone"]
            or (manifest["strategy"] == "QUALITY_DIPS" and scope["timezone"] != "America/New_York")):
        raise ValueError("Exact account/epoch/policy/calendar scope required")
    ZoneInfo(scope["timezone"])


def frame(scope, manifest, pin, rows, head, day, observed):
    validate_scope(scope, manifest)
    if type(observed) is not int or observed <= 0 or type(day) is not str:
        raise ValueError("Exact report observation clock/date required")
    local = date.fromisoformat(day)
    if local.isoformat() != day:
        raise ValueError("Canonical reporting date required")
    zone = ZoneInfo(scope["timezone"])
    start = int(datetime.combine(local, time(), zone).timestamp())
    end = int(datetime.combine(local + timedelta(days=1), time(), zone).timestamp())
    effective = min(observed, end)
    if effective <= max(start, manifest["opened_at"]):
        raise ValueError("No report period after authenticated inception")
    if (pin["epoch"] != manifest["epoch"] or len(pin["entries"]) != len(rows)
            or any(strict(r["command"])["timestamp"] > observed for r in rows)):
        raise ValueError("Source count/epoch or future-information mismatch")
    required = sum(strict(r["receipt"])["projection_required"] for r in rows)
    return {"schema": "FS3_DAILY_REPORT_V1", "report_version": 2 if manifest["schema"] == "PAPER_EPOCH_AUTONOMOUS_QD_V1" else 1,
            "account_id": scope["account_id"], "epoch": scope["epoch"], "policy_digest": scope["policy_digest"],
            "strategy": manifest["strategy"], "currency": manifest["currency"],
            "cost_policy": manifest["cost_policy"], "cost_allocation": "QD_AUTO_SIDE_COST_ALLOCATION_V1" if manifest["schema"] == "PAPER_EPOCH_AUTONOMOUS_QD_V1" else "FS3_FEE_FIRST_REMAINDER_SLIPPAGE_V1", "timezone": scope["timezone"], "date": day,
            "observed_at": observed, "period": {"start": start, "end_exclusive": end,
            "effective_end_exclusive": effective, "inception": manifest["opened_at"],
            "coverage_start": max(start, manifest["opened_at"]), "cash_opening_at": max(start, manifest["opened_at"])},
            "source": {"root": pin["root"], "inception": pin["inception"], "revision": len(rows),
                       "head": head, "record_lineage": pin["entries"],
                       "cutoff_revision": sum(strict(r["command"])["timestamp"] < effective for r in rows)},
            "status": "COMPLETE" if observed >= end else "INCOMPLETE",
            "reasons": [] if observed >= end else ["CUTOFF_NOT_REACHED"],
            "projection_status": "FULLY_ACKNOWLEDGED" if required else "NOT_REQUIRED",
            "projection_counts": {"required": required, "acknowledged": required, "not_required": len(rows) - required},
            "operation_status": "FULLY_ACKNOWLEDGED", "valuation": None,
            "valuation_status": "UNAVAILABLE", "lifecycle_status": "NOT_EVALUATED",
            "startup_authorized": False, "production_authorized": False}


def build_daily_report(scope, manifest, pin, rows, day, observed):
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        full, head, _ = replay_verified_events(manifest, rows)
        audit_financial_events(manifest, rows, full)
        report = frame(scope, manifest, pin, rows, head, day, observed)
        start, end = report["period"]["start"], report["period"]["effective_end_exclusive"]
        before_rows = [r for r in rows if strict(r["command"])["timestamp"] < start]
        through_rows = [r for r in rows if strict(r["command"])["timestamp"] < end]
        before, _, _ = replay_verified_events(manifest, before_rows)
        after, _, _ = replay_verified_events(manifest, through_rows)
        audit_financial_events(manifest, before_rows, before)
        audit_financial_events(manifest, through_rows, after)
        totals = {k: str(number(after[k]) - number(before[k])) for k in ("gross", "costs", "net")}
        fee, slip, counts = Decimal(0), Decimal(0), {"entries": 0, "exits": 0}
        for row in through_rows:
            command, receipt = strict(row["command"]), strict(row["receipt"])
            if command["timestamp"] < start:
                continue
            if command["kind"] == "ENTRY":
                counts["entries"] += 1
            else:
                counts["exits"] += 1
                entry = number(after["positions"][receipt["position_id"]]["entry"])
                qty = number(command["quantity"])
                allocated_fee = 2 * entry * qty * number(manifest["fees_bps"]) / 10000
                allocated_cost = 2 * entry * qty * (number(manifest["fees_bps"]) + number(manifest["slippage_bps"])) / 10000
                if manifest["schema"] == "PAPER_EPOCH_AUTONOMOUS_QD_V1":
                    # Receipt-bound replay determines deferred entry allocation exactly.
                    prefix = through_rows[:through_rows.index(row)]
                    prior, _, _ = replay_verified_events(manifest, prefix)
                    current, _, _ = replay_verified_events(manifest, [*prefix, row])
                    allocated_cost = number(current["costs"]) - number(prior["costs"])
                    allocated_fee = allocated_cost * number(manifest["fees_bps"]) / (number(manifest["fees_bps"]) + number(manifest["slippage_bps"]))
                fee += allocated_fee
                slip += allocated_cost - allocated_fee
        report.update(cash={"opening": before["cash"], "closing": after["cash"]},
                      realized={**totals, "fees": str(fee), "slippage": str(slip)}, counts=counts,
                      open_positions={k: v for k, v in after["positions"].items() if number(v["remaining"]) > 0})
        audit_daily_report(report, scope, manifest, pin, rows, full)
        return report


def audit_daily_report(report, scope, manifest, pin, rows, snapshot):
    """Independent financial/event and day arithmetic. Never calls replay/build."""
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        audit_financial_events(manifest, rows, snapshot)
        parent = digest(manifest)
        for row in rows:
            command, receipt = strict(row["command"]), strict(row["receipt"])
            if row["parent"] != parent or row["digest"] != digest([parent, command, receipt]):
                raise ValueError("Independent source chain mismatch")
            parent = row["digest"]
        metadata = frame(scope, manifest, pin, rows, parent, report["date"], report["observed_at"])
        if (type(report.get("report_version")) is not int or type(report["source"]["revision"]) is not int
                or any(body(report.get(k)) != body(v) for k, v in metadata.items())):
            raise ValueError("Report metadata/source/cutoff mismatch")
        start, end = metadata["period"]["start"], metadata["period"]["effective_end_exclusive"]
        cash, opening = number(manifest["opening_cash"]), number(manifest["opening_cash"])
        autonomous = manifest["schema"] == "PAPER_EPOCH_AUTONOMOUS_QD_V1"
        positions, seen = {}, set()
        gross = fees = slippage = costs = net = Decimal(0)
        counts = {"entries": 0, "exits": 0}
        for row in rows:
            c, receipt = strict(row["command"]), strict(row["receipt"])
            if c["operation_id"] in seen:
                raise ValueError("Duplicate financial operation")
            seen.add(c["operation_id"])
            if c["timestamp"] >= end:
                continue
            qty, price, ident = number(c["quantity"]), number(c["quote"]["price"]), receipt["position_id"]
            within = c["timestamp"] >= start
            if c["kind"] == "ENTRY":
                positions[ident] = {"symbol": c["symbol"], "side": c["side"], "entry": str(price),
                    "quantity": str(qty), "remaining": str(qty), "risk_price": c["risk_price"],
                    "revision": 1, "origin_ref": c["origin_ref"], "realized_net": "0"}
                if manifest["strategy"] == "QUALITY_DIPS":
                    cash -= price * qty
                if autonomous:
                    entry_cost = price * qty * (number(manifest["fees_bps"]) + number(manifest["slippage_bps"])) / 10000
                    cash -= entry_cost
                    positions[ident].update(entry_costs=str(entry_cost), remaining_entry_costs=str(entry_cost),
                        entry_snapshot=c["evidence"]["entry_snapshot"], instrument=c["evidence"]["instrument"])
                if within: counts["entries"] += 1
            else:
                p = positions[ident]
                entry = number(p["entry"])
                gain = (price - entry) * qty * (1 if p["side"] == "LONG" else -1)
                fee = 2 * entry * qty * number(manifest["fees_bps"]) / 10000
                cost = 2 * entry * qty * (number(manifest["fees_bps"]) + number(manifest["slippage_bps"])) / 10000
                if autonomous:
                    allocation = number(p["remaining_entry_costs"]) if qty == number(p["remaining"]) else number(p["entry_costs"]) * qty / number(p["quantity"])
                    exit_cost = price * qty * (number(manifest["fees_bps"]) + number(manifest["slippage_bps"])) / 10000
                    cost = allocation + exit_cost
                    fee = cost * number(manifest["fees_bps"]) / (number(manifest["fees_bps"]) + number(manifest["slippage_bps"]))
                    p["remaining_entry_costs"] = str(number(p["remaining_entry_costs"]) - allocation)
                slip = cost - fee
                realized = gain - cost
                p.update(remaining=str(number(p["remaining"]) - qty), revision=p["revision"] + 1,
                         realized_net=str(number(p["realized_net"]) + realized))
                cash += price * qty - (exit_cost if autonomous else cost) if manifest["strategy"] == "QUALITY_DIPS" else realized
                if within:
                    counts["exits"] += 1
                    gross += gain
                    fees += fee
                    slippage += slip
                    costs += cost
                    net += realized
            if not within: opening = cash
        expected = {"cash": {"opening": str(opening), "closing": str(cash)},
                    "realized": {"gross": str(gross), "fees": str(fees), "slippage": str(slippage),
                                 "costs": str(costs), "net": str(net)}, "counts": counts,
                    "open_positions": {k: v for k, v in positions.items() if number(v["remaining"]) > 0}}
        # Decimal strings may legitimately retain different trailing zero scales
        # across subtraction. Compare exact finite Decimal values for money only.
        for group in ("cash", "realized"):
            if set(report[group]) != set(expected[group]) or any(number(report[group][k]) != number(v) for k, v in expected[group].items()):
                raise ValueError("Independent daily cash/cost/P&L mismatch")
        if (body(report["counts"]) != body(counts) or body(report["open_positions"]) != body(expected["open_positions"])
                or set(report) != set(metadata) | set(expected)):
            raise ValueError("Independent daily position/count/schema mismatch")
        return {"schema": "FS3_DAILY_AUDIT_V1", "source_revision": len(rows), "financially_consistent": True,
                "operational_acceptance": False}
