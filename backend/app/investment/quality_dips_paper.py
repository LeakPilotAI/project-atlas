"""Durable PAPER-only lifecycle journal for Quality Dips V3.

This module records simulated investment decisions/lots only. It has no broker
adapter and cannot submit real orders. Sizing is explicit: callers must supply a
positive PAPER notional rather than inheriting or inventing live buying power.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, Optional

from app.investment.storage import QUALITY_DIPS_PAPER_JOURNAL_PATH

STRATEGY_VERSION = "QUALITY_DIPS_V3"
POLICY_VERSION = "quality-dips-v3-mos-15-20-25-30-v1"
PAPER_POLICY_VERSION = "QUALITY_DIPS_PAPER_V1"
EXECUTION_MODEL_VERSION = "quality-dips-paper-v1-explicit-notional-no-broker"
VALID_LEVELS = frozenset({"L1", "L2", "L3", "L4"})
PAPER_NOTIONAL_BY_LEVEL = {"L1": 100.0, "L2": 100.0, "L3": 100.0, "L4": 100.0}
ACTIONABLE_STATES = frozenset({"ACCUMULATION", "DEEP_VALUE", "GENERATIONAL"})
_lock = RLock()


@contextmanager
def _exclusive_journal_writer(path: Path):
    """Nonblocking OS lock for one journal across processes; fail closed.

    The lock file is persistent; its existence does not indicate ownership.
    The OS releases the byte-range lock when a process exits or crashes.
    """
    path = Path(path)
    lock_path = path.with_name(path.name + ".writer.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError("PAPER_JOURNAL_WRITER_OWNED_BY_ANOTHER_PROCESS") from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError("PAPER_JOURNAL_WRITER_OWNED_BY_ANOTHER_PROCESS") from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _serialized_paper_mutation(fn):
    """Protect the entire journal replay/validate/append across processes."""
    @wraps(fn)
    def guarded(*args, **kwargs):
        path = Path(kwargs.get("path", QUALITY_DIPS_PAPER_JOURNAL_PATH))
        with _lock:
            with _exclusive_journal_writer(path):
                return fn(*args, **kwargs)
    return guarded


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _positive_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive finite number") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field} must be a positive finite number")
    return number


def _nonnegative_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a nonnegative finite number") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a nonnegative finite number")
    return number


def read_events(path: Path = QUALITY_DIPS_PAPER_JOURNAL_PATH) -> list[Dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    with _lock:
        with path.open(encoding="utf-8") as stream:
            return [json.loads(line) for line in stream if line.strip()]


def _append(row: Dict[str, Any], path: Path) -> Dict[str, Any]:
    payload = json.dumps(row, sort_keys=True, allow_nan=False, default=str)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(payload + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return row


def _event_id(*parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()


@_serialized_paper_mutation
def initialize_paper_account(
    *,
    account_id: str,
    opening_cash: Any,
    fee_bps_per_side: Any,
    max_open_positions: int = 1,
    data_provenance: str = "TEST_DATA",
    path: Path = QUALITY_DIPS_PAPER_JOURNAL_PATH,
) -> Dict[str, Any]:
    """Create one provenance-bound simulated account in an isolated PAPER journal."""
    ident = str(account_id or "").strip()
    cash = _positive_number(opening_cash, "opening_cash")
    fee_bps = _nonnegative_number(fee_bps_per_side, "fee_bps_per_side")
    if (
        not ident
        or fee_bps > 1000
        or type(max_open_positions) is not int
        or max_open_positions < 1
        or data_provenance not in {"TEST_DATA", "FORWARD_COLLECTION"}
    ):
        raise ValueError("valid simulated PAPER account configuration required")
    rows = read_events(path)
    existing = [row for row in rows if row.get("event") == "account_opened"]
    expected = {
        "account_id": ident,
        "opening_cash": round(cash, 8),
        "currency": "SIMULATED_USD",
        "fee_bps_per_side": fee_bps,
        "max_open_positions": max_open_positions,
        "data_provenance": data_provenance,
    }
    if data_provenance == "FORWARD_COLLECTION":
        expected["max_entry_notional"] = 100.0
    if existing:
        if len(existing) != 1 or any(
            existing[0].get(key) != value for key, value in expected.items()
        ):
            raise ValueError("PAPER account configuration conflicts with durable journal")
        return existing[0]
    if rows:
        raise ValueError("PAPER account must be initialized before journal transactions")
    row = {
        "schema_version": 1,
        "event": "account_opened",
        "event_id": _event_id("account_opened", ident),
        "timestamp": _now(),
        **expected,
        "execution": "PAPER_ONLY",
        "broker_order_created": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
    return _append(row, Path(path))


def initialize_test_account(
    *,
    account_id: str,
    opening_cash: Any,
    fee_bps_per_side: Any,
    max_open_positions: int = 1,
    path: Path = QUALITY_DIPS_PAPER_JOURNAL_PATH,
) -> Dict[str, Any]:
    """Create one explicitly TEST_DATA account in an isolated PAPER journal."""
    return initialize_paper_account(
        account_id=account_id,
        opening_cash=opening_cash,
        fee_bps_per_side=fee_bps_per_side,
        max_open_positions=max_open_positions,
        data_provenance="TEST_DATA",
        path=path,
    )


@_serialized_paper_mutation
def record_decision(
    observation: Dict[str, Any],
    *,
    decision: str,
    reason: str = "",
    account_id: Optional[str] = None,
    path: Path = QUALITY_DIPS_PAPER_JOURNAL_PATH,
) -> Dict[str, Any]:
    """Record a frozen PAPER decision, including HOLD/WAIT/skipped outcomes."""
    observation_id = str(observation.get("observation_id") or "").strip()
    symbol = str(observation.get("symbol") or "").upper().strip()
    if not observation_id or not symbol:
        raise ValueError("observation_id and symbol are required")
    decision = str(decision or "").upper().strip()
    if not decision:
        raise ValueError("decision is required")
    eid = _event_id("decision", observation_id, decision)
    existing = read_events(path)
    for row in existing:
        if row.get("event_id") == eid:
            return row
    row = {
        "schema_version": 1,
        "event": "decision",
        "event_id": eid,
        "timestamp": _now(),
        "observation_id": observation_id,
        "symbol": symbol,
        "strategy_version": STRATEGY_VERSION,
        "policy_version": POLICY_VERSION,
        "paper_policy_version": PAPER_POLICY_VERSION,
        "execution_model_version": EXECUTION_MODEL_VERSION,
        "decision": decision,
        "reason": str(reason or ""),
        "account_id": account_id,
        "classification": observation.get("classification"),
        "source_timestamp": observation.get("source_timestamp"),
        "evidence_class": observation.get("evidence_class"),
        "execution": "PAPER_ONLY",
        "broker_order_created": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
    return _append(row, Path(path))


@_serialized_paper_mutation
def open_lot(
    observation: Dict[str, Any],
    *,
    level: str,
    paper_notional_dollars: Any,
    fill_price: Optional[Any] = None,
    account_id: Optional[str] = None,
    fee_bps_per_side: Any = 0,
    path: Path = QUALITY_DIPS_PAPER_JOURNAL_PATH,
) -> Dict[str, Any]:
    """Open one idempotent long-only simulated lot from a frozen observation."""
    observation_id = str(observation.get("observation_id") or "").strip()
    symbol = str(observation.get("symbol") or "").upper().strip()
    if not observation_id or not symbol:
        raise ValueError("observation_id and symbol are required")
    level = str(level or "").upper().strip()
    if level not in VALID_LEVELS:
        raise ValueError("level must be one of L1/L2/L3/L4")
    notional = _positive_number(paper_notional_dollars, "paper_notional_dollars")
    price = _positive_number(
        observation.get("price") if fill_price is None else fill_price, "fill_price"
    )
    fee_bps = _nonnegative_number(fee_bps_per_side, "fee_bps_per_side")
    if fee_bps > 1000:
        raise ValueError("fee_bps_per_side exceeds supported PAPER limit")
    if account_id is not None and (type(account_id) is not str or not account_id.strip()):
        raise ValueError("account_id must be a nonempty string")
    event_parts = ("lot", observation_id, level, PAPER_POLICY_VERSION)
    if account_id is not None:
        event_parts += (account_id,)
    lot_id = _event_id(*event_parts)
    rows = read_events(path)
    entry_fee = round(notional * fee_bps / 10000.0, 8)
    for row in rows:
        if row.get("event") == "open_lot" and row.get("lot_id") == lot_id:
            expected = (
                row.get("account_id") == account_id
                and float(row.get("paper_notional_dollars", 0)) == round(notional, 8)
                and float(row.get("fill_price", 0)) == round(price, 8)
                and float(row.get("fee_bps_per_side", 0)) == fee_bps
            )
            if not expected:
                raise ValueError("conflicting retry for existing PAPER lot")
            return row
    if account_id is not None:
        account = accounting_snapshot(rows, account_id=account_id)
        if account is None:
            raise ValueError("initialized TEST_DATA account required")
        provenance = account["data_provenance"]
        if observation.get("evidence_class") != provenance:
            raise ValueError(f"{provenance} account refuses mismatched observations")
        if fee_bps != account["fee_bps_per_side"]:
            raise ValueError("PAPER fee policy differs from initialized account")
        max_entry_notional = account.get("max_entry_notional")
        if max_entry_notional is not None and notional > float(max_entry_notional):
            raise ValueError("PAPER account per-entry notional limit reached")
        if account["open_positions"] >= account["max_open_positions"]:
            raise ValueError("PAPER account open-position limit reached")
        if account["available_cash"] + 1e-8 < notional + entry_fee:
            raise ValueError("insufficient simulated cash")
    row = {
        "schema_version": 1,
        "event": "open_lot",
        "event_id": _event_id("open_lot", lot_id),
        "lot_id": lot_id,
        "timestamp": _now(),
        "observation_id": observation_id,
        "symbol": symbol,
        "side": "LONG",
        "level": level,
        "paper_notional_dollars": round(notional, 8),
        "fill_price": round(price, 8),
        "quantity_shares": round(notional / price, 12),
        "account_id": account_id,
        "fee_bps_per_side": fee_bps,
        "entry_fee": entry_fee,
        "data_provenance": (
            accounting_snapshot(read_events(path), account_id=account_id)["data_provenance"]
            if account_id is not None
            else observation.get("evidence_class")
        ),
        "strategy_version": STRATEGY_VERSION,
        "policy_version": POLICY_VERSION,
        "paper_policy_version": PAPER_POLICY_VERSION,
        "execution_model_version": EXECUTION_MODEL_VERSION,
        "classification": observation.get("classification"),
        "source_timestamp": observation.get("source_timestamp"),
        "evidence_class": observation.get("evidence_class"),
        "execution": "PAPER_ONLY",
        "status": "OPEN",
        "broker_order_created": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
    return _append(row, Path(path))


def open_lots(events: Optional[Iterable[Dict[str, Any]]] = None) -> list[Dict[str, Any]]:
    rows = list(events) if events is not None else read_events()
    opened: Dict[str, Dict[str, Any]] = {}
    closed: set[str] = set()
    for row in rows:
        lot_id = str(row.get("lot_id") or "")
        if row.get("event") == "open_lot" and lot_id:
            opened[lot_id] = row
        elif row.get("event") == "close_lot" and lot_id:
            closed.add(lot_id)
    return [row for lot_id, row in opened.items() if lot_id not in closed]


def accounting_snapshot(
    events: Iterable[Dict[str, Any]],
    *,
    account_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Reconstruct simulated cash and costs from the same append-only journal."""
    rows = list(events)
    accounts = [row for row in rows if row.get("event") == "account_opened"]
    if not accounts:
        return None
    if len(accounts) != 1 or accounts[0].get("data_provenance") not in {
        "TEST_DATA", "FORWARD_COLLECTION"
    }:
        raise ValueError("PAPER account journal identity is ambiguous")
    account = accounts[0]
    ident = account.get("account_id")
    if account_id is not None and account_id != ident:
        return None
    financial_events = {"open_lot", "mark_lot", "close_lot"}
    if any(row.get("event") in financial_events and row.get("account_id") != ident for row in rows):
        raise ValueError("financial event account identity conflicts with journal")
    provenance = account["data_provenance"]
    if any(
        row.get("account_id") == ident and row.get("data_provenance") != provenance
        for row in rows
        if row.get("event") in financial_events
    ):
        raise ValueError("PAPER event provenance conflicts with its account")

    opened = {
        row["lot_id"]: row
        for row in rows
        if row.get("event") == "open_lot" and row.get("account_id") == ident and row.get("lot_id")
    }
    closed = {
        row["lot_id"]: row
        for row in rows
        if row.get("event") == "close_lot" and row.get("account_id") == ident and row.get("lot_id")
    }
    if len(opened) != sum(
        row.get("event") == "open_lot" and row.get("account_id") == ident for row in rows
    ):
        raise ValueError("duplicate account entry in PAPER journal")
    if any(lot_id not in opened for lot_id in closed):
        raise ValueError("PAPER close has no matching account entry")

    cash = float(account["opening_cash"])
    fees_paid = 0.0
    gross_realized = 0.0
    net_realized = 0.0
    for lot_id, lot in opened.items():
        notional = _positive_number(lot.get("paper_notional_dollars"), "paper_notional_dollars")
        entry_fee = _nonnegative_number(lot.get("entry_fee", 0), "entry_fee")
        cash -= notional + entry_fee
        fees_paid += entry_fee
        close = closed.get(lot_id)
        if close is not None:
            proceeds = float(close["quantity_shares"]) * float(close["exit_price"])
            exit_fee = _nonnegative_number(close.get("exit_fee", 0), "exit_fee")
            gross = _positive_or_negative_number(close.get("realized_pnl", 0), "realized_pnl")
            net = _positive_or_negative_number(
                close.get("net_realized_pnl", gross - entry_fee - exit_fee),
                "net_realized_pnl",
            )
            if abs(net - (gross - entry_fee - exit_fee)) > 1e-7:
                raise ValueError("PAPER net P&L does not reconcile to recorded costs")
            cash += proceeds - exit_fee
            fees_paid += exit_fee
            gross_realized += gross
            net_realized += net

    if cash < -1e-7:
        raise ValueError("reconstructed simulated cash is negative")
    open_count = sum(lot_id not in closed for lot_id in opened)
    return {
        "account_id": ident,
        "currency": account["currency"],
        "data_provenance": provenance,
        "opening_cash": round(float(account["opening_cash"]), 8),
        "available_cash": round(cash, 8),
        "fees_paid": round(fees_paid, 8),
        "gross_realized_pnl": round(gross_realized, 8),
        "net_realized_pnl": round(net_realized, 8),
        "fee_bps_per_side": float(account["fee_bps_per_side"]),
        "max_open_positions": int(account["max_open_positions"]),
        "max_entry_notional": account.get("max_entry_notional"),
        "open_positions": open_count,
        "cash_reconciled": True,
        "cash_difference": 0.0,
    }


