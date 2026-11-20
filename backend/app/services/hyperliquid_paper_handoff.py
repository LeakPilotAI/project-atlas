"""Pure fixture-only selected-lane handoff; never loads runtime stores or authorizes I/O."""
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from app.services.daily_paper_fixture_adapter import adapt_legacy_rows
from app.services.paper_execution_model import execution_assumptions
from app.services.paper_risk import MAX_CONCURRENT_PAPER, MAX_RISK_USD_PER_TRADE, check_paper_risk


def fixture_scope():
    return {"schema": "HYPERLIQUID_MANUAL_FIXTURE_V1", "symbols": ["BTC", "ETH", "SOL"],
            "initial_cash": "1000", "currency": "USD", "manual_only": True,
            # Preserve the existing mirror's explicit $1 sizing, not just its $25 guard.
            "max_risk_usd": str(min(Decimal(1), Decimal(str(MAX_RISK_USD_PER_TRADE)))),
            "max_positions": min(3, MAX_CONCURRENT_PAPER), "costs": execution_assumptions(),
            "funding_modeled": False, "production_authorized": False, "startup_authorized": False}


def _number(value):
    if type(value) not in (str, int, float, Decimal):
        raise ValueError("Explicit financial number required")
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError("Nonfinite financial evidence")
    return value


def validate_fixture_entry(*, symbol, side, risk_usd, manual_confirmation, quote, now,
                           open_positions, session_net_r, kill_switch, controls_reliable):
    scope = fixture_scope()
    risk = _number(risk_usd)
    if (symbol not in scope["symbols"] or side not in ("LONG", "SHORT")
            or manual_confirmation is not True or not 0 < risk <= Decimal(scope["max_risk_usd"])):
        raise ValueError("Outside proposed manual fixture scope or stricter existing risk")
    if (type(now) is not int or type(quote) is not dict or quote.get("verified") is not True
            or quote.get("symbol") != symbol
            or type(quote.get("source_id")) is not str or not quote["source_id"]
            or type(quote.get("observed_at")) is not int
            or not 0 <= now - quote["observed_at"] <= 30 or _number(quote.get("price")) <= 0):
        raise ValueError("Missing, stale or malformed fixture price evidence")
    if type(open_positions) is not list or len(open_positions) >= scope["max_positions"]:
        raise ValueError("Fixture position capacity unavailable")
    decision = check_paper_risk(open_positions=open_positions, requested_risk_usd=float(risk),
                                session_net_r=session_net_r, kill_switch=kill_switch,
                                accounting_reliable=True, controls_reliable=controls_reliable)
    if not decision["allowed"]:
        raise ValueError("Existing PAPER risk guard refused fixture entry")
    return {"fixture_eligible": True, "risk_usd": str(risk), "price": str(_number(quote["price"])),
            "production_authorized": False, "paper_trading_authorized": False}


