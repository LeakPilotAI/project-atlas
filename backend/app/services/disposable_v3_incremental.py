"""Incremental, restartable TEST_DATA V3 simulation; never forward authority.

No broker, authenticated feed or native financial custody access. Every tick is
explicitly caller supplied; restart reconstructs position state from journal.
"""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from app.investment.quality_dips_paper import (
    accounting_snapshot, journal_mutation_transaction, open_lots, read_events, _append)
from app.services.personal_paper_fixture_executor import execute_disposable_validated_quote_step
from app.services.personal_paper_price_evidence import validate_stock_iex_quote
from app.services.personal_paper_strategy_signal import evaluate_iex_quality_dips_signal


def _provider_instant(value: str) -> datetime:
    if type(value) is not str:
        raise ValueError("INCREMENTAL_V3_PROVIDER_TIMESTAMP_INVALID")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INCREMENTAL_V3_PROVIDER_TIMESTAMP_INVALID") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("INCREMENTAL_V3_PROVIDER_TIMESTAMP_INVALID")
    return instant.astimezone(UTC)


def execute_incremental_test_v3_tick(*, path: Path, account_id: str,
                                     observation: dict, research: dict,
                                     quote: dict, now: datetime,
                                     stop_loss_pct: float = 2,
                                     take_profit_pct: float = 3,
                                     flatten_at_session_end: bool = False) -> dict:
    if (type(observation) is not dict or observation.get("evidence_class") != "TEST_DATA"
            or type(research) is not dict or observation.get("symbol") != research.get("symbol")
            or type(account_id) is not str or not account_id):
        raise ValueError("INCREMENTAL_V3_TEST_DATA_ONLY")
    try:
        stop = Decimal(str(stop_loss_pct))
        target = Decimal(str(take_profit_pct))
    except (ValueError, ArithmeticError) as exc:
        raise ValueError("INCREMENTAL_V3_RISK_INVALID") from exc
    if (not stop.is_finite() or not target.is_finite()
            or not 0 < stop <= 25 or not 0 < target <= 50):
        raise ValueError("INCREMENTAL_V3_RISK_INVALID")
    if type(flatten_at_session_end) is not bool:
        raise ValueError("INCREMENTAL_V3_SESSION_END_FLAG_INVALID")
    evidence = validate_stock_iex_quote(quote, symbol=observation["symbol"], now=now)
    # One journal OS lock covers replay admission, simulation and completion.
    # An interrupted tick is deliberately blocked for operator reconciliation.
    with journal_mutation_transaction(path):
        return _execute_locked(path=path, account_id=account_id,
                               observation=observation, research=research,
                               quote=quote, now=now, evidence=evidence,
                               stop_loss_pct=stop_loss_pct,
                               take_profit_pct=take_profit_pct,
                               flatten_at_session_end=flatten_at_session_end)