def _positive_or_negative_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number



def _reached_levels(observation: Dict[str, Any]) -> list[str]:
    prediction = observation.get("prediction") or {}
    ladder = prediction.get("entry_ladder") or {}
    if not ladder.get("ready"):
        return []
    reached = []
    for item in ladder.get("levels") or []:
        level = str(item.get("level") or "").upper()
        if level in VALID_LEVELS and item.get("reached") is True:
            reached.append(level)
    return sorted(set(reached), key=lambda x: int(x[1:]))


def mirror_forward_observation(
    observation: Dict[str, Any],
    *,
    paper_notional_by_level: Optional[Dict[str, Any]] = None,
    account_id: Optional[str] = None,
    path: Path = QUALITY_DIPS_PAPER_JOURNAL_PATH,
) -> Dict[str, Any]:
    """Mirror one frozen forward V3 observation into deterministic PAPER evidence.

    Only levels already marked reached by the frozen V3 policy can open. The
    simulated fill uses the observation's point-in-time price; no chart-touch,
    future price, live buying power, or broker state is consulted.
    """
    if str(observation.get("strategy_version") or "") != STRATEGY_VERSION:
        raise ValueError("observation is not QUALITY_DIPS_V3")
    if str(observation.get("policy_version") or "") != POLICY_VERSION:
        raise ValueError("observation policy_version does not match frozen V3 policy")
    if str(observation.get("evidence_class") or "").upper() != "FORWARD_COLLECTION":
        raise ValueError("only FORWARD_COLLECTION observations may create PAPER lots")
    state = str(observation.get("classification") or "").upper()
    reached = _reached_levels(observation)
    if state not in ACTIONABLE_STATES or not reached:
        row = record_decision(
            observation,
            decision="PAPER_NO_FILL",
            reason="V3 state not actionable or no frozen ladder level reached",
            account_id=account_id,
            path=path,
        )
        return {"decision": row, "opened_lots": []}

    notionals = dict(PAPER_NOTIONAL_BY_LEVEL)
    if paper_notional_by_level is not None:
        notionals.update(paper_notional_by_level)
    decision = record_decision(
        observation,
        decision="PAPER_OPEN_" + "_".join(reached),
        reason="Frozen V3 forward observation reached eligible long-only ladder level(s)",
        account_id=account_id,
        path=path,
    )
    lots = [
        open_lot(
            observation,
            level=level,
            paper_notional_dollars=notionals[level],
            fill_price=observation.get("price"),
            account_id=account_id,
            fee_bps_per_side=(
                accounting_snapshot(read_events(path), account_id=account_id)["fee_bps_per_side"]
                if account_id is not None
                else 0
            ),
            path=path,
        )
        for level in reached
    ]
    return {"decision": decision, "opened_lots": lots}