def _pairs(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise ValueError("Duplicate journal field")
        row[key] = value
    return row


def _constant(_value):
    raise ValueError("Nonfinite JSON journal evidence")


def journal_fixture_handoff(raw, *, expected_sha256, observed_at):
    """Bind supplied actual-interface bytes, not source authenticity/completeness.

    No file paths are accepted. Native partial-close or interrupted records are
    refused; only the separate versioned fixture ledger can represent partials.
    """
    if (type(observed_at) is not int or type(raw) is not bytes or not raw or len(raw) > 1048576 or not raw.endswith(b"\n")
            or hashlib.sha256(raw).hexdigest() != expected_sha256):
        raise ValueError("Bounded complete journal bytes and exact revision required")
    rows = [json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant) for line in raw.decode("utf-8").splitlines()]
    opens, closes, trades, rounding, financial, operations = {}, {}, [], {}, {}, set()
    for row in rows:
        if type(row) is not dict:
            raise ValueError("Malformed journal record")
        stamp = row.get("entry_timestamp") if row.get("event") == "open" else row.get("exit_timestamp") if row.get("event") == "close" else row.get("timestamp")
        try:
            clock = datetime.fromisoformat(stamp)
            if clock.tzinfo is None or clock.utcoffset() is None or clock > datetime.fromtimestamp(observed_at, UTC):
                raise ValueError("Unqualified or future journal evidence")
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid source record timestamp") from error
        if row.get("event") == "session_start":
            if type(row.get("session_id")) is not str or not row["session_id"]:
                raise ValueError("Missing session identity")
            continue
        ident = row.get("trade_id")
        event = row.get("event")
        if type(ident) is not str or not ident or event not in ("open", "mark", "close"):
            raise ValueError("Unknown journal identity/event")
        if event == "open":
            if ident in opens or row.get("source") != "fixture_hyperliquid_manual" or row.get("counts_for_live") is not False:
                raise ValueError("Duplicate or outside-scope fixture source")
            if row.get("symbol") not in fixture_scope()["symbols"] or not 0 < _number(row["risk_dollars"]) <= Decimal(fixture_scope()["max_risk_usd"]):
                raise ValueError("Outside fixture asset/risk scope")
            if (row.get("side") not in ("LONG", "SHORT")
                    or min(_number(row[key]) for key in ("actual_entry_price", "risk_price", "position_size")) <= 0
                    or row.get("features", {}).get("fixture_manual_confirmation") is not True
                    or len(set(opens) - set(closes)) >= fixture_scope()["max_positions"]):
                raise ValueError("Invalid fixture position or missing manual confirmation/capacity")
            operation = row["features"].get("fixture_operation_id")
            if type(operation) is not str or not operation or operation in operations:
                raise ValueError("Missing or replayed fixture entry operation")
            operations.add(operation)
            delta = _number(row["risk_price"]) * _number(row["position_size"]) - _number(row["risk_dollars"])
            if abs(delta) > Decimal("1e-12"):
                raise ValueError("Recorded quantity/risk mismatch")
            rounding[ident] = str(delta)
            if (_number(row["fees_bps"]) < Decimal(str(fixture_scope()["costs"]["fee_bps_per_side"]))
                    or _number(row["slippage_bps"]) < Decimal(str(fixture_scope()["costs"]["slippage_bps_per_side"]))):
                raise ValueError("Fixture costs cannot weaken existing conservative assumptions")
            opens[ident] = row
        elif ident not in opens or ident in closes:
            raise ValueError("Orphan or post-close journal event")
        if event == "close":
            closes[ident] = row
            p = opens[ident]
            entry, risk, quantity = (_number(p[key]) for key in ("actual_entry_price", "risk_price", "position_size"))
            gross = (_number(row["actual_exit_price"]) - entry) / risk * (1 if p["side"] == "LONG" else -1)
            cost = 2 * entry / risk * (_number(p["fees_bps"]) + _number(p["slippage_bps"])) / 10000
            if abs(_number(row["gross_pnl_r"]) - gross) > Decimal("0.00005") or abs(_number(row["net_pnl_r"]) - (gross - cost)) > Decimal("0.00005"):
                raise ValueError("Native recorded R contradicts quantity/cost evidence")
            financial[ident] = {"net_currency": str((gross - cost) * risk * quantity),
                                "cost_currency": str(cost * risk * quantity), "rounded_native_net_r": str(row["net_pnl_r"])}
        trades.append(row)
    positions = adapt_legacy_rows(trades, currency="USD")
    for position in positions:
        for key in ("actual_entry_price", "risk_price", "quantity", "fees_bps", "slippage_bps"):
            position[key] = str(_number(position[key]))
        position.update(source_sha256=expected_sha256, source_record_revision=len(rows))
    return {"schema": "HYPERLIQUID_JOURNAL_HANDOFF_V1", "source_sha256": expected_sha256,
            "observed_at": observed_at,
            "record_revision": len(rows), "open_positions": positions, "closed_ids": sorted(closes),
            "source_position_identities": {ident: {"symbol": p["symbol"], "side": p["side"],
                                                   "entry_price": str(_number(p["actual_entry_price"])),
                                                   "exit_price": str(_number(closes[ident]["actual_exit_price"])) if ident in closes else None}
                                           for ident, p in opens.items()},
            "derived_closed_accounting": financial, "native_risk_rounding_deltas": rounding,
            "source_completeness_independently_proven": False, "production_authorized": False,
            "recovery_authorized": False, "paper_trading_authorized": False}