def _execute_locked(*, path, account_id, observation, research, quote, now,
                    evidence, stop_loss_pct, take_profit_pct,
                    flatten_at_session_end):
    events = read_events(path)
    ticks = [e for e in events if e.get("event") in ("v3_tick_started", "v3_tick_completed")]
    pending = None
    completed_stamps = []
    for row in events:
        kind = row.get("event")
        if kind == "v3_tick_started":
            ident = row.get("event_id")
            if (pending is not None or row.get("account_id") != account_id
                    or type(ident) is not str or not ident.startswith("start-")):
                raise ValueError("INCREMENTAL_V3_MALFORMED_TICK_HISTORY")
            pending = {"digest": ident[6:], "stamp": row.get("provider_timestamp"),
                       "financial": []}
        elif kind in ("open_lot", "mark_lot", "close_lot") and pending is not None:
            pending["financial"].append(row)
        elif kind == "v3_tick_completed":
            ident = row.get("event_id")
            if (pending is None or row.get("account_id") != account_id
                    or type(ident) is not str or ident != "done-" + pending["digest"]
                    or _provider_instant(row.get("provider_timestamp")) !=
                    _provider_instant(pending["stamp"])):
                raise ValueError("INCREMENTAL_V3_MALFORMED_TICK_HISTORY")
            action = row.get("action")
            expected = {"WAIT": None, "ENTER": "open_lot",
                        "MARK": "mark_lot", "EXIT": "close_lot"}
            financial = pending["financial"]
            if (action not in expected or len(financial) != (0 if action == "WAIT" else 1)
                    or (financial and (financial[0].get("event") != expected[action]
                         or financial[0].get("account_id") != account_id
                         or financial[0].get("event_id") != row.get("simulated_event_id")))
                    or (not financial and row.get("simulated_event_id") is not None)):
                raise ValueError("INCREMENTAL_V3_FINANCIAL_TICK_HISTORY_MISMATCH")
            completed_stamps.append(_provider_instant(pending["stamp"]))
            pending = None
    if pending is not None:
        raise ValueError("INCREMENTAL_V3_INTERRUPTED_TICK_REQUIRES_RECONCILIATION")
    if any(current <= prior for prior, current in zip(completed_stamps, completed_stamps[1:])):
        raise ValueError("INCREMENTAL_V3_NONMONOTONIC_HISTORY")
    stamp = evidence["provider_timestamp"]
    if completed_stamps and _provider_instant(stamp) <= completed_stamps[-1]:
        raise ValueError("INCREMENTAL_V3_REPLAYED_OR_OLDER_TICK")
    account = accounting_snapshot(events, account_id=account_id)
    if account is None or account.get("data_provenance") != "TEST_DATA" or not account["cash_reconciled"]:
        raise ValueError("INCREMENTAL_V3_ACCOUNT_NOT_RECONCILED")
    positions = open_lots(events)
    if any(p.get("account_id") != account_id for p in positions) or len(positions) > 1:
        raise ValueError("INCREMENTAL_V3_FOREIGN_OR_MULTIPLE_POSITIONS")
    # Risk exits must not be blocked by stale entry research. Entry evaluation
    # is only relevant when the simulated account is flat.
    decision = {"candidate": False}
    if not positions and not flatten_at_session_end:
        decision = evaluate_iex_quality_dips_signal(
            quote=quote, symbol=observation["symbol"], now=now, research=research)
        if decision["paper_fill_authorized"] is not False:
            raise ValueError("INCREMENTAL_V3_UNEXPECTED_AUTHORITY")
    if positions:
        entry = Decimal(str(positions[0]["fill_price"]))
        bid = Decimal(evidence["bid"]) * Decimal("0.9998")
        if bid <= entry * (1-Decimal(str(stop_loss_pct))/100):
            action, reason = "EXIT", "SYNTHETIC_STOP_LOSS"
        elif bid >= entry * (1+Decimal(str(take_profit_pct))/100):
            action, reason = "EXIT", "SYNTHETIC_TAKE_PROFIT"
        elif flatten_at_session_end:
            action, reason = "EXIT", "SYNTHETIC_EXPLICIT_SESSION_END"
        else:
            action, reason = "MARK", "SYNTHETIC_HOLD"
    elif not flatten_at_session_end and decision["candidate"] and not any(e.get("event") == "open_lot" for e in events):
        action, reason = "ENTER", "SYNTHETIC_V3_CANDIDATE"
    else:
        action, reason = "WAIT", "SYNTHETIC_NO_ENTRY"
    event_digest = hashlib.sha256(json.dumps({"account_id": account_id,
        "symbol": observation["symbol"], "stamp": stamp, "bid": evidence["bid"],
        "ask": evidence["ask"]}, sort_keys=True).encode()).hexdigest()
    _append({"event": "v3_tick_started", "event_id": "start-" + event_digest,
             "provider_timestamp": stamp, "account_id": account_id,
             "evidence_class": "TEST_DATA", "execution": "PAPER_ONLY",
             "broker_order_created": False}, path)
    if action != "WAIT":
        outcome = execute_disposable_validated_quote_step(
            path=path, account_id=account_id, observation=observation,
            action=action, quote=quote, now=now)
        event_id = outcome["event_id"]
    else:
        event_id = None
    final = accounting_snapshot(read_events(path), account_id=account_id)
    if not final["cash_reconciled"]:
        raise ValueError("INCREMENTAL_V3_POST_TICK_RECONCILIATION_FAILED")
    _append({"event": "v3_tick_completed", "event_id": "done-" + event_digest,
             "provider_timestamp": stamp, "account_id": account_id,
             "action": action, "simulated_event_id": event_id,
             "evidence_class": "TEST_DATA", "execution": "PAPER_ONLY",
             "broker_order_created": False}, path)
    return {"schema": "ATLAS_INCREMENTAL_TEST_V3_TICK_V1", "action": action,
            "reason": reason, "event_id": event_id,
            "candidate": decision["candidate"], "cash_reconciled": final["cash_reconciled"],
            "open_positions": final["open_positions"],
            "net_realized_pnl": final["net_realized_pnl"],
            "evidence_class": "TEST_DATA", "provider_authenticated": False,
            "research_provenance_attested": False,
            "forward_trading_authorized": False, "live_order_authorized": False}


