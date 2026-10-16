"""PAPER mirror for Atlas manual equity day-trade resting-limit instructions.

This module never places a broker order.  It mirrors the L1 limit Atlas tells the
operator to place, waits for a later observed mark to touch that resting limit,
and only then opens an isolated PAPER trade.  Pending limits are append-only and
durable across process restarts.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.core.logging import get_logger
from app.services.paper_execution_model import (
    DEFAULT_FEE_BPS_PER_SIDE,
    DEFAULT_SLIPPAGE_BPS_PER_SIDE,
    conservative_stop_exit,
    conservative_target_exit,
    touched_with_buffer,
)
from app.services.paper_journal import paper_journal

log = get_logger("equity_daytrade_paper_mirror")

SOURCE = "equity_daytrade_manual_auto"
STRATEGY = "equity_daytrade_manual_limit_v1"
PENDING_EVENT_PATH = Path(__file__).resolve().parents[2] / "data" / "equity_daytrade_paper_limits.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_day() -> str:
    # Caller only runs this service during the US equity session; identity is
    # intentionally day-scoped so a new session can publish a new L1.
    from app.services.day_trade_assistant import ET
    return datetime.now(ET).strftime("%Y-%m-%d")


class EquityDayTradePaperMirror:
    def __init__(self, *, pending_path: Path | None = None) -> None:
        self._pending_path = pending_path or PENDING_EVENT_PATH
        self._seeded = False
        self._pending: dict[str, dict[str, Any]] = {}
        self._terminal: set[str] = set()

    @staticmethod
    def _order_id(symbol: str, day: str) -> str:
        return f"{day}|{symbol.upper()}|L1"

    def _append(self, row: dict[str, Any]) -> None:
        self._pending_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": _now(), **row}
        with self._pending_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass

    def _seed(self) -> None:
        if self._seeded:
            return
        if self._pending_path.exists():
            with self._pending_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(row, dict):
                        continue
                    oid = str(row.get("paper_order_id") or "")
                    if not oid:
                        continue
                    event = str(row.get("event") or "").lower()
                    if event == "armed":
                        self._pending[oid] = row
                    elif event in {"filled", "cancelled"}:
                        self._pending.pop(oid, None)
                        self._terminal.add(oid)
        self._seeded = True

    def _cancel(self, oid: str, reason: str, mark: float | None = None) -> None:
        row = self._pending.pop(oid, None)
        if not row:
            return
        self._terminal.add(oid)
        self._append({
            "event": "cancelled",
            "paper_order_id": oid,
            "symbol": row.get("symbol"),
            "reason": reason,
            "mark": mark,
        })

    def _arm(self, plan: Any, day: str) -> bool:
        symbol = str(getattr(plan, "symbol", "") or "").upper()
        oid = self._order_id(symbol, day)
        if not symbol or oid in self._pending or oid in self._terminal:
            return False
        if str(getattr(plan, "action", "") or "").upper() not in {"PREPARE", "TRIGGER"}:
            return False
        try:
            limit_price = float(plan.l1)
            stop = float(plan.stop)
            tp1 = float(plan.tp1)
            tp2 = float(plan.tp2)
            signal_price = float(plan.price)
        except (TypeError, ValueError):
            return False
        if min(limit_price, stop, tp1, tp2, signal_price) <= 0:
            return False
        row = {
            "event": "armed",
            "paper_order_id": oid,
            "session_day": day,
            "symbol": symbol,
            "side": "LONG",
            "limit_price": limit_price,
            "l2_reference": float(getattr(plan, "l2", 0.0) or 0.0),
            "stop": stop,
            "tp1": tp1,
            "tp2": tp2,
            "signal_price": signal_price,
            "signal_score": float(getattr(plan, "confidence", 0.0) or 0.0),
            "phase_at_arm": str(getattr(plan, "phase", "") or "").upper(),
            "action_at_arm": str(getattr(plan, "action", "") or "").upper(),
            "source": SOURCE,
            "strategy": STRATEGY,
        }
        self._append(row)
        self._pending[oid] = {"timestamp": _now(), **row}
        return True

    async def _fill(self, oid: str, mark: float) -> bool:
        row = self._pending.get(oid)
        if not row:
            return False
        limit_price = float(row.get("limit_price") or 0.0)
        stop = float(row.get("stop") or 0.0)
        if mark <= stop:
            self._cancel(oid, "INVALIDATED_BEFORE_FILL", mark)
            return False
        if not touched_with_buffer(side="LONG", mark=mark, limit_price=limit_price):
            return False

        symbol = str(row.get("symbol") or "").upper()
        # PaperJournal's existing same-symbol/side guard remains the final
        # cross-pipeline collision protection.  A returned existing id is not
        # treated as a fill unless this mirror can identify its own order id.
        before_ids = {str(x.get("trade_id") or "") for x in paper_journal.list_open()}
        trade_id = await paper_journal.open_trade(
            symbol=symbol,
            side="LONG",
            entry=limit_price,
            stop=stop,
            tp1=float(row.get("tp1") or 0.0),
            tp2=float(row.get("tp2") or 0.0),
            signal_price=float(row.get("signal_price") or mark),
            signal_timestamp=str(row.get("timestamp") or _now()),
            signal_score=float(row.get("signal_score") or 0.0),
            source=SOURCE,
            strategy=STRATEGY,
            tier="manual",
            notes="PAPER fill of Atlas equity day-trade L1 instruction; no broker order placed.",
            features={
                "paper_order_id": oid,
                "manual_trigger_mirror": True,
                "paper_order_model": "RESTING_L1_LIMIT",
                "paper_fill_model": "LIMIT_TOUCH_PLUS_BUFFER",
                "phase_at_arm": row.get("phase_at_arm"),
                "action_at_arm": row.get("action_at_arm"),
                "l2_reference": row.get("l2_reference"),
                "setup_rr": 1.8,
            },
            counts_for_live=False,
            fees_bps=DEFAULT_FEE_BPS_PER_SIDE,
            slippage_bps=DEFAULT_SLIPPAGE_BPS_PER_SIDE,
            trade_type="PAPER",
        )
        after = {str(x.get("trade_id") or ""): x for x in paper_journal.list_open()}
        opened = after.get(str(trade_id))
        if str(trade_id) in before_ids or not opened:
            self._cancel(oid, "PAPER_POSITION_ALREADY_OPEN", mark)
            return False
        features = opened.get("features") if isinstance(opened.get("features"), dict) else {}
        if str(features.get("paper_order_id") or "") != oid:
            self._cancel(oid, "PAPER_POSITION_COLLISION", mark)
            return False

        self._append({
            "event": "filled",
            "paper_order_id": oid,
            "symbol": symbol,
            "limit_price": limit_price,
            "touch_mark": mark,
            "trade_id": trade_id,
        })
        self._pending.pop(oid, None)
        self._terminal.add(oid)
        return True

    async def sync(self, plans: Iterable[Any], *, phase: str, day: str | None = None) -> dict[str, int]:
        self._seed()
        day = day or _session_day()
        plans = list(plans)
        by_symbol = {str(getattr(p, "symbol", "") or "").upper(): p for p in plans}
        armed = filled = closed = cancelled = marked = 0

        # Manage already-filled positions first using the newest observed marks.
        for trade in list(paper_journal.list_open()):
            if str(trade.get("source") or "") != SOURCE:
                continue
            symbol = str(trade.get("symbol") or "").upper()
            plan = by_symbol.get(symbol)
            mark = float(getattr(plan, "price", 0.0) or 0.0) if plan else 0.0
            if mark <= 0:
                continue
            tid = str(trade.get("trade_id") or "")
            if not tid:
                continue
            paper_journal.update_excursion(tid, mark)
            marked += 1
            stop = float(trade.get("working_stop") or trade.get("stop_price") or 0.0)
            tp1 = float(trade.get("tp1_price") or 0.0)
            if mark <= stop:
                exit_price = conservative_stop_exit(side="LONG", mark=mark, stop_price=stop)
                await paper_journal.close_trade(tid, exit_price=exit_price, result="LOSS", exit_reason="EQUITY_DAY_STOP")
                closed += 1
            elif mark >= tp1:
                exit_price = conservative_target_exit(side="LONG", mark=mark, target_price=tp1)
                await paper_journal.close_trade(tid, exit_price=exit_price, result="WIN", exit_reason="EQUITY_DAY_TP1")
                closed += 1

        # 11:30 ET policy: no phantom fills after Atlas tells the operator to
        # cancel unfilled limits.
        if str(phase).upper() in {"MIDDAY", "CLOSED"}:
            for oid in list(self._pending):
                self._cancel(oid, "SESSION_ENTRY_CUTOFF")
                cancelled += 1
            return {"armed": 0, "pending": len(self._pending), "filled": 0, "closed": closed, "cancelled": cancelled, "marked": marked}

        # Fill only orders that existed before this scan.  Newly displayed
        # instructions are armed below and require later market evidence.
        for oid, row in list(self._pending.items()):
            if str(row.get("session_day") or "") != day:
                self._cancel(oid, "SESSION_ROLLOVER")
                cancelled += 1
                continue
            plan = by_symbol.get(str(row.get("symbol") or "").upper())
            mark = float(getattr(plan, "price", 0.0) or 0.0) if plan else 0.0
            if mark > 0 and await self._fill(oid, mark):
                filled += 1

        for plan in plans:
            if self._arm(plan, day):
                armed += 1

        return {
            "armed": armed,
            "pending": len(self._pending),
            "filled": filled,
            "closed": closed,
            "cancelled": cancelled,
            "marked": marked,
        }

    def status(self) -> dict[str, int | str | bool]:
        self._seed()
        return {
            "source": SOURCE,
            "strategy": STRATEGY,
            "pending_count": len(self._pending),
            "terminal_order_count": len(self._terminal),
            "execution": "PAPER_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }


equity_daytrade_paper_mirror = EquityDayTradePaperMirror()
