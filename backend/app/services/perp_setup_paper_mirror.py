"""Automatic paper mirror for manual perp resting-limit instructions.

Real Hyperliquid/Axiom execution remains manual-only. When Atlas tells the user to
place a verified resting L1 limit, this module arms the same PAPER limit. A paper
position is opened only after a later market mark actually touches that limit.
Pending paper limits are durable across restarts; no PREPARE state is treated as a
fill and no exchange order is ever submitted here.

Parity rule: every fresh setup that Atlas exposes as a manual PLACE_RESTING_L1
instruction is eligible for the same auto-paper mirror, regardless of display tier.
This keeps manual opportunity logging and paper evidence aligned.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.paper_journal import JOURNAL_PATH, iter_jsonl, paper_journal
from app.trading_core.perp_board import build_perp_board

log = get_logger("perp_setup_paper_mirror")

SOURCE = "perp_manual_auto"
STRATEGY = "perp_setup_auto_v2_resting_limit"
PENDING_EVENT_PATH = Path(__file__).resolve().parents[2] / "data" / "perp_setup_paper_limits.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PerpSetupPaperMirror:
    def __init__(self, *, pending_path: Path | None = None) -> None:
        self._seeded = False
        self._mirrored_instances: set[str] = set()
        self._pending: dict[str, dict[str, Any]] = {}
        self._pending_path = pending_path or PENDING_EVENT_PATH

    def _instance_id(self, setup: dict[str, Any]) -> str:
        key = str(setup.get("setup_key") or "")
        first = str(setup.get("first_seen_at") or "")
        epoch = str(setup.get("paper_mirror_epoch_at") or first)
        return f"{key}|{first}|{epoch}"

    def _append_pending_event(self, row: dict[str, Any]) -> None:
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
        for row in iter_jsonl(JOURNAL_PATH):
            features = row.get("features") if isinstance(row.get("features"), dict) else {}
            instance = str(features.get("setup_instance_id") or "")
            if instance:
                self._mirrored_instances.add(instance)

        pending: dict[str, dict[str, Any]] = {}
        for row in iter_jsonl(self._pending_path):
            if row.get("event") == "_malformed":
                continue
            instance = str(row.get("setup_instance_id") or "")
            if not instance:
                continue
            event = str(row.get("event") or "").lower()
            if event == "armed":
                pending[instance] = dict(row)
            elif event in {"filled", "cancelled"}:
                pending.pop(instance, None)
                if event == "filled":
                    self._mirrored_instances.add(instance)
        self._pending = pending
        self._seeded = True

    @staticmethod
    def _instruction(setup: dict[str, Any]) -> dict[str, Any]:
        board = build_perp_board([setup], limit=1)
        if not board:
            return {}
        instruction = board[0].get("manual_instruction")
        return dict(instruction) if isinstance(instruction, dict) else {}

    @staticmethod
    def _limit_touched(*, side: str, mark: float, limit_price: float) -> bool:
        return (side == "LONG" and mark <= limit_price) or (side == "SHORT" and mark >= limit_price)

    @staticmethod
    def _invalidated_before_fill(*, side: str, mark: float, stop: float) -> bool:
        return (side == "LONG" and mark <= stop) or (side == "SHORT" and mark >= stop)

    @staticmethod
    def _crossed_from_prior_resting(setup: dict[str, Any], *, mark: float) -> bool:
        """Prove a published resting L1 was crossed between consecutive snapshots.

        This is not an inferred live-account fill. It is only a PAPER recovery path
        for a manual instruction Atlas had already published on the prior snapshot.
        """
        if bool(setup.get("previous_discovery_stale")):
            return False
        state = str(setup.get("state") or "").upper()
        previous_state = str(setup.get("previous_state") or "").upper()
        if state not in {"L1_ACTIVE", "L2_ACTIVE", "L3_ACTIVE"}:
            return False
        if previous_state not in {"PREPARE", "L1_ACTIVE", "L2_ACTIVE", "L3_ACTIVE"}:
            return False
        levels = setup.get("levels") if isinstance(setup.get("levels"), dict) else {}
        try:
            previous_price = float(setup.get("previous_price") or 0.0)
            l1 = float(levels.get("l1") or 0.0)
        except (TypeError, ValueError):
            return False
        if min(previous_price, l1, mark) <= 0:
            return False
        side = str(setup.get("side") or "").upper()
        if side == "LONG":
            return previous_price > l1 and mark <= l1
        if side == "SHORT":
            return previous_price < l1 and mark >= l1
        return False

    def _arm(self, setup: dict[str, Any], *, mark: float, instruction: dict[str, Any]) -> bool:
        tier = str(setup.get("tier") or "").upper()
        symbol = str(setup.get("symbol") or "").upper()
        side = str(setup.get("side") or "").upper()
        instance = self._instance_id(setup)
        levels = setup.get("levels") if isinstance(setup.get("levels"), dict) else {}
        try:
            limit_price = float(instruction.get("limit_price") or levels.get("l1") or 0.0)
            stop = float(levels.get("stop") or 0.0)
            tp1 = float(levels.get("tp1") or 0.0)
            tp2 = float(levels.get("tp2") or 0.0)
        except (TypeError, ValueError):
            return False
        if (
            not instance
            or instance in self._mirrored_instances
            or instance in self._pending
            or symbol == ""
            or side not in {"LONG", "SHORT"}
            or str(instruction.get("action") or "") != "PLACE_RESTING_L1"
            or min(limit_price, stop, tp1, tp2, mark) <= 0
        ):
            return False
        row = {
            "event": "armed",
            "setup_instance_id": instance,
            "paper_mirror_epoch_at": setup.get("paper_mirror_epoch_at"),
            "setup_key": setup.get("setup_key"),
            "symbol": symbol,
            "side": side,
            "tier": tier,
            "limit_price": limit_price,
            "stop": stop,
            "tp1": tp1,
            "tp2": tp2,
            "signal_price": mark,
            "signal_score": float(setup.get("score") or 0.0),
            "target_rr": float(levels.get("target_rr") or 1.8),
            "volatility_pct": setup.get("volatility_pct"),
            "momentum_pct": setup.get("momentum_pct"),
            "trend_pct": setup.get("trend_pct"),
            "state_at_arm": str(setup.get("state") or "").upper(),
            "manual_trigger_mirror": True,
            "recovered_limit_cross": bool(instruction.get("recovered_limit_cross")),
            "source": SOURCE,
            "strategy": STRATEGY,
        }
        self._append_pending_event(row)
        self._pending[instance] = {"timestamp": _now(), **row}
        log.info(
            "Auto paper resting limit armed",
            symbol=symbol,
            side=side,
            tier=tier,
            limit_price=limit_price,
            paper_mirror_epoch_at=setup.get("paper_mirror_epoch_at"),
            recovered_limit_cross=bool(instruction.get("recovered_limit_cross")),
        )
        return True

    def _cancel_pending(self, instance: str, *, reason: str, mark: float | None = None) -> None:
        row = self._pending.pop(instance, None)
        if not row:
            return
        self._append_pending_event({
            "event": "cancelled",
            "setup_instance_id": instance,
            "setup_key": row.get("setup_key"),
            "symbol": row.get("symbol"),
            "side": row.get("side"),
            "reason": reason,
            "mark": mark,
        })
        log.info("Auto paper resting limit cancelled", symbol=row.get("symbol"), reason=reason)

    async def _fill_pending(self, instance: str, *, mark: float) -> bool:
        row = self._pending.get(instance)
        if not row:
            return False
        symbol = str(row.get("symbol") or "").upper()
        side = str(row.get("side") or "").upper()
        limit_price = float(row.get("limit_price") or 0.0)
        stop = float(row.get("stop") or 0.0)
        tp1 = float(row.get("tp1") or 0.0)
        tp2 = float(row.get("tp2") or 0.0)
        if min(mark, limit_price, stop, tp1, tp2) <= 0:
            return False
        if self._invalidated_before_fill(side=side, mark=mark, stop=stop):
            self._cancel_pending(instance, reason="INVALIDATED_BEFORE_FILL", mark=mark)
            return False
        if not self._limit_touched(side=side, mark=mark, limit_price=limit_price):
            return False

        open_pairs = {
            (str(p.get("symbol") or "").upper(), str(p.get("side") or "").upper())
            for p in paper_journal.list_open()
            if str(p.get("trade_type") or "PAPER").upper() == "PAPER"
        }
        if (symbol, side) in open_pairs:
            self._cancel_pending(instance, reason="PAPER_POSITION_ALREADY_OPEN", mark=mark)
            return False

        features = {
            "setup_instance_id": instance,
            "paper_mirror_epoch_at": row.get("paper_mirror_epoch_at"),
            "setup_key": row.get("setup_key"),
            "tier": row.get("tier"),
            "state_at_arm": row.get("state_at_arm"),
            "manual_trigger_mirror": True,
            "recovered_limit_cross": bool(row.get("recovered_limit_cross")),
            "paper_order_model": "RESTING_L1_LIMIT",
            "paper_fill_model": "LIMIT_TOUCH",
            "paper_order_armed_at": row.get("timestamp"),
            "paper_filled_at": _now(),
            "setup_rr": float(row.get("target_rr") or 1.8),
            "volatility_pct": row.get("volatility_pct"),
            "momentum_pct": row.get("momentum_pct"),
            "trend_pct": row.get("trend_pct"),
        }
        await paper_journal.open_trade(
            symbol=symbol,
            side=side,
            entry=limit_price,
            stop=stop,
            tp1=tp1,
            tp2=tp2,
            signal_price=float(row.get("signal_price") or mark),
            signal_timestamp=str(row.get("timestamp") or _now()),
            signal_score=float(row.get("signal_score") or 0.0),
            source=SOURCE,
            strategy=STRATEGY,
            tier=str(row.get("tier") or "manual").lower(),
            notes="Auto paper fill of Atlas manual resting L1 instruction; no live order placed.",
            features=features,
            counts_for_live=False,
            fees_bps=2.0,
            slippage_bps=1.0,
            trade_type="PAPER",
        )
        self._append_pending_event({
            "event": "filled",
            "setup_instance_id": instance,
            "setup_key": row.get("setup_key"),
            "symbol": symbol,
            "side": side,
            "limit_price": limit_price,
            "touch_mark": mark,
            "recovered_limit_cross": bool(row.get("recovered_limit_cross")),
        })
        self._pending.pop(instance, None)
        self._mirrored_instances.add(instance)
        log.info(
            "Auto paper resting limit filled",
            symbol=symbol,
            side=side,
            entry=limit_price,
            touch_mark=mark,
            recovered_limit_cross=bool(row.get("recovered_limit_cross")),
        )
        return True

    def status(self) -> dict[str, int]:
        self._seed()
        rows = iter_jsonl(JOURNAL_PATH)
        source_open_ids: set[str] = set()
        opened_ids: set[str] = set()
        closed_ids: set[str] = set()
        source_ids: set[str] = set()
        for row in rows:
            tid = str(row.get("trade_id") or "")
            if not tid:
                continue
            if row.get("event") == "open" and str(row.get("source") or "") == SOURCE:
                source_ids.add(tid)
                opened_ids.add(tid)
                source_open_ids.add(tid)
            elif row.get("event") == "close" and tid in source_ids:
                closed_ids.add(tid)
                source_open_ids.discard(tid)
        return {
            "pending_count": len(self._pending),
            "open_count": len(source_open_ids),
            "opened_total": len(opened_ids),
            "closed_total": len(closed_ids),
        }

    async def sync(self, setups: list[dict[str, Any]], price_map: dict[str, float]) -> dict[str, int]:
        """Mirror every fresh manual resting-limit instruction into PAPER."""
        self._seed()
        opened = closed = marked = skipped = armed = filled = cancelled = recovered = 0

        # Manage previously filled auto-mirror positions first.
        for trade in list(paper_journal.list_open()):
            if str(trade.get("source") or "") != SOURCE:
                continue
            symbol = str(trade.get("symbol") or "").upper()
            mark = price_map.get(symbol)
            if mark is None or mark <= 0:
                continue
            tid = str(trade.get("trade_id") or "")
            if not tid:
                continue
            paper_journal.update_excursion(tid, float(mark))
            marked += 1
            side = str(trade.get("side") or "").upper()
            stop = float(trade.get("working_stop") or trade.get("stop_price") or 0.0)
            tp1 = float(trade.get("tp1_price") or 0.0)
            hit_stop = (side == "LONG" and mark <= stop) or (side == "SHORT" and mark >= stop)
            hit_tp1 = (side == "LONG" and mark >= tp1) or (side == "SHORT" and mark <= tp1)
            if hit_stop:
                await paper_journal.close_trade(tid, exit_price=float(mark), result="LOSS", exit_reason="SETUP_STOP")
                closed += 1
            elif hit_tp1:
                await paper_journal.close_trade(tid, exit_price=float(mark), result="WIN", exit_reason="SETUP_TP1")
                closed += 1

        # Cancel only explicit terminal invalidations. Discovery-stale rows deliberately
        # keep an already-armed resting order unchanged, matching the manual board text.
        current_by_instance = {self._instance_id(s): s for s in setups if self._instance_id(s)}
        for instance in list(self._pending):
            setup = current_by_instance.get(instance)
            if setup and str(setup.get("state") or "").upper() in {"INVALIDATED", "TP1_HIT", "TP2_HIT"}:
                self._cancel_pending(instance, reason=f"SETUP_{str(setup.get('state')).upper()}")
                cancelled += 1

        # Arm exactly what the manual board tells the user to place, regardless of
        # PRIME / QUALIFIED / WATCH presentation tier. paper_mirror_epoch_at makes
        # a later re-entry into a manual opportunity a distinct paper experiment.
        # If a resting L1 was published on the prior snapshot and the next snapshot
        # proves price crossed it, recover that paper fill even if the current board
        # can no longer advertise the now-marketable order.
        for setup in setups:
            symbol = str(setup.get("symbol") or "").upper()
            mark = float(price_map.get(symbol) or setup.get("price") or setup.get("mark") or 0.0)
            if mark <= 0:
                skipped += 1
                continue
            instruction = self._instruction(setup)
            if str(instruction.get("action") or "") != "PLACE_RESTING_L1" and self._crossed_from_prior_resting(setup, mark=mark):
                levels = setup.get("levels") if isinstance(setup.get("levels"), dict) else {}
                instruction = {
                    "action": "PLACE_RESTING_L1",
                    "limit_price": levels.get("l1"),
                    "recovered_limit_cross": True,
                }
            if self._arm(setup, mark=mark, instruction=instruction):
                armed += 1
                if bool(instruction.get("recovered_limit_cross")):
                    recovered += 1

        # A later (or same-pass) touch converts a pending paper limit into an open
        # PAPER position. PREPARE itself is never an assumed fill.
        for instance, row in list(self._pending.items()):
            symbol = str(row.get("symbol") or "").upper()
            mark = float(price_map.get(symbol) or 0.0)
            if mark <= 0:
                continue
            before = instance in self._pending
            try:
                if await self._fill_pending(instance, mark=mark):
                    filled += 1
                    opened += 1
                elif before and instance not in self._pending:
                    cancelled += 1
            except Exception as exc:
                skipped += 1
                log.warning("Auto paper resting-limit fill skipped", symbol=symbol, error=str(exc)[:160])

        return {
            "armed": armed,
            "pending": len(self._pending),
            "filled": filled,
            "opened": opened,
            "closed": closed,
            "marked": marked,
            "cancelled": cancelled,
            "recovered": recovered,
            "skipped": skipped,
        }


perp_setup_paper_mirror = PerpSetupPaperMirror()
