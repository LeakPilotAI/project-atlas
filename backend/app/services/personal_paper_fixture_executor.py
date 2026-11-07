"""Isolated TEST_DATA simulated execution rehearsal, never a forward fill grant.

This executor intentionally refuses FORWARD_COLLECTION accounts. It exercises
real journal entry/mark/exit mechanics without any broker or provider adapter.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.investment.quality_dips_paper import (
    accounting_snapshot, close_lot, journal_mutation_transaction,
    mark_lot, open_lot, open_lots, read_events,
)
from app.services.paper_financial_replay import body, strict


def execute_disposable_test_paper_step(*, path: Path, account_id: str,
                                       observation: dict[str, Any], action: str,
                                       price: Any, notional: Any = 50,
                                       level: str = "L1", reason: str = "TEST_REHEARSAL") -> dict[str, Any]:
    """Explicit, one-step, replay-safe TEST_DATA-only simulation.

    Caller-supplied price is synthetic; this must not be used to claim real
    provider fills, forward results, or strategy profitability.
    """
    if (not isinstance(path, Path) or type(account_id) is not str or not account_id
            or type(observation) is not dict or observation.get("evidence_class") != "TEST_DATA"
            or action not in ("ENTER", "MARK", "EXIT")):
        raise ValueError("DISPOSABLE_PAPER_TEST_ONLY_INPUT_REQUIRED")
    with journal_mutation_transaction(path):
        events = read_events(path)
        account = accounting_snapshot(events, account_id=account_id)
        if (account is None or account.get("data_provenance") != "TEST_DATA"
                or account.get("cash_reconciled") is not True):
            raise ValueError("DISPOSABLE_PAPER_REFUSES_FORWARD_ACCOUNT")
        positions = open_lots(events)
        if any(p.get("account_id") != account_id for p in positions):
            raise ValueError("DISPOSABLE_PAPER_FOREIGN_POSITION")
        if action == "ENTER":
            if positions:
                raise ValueError("DISPOSABLE_PAPER_POSITION_ALREADY_OPEN")
            event = open_lot(observation, level=level, paper_notional_dollars=notional,
                             fill_price=price, account_id=account_id,
                             fee_bps_per_side=account["fee_bps_per_side"], path=path)
        else:
            if len(positions) != 1 or positions[0]["symbol"] != observation.get("symbol"):
                raise ValueError("DISPOSABLE_PAPER_SINGLE_POSITION_REQUIRED")
            lot_id = positions[0]["lot_id"]
            event = (mark_lot(lot_id, market_price=price, path=path) if action == "MARK"
                     else close_lot(lot_id, exit_price=price, reason=reason, path=path))
        updated = accounting_snapshot(read_events(path), account_id=account_id)
        if updated["cash_reconciled"] is not True:
            raise ValueError("DISPOSABLE_PAPER_ACCOUNT_RECONCILIATION_FAILED")
        return strict(body({"schema": "ATLAS_DISPOSABLE_TEST_PAPER_STEP_V1",
                            "action": action, "event_id": event["event_id"],
                            "open_positions": updated["open_positions"],
                            "available_cash": updated["available_cash"],
                            "net_realized_pnl": updated["net_realized_pnl"],
                            "forward_trading_authorized": False,
                            "live_order_authorized": False}))
