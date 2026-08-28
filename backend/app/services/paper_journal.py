"""Paper journal — sole source of truth for Hyperliquid paper stats + MFE/MAE + candidates."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)

JOURNAL_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_journal.jsonl"
CANDIDATE_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_candidates.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).isoformat()


class PaperJournal:
    def __init__(self) -> None:
        JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        CANDIDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._open: Dict[str, Dict[str, Any]] = {}
        self._load_open_from_disk()

    def _load_open_from_disk(self) -> None:
        if not JOURNAL_PATH.exists():
            return
        closed_ids = set()
        opens: Dict[str, Dict[str, Any]] = {}
        try:
            with JOURNAL_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    tid = row.get("trade_id")
                    if not tid:
                        continue
                    if str(row.get("trade_type") or "PAPER").upper() == "TEST":
                        continue
                    ev = row.get("event")
                    if ev == "open":
                        opens[tid] = row
                    elif ev == "mark" and tid in opens:
                        opens[tid]["mfe_r"] = max(float(opens[tid].get("mfe_r") or 0), float(row.get("mfe_r") or 0))
                        opens[tid]["mae_r"] = max(float(opens[tid].get("mae_r") or 0), float(row.get("mae_r") or 0))
                        if row.get("mark") is not None:
                            opens[tid]["mark"] = row.get("mark")
                        if row.get("mfe_price") is not None:
                            opens[tid]["mfe_price"] = row.get("mfe_price")
                        if row.get("mae_price") is not None:
                            opens[tid]["mae_price"] = row.get("mae_price")
                    elif ev == "close":
                        closed_ids.add(tid)
            for tid, row in opens.items():
                if tid not in closed_ids:
                    self._open[tid] = row
        except Exception as e:
            log.warning("paper journal load failed", error=str(e)[:200])

    def _append(self, path: Path, row: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")

    async def log_candidate(
        self,
        *,
        symbol: str,
        side: Optional[str],
        taken: bool,
        signal_price: float,
        score: float = 0.0,
        regime: str = "",
        features: Optional[Dict[str, Any]] = None,
        reject_reason: str = "",
        strategy: str = "perp_micro",
    ) -> str:
        cid = str(uuid.uuid4())[:12]
        row = {
            "event": "candidate",
            "candidate_id": cid,
            "timestamp": _iso(),
            "symbol": symbol.upper(),
            "side": side,
            "taken": taken,
            "signal_price": signal_price,
            "score": score,
            "regime": regime,
            "strategy": strategy,
            "features": features or {},
            "reject_reason": reject_reason,
        }
        self._append(CANDIDATE_PATH, row)
        return cid

    async def open_trade(
        self,
        *,
        symbol: str,
        side: str,
        entry: float,
        stop: float,
        tp1: float,
        tp2: float,
        risk_usd: float = 1.0,
        regime: str = "",
        notes: str = "",
        source: str = "perp_micro",
        signal_price: Optional[float] = None,
        signal_timestamp: Optional[str] = None,
        strategy: str = "mean_reversion_rsi",
        signal_score: float = 0.0,
        features: Optional[Dict[str, Any]] = None,
        tier: str = "alt",
        counts_for_live: bool = True,
        fees_bps: float = 2.0,
        slippage_bps: float = 1.0,
        trade_type: str = "PAPER",
    ) -> str:
        """Entry is ALWAYS actual_entry_price (current mark)."""
        ttype = str(trade_type or "PAPER").upper()
        if ttype == "PAPER":
            for existing_id, existing in self._open.items():
                if str(existing.get("trade_type") or "PAPER").upper() != "PAPER":
                    continue
                if (
                    str(existing.get("symbol") or "").upper() == symbol.upper()
                    and str(existing.get("side") or "").upper() == side.upper()
                ):
                    log.info(
                        "duplicate paper open prevented",
                        trade_id=existing_id,
                        symbol=symbol,
                        side=side,
                    )
                    return existing_id
        tid = str(uuid.uuid4())[:12]
        actual_entry = float(entry)
        sig_px = float(signal_price) if signal_price is not None else actual_entry
        risk = abs(actual_entry - float(stop)) or 1e-12
        ttype = str(trade_type or "PAPER").upper()
        row = {
            "event": "open",
            "trade_id": tid,
            "trade_type": ttype,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "signal_timestamp": signal_timestamp or _iso(),
            "entry_timestamp": _iso(),
            "signal_price": sig_px,
            "actual_entry_price": actual_entry,
            "stop_price": float(stop),
            "tp1_price": float(tp1),
            "tp2_price": float(tp2),
            "risk_dollars": float(risk_usd),
            "risk_price": risk,
            "position_size": float(risk_usd) / risk if risk > 0 else 0.0,
            "regime": regime,
            "regime_normalized": str((features or {}).get("regime_normalized") or regime or "UNKNOWN"),
            "strategy": strategy,
            "signal_score": float(signal_score),
            "features": features or {},
            "notes": notes,
            "source": source,
            "tier": tier,
            "counts_for_live": bool(counts_for_live) and ttype == "PAPER",
            "fees_bps": fees_bps,
            "slippage_bps": slippage_bps,
            "mfe_r": 0.0,
            "mae_r": 0.0,
            "mfe_price": actual_entry,
            "mae_price": actual_entry,
            "mark": actual_entry,
            "status": "open",
        }
        self._open[tid] = row
        self._append(JOURNAL_PATH, row)
        log.info(
            "paper open",
            trade_id=tid,
            trade_type=ttype,
            symbol=symbol,
            side=side,
            entry=actual_entry,
            signal_price=sig_px,
        )
        return tid

    def update_excursion(self, trade_id: str, mark: float) -> None:
        p = self._open.get(trade_id)
        if not p:
            return
        entry = float(p["actual_entry_price"])
        risk = float(p.get("risk_price") or abs(entry - float(p["stop_price"])) or 1e-12)
        side = p["side"]
        if side == "LONG":
            fav = (mark - entry) / risk
            adv = (entry - mark) / risk
        else:
            fav = (entry - mark) / risk
            adv = (mark - entry) / risk
        p["mark"] = mark
        if fav > float(p.get("mfe_r") or 0):
            p["mfe_r"] = fav
            p["mfe_price"] = mark
        if adv > float(p.get("mae_r") or 0):
            p["mae_r"] = adv
            p["mae_price"] = mark
        last = float(p.get("_last_persisted_mfe") or 0), float(p.get("_last_persisted_mae") or 0)
        if (p["mfe_r"] - last[0]) >= 0.05 or (p["mae_r"] - last[1]) >= 0.05:
            p["_last_persisted_mfe"] = p["mfe_r"]
            p["_last_persisted_mae"] = p["mae_r"]
            ur = fav if fav >= 0 else -adv
            self._append(
                JOURNAL_PATH,
                {
                    "event": "mark",
                    "trade_id": trade_id,
                    "timestamp": _iso(),
                    "mark": mark,
                    "mfe_r": round(float(p["mfe_r"]), 4),
                    "mae_r": round(float(p["mae_r"]), 4),
                    "mfe_price": p.get("mfe_price"),
                    "mae_price": p.get("mae_price"),
                    "unrealized_r": round(ur, 4),
                    "trade_type": p.get("trade_type", "PAPER"),
                },
            )

    async def close_trade(
        self,
        trade_id: str,
        *,
        exit_price: float,
        result: str,
        pnl_r: Optional[float] = None,
        exit_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        p = self._open.pop(trade_id, None)
        if not p:
            existing_close: Optional[Dict[str, Any]] = None
            if JOURNAL_PATH.exists():
                try:
                    with JOURNAL_PATH.open("r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            row = json.loads(line)
                            if row.get("trade_id") != trade_id:
                                continue
                            if row.get("event") == "close":
                                existing_close = row
                            elif row.get("event") == "open" and p is None:
                                p = row
                except Exception:
                    p = p
            if existing_close:
                return existing_close
            if not p:
                return {}
        entry = float(p["actual_entry_price"])
        risk = float(p.get("risk_price") or 1e-12)
        side = p["side"]
        if pnl_r is None:
            if side == "LONG":
                pnl_r = (exit_price - entry) / risk
            else:
                pnl_r = (entry - exit_price) / risk
        self._open[trade_id] = p
        self.update_excursion(trade_id, exit_price)
        p = self._open.pop(trade_id)
        fees = float(p.get("fees_bps") or 0) / 10000.0
        slip = float(p.get("slippage_bps") or 0) / 10000.0
        cost_r = (fees + slip) * 2 * (entry / risk) if risk else 0.0
        net_r = float(pnl_r) - cost_r
        opened = p.get("entry_timestamp")
        try:
            t0 = datetime.fromisoformat(opened.replace("Z", "+00:00")) if opened else _now()
        except Exception:
            t0 = _now()
        hold_s = (_now() - t0).total_seconds()
        mfe = float(p.get("mfe_r") or 0)
        mae = float(p.get("mae_r") or 0)
        close_row = {
            **{k: v for k, v in p.items() if k != "event" and not str(k).startswith("_")},
            "event": "close",
            "status": "closed",
            "exit_timestamp": _iso(),
            "actual_exit_price": float(exit_price),
            "exit_reason": exit_reason or result,
            "result": result,
            "R_multiple": round(float(pnl_r), 4),
            "gross_pnl_r": round(float(pnl_r), 4),
            "net_pnl_r": round(net_r, 4),
            "mfe_r": round(mfe, 4),
            "mae_r": round(mae, 4),
            "holding_time_sec": int(hold_s),
            "duration_sec": int(hold_s),
            "win": bool(pnl_r > 0),
            "reached_0_5r": bool(mfe + 1e-12 >= 0.5),
            "reached_1r": bool(mfe + 1e-12 >= 1.0),
            "reached_1_5r": bool(mfe + 1e-12 >= 1.5),
            "reached_1_8r": bool(mfe + 1e-12 >= 1.8),
            "reached_2r": bool(mfe + 1e-12 >= 2.0),
            "excursion_efficiency": round((float(pnl_r) / mfe), 4) if mfe > 1e-12 else 0.0,
            "mae_before_profit": round(mae, 4),
        }
        self._append(JOURNAL_PATH, close_row)
        log.info(
            "paper close",
            trade_id=trade_id,
            trade_type=p.get("trade_type", "PAPER"),
            result=result,
            pnl_r=pnl_r,
            mfe_r=close_row["mfe_r"],
            mae_r=close_row["mae_r"],
        )
        return close_row

    def list_open(self) -> List[Dict[str, Any]]:
        return [p for p in self._open.values() if str(p.get("trade_type") or "PAPER").upper() != "TEST"]

    async def stats(self) -> Dict[str, Any]:
        wins = losses = 0
        sum_r = 0.0
        sum_mfe = 0.0
        sum_mae = 0.0
        n_closed = 0
        live_wins = live_losses = 0
        live_sum_r = 0.0
        if JOURNAL_PATH.exists():
            with JOURNAL_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if row.get("event") != "close":
                        continue
                    if str(row.get("trade_type") or "PAPER").upper() == "TEST":
                        continue
                    n_closed += 1
                    r = float(row.get("net_pnl_r") or row.get("R_multiple") or 0)
                    sum_r += r
                    sum_mfe += float(row.get("mfe_r") or 0)
                    sum_mae += float(row.get("mae_r") or 0)
                    if r > 0:
                        wins += 1
                    else:
                        losses += 1
                    if row.get("counts_for_live"):
                        live_sum_r += r
                        if r > 0:
                            live_wins += 1
                        else:
                            live_losses += 1
        closed = wins + losses
        wr = (wins / closed) if closed else 0.0
        live_closed = live_wins + live_losses
        return {
            "open": len(self.list_open()),
            "closed": closed,
            "wins": wins,
            "losses": losses,
            "winrate": round(wr, 4),
            "sum_r": round(sum_r, 4),
            "avg_r": round(sum_r / closed, 4) if closed else 0.0,
            "avg_mfe_r": round(sum_mfe / n_closed, 4) if n_closed else 0.0,
            "avg_mae_r": round(sum_mae / n_closed, 4) if n_closed else 0.0,
            "live_closed": live_closed,
            "live_wins": live_wins,
            "live_losses": live_losses,
            "live_sum_r": round(live_sum_r, 4),
            "journal_path": str(JOURNAL_PATH),
            "candidates_path": str(CANDIDATE_PATH),
        }


paper_journal = PaperJournal()
