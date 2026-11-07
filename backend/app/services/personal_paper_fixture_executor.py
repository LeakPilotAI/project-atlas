"""Isolated TEST_DATA simulated execution rehearsal, never a forward fill grant.

This executor intentionally refuses FORWARD_COLLECTION accounts. It exercises
real journal entry/mark/exit mechanics without any broker or provider adapter.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
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
                                       level: str = "L1", reason: str = "TEST_REHEARSAL",
                                       slippage_bps: Any = 2) -> dict[str, Any]:
    """Explicit, one-step, replay-safe TEST_DATA-only simulation.

    Caller-supplied price is synthetic; this must not be used to claim real
    provider fills, forward results, or strategy profitability.
    """
    if (not isinstance(path, Path) or type(account_id) is not str or not account_id
            or type(observation) is not dict or observation.get("evidence_class") != "TEST_DATA"
            or action not in ("ENTER", "MARK", "EXIT")):
        raise ValueError("DISPOSABLE_PAPER_TEST_ONLY_INPUT_REQUIRED")
    # Conservative test fills: buys pay above the synthetic ask; sells
    # receive below the synthetic bid. No fill may improve due to slippage.
    try:
        quoted = Decimal(str(price))
        slip = Decimal(str(slippage_bps))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("DISPOSABLE_PAPER_SLIPPAGE_INVALID") from exc
    if (not quoted.is_finite() or quoted <= 0 or not slip.is_finite()
            or not Decimal(0) <= slip <= Decimal(100)):
        raise ValueError("DISPOSABLE_PAPER_SLIPPAGE_INVALID")
    factor = (Decimal(1) + slip / Decimal(10000) if action == "ENTER"
              else Decimal(1) - slip / Decimal(10000))
    execution_price = round(quoted * factor, 8)
    if execution_price <= 0:
        raise ValueError("DISPOSABLE_PAPER_SLIPPAGE_INVALID")
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
                             fill_price=execution_price, account_id=account_id,
                             fee_bps_per_side=account["fee_bps_per_side"], path=path)
        else:
            if len(positions) != 1 or positions[0]["symbol"] != observation.get("symbol"):
                raise ValueError("DISPOSABLE_PAPER_SINGLE_POSITION_REQUIRED")
            lot_id = positions[0]["lot_id"]
            event = (mark_lot(lot_id, market_price=execution_price, path=path) if action == "MARK"
                     else close_lot(lot_id, exit_price=execution_price, reason=reason, path=path))
        updated = accounting_snapshot(read_events(path), account_id=account_id)
        if updated["cash_reconciled"] is not True:
            raise ValueError("DISPOSABLE_PAPER_ACCOUNT_RECONCILIATION_FAILED")
        return strict(body({"schema": "ATLAS_DISPOSABLE_TEST_PAPER_STEP_V1",
                            "action": action, "event_id": event["event_id"],
                            "synthetic_quote_price": str(quoted),
                            "simulated_execution_price": float(execution_price),
                            "slippage_bps": float(slip),
                            "open_positions": updated["open_positions"],
                            "available_cash": updated["available_cash"],
                            "net_realized_pnl": updated["net_realized_pnl"],
                            "forward_trading_authorized": False,
                            "live_order_authorized": False}))


def execute_disposable_validated_quote_step(*, path: Path, account_id: str,
                                            observation: dict[str, Any],
                                            action: str, quote: dict[str, Any],
                                            now: Any, notional: Any = 50,
                                            slippage_bps: Any = 2) -> dict[str, Any]:
    """TEST_DATA-only quote-to-journal bridge; quote is caller-supplied.

    Validating a quote does not attest provider authentication. This adapter
    never accepts FORWARD_COLLECTION evidence or grants financial authority.
    """
    from app.services.personal_paper_price_evidence import validate_stock_iex_quote
    if type(observation) is not dict or observation.get("evidence_class") != "TEST_DATA":
        raise ValueError("DISPOSABLE_QUOTE_TEST_DATA_ONLY")
    if action not in ("ENTER", "MARK", "EXIT"):
        raise ValueError("DISPOSABLE_QUOTE_ACTION_INVALID")
    evidence = validate_stock_iex_quote(quote, symbol=observation.get("symbol"), now=now)
    if evidence.get("paper_fill_authorized") is not False:
        raise ValueError("DISPOSABLE_QUOTE_UNEXPECTED_AUTHORITY")
    side_price = evidence["ask"] if action == "ENTER" else evidence["bid"]
    result = execute_disposable_test_paper_step(
        path=path, account_id=account_id, observation=observation,
        action=action, price=side_price, notional=notional,
        slippage_bps=slippage_bps)
    return strict(body({**result, "quote_evidence": evidence,
                        "provider_authenticated": False,
                        "forward_trading_authorized": False}))


def rehearse_disposable_quote_lifecycle(*, path: Path, account_id: str,
                                       observation: dict[str, Any],
                                       quotes: list[dict[str, Any]],
                                       times: list[Any],
                                       slippage_bps: Any = 2) -> dict[str, Any]:
    """Explicit TEST_DATA-only entry, marks, exit across distinct quote events.

    This is a fixed scripted lifecycle, NOT a strategy or autonomous runtime.
    It deliberately cannot run on FORWARD_COLLECTION journals.
    """
    from app.services.personal_paper_observations import _aware
    if (type(observation) is not dict or observation.get("evidence_class") != "TEST_DATA"
            or type(quotes) is not list or type(times) is not list
            or len(quotes) != len(times) or not 3 <= len(quotes) <= 30):
        raise ValueError("DISPOSABLE_LIFECYCLE_TEST_DATA_BOUNDED_REQUIRED")
    # Validate the entire supplied sequence before its first financial write.
    from app.services.personal_paper_price_evidence import validate_stock_iex_quote
    stamps = []
    for quote, now in zip(quotes, times, strict=True):
        evidence = validate_stock_iex_quote(quote, symbol=observation.get("symbol"), now=now)
        stamp = _aware(evidence["provider_timestamp"], "disposable provider event")
        if stamps and stamp <= stamps[-1]:
            raise ValueError("DISPOSABLE_LIFECYCLE_REPLAYED_QUOTE")
        stamps.append(stamp)
    results = []
    for index, (quote, now) in enumerate(zip(quotes, times, strict=True)):
        action = "ENTER" if index == 0 else "EXIT" if index == len(quotes)-1 else "MARK"
        results.append(execute_disposable_validated_quote_step(
            path=path, account_id=account_id, observation=observation,
            action=action, quote=quote, now=now, slippage_bps=slippage_bps))
    return strict(body({"schema": "ATLAS_DISPOSABLE_QUOTE_LIFECYCLE_V1",
                        "steps": results, "completed": len(results),
                        "forward_trading_authorized": False,
                        "live_order_authorized": False}))


def rehearse_disposable_rule_driven_session(*, path: Path, account_id: str,
                                           observation: dict[str, Any],
                                           quotes: list[dict[str, Any]],
                                           times: list[Any], entry_signals: list[bool],
                                           stop_loss_pct: Any = 2,
                                           take_profit_pct: Any = 3,
                                           slippage_bps: Any = 2) -> dict[str, Any]:
    """Rule-driven TEST_DATA journal rehearsal; never provider-authenticated.

    Validate the entire synthetic sequence before mutation. Enter on the first
    true signal, mark while held, exit at a bid-side stop/target or session end.
    Never re-enter during the same rehearsal.
    """
    from app.services.personal_paper_observations import _aware
    from app.services.personal_paper_price_evidence import validate_stock_iex_quote
    if (type(observation) is not dict or observation.get("evidence_class") != "TEST_DATA"
            or type(quotes) is not list or type(times) is not list
            or type(entry_signals) is not list or not 2 <= len(quotes) <= 30
            or len(quotes) != len(times) or len(quotes) != len(entry_signals)
            or any(type(flag) is not bool for flag in entry_signals)):
        raise ValueError("DISPOSABLE_RULE_SESSION_TEST_DATA_BOUNDED_REQUIRED")
    try:
        stop = Decimal(str(stop_loss_pct))
        target = Decimal(str(take_profit_pct))
        slip = Decimal(str(slippage_bps))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("DISPOSABLE_RULE_SESSION_RISK_INVALID") from exc
    if (not stop.is_finite() or not target.is_finite() or not slip.is_finite()
            or not 0 < stop <= 25 or not 0 < target <= 50
            or not 0 <= slip <= 100):
        raise ValueError("DISPOSABLE_RULE_SESSION_RISK_INVALID")
    evidence = []
    last = None
    for quote, now in zip(quotes, times, strict=True):
        item = validate_stock_iex_quote(quote, symbol=observation.get("symbol"), now=now)
        stamp = _aware(item["provider_timestamp"], "disposable provider event")
        if last is not None and stamp <= last:
            raise ValueError("DISPOSABLE_RULE_SESSION_REPLAYED_QUOTE")
        last = stamp
        evidence.append(item)
    # A rehearsal cannot mutate an account that is already holding a position.
    with journal_mutation_transaction(path):
        events = read_events(path)
        account = accounting_snapshot(events, account_id=account_id)
        if account is None or account.get("data_provenance") != "TEST_DATA" or not account.get("cash_reconciled"):
            raise ValueError("DISPOSABLE_RULE_SESSION_REFUSES_FORWARD_ACCOUNT")
        if open_lots(events):
            raise ValueError("DISPOSABLE_RULE_SESSION_REQUIRES_FLAT_ACCOUNT")
        actions = []
        entry_price = None
        closed = False
        for i, item in enumerate(evidence):
            action = "WAIT"
            reason = "NO_ENTRY_SIGNAL"
            if entry_price is None and not closed and entry_signals[i] and i < len(evidence)-1:
                action, reason = "ENTER", "SYNTHETIC_SIGNAL"
            elif entry_price is not None and not closed:
                bid = Decimal(str(item["bid"])) * (1-slip/Decimal(10000))
                if bid <= entry_price * (1-stop/Decimal(100)):
                    action, reason = "EXIT", "SYNTHETIC_STOP_LOSS"
                elif bid >= entry_price * (1+target/Decimal(100)):
                    action, reason = "EXIT", "SYNTHETIC_TAKE_PROFIT"
                elif i == len(evidence)-1:
                    action, reason = "EXIT", "SYNTHETIC_SESSION_END"
                else:
                    action, reason = "MARK", "SYNTHETIC_HOLD"
            elif closed:
                reason = "SESSION_ALREADY_CLOSED"
            if action == "WAIT":
                actions.append({"action": action, "reason": reason})
                continue
            result = execute_disposable_validated_quote_step(
                path=path, account_id=account_id, observation=observation,
                action=action, quote=quotes[i], now=times[i], slippage_bps=slip)
            actions.append({"action": action, "reason": reason, "event_id": result["event_id"]})
            if action == "ENTER":
                entry_price = Decimal(str(result["simulated_execution_price"]))
            elif action == "EXIT":
                closed = True
        final = accounting_snapshot(read_events(path), account_id=account_id)
        return strict(body({"schema": "ATLAS_DISPOSABLE_RULE_SESSION_V1",
                            "actions": actions, "completed_ticks": len(actions),
                            "open_positions": final["open_positions"],
                            "net_realized_pnl": final["net_realized_pnl"],
                            "cash_reconciled": final["cash_reconciled"],
                            "provider_authenticated": False,
                            "forward_trading_authorized": False,
                            "live_order_authorized": False}))
