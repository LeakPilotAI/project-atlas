"""FS3 pure deterministic daily reports; source authentication is caller-owned.

The report auditor independently derives daily arithmetic without invoking the
financial transition/replay or the report builder. No stores/services/providers.
"""
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, Inexact, localcontext
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
    restatement = type(scope) is dict and scope.get("schema") in ("FS3_PERP_REPORT_SCOPE_V2", "FS3_PERP_REPORT_SCOPE_V3")
    session = type(scope) is dict and scope.get("schema") == "FS3_PERP_REPORT_SCOPE_V3"
    qd_session = type(scope) is dict and scope.get('schema') == 'FS3_QD_REPORT_SCOPE_V2'
    extra = {"funding_reporting_policy"} if restatement else set()
    if session or qd_session:
        extra.add("session_reporting_policy")
    if (type(scope) is not dict or set(scope) != {"schema", "account_id", "epoch", "policy_digest", "timezone"} | extra
            or scope["schema"] not in ("FS3_REPORT_SCOPE_V1", "FS3_PERP_REPORT_SCOPE_V2", "FS3_PERP_REPORT_SCOPE_V3", 'FS3_QD_REPORT_SCOPE_V2')
            or (session or qd_session) and scope["session_reporting_policy"] != "ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1"
            or qd_session and manifest['schema'] != 'PAPER_EPOCH_AUTONOMOUS_QD_V1'
            or restatement and (manifest["schema"] not in ("PAPER_EPOCH_PERP_FIXTURE_V2", "PAPER_EPOCH_PERP_OPERATIONAL_V1")
                                or scope["funding_reporting_policy"] != "POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1")
            or type(scope["account_id"]) is not str
            or not 1 <= len(scope["account_id"]) <= 96 or scope["epoch"] != manifest["epoch"]
            or scope["policy_digest"] != digest(manifest) or scope["timezone"] != manifest["timezone"]
            or (manifest["strategy"] == "QUALITY_DIPS" and scope["timezone"] != "America/New_York")):
        raise ValueError("Exact account/epoch/policy/calendar scope required")
    ZoneInfo(scope["timezone"])