def inspect_incremental_test_v3_recovery(*, path: Path, account_id: str) -> dict:
    """Read-only operator recovery report; never repairs an ambiguous journal."""
    if type(account_id) is not str or not account_id:
        raise ValueError("INCREMENTAL_V3_RECOVERY_ACCOUNT_REQUIRED")
    with journal_mutation_transaction(path):
        events = read_events(path)
        account = accounting_snapshot(events, account_id=account_id)
        if account is None or account.get("data_provenance") != "TEST_DATA":
            raise ValueError("INCREMENTAL_V3_RECOVERY_TEST_ACCOUNT_REQUIRED")
        starts = {}
        completed = set()
        anomalies = []
        last_stamp = None
        for row in events:
            kind = row.get("event")
            if kind not in ("v3_tick_started", "v3_tick_completed"):
                continue
            if row.get("account_id") != account_id:
                anomalies.append("FOREIGN_TICK_ACCOUNT")
                continue
            ident = row.get("event_id")
            stamp = row.get("provider_timestamp")
            if (type(ident) is not str or type(stamp) is not str
                    or not ident.startswith("start-" if kind == "v3_tick_started" else "done-")):
                anomalies.append("MALFORMED_TICK_EVENT")
                continue
            digest = ident.split("-", 1)[1]
            if kind == "v3_tick_started":
                try:
                    instant = _provider_instant(stamp)
                except ValueError:
                    anomalies.append("MALFORMED_PROVIDER_TIMESTAMP")
                    continue
                if digest in starts or (last_stamp is not None and instant <= last_stamp):
                    anomalies.append("DUPLICATE_OR_NONMONOTONIC_START")
                starts[digest] = instant
                last_stamp = instant
            else:
                try:
                    instant = _provider_instant(stamp)
                except ValueError:
                    anomalies.append("MALFORMED_PROVIDER_TIMESTAMP")
                    continue
                if digest not in starts or digest in completed or starts[digest] != instant:
                    anomalies.append("UNMATCHED_COMPLETION")
                completed.add(digest)
        pending = [digest for digest in starts if digest not in completed]
        if pending:
            anomalies.append("INCOMPLETE_TICK")
        if account["cash_reconciled"] is not True:
            anomalies.append("CASH_RECONCILIATION_FAILED")
        return {"schema": "ATLAS_INCREMENTAL_TEST_V3_RECOVERY_REPORT_V1",
                "account_id": account_id, "completed_ticks": len(completed),
                "pending_tick_count": len(pending),
                "anomalies": sorted(set(anomalies)),
                "recovery_status": "BLOCKED_MANUAL_REVIEW" if anomalies else "CLEAN",
                "cash_reconciled": account["cash_reconciled"],
                "open_positions": account["open_positions"],
                "net_realized_pnl": account["net_realized_pnl"],
                "journal_mutated": False, "automatic_recovery_authorized": False,
                "forward_trading_authorized": False, "live_order_authorized": False}
