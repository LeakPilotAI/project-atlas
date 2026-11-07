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
                                     take_profit_pct: float = 3) -> dict:
    if (type(observation) is not dict or observation.get("evidence_class") != "TEST_DATA"
            or type(research) is not dict or observation.get("symbol") != research.get("symbol")
            or type(account_id) is not str or not account_id):
        raise ValueError("INCREMENTAL_V3_TEST_DATA_ONLY")
    if not (0 < stop_loss_pct <= 25 and 0 < take_profit_pct <= 50):
        raise ValueError("INCREMENTAL_V3_RISK_INVALID")
    evidence = validate_stock_iex_quote(quote, symbol=observation["symbol"], now=now)
    decision = evaluate_iex_quality_dips_signal(
        quote=quote, symbol=observation["symbol"], now=now, research=research)
    if decision["paper_fill_authorized"] is not False:
        raise ValueError("INCREMENTAL_V3_UNEXPECTED_AUTHORITY")
    # One journal OS lock covers replay admission, simulation and completion.
    # An interrupted tick is deliberately blocked for operator reconciliation.
    with journal_mutation_transaction(path):
        return _execute_locked(path=path, account_id=account_id,
                               observation=observation, research=research,
                               quote=quote, now=now, evidence=evidence,
                               decision=decision, stop_loss_pct=stop_loss_pct,
                               take_profit_pct=take_profit_pct)


def _execute_locked(*, path, account_id, observation, research, quote, now,
                    evidence, decision, stop_loss_pct, take_profit_pct):
    events = read_events(path)
    ticks = [e for e in events if e.get("event") in ("v3_tick_started", "v3_tick_completed")]
    pending = set()
    for row in ticks:
        ident = row.get("event_id")
        if type(ident) is not str or not ident.startswith(
                "start-" if row["event"] == "v3_tick_started" else "done-"):
            raise ValueError("INCREMENTAL_V3_MALFORMED_TICK_HISTORY")
        digest = ident.split("-", 1)[1]
        if row["event"] == "v3_tick_started":
            if pending:
                raise ValueError("INCREMENTAL_V3_INTERRUPTED_TICK_REQUIRES_RECONCILIATION")
            pending.add(digest)
        elif digest not in pending:
            raise ValueError("INCREMENTAL_V3_MALFORMED_TICK_HISTORY")
        else:
            pending.remove(digest)
    if pending:
        raise ValueError("INCREMENTAL_V3_INTERRUPTED_TICK_REQUIRES_RECONCILIATION")
    stamp = evidence["provider_timestamp"]
    completed = [e for e in ticks if e["event"] == "v3_tick_completed"]
    for prior, current in zip(completed, completed[1:]):
        if _provider_instant(current["provider_timestamp"]) <= _provider_instant(prior["provider_timestamp"]):
            raise ValueError("INCREMENTAL_V3_NONMONOTONIC_HISTORY")
    if completed and _provider_instant(stamp) <= _provider_instant(completed[-1]["provider_timestamp"]):
        raise ValueError("INCREMENTAL_V3_REPLAYED_OR_OLDER_TICK")
    account = accounting_snapshot(events, account_id=account_id)
    if account is None or account.get("data_provenance") != "TEST_DATA" or not account["cash_reconciled"]:
        raise ValueError("INCREMENTAL_V3_ACCOUNT_NOT_RECONCILED")
    positions = open_lots(events)
    if any(p.get("account_id") != account_id for p in positions) or len(positions) > 1:
        raise ValueError("INCREMENTAL_V3_FOREIGN_OR_MULTIPLE_POSITIONS")
    if positions:
        entry = Decimal(str(positions[0]["fill_price"]))
        bid = Decimal(evidence["bid"]) * Decimal("0.9998")
        if bid <= entry * (1-Decimal(str(stop_loss_pct))/100):
            action, reason = "EXIT", "SYNTHETIC_STOP_LOSS"
        elif bid >= entry * (1+Decimal(str(take_profit_pct))/100):
            action, reason = "EXIT", "SYNTHETIC_TAKE_PROFIT"
        else:
            action, reason = "MARK", "SYNTHETIC_HOLD"
    elif decision["candidate"] and not any(e.get("event") == "open_lot" for e in events):
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