def frame(scope, manifest, pin, rows, head, day, observed, *, session=None):
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
    result = {**({"funding_reporting_policy": scope["funding_reporting_policy"], "scope_digest": digest(scope)}
               if scope["schema"] in ("FS3_PERP_REPORT_SCOPE_V2", "FS3_PERP_REPORT_SCOPE_V3") else {}),
            **({"session_reporting_policy": scope["session_reporting_policy"]} if scope["schema"] == "FS3_PERP_REPORT_SCOPE_V3" else {}),
            "schema": "FS3_DAILY_REPORT_V1", "report_version": 2 if manifest["schema"] == "PAPER_EPOCH_AUTONOMOUS_QD_V1" else 1,
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
    if session is not None:
        if (scope['schema'] != 'FS3_QD_REPORT_SCOPE_V2' or type(session) is not dict
                or set(session) != {'session_id', 'started_at', 'cutoff_at'}
                or type(session['session_id']) is not str or not session['session_id']
                or any(type(session[k]) is not int for k in ('started_at', 'cutoff_at'))
                or not manifest['opened_at'] <= session['started_at'] <= session['cutoff_at'] <= observed <= session['cutoff_at'] + 5):
            raise ValueError('QD_ACCEPTED_CURRENT_SESSION_SCOPE_REQUIRED')
        cutoff = session['cutoff_at']
        if day != datetime.fromtimestamp(cutoff, zone).date().isoformat():
            raise ValueError('QD_SESSION_CALENDAR_IDENTITY_MISMATCH')
        result.update(schema='FS3_QD_SESSION_REPORT_V1', report_version=1, session=strict(body(session)), session_id=session['session_id'],
                      scope_digest=digest(scope), session_reporting_policy=scope['session_reporting_policy'],
                      period={'kind': 'SESSION_CUT', 'start': session['started_at'], 'cutoff_inclusive': cutoff,
                              'end_exclusive': cutoff + 1, 'effective_end_exclusive': cutoff + 1},
                      status='COMPLETE' if all(strict(r['command'])['timestamp'] <= cutoff for r in rows) else 'INCOMPLETE',
                      reasons=[] if all(strict(r['command'])['timestamp'] <= cutoff for r in rows) else ['SOURCE_ADVANCED_BEYOND_CUTOFF'])
        result['source']['cutoff_revision'] = sum(strict(r['command'])['timestamp'] <= cutoff for r in rows)
        if any(strict(r['receipt']).get('projection_required') is not True for r in rows):
            result['status'] = 'INCOMPLETE'
            result['reasons'].append('PROJECTION_ACK_REQUIRED')
    return result


def build_daily_report(scope, manifest, pin, rows, day, observed, *, session=None):
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        full, head, _ = replay_verified_events(manifest, rows)
        audit_financial_events(manifest, rows, full)
        report = frame(scope, manifest, pin, rows, head, day, observed, session=session)
        if manifest["schema"] in ("PAPER_EPOCH_PERP_FIXTURE_V2", "PAPER_EPOCH_PERP_OPERATIONAL_V1"):
            with localcontext() as context:
                context.traps[Inexact] = True
                try:
                    return _build_perp_report(report, scope, manifest, pin, rows, full)
                except Inexact as exc:
                    raise ValueError("Perpetual reporting precision refusal") from exc
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
        if manifest["schema"] in ("PAPER_EPOCH_PERP_FIXTURE_V2", "PAPER_EPOCH_PERP_OPERATIONAL_V1"):
            with localcontext() as context:
                context.traps[Inexact] = True
                try:
                    return _audit_perp_report(report, scope, manifest, pin, rows)
                except Inexact as exc:
                    raise ValueError("Independent perpetual report precision refusal") from exc
        parent = digest(manifest)
        for row in rows:
            command, receipt = strict(row["command"]), strict(row["receipt"])
            if row["parent"] != parent or row["digest"] != digest([parent, command, receipt]):
                raise ValueError("Independent source chain mismatch")
            parent = row["digest"]
        metadata = frame(scope, manifest, pin, rows, parent, report["date"], report["observed_at"],
                         session=report.get('session') if report.get('schema') == 'FS3_QD_SESSION_REPORT_V1' else None)
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


def _perp_inventory(positions):
    return {key: {"symbol": p["symbol"], "side": p["side"],
                  "quantity": str(p["quantity"]), "remaining": str(p["remaining"]),
                  "entry": str(p["entry"]), "margin": str(p["margin"]),
                  "remaining_funding": str(p["remaining_funding"]),
                  "next_funding": p["next_funding"]}
            for key, p in positions.items() if number(str(p["remaining"])) > 0}


def _perp_metadata(report, positions):
    report.update(report_version=3, cost_allocation="PERP_SIDE_CASH_COST_V2",
                  collateral_model="INITIAL_RESERVE_CASH_SETTLED_FUNDING_V2")
    if any(p["next_funding"] < report["period"]["effective_end_exclusive"] for p in positions.values()):
        report["status"] = "INCOMPLETE"
        report["reasons"] = [*report["reasons"], "FUNDING_HISTORY_INCOMPLETE"]
    return report


def _perp_recovery_reporting(report, rows, *, facts=None, manifest=None):
    postings = []
    zone = ZoneInfo(report["timezone"])
    restatement = False
    for row in rows:
        c = strict(row["command"])
        if c["schema"] != "PAPER_PERP_FUNDING_RECOVERY_V1":
            continue
        e = c["evidence"]
        settled = datetime.fromtimestamp(e["settlement_at"], zone).date().isoformat()
        posted = datetime.fromtimestamp(c["timestamp"], zone).date().isoformat()
        if report["date"] not in (settled, posted):
            continue
        postings.append({"operation_id": c["operation_id"], "settlement_at": e["settlement_at"],
                         "posted_at": c["timestamp"], "quantity": c["recovery"]["quantity"],
                         "oracle": e["oracle"], "rate": e["rate"], "source_id": e["source_id"],
                         "authority_ref": c["recovery"]["authority_ref"]})
        restatement |= settled != posted
    if postings:
        report.update(funding_postings=postings, funding_reporting_basis="POSTED_CASH_NOT_RESTATED_SETTLEMENT")
    if report.get("funding_reporting_policy") == "POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1":
        if facts is None:
            from app.services.paper_financial_replay import apply_event, initial_state
            state, facts = initial_state(manifest), []
            for row in rows:
                c = strict(row["command"])
                before = number(state["funding"])
                state, receipt = apply_event(manifest, state, c)
                if c["kind"] == "FUNDING":
                    facts.append({"position_id": receipt["position_id"], "settlement_at": c["evidence"]["settlement_at"],
                                  "posted_at": c["timestamp"], "cash": str(number(state["funding"]) - before)})
        report["report_version"] = 4
        start, end = report["period"]["start"], report["period"]["effective_end_exclusive"]
        settled = sum((number(f["cash"]) for f in facts if start <= f["settlement_at"] < end), Decimal(0))
        unpaid = {}
        for f in facts:
            if f["settlement_at"] < end <= f["posted_at"]:
                unpaid[f["position_id"]] = str(number(unpaid.get(f["position_id"], "0")) + number(f["cash"]))
        report["funding_accrual"] = {"settled_in_period": str(settled), "unposted_at_cutoff": unpaid,
                                     "basis": "SETTLEMENT_TIME_SEPARATE_FROM_POSTED_CASH"}
        covered = {(f["position_id"], f["settlement_at"]) for f in facts}
        complete = all(all((ident, at) in covered for at in range(p["next_funding"], end, 3600))
                       for ident, p in report["open_positions"].items())
        if complete:
            report["reasons"] = [r for r in report["reasons"] if r != "FUNDING_HISTORY_INCOMPLETE"]
            report["status"] = "INCOMPLETE" if report["reasons"] else "COMPLETE"
    elif restatement:
        report["status"] = "INCOMPLETE"
        report["reasons"] = [*report["reasons"], "RECOVERY_RESTATEMENT_REQUIRED"]
    if any(strict(row["command"])["schema"] == "PAPER_PERP_LIQUIDATION_V1" for row in rows):
        report["report_version"] = 5
    return report


def _build_perp_report(report, scope, m, pin, rows, full):
    start, end = report["period"]["start"], report["period"]["effective_end_exclusive"]
    before_rows = [r for r in rows if strict(r["command"])["timestamp"] < start]
    through_rows = [r for r in rows if strict(r["command"])["timestamp"] < end]
    before = replay_verified_events(m, before_rows)[0]
    after = replay_verified_events(m, through_rows)[0]
    inventory = _perp_inventory(after["positions"])
    report = _perp_metadata(report, inventory)
    commands = [strict(r["command"]) for r in through_rows if strict(r["command"])["timestamp"] >= start]
    report.update(cash={"opening": before["cash"], "closing": after["cash"]},
                  realized={k: str(number(after[k]) - number(before[k])) for k in ("gross", "fees", "slippage", "costs", "funding", "net")},
                  counts={k: sum(c["kind"] == kind for c in commands) for k, kind in
                          (("entries", "ENTRY"), ("exits", "EXIT"), ("funding", "FUNDING"), ("marks", "MARK"))},
                  open_positions=inventory,
                  collateral={"opening_reserved": before["reserved_margin"], "closing_reserved": after["reserved_margin"],
                              "opening_available": before["available_cash"], "closing_available": after["available_cash"]})
    if any(strict(row["command"])["schema"] == "PAPER_PERP_LIQUIDATION_V1" for row in rows):
        report["realized"]["liquidation_fees"] = str(number(after.get("liquidation_fees", "0")) - number(before.get("liquidation_fees", "0")))
    report = _perp_recovery_reporting(report, rows, manifest=m)
    audit_daily_report(report, scope, m, pin, rows, full)
    return report


def _audit_perp_report(report, scope, m, pin, rows):
    from app.services.paper_financial_audit import _audit_perp

    parent = digest(m)
    for row in rows:
        c, r = strict(row["command"]), strict(row["receipt"])
        if row["parent"] != parent or row["digest"] != digest([parent, c, r]):
            raise ValueError("Independent perpetual report source mismatch")
        parent = row["digest"]
    metadata = frame(scope, m, pin, rows, parent, report["date"], report["observed_at"])
    start, end = metadata["period"]["start"], metadata["period"]["effective_end_exclusive"]
    before = _audit_perp(m, [r for r in rows if strict(r["command"])["timestamp"] < start], None)
    through = [r for r in rows if strict(r["command"])["timestamp"] < end]
    after = _audit_perp(m, through, None)
    inventory = _perp_inventory(after["positions"])
    metadata = _perp_metadata(metadata, inventory)
    commands = [strict(r["command"]) for r in through if strict(r["command"])["timestamp"] >= start]
    expected = {"cash": {"opening": before["totals"]["cash"], "closing": after["totals"]["cash"]},
                "realized": {k: after["totals"][k] - before["totals"][k] for k in ("gross", "fees", "slippage", "costs", "funding", "net")},
                "collateral": {"opening_reserved": before["totals"]["reserved_margin"], "closing_reserved": after["totals"]["reserved_margin"],
                               "opening_available": before["totals"]["available_cash"], "closing_available": after["totals"]["available_cash"]}}
    if any(strict(row["command"])["schema"] == "PAPER_PERP_LIQUIDATION_V1" for row in rows):
        expected["realized"]["liquidation_fees"] = after["totals"].get("liquidation_fees", Decimal(0)) - before["totals"].get("liquidation_fees", Decimal(0))
    metadata["open_positions"] = inventory
    full_facts = _audit_perp(m, rows, None)["funding_events"]
    metadata = _perp_recovery_reporting(metadata, rows, facts=full_facts)
    metadata.pop("open_positions")
    counts = {k: sum(c["kind"] == kind for c in commands) for k, kind in
              (("entries", "ENTRY"), ("exits", "EXIT"), ("funding", "FUNDING"), ("marks", "MARK"))}
    if (any(body(report.get(k)) != body(v) for k, v in metadata.items())
            or set(report) != set(metadata) | set(expected) | {"counts", "open_positions"}
            or body(report["counts"]) != body(counts) or body(report["open_positions"]) != body(inventory)):
        raise ValueError("Independent perpetual report inventory/schema mismatch")
    for group, values in expected.items():
        if set(report[group]) != set(values) or any(number(report[group][k]) != value for k, value in values.items()):
            raise ValueError("Independent perpetual daily conservation mismatch")
    return {"schema": "FS3_PERP_DAILY_AUDIT_V2", "financially_consistent": True, "operational_acceptance": False}
