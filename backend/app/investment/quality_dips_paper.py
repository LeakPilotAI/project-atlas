"""Durable PAPER-only lifecycle journal for Quality Dips V3.

This module records simulated investment decisions/lots only. It has no broker
adapter and cannot submit real orders. Sizing is explicit: callers must supply a
positive PAPER notional rather than inheriting or inventing live buying power.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
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


def record_decision(
    observation: Dict[str, Any],
    *,
    decision: str,
    reason: str = "",
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
        "classification": observation.get("classification"),
        "source_timestamp": observation.get("source_timestamp"),
        "evidence_class": observation.get("evidence_class"),
        "execution": "PAPER_ONLY",
        "broker_order_created": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
    return _append(row, Path(path))


def open_lot(
    observation: Dict[str, Any],
    *,
    level: str,
    paper_notional_dollars: Any,
    fill_price: Optional[Any] = None,
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
    lot_id = _event_id("lot", observation_id, level, PAPER_POLICY_VERSION)
    for row in read_events(path):
        if row.get("event") == "open_lot" and row.get("lot_id") == lot_id:
            return row
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
        path=path,
    )
    lots = [
        open_lot(
            observation,
            level=level,
            paper_notional_dollars=notionals[level],
            fill_price=observation.get("price"),
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
            "timestamp": ts,
            "symbol": lot["symbol"],
            "market_price": round(price, 8),
            "market_value": round(price * qty, 8),
            "unrealized_pnl": round(unrealized, 8),
            "unrealized_return_pct": round(((price / entry) - 1.0) * 100.0, 8),
            "execution": "PAPER_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        },
        Path(path),
    )


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
    return _append(
        {
            "schema_version": 1,
            "event": "close_lot",
            "event_id": _event_id("close_lot", lot_id),
            "lot_id": lot_id,
            "timestamp": str(closed_at or _now()),
            "symbol": lot["symbol"],
            "exit_price": round(price, 8),
            "quantity_shares": qty,
            "realized_pnl": round(pnl, 8),
            "realized_return_pct": round(((price / entry) - 1.0) * 100.0, 8),
            "reason": str(reason or "UNSPECIFIED"),
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
        unrealized += lot_unrealized
        observed_prices = [entry] + [float(x["market_price"]) for x in lot_marks]
        positions.append(
            {
                **lot,
                "market_price": round(mark_price, 8),
                "market_value": round(mark_price * qty, 8),
                "unrealized_pnl": round(lot_unrealized, 8),
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
        },
        "positions": positions,
        "by_symbol": by_symbol,
        "closed_lots": closed_positions,
        "lots": lot_details,
        "timeline": [row for row in rows if row.get("event") in {"open_lot", "mark_lot", "close_lot"}],
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def execute_broker_order(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError("QUALITY_DIPS_PAPER_V1 is PAPER ONLY; brokerage execution is forbidden.")