def native_full_close_fixture_projection(handoff, trade_id, *, committed_partial_fills):
    """Pure compatibility check, not proof the supplied fill inventory is complete."""
    if type(committed_partial_fills) is not list or committed_partial_fills:
        raise ValueError("Native journal partial-close projection unsupported; retain original source position")
    positions = [p for p in handoff["open_positions"] if p["trade_id"] == trade_id]
    if len(positions) != 1 or handoff.get("production_authorized") is not False:
        raise ValueError("Exact fixture source position required")
    return {"trade_id": trade_id, "source_sha256": handoff["source_sha256"],
            "source_record_revision": handoff["record_revision"],
            "scope": "FULL_CLOSE_COMPATIBLE_FIXTURE_ONLY", "production_authorized": False}


def manual_journal_fixture_consistency(raw, *, expected_sha256, journal):
    """Compare exact supplied native snapshot/journal revisions; never clear pending state.

    The caller must first use the real ManualPerpStateStore.load() to refuse its
    pending/temp namespace. Byte matching is not namespace or recovery authority.
    """
    if (type(raw) is not bytes or not raw or len(raw) > 1048576 or not raw.endswith(b"\n")
            or hashlib.sha256(raw).hexdigest() != expected_sha256):
        raise ValueError("Bounded complete manual bytes and pinned revision required")
    state = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    if (type(state) is not dict or set(state) != {"version", "plans", "setup_history"}
            or type(state["version"]) is not int or state["version"] != 1
            or type(state["plans"]) is not list or len(state["plans"]) > 100
            or type(state["setup_history"]) is not list or len(state["setup_history"]) > 100
            or journal.get("schema") != "HYPERLIQUID_JOURNAL_HANDOFF_V1"
            or journal.get("production_authorized") is not False):
        raise ValueError("Unsupported manual/journal source schema")
    entered, closed, seen, planned = set(), set(), set(), 0
    for plan in state["plans"]:
        if type(plan) is not dict:
            raise ValueError("Malformed native manual plan")
        status = plan.get("status")
        ident = plan.get("fixture_journal_trade_id")
        if status == "PLANNED" and not plan.get("entered") and ident is None:
            planned += 1
            continue  # An intent is not a fill or cash movement.
        if (status not in ("ENTERED", "CLOSED") or type(ident) is not str or ident in seen
                or ident not in journal["source_position_identities"]
                or plan.get("source") != "hyperliquid" or plan.get("mode") != "MANUAL_ONLY"
                or plan.get("entered") is not (status == "ENTERED")):
            raise ValueError("Missing, duplicate or incompatible manual source identity")
        seen.add(ident)
        original = journal["source_position_identities"][ident]
        if (plan.get("symbol") != original["symbol"] or plan.get("side") != original["side"]
                or _number(plan["entry_price"]) != _number(original["entry_price"])):
            raise ValueError("Contradictory manual/journal position")
        if status == "CLOSED":
            if original["exit_price"] is None or _number(plan["exit_price"]) != _number(original["exit_price"]):
                raise ValueError("Contradictory native full close")
            closed.add(ident)
        else:
            entered.add(ident)
    if entered != {p["trade_id"] for p in journal["open_positions"]} or closed != set(journal["closed_ids"]):
        raise ValueError("Missing or conflicting native position lifecycle")
    return {"schema": "HYPERLIQUID_NATIVE_FIXTURE_CONSISTENCY_V1", "manual_sha256": expected_sha256,
            "journal_sha256": journal["source_sha256"], "journal_record_revision": journal["record_revision"],
            "entered_ids": sorted(entered), "closed_ids": sorted(closed), "unfilled_plan_n": planned,
            "native_positions_flat": not entered, "source_completeness_independently_proven": False,
            "startup_authorized": False, "shutdown_authorized": False, "production_authorized": False}
