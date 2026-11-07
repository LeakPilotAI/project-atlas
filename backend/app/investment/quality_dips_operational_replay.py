"""Read-only operational replay. No store, writer, test-schema conversion or issuer."""
import copy
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Context, Inexact, localcontext
from zoneinfo import ZoneInfo

from app.investment.quality_dips_operational_contract import exact, positive, validate_enrollment
from app.services.paper_financial_audit import _audit
from app.services.paper_financial_replay import _transition_in_place, body, digest, number, text


def parameters(enrollment):
    validate_enrollment(enrollment)
    # Arithmetic parameters only, not a re-labeled financial manifest.
    return {"epoch": enrollment["account"]["epoch"], "strategy": "QUALITY_DIPS", "fees_bps": "2",
            "slippage_bps": "2", "initial_net_r": "0", "opening_cash": "1000"}


def initial():
    # No inception timestamp is asserted by ACCOUNT_V1. last_clock is a replay
    # ordering sentinel, not an authenticated account creation date.
    return {"positions": {}, "cash": "1000", "gross": "0", "costs": "0", "net": "0",
            "net_r": "0", "revision": 0, "last_clock": 0}


def transition(enrollment, state, command):
    """Pure existing arithmetic kernel; not a financial command dispatcher."""
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as ctx:
        ctx.traps[Inexact] = True
        return _transition_checked(enrollment, state, command)


def _transition_checked(enrollment, state, command):
    m = parameters(enrollment)
    c = copy.deepcopy(command)
    original = body(c)
    if c.get("kind") == "ENTRY":
        evidence = c.pop("eligibility", None)
        exact(evidence, "QD_OP_EXECUTION_EVIDENCE_V1", {"instrument_id", "symbol", "asset_class",
              "fractional_supported", "ranked_at", "ranking_revision", "execution_eligible"})
        text(evidence["instrument_id"])
        positive(evidence["ranking_revision"])
        if (evidence["symbol"] != c["symbol"] or evidence["asset_class"] not in ("STOCK", "ETF")
                or evidence["execution_eligible"] is not True or type(evidence["fractional_supported"]) is not bool
                or type(evidence["ranked_at"]) is not int or not 0 <= c["timestamp"] - evidence["ranked_at"] <= 30
                or (not evidence["fractional_supported"] and number(c["quantity"]) % 1)
                or number(c["quantity"]) * number(c["quote"]["price"]) > 100
                or any(number(p["remaining"]) > 0 for p in state["positions"].values())):
            raise ValueError("OPERATIONAL_ENTRY_POLICY_MISMATCH")
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as ctx:
        ctx.traps[Inexact] = True
        candidate = copy.deepcopy(state)
        receipt = _transition_in_place(m, candidate, c, command_schema="QD_OP_COMMAND_V1",
                                        receipt_schema="QD_OP_RECEIPT_V1")
    receipt.update(payload_digest=digest(command), projection_required=True)
    if original != body(command):
        raise ValueError("INPUT_CHANGED")
    return candidate, receipt


def replay(enrollment, current, records, now):
    """Independent arithmetic audit after every verified immutable operation."""
    m = parameters(enrollment)
    state, rows, snapshots, operations = initial(), [], [initial()], set()
    previous = current["source"]["inception"]
    if len(records) != current["revision"] or len(records) > 128:
        raise ValueError("OPERATIONAL_RECORD_COUNT")
    for revision, record in enumerate(records, 1):
        exact(record, "QD_OP_FINANCIAL_RECORD_V1", {"enrollment_digest", "revision", "operation_id",
              "predecessor", "command", "receipt", "commit", "ack"})
        c = record["command"]
        if (type(record["revision"]) is not int or record["revision"] != revision
                or record["enrollment_digest"] != digest(enrollment) or body(record["predecessor"]) != body(previous)
                or record["operation_id"] != c["operation_id"] or c["operation_id"] in operations
                or type(c["timestamp"]) is not int or c["timestamp"] > now):
            raise ValueError("OPERATIONAL_LINEAGE_OR_DUPLICATE")
        state, receipt = transition(enrollment, state, c)
        commit = {"schema": "QD_OP_COMMIT_V1", "revision": revision,
                  "event_digest": digest([previous, c, receipt])}
        ack = {"schema": "QD_OP_ACK_V1", "commit_digest": digest(commit),
               "projection_state_digest": digest(state), "status": "ACKNOWLEDGED"}
        if body(record["receipt"]) != body(receipt) or body(record["commit"]) != body(commit) or body(record["ack"]) != body(ack):
            raise ValueError("OPERATIONAL_COMMIT_ACK_INCONSISTENT")
        rows.append({"schema": "QD_OP_AUDIT_ROW_V1", "revision": revision, "operation_id": c["operation_id"],
                     "command": body(c), "receipt": body(receipt)})
        with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
            _audit(m, rows, state, record_schema="QD_OP_AUDIT_ROW_V1")
        snapshots.append(copy.deepcopy(state))
        operations.add(c["operation_id"])
        previous = current["source"]["records"][revision - 1]
    return state, snapshots


def history(records, snapshots, cutoff, timezone):
    """Event-day/cutoff-day history; does not invent an inception date or valuation."""
    positive(cutoff)
    if timezone != "America/New_York":
        raise ValueError("QUALITY_DIPS_EXCHANGE_TIMEZONE_REQUIRED")
    zone = ZoneInfo(timezone)
    commands = [r["command"] for r in records]
    days = {datetime.fromtimestamp(cutoff, zone).date()}
    days.update(datetime.fromtimestamp(c["timestamp"], zone).date() for c in commands)
    result = []
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        for day in sorted(days):
            start = int(datetime.combine(day, time(), zone).timestamp())
            end = int(datetime.combine(day + timedelta(days=1), time(), zone).timestamp())
            effective = min(cutoff, end)
            a = sum(c["timestamp"] < start for c in commands)
            b = sum(c["timestamp"] < effective for c in commands)
            before, after = snapshots[a], snapshots[b]
            result.append({"date": day.isoformat(), "start": start, "end_exclusive": end,
                "effective_end_exclusive": effective, "status": "COMPLETE" if cutoff >= end else "INCOMPLETE",
                "opening_cash": before["cash"], "closing_cash": after["cash"],
                "realized": {k: str(number(after[k]) - number(before[k])) for k in ("gross", "costs", "net")},
                "source_revisions": [a, b], "open_positions": {k: v for k, v in after["positions"].items() if number(v["remaining"]) > 0},
                "valuation": None})
    return result
