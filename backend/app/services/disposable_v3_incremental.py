"""Incremental, restartable TEST_DATA V3 simulation; never forward authority.

No broker, authenticated feed or native financial custody access. Every tick is
explicitly caller supplied; restart reconstructs position state from journal.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from app.investment.quality_dips_paper import (
    accounting_snapshot, journal_mutation_transaction, open_lots, read_events, _append)
from app.services.personal_paper_fixture_executor import execute_disposable_validated_quote_step
from app.services.personal_paper_price_evidence import validate_stock_iex_quote
from app.services.personal_paper_strategy_signal import evaluate_iex_quality_dips_signal


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
    if ticks and ticks[-1]["event"] != "v3_tick_completed":
        raise ValueError("INCREMENTAL_V3_INTERRUPTED_TICK_REQUIRES_RECONCILIATION")
    stamp = evidence["provider_timestamp"]
    completed = [e for e in ticks if e["event"] == "v3_tick_completed"]
    if completed and stamp <= completed[-1]["provider_timestamp"]:
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
