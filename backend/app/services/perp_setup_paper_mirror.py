"""Automatic paper mirror for manual perp setups.

This module mirrors qualified Atlas perp setups into the existing append-only paper
journal. It never places exchange orders and never unlocks live capital.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.paper_journal import JOURNAL_PATH, iter_jsonl, paper_journal

log = get_logger("perp_setup_paper_mirror")

ENTRY_STATES = {"L1_ACTIVE", "L2_ACTIVE", "L3_ACTIVE"}
ENTRY_TIERS = {"PRIME", "QUALIFIED"}
SOURCE = "perp_manual_auto"
STRATEGY = "perp_setup_auto_v1"


class PerpSetupPaperMirror:
    def __init__(self) -> None:
        self._seeded = False
        self._mirrored_instances: set[str] = set()

    def _instance_id(self, setup: dict[str, Any]) -> str:
        key = str(setup.get("setup_key") or "")
        first = str(setup.get("first_seen_at") or "")
        return f"{key}|{first}"

    def _seed(self) -> None:
        if self._seeded:
            return
        for row in iter_jsonl(JOURNAL_PATH):
            features = row.get("features") if isinstance(row.get("features"), dict) else {}
            instance = str(features.get("setup_instance_id") or "")
            if instance:
                self._mirrored_instances.add(instance)
        self._seeded = True

    async def sync(self, setups: list[dict[str, Any]], price_map: dict[str, float]) -> dict[str, int]:
        """Open newly-triggered setup paper trades and manage owned open trades."""
        self._seed()
        opened = closed = marked = skipped = 0

        # Manage previously opened auto-mirror positions first.
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

        # Do not duplicate any currently open PAPER symbol+side position, regardless of strategy.
        open_pairs = {
            (str(p.get("symbol") or "").upper(), str(p.get("side") or "").upper())
            for p in paper_journal.list_open()
            if str(p.get("trade_type") or "PAPER").upper() == "PAPER"
        }

        for setup in setups:
            tier = str(setup.get("tier") or "").upper()
            state = str(setup.get("state") or "").upper()
            symbol = str(setup.get("symbol") or "").upper()
            side = str(setup.get("side") or "").upper()
            instance = self._instance_id(setup)
            levels = setup.get("levels") if isinstance(setup.get("levels"), dict) else {}
            if tier not in ENTRY_TIERS or state not in ENTRY_STATES or not symbol or side not in {"LONG", "SHORT"}:
                continue
            if not instance or instance in self._mirrored_instances:
                continue
            if (symbol, side) in open_pairs:
                skipped += 1
                continue
            try:
                entry = float(levels.get("l1") or 0.0)
                stop = float(levels.get("stop") or 0.0)
                tp1 = float(levels.get("tp1") or 0.0)
                tp2 = float(levels.get("tp2") or 0.0)
                mark = float(price_map.get(symbol) or setup.get("price") or 0.0)
                if min(entry, stop, tp1, tp2, mark) <= 0:
                    skipped += 1
                    continue
                features = {
                    "setup_instance_id": instance,
                    "setup_key": setup.get("setup_key"),
                    "tier": tier,
                    "state_at_entry": state,
                    "paper_fill_model": "L1_LIMIT_ASSUMED",
                    "setup_rr": float(levels.get("target_rr") or 1.8),
                    "volatility_pct": setup.get("volatility_pct"),
                    "momentum_pct": setup.get("momentum_pct"),
                    "trend_pct": setup.get("trend_pct"),
                }
                await paper_journal.open_trade(
                    symbol=symbol,
                    side=side,
                    entry=entry,
                    stop=stop,
                    tp1=tp1,
                    tp2=tp2,
                    signal_price=mark,
                    signal_score=float(setup.get("score") or 0.0),
                    source=SOURCE,
                    strategy=STRATEGY,
                    tier=tier.lower(),
                    notes="Auto paper mirror of Atlas manual perp setup; no live order placed.",
                    features=features,
                    counts_for_live=False,
                    fees_bps=2.0,
                    slippage_bps=1.0,
                    trade_type="PAPER",
                )
                self._mirrored_instances.add(instance)
                open_pairs.add((symbol, side))
                opened += 1
            except Exception as exc:
                skipped += 1
                log.warning("Auto paper setup mirror skipped", symbol=symbol, error=str(exc)[:160])

        return {"opened": opened, "closed": closed, "marked": marked, "skipped": skipped}


perp_setup_paper_mirror = PerpSetupPaperMirror()