def _lot_by_id(lot_id: str, events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    for row in events:
        if row.get("event") == "open_lot" and row.get("lot_id") == lot_id:
            return row
    raise ValueError("unknown PAPER lot_id")


@_serialized_paper_mutation
def mark_lot(
    lot_id: str,
    *,
    market_price: Any,
    observed_at: Optional[str] = None,
    path: Path = QUALITY_DIPS_PAPER_JOURNAL_PATH,
) -> Dict[str, Any]:
    """Append a point-in-time PAPER mark; never mutates the opening lot."""
    price = _positive_number(market_price, "market_price")
    events = read_events(path)
    lot = _lot_by_id(str(lot_id), events)
    if any(row.get("event") == "close_lot" and row.get("lot_id") == lot_id for row in events):
        raise ValueError("cannot mark a closed PAPER lot")
    ts = str(observed_at or _now())
    eid = _event_id("mark_lot", lot_id, ts, round(price, 8))
    for row in events:
        if row.get("event_id") == eid:
            return row
    entry = float(lot["fill_price"])
    qty = float(lot["quantity_shares"])
    unrealized = (price - entry) * qty
    return _append(
        {
            "schema_version": 1,
            "event": "mark_lot",
            "event_id": eid,
            "lot_id": lot_id,
            "account_id": lot.get("account_id"),
            "timestamp": ts,
            "symbol": lot["symbol"],
            "market_price": round(price, 8),
            "market_value": round(price * qty, 8),
            "unrealized_pnl": round(unrealized, 8),
            "unrealized_return_pct": round(((price / entry) - 1.0) * 100.0, 8),
            "data_provenance": lot.get("data_provenance"),
            "execution": "PAPER_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        },
        Path(path),
    )


@_serialized_paper_mutation
def close_lot(
    lot_id: str,
    *,
    exit_price: Any,
    reason: str,
    closed_at: Optional[str] = None,
    path: Path = QUALITY_DIPS_PAPER_JOURNAL_PATH,
) -> Dict[str, Any]:
    """Close a PAPER lot exactly once using an explicit observed exit price."""
    price = _positive_number(exit_price, "exit_price")
    events = read_events(path)
    lot = _lot_by_id(str(lot_id), events)
    for row in events:
        if row.get("event") == "close_lot" and row.get("lot_id") == lot_id:
            return row
    entry = float(lot["fill_price"])
    qty = float(lot["quantity_shares"])
    pnl = (price - entry) * qty
    entry_fee = _nonnegative_number(lot.get("entry_fee", 0), "entry_fee")
    fee_bps = _nonnegative_number(lot.get("fee_bps_per_side", 0), "fee_bps_per_side")
    exit_fee = round(price * qty * fee_bps / 10000.0, 8)
    return _append(
        {
            "schema_version": 1,
            "event": "close_lot",
            "event_id": _event_id("close_lot", lot_id),
            "lot_id": lot_id,
            "account_id": lot.get("account_id"),
            "timestamp": str(closed_at or _now()),
            "symbol": lot["symbol"],
            "exit_price": round(price, 8),
            "quantity_shares": qty,
            "realized_pnl": round(pnl, 8),
            "entry_fee": entry_fee,
            "exit_fee": exit_fee,
            "fees_paid": round(entry_fee + exit_fee, 8),
            "net_realized_pnl": round(pnl - entry_fee - exit_fee, 8),
            "realized_return_pct": round(((price / entry) - 1.0) * 100.0, 8),
            "reason": str(reason or "UNSPECIFIED"),
            "data_provenance": lot.get("data_provenance"),
            "status": "CLOSED",
            "execution": "PAPER_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        },
        Path(path),
    )


def portfolio_snapshot(
    events: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Rebuild read-only PAPER accounting from the append-only journal."""
    rows = list(events) if events is not None else read_events()
    account = accounting_snapshot(rows)
    opened = {r["lot_id"]: r for r in rows if r.get("event") == "open_lot" and r.get("lot_id")}
    closes = {r["lot_id"]: r for r in rows if r.get("event") == "close_lot" and r.get("lot_id")}
    marks: Dict[str, list[Dict[str, Any]]] = {}
    for row in rows:
        if row.get("event") == "mark_lot" and row.get("lot_id"):
            marks.setdefault(row["lot_id"], []).append(row)

    positions = []
    closed_positions = []
    realized = 0.0
    unrealized = 0.0
    for lot_id, lot in opened.items():
        if lot_id in closes:
            close = closes[lot_id]
            realized += float(close.get("realized_pnl") or 0.0)
            lot_marks = marks.get(lot_id, [])
            entry = float(lot["fill_price"])
            observed_prices = [entry] + [float(x["market_price"]) for x in lot_marks] + [float(close["exit_price"])]
            try:
                opened_dt = datetime.fromisoformat(str(lot.get("timestamp") or "").replace("Z", "+00:00"))
                closed_dt = datetime.fromisoformat(str(close.get("timestamp") or "").replace("Z", "+00:00"))
                holding_hours = max(0.0, (closed_dt - opened_dt).total_seconds() / 3600.0)
            except Exception:
                holding_hours = None
            closed_positions.append({
                "lot_id": lot_id,
                "symbol": lot["symbol"],
                "level": lot.get("level"),
                "entry_price": entry,
                "exit_price": float(close["exit_price"]),
                "quantity_shares": float(lot["quantity_shares"]),
                "realized_pnl": float(close.get("realized_pnl") or 0.0),
                "fees_paid": float(close.get("fees_paid") or 0.0),
                "net_realized_pnl": float(
                    close.get("net_realized_pnl", close.get("realized_pnl") or 0.0)
                ),
                "realized_return_pct": float(close.get("realized_return_pct") or 0.0),
                "mfe_pct": round((max(observed_prices) / entry - 1.0) * 100.0, 8),
                "mae_pct": round((min(observed_prices) / entry - 1.0) * 100.0, 8),
                "opened_at": lot.get("timestamp"),
                "closed_at": close.get("timestamp"),
                "holding_hours": None if holding_hours is None else round(holding_hours, 4),
                "close_reason": close.get("reason"),
                "observation_id": lot.get("observation_id"),
                "classification": lot.get("classification"),
                "evidence_class": lot.get("evidence_class"),
                "paper_policy_version": lot.get("paper_policy_version"),
                "execution_model_version": lot.get("execution_model_version"),
            })
            continue
        lot_marks = marks.get(lot_id, [])
        latest = lot_marks[-1] if lot_marks else None
        entry = float(lot["fill_price"])
        qty = float(lot["quantity_shares"])
        mark_price = float(latest["market_price"]) if latest else entry
        lot_unrealized = (mark_price - entry) * qty
        entry_fee = float(lot.get("entry_fee") or 0.0)
        estimated_exit_fee = round(
            mark_price * qty * float(lot.get("fee_bps_per_side") or 0.0) / 10000.0,
            8,
        )
        unrealized += lot_unrealized
        observed_prices = [entry] + [float(x["market_price"]) for x in lot_marks]
        positions.append(
            {
                **lot,
                "market_price": round(mark_price, 8),
                "market_value": round(mark_price * qty, 8),
                "unrealized_pnl": round(lot_unrealized, 8),
                "fees_paid": round(entry_fee, 8),
                "estimated_exit_fee": estimated_exit_fee,
                "unrealized_net_pnl": round(
                    lot_unrealized - entry_fee - estimated_exit_fee, 8
                ),
                "unrealized_return_pct": round(((mark_price / entry) - 1.0) * 100.0, 8),
                "mfe_pct": round((max(observed_prices) / entry - 1.0) * 100.0, 8),
                "mae_pct": round((min(observed_prices) / entry - 1.0) * 100.0, 8),
            }
        )
    grouped: Dict[str, Dict[str, float]] = {}
    for pos in positions:
        g = grouped.setdefault(pos["symbol"], {"shares": 0.0, "cost": 0.0, "market_value": 0.0})
        qty = float(pos["quantity_shares"])
        g["shares"] += qty
        g["cost"] += qty * float(pos["fill_price"])
        g["market_value"] += float(pos["market_value"])
    by_symbol = []
    for symbol, g in sorted(grouped.items()):
        by_symbol.append(
            {
                "symbol": symbol,
                "shares": round(g["shares"], 12),
                "weighted_cost_basis": round(g["cost"] / g["shares"], 8) if g["shares"] else None,
                "cost_basis": round(g["cost"], 8),
                "market_value": round(g["market_value"], 8),
                "unrealized_pnl": round(g["market_value"] - g["cost"], 8),
            }
        )
    lot_details = []
    for lot_id, lot in opened.items():
        close = closes.get(lot_id)
        lot_timeline = [
            row for row in rows
            if row.get("lot_id") == lot_id and row.get("event") in {"open_lot", "mark_lot", "close_lot"}
        ]
        lot_details.append({
            "lot_id": lot_id,
            "symbol": lot.get("symbol"),
            "level": lot.get("level"),
            "status": "CLOSED" if close else "OPEN",
            "entry": lot,
            "marks": marks.get(lot_id, []),
            "terminal": close,
            "timeline": lot_timeline,
            "provenance": {
                "observation_id": lot.get("observation_id"),
                "source_timestamp": lot.get("source_timestamp"),
                "classification": lot.get("classification"),
                "evidence_class": lot.get("evidence_class"),
                "strategy_version": lot.get("strategy_version"),
                "policy_version": lot.get("policy_version"),
                "paper_policy_version": lot.get("paper_policy_version"),
                "execution_model_version": lot.get("execution_model_version"),
                "data_provenance": lot.get("data_provenance"),
                "execution": "PAPER_ONLY",
            },
        })
    return {
        "paper_policy_version": PAPER_POLICY_VERSION,
        "execution": "PAPER_ONLY",
        "summary": {
            "open_lots": len(positions),
            "closed_lots": len(closes),
            "realized_pnl": round(realized, 8),
            "unrealized_pnl": round(unrealized, 8),
            "net_realized_pnl": round(
                sum(float(row.get("net_realized_pnl", row.get("realized_pnl") or 0.0))
                    for row in closes.values()),
                8,
            ),
            "fees_paid": round(
                sum(float(row.get("fees_paid") or 0.0) for row in closes.values())
                + sum(float(row.get("entry_fee") or 0.0) for lot_id, row in opened.items()
                      if lot_id not in closes),
                8,
            ),
        },
        "positions": positions,
        "by_symbol": by_symbol,
        "closed_lots": closed_positions,
        "lots": lot_details,
        "timeline": [row for row in rows if row.get("event") in {"open_lot", "mark_lot", "close_lot"}],
        "accounting": account,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def execute_broker_order(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError("QUALITY_DIPS_PAPER_V1 is PAPER ONLY; brokerage execution is forbidden.")
