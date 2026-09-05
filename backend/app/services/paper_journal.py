"""Paper journal — sole source of truth for Hyperliquid paper stats + MFE/MAE + candidates."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)

JOURNAL_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_journal.jsonl"
CANDIDATE_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_candidates.jsonl"
SESSION_ID = "desk-v2"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).isoformat()


def iter_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Parse jsonl line-by-line. A truncated/corrupt line does not abort the file."""
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                rows.append({"event": "_malformed", "line": i, "raw": raw[:200]})
                continue
            if isinstance(row, dict):
                rows.append(row)
            else:
                rows.append({"event": "_malformed", "line": i, "raw": raw[:200]})
    return rows


class PaperJournal:
    def __init__(self) -> None:
        JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        CANDIDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._open: Dict[str, Dict[str, Any]] = {}
        self._malformed_lines: List[Dict[str, Any]] = []
        self._last_reconcile: Dict[str, Any] = {}
        self._load_open_from_disk()

    def _load_open_from_disk(self) -> None:
        self._open = {}
        self._malformed_lines = []
        if not JOURNAL_PATH.exists():
            return
        closed_ids = set()
        opens: Dict[str, Dict[str, Any]] = {}
        for row in iter_jsonl(JOURNAL_PATH):
            if row.get("event") == "_malformed":
                self._malformed_lines.append(row)
                continue
            tid = row.get("trade_id")
            if not tid:
                continue
            if str(row.get("trade_type") or "PAPER").upper() == "TEST":
                continue
            ev = row.get("event")
            if ev == "open":
                opens[tid] = row
            elif ev == "mark" and tid in opens:
                try:
                    opens[tid]["mfe_r"] = max(float(opens[tid].get("mfe_r") or 0), float(row.get("mfe_r") or 0))
                    opens[tid]["mae_r"] = max(float(opens[tid].get("mae_r") or 0), float(row.get("mae_r") or 0))
                except (TypeError, ValueError):
                    pass
                if row.get("mark") is not None:
                    opens[tid]["mark"] = row.get("mark")
                if row.get("mfe_price") is not None:
                    opens[tid]["mfe_price"] = row.get("mfe_price")
                if row.get("mae_price") is not None:
                    opens[tid]["mae_price"] = row.get("mae_price")
                if row.get("be_armed"):
                    opens[tid]["be_armed"] = True
                if row.get("working_stop") is not None:
                    opens[tid]["working_stop"] = row.get("working_stop")
                if row.get("exit_mode"):
                    opens[tid]["exit_mode"] = row.get("exit_mode")
            elif ev == "close":
                closed_ids.add(tid)
        for tid, row in opens.items():
            if tid not in closed_ids:
                self._open[tid] = row

    def reload(self) -> None:
        """Re-read journal from disk. Idempotent. Used after crash-sim / tests."""
        self._load_open_from_disk()

    def flush(self) -> None:
        """Append-only journal is already durable per write (flush+fsync)."""
        return None

    def _append(self, path: Path, row: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, default=str) + "\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass

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
            "exit_mode": str((features or {}).get("exit_mode") or "SCALP"),
            "scalp_tp_r": float((features or {}).get("scalp_tp_r") or 1.0),
            "be_after_r": float(
                (features or {}).get("be_after_r")
                if (features or {}).get("be_after_r") is not None
                else 0.5
            ),
            "setup_rr": float((features or {}).get("setup_rr") or 1.8),
            "initial_stop": float(stop),
            "working_stop": float(stop),
            "be_armed": False,
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

    def update_excursion(self, trade_id: str, mark: float, *, force: bool = False) -> None:
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
        if force or (p["mfe_r"] - last[0]) >= 0.05 or (p["mae_r"] - last[1]) >= 0.05:
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

    def note_be_armed(self, trade_id: str, working_stop: float) -> None:
        """Append-only BE arm. Does not rewrite the open event."""
        p = self._open.get(trade_id)
        if not p:
            return
        p["be_armed"] = True
        p["working_stop"] = float(working_stop)
        self._append(
            JOURNAL_PATH,
            {
                "event": "mark",
                "trade_id": trade_id,
                "timestamp": _iso(),
                "mark": p.get("mark"),
                "mfe_r": round(float(p.get("mfe_r") or 0), 4),
                "mae_r": round(float(p.get("mae_r") or 0), 4),
                "be_armed": True,
                "working_stop": float(working_stop),
                "exit_mode": p.get("exit_mode") or "SCALP",
                "trade_type": p.get("trade_type", "PAPER"),
            },
        )

    def persist_open_marks(self) -> int:
        """Force a mark event for every in-memory open. Used on graceful shutdown."""
        n = 0
        for tid, p in list(self._open.items()):
            mark = p.get("mark")
            if mark is None:
                continue
            try:
                self.update_excursion(tid, float(mark), force=True)
                n += 1
            except Exception:
                pass
        return n

    def reconcile_from_disk(self) -> Dict[str, Any]:
        """Journal file is source of truth.

        - Add disk-only opens into memory (crash/orphan recovery).
        - Drop memory rows whose close is already on disk.
        - Preserve in-memory MFE/MAE when the trade is still open.
        Does not rewrite historical records.
        """
        closed_ids = set()
        opens: Dict[str, Dict[str, Any]] = {}
        malformed: List[Dict[str, Any]] = []
        open_counts: Dict[str, int] = {}
        if JOURNAL_PATH.exists():
            for row in iter_jsonl(JOURNAL_PATH):
                if row.get("event") == "_malformed":
                    malformed.append(row)
                    continue
                tid = row.get("trade_id")
                if not tid:
                    continue
                if str(row.get("trade_type") or "PAPER").upper() == "TEST":
                    continue
                ev = row.get("event")
                if ev == "open":
                    opens[tid] = row
                    open_counts[tid] = open_counts.get(tid, 0) + 1
                elif ev == "mark" and tid in opens:
                    try:
                        opens[tid]["mfe_r"] = max(
                            float(opens[tid].get("mfe_r") or 0), float(row.get("mfe_r") or 0)
                        )
                        opens[tid]["mae_r"] = max(
                            float(opens[tid].get("mae_r") or 0), float(row.get("mae_r") or 0)
                        )
                    except (TypeError, ValueError):
                        pass
                    if row.get("mark") is not None:
                        opens[tid]["mark"] = row.get("mark")
                    if row.get("mfe_price") is not None:
                        opens[tid]["mfe_price"] = row.get("mfe_price")
                    if row.get("mae_price") is not None:
                        opens[tid]["mae_price"] = row.get("mae_price")
                elif ev == "close":
                    closed_ids.add(tid)
        self._malformed_lines = malformed
        dropped_closed = 0
        for tid in list(self._open):
            if tid in closed_ids:
                self._open.pop(tid, None)
                dropped_closed += 1
        added = 0
        for tid, row in opens.items():
            if tid in closed_ids:
                continue
            if tid not in self._open:
                self._open[tid] = row
                added += 1
            else:
                mem = self._open[tid]
                try:
                    mem["mfe_r"] = max(float(mem.get("mfe_r") or 0), float(row.get("mfe_r") or 0))
                    mem["mae_r"] = max(float(mem.get("mae_r") or 0), float(row.get("mae_r") or 0))
                except (TypeError, ValueError):
                    pass
                if mem.get("entry_timestamp") is None:
                    mem["entry_timestamp"] = row.get("entry_timestamp")
        duplicates = sum(1 for tid, n in open_counts.items() if n > 1 and tid not in closed_ids)
        self._last_reconcile = {
            "added": added,
            "dropped_closed": dropped_closed,
            "already_closed": len(closed_ids),
            "duplicates": duplicates,
            "malformed": len(malformed),
            "persisted_open": len(self.list_open()),
        }
        return self._last_reconcile

    def _scan_trade(self, trade_id: str) -> tuple:
        open_row: Optional[Dict[str, Any]] = None
        close_row: Optional[Dict[str, Any]] = None
        if not JOURNAL_PATH.exists():
            return open_row, close_row
        for row in iter_jsonl(JOURNAL_PATH):
            if row.get("event") == "_malformed":
                continue
            if row.get("trade_id") != trade_id:
                continue
            ev = row.get("event")
            if ev == "open":
                open_row = row
            elif ev == "close":
                close_row = row
        return open_row, close_row

    async def close_trade(
        self,
        trade_id: str,
        *,
        exit_price: float,
        result: str,
        pnl_r: Optional[float] = None,
        exit_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        disk_open, existing_close = self._scan_trade(trade_id)
        if existing_close:
            self._open.pop(trade_id, None)
            return existing_close
        p = self._open.get(trade_id) or disk_open
        if not p:
            return {}
        self._open[trade_id] = p
        entry = float(p["actual_entry_price"])
        risk = float(p.get("risk_price") or 1e-12)
        side = p["side"]
        if pnl_r is None:
            if side == "LONG":
                pnl_r = (exit_price - entry) / risk
            else:
                pnl_r = (entry - exit_price) / risk
        self.update_excursion(trade_id, exit_price, force=True)
        p = self._open[trade_id]
        fees = float(p.get("fees_bps") or 0) / 10000.0
        slip = float(p.get("slippage_bps") or 0) / 10000.0
        cost_r = (fees + slip) * 2 * (entry / risk) if risk else 0.0
        net_r = float(pnl_r) - cost_r
        result_u = str(result or "").upper()
        if result_u in ("BE", "SCRATCH"):
            net_r = 0.0
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
            "win": bool(net_r > 0),
            "scratch": result_u in ("BE", "SCRATCH") or abs(net_r) < 1e-9,
            "reached_0_5r": bool(mfe + 1e-12 >= 0.5),
            "reached_1r": bool(mfe + 1e-12 >= 1.0),
            "reached_1_5r": bool(mfe + 1e-12 >= 1.5),
            "reached_1_8r": bool(mfe + 1e-12 >= 1.8),
            "reached_2r": bool(mfe + 1e-12 >= 2.0),
            "excursion_efficiency": round((float(pnl_r) / mfe), 4) if mfe > 1e-12 else 0.0,
            "mae_before_profit": round(mae, 4),
        }
        self._append(JOURNAL_PATH, close_row)
        self._open.pop(trade_id, None)
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

    def current_session(self) -> Dict[str, Any]:
        """Last session_start in the journal. Missing → all-time window."""
        started_at = None
        session_id = None
        label = None
        note = None
        if JOURNAL_PATH.exists():
            for row in iter_jsonl(JOURNAL_PATH):
                if row.get("event") != "session_start":
                    continue
                started_at = row.get("started_at") or row.get("timestamp")
                session_id = row.get("session_id")
                label = row.get("label")
                note = row.get("note")
        if not started_at:
            return {
                "session_id": "all-time",
                "started_at": None,
                "label": "all-time (no session marker)",
                "note": "Stats count every PAPER close. Journal was not reset.",
            }
        return {
            "session_id": session_id or "unknown",
            "started_at": started_at,
            "label": label or session_id,
            "note": note or "Prior closes remain in the journal.",
        }

    def start_session(
        self,
        *,
        session_id: str,
        label: str,
        note: str = "",
        prior_closed: int = 0,
    ) -> Dict[str, Any]:
        """Append a session marker. Never deletes or rewrites closes."""
        row = {
            "event": "session_start",
            "session_id": session_id,
            "label": label,
            "note": note,
            "started_at": _iso(),
            "timestamp": _iso(),
            "prior_closed_archived": int(prior_closed),
        }
        self._append(JOURNAL_PATH, row)
        log.info(
            "paper session started",
            session_id=session_id,
            prior_closed_archived=prior_closed,
        )
        return row

    def bootstrap_session(
        self,
        session_id: str = SESSION_ID,
        *,
        label: str = "Desktop testing window",
        note: str = "New testing window. Prior PAPER closes stay in the journal and all-time research.",
    ) -> Dict[str, Any]:
        cur = self.current_session()
        if cur.get("session_id") == session_id and cur.get("started_at"):
            return {"created": False, **cur}
        prior = 0
        if JOURNAL_PATH.exists():
            for row in iter_jsonl(JOURNAL_PATH):
                if row.get("event") != "close":
                    continue
                if str(row.get("trade_type") or "PAPER").upper() == "TEST":
                    continue
                prior += 1
        started = self.start_session(
            session_id=session_id,
            label=label,
            note=note,
            prior_closed=prior,
        )
        return {"created": True, "prior_closed_archived": prior, **started}

    def recovery_report(self) -> Dict[str, Any]:
        opens = self.list_open()
        rec = dict(self._last_reconcile or {})
        return {
            "title": "ATLAS PAPER RECOVERY",
            "persisted_open": len(opens),
            "recovered": len(opens),
            "already_closed": int(rec.get("already_closed") or 0),
            "malformed": len(self._malformed_lines),
            "malformed_lines": list(self._malformed_lines),
            "duplicates": int(rec.get("duplicates") or 0),
            "added_from_disk": int(rec.get("added") or 0),
            "open_ids": [r.get("trade_id") for r in opens],
            "note": "Journal is source of truth. OPEN ≠ hung. MARKET_DATA_UNAVAILABLE ≠ CLOSED.",
        }

    async def stats(self) -> Dict[str, Any]:
        session = self.current_session()
        started = session.get("started_at")
        all_rows: List[Dict[str, Any]] = []
        session_rows: List[Dict[str, Any]] = []
        if JOURNAL_PATH.exists():
            for row in iter_jsonl(JOURNAL_PATH):
                if row.get("event") != "close":
                    continue
                if str(row.get("trade_type") or "PAPER").upper() == "TEST":
                    continue
                all_rows.append(row)
                ts = str(row.get("exit_timestamp") or row.get("timestamp") or "")
                if not started or ts >= str(started):
                    session_rows.append(row)
        primary = self._tally(session_rows)
        all_time = self._tally(all_rows)
        primary.update(
            {
                "open": len(self.list_open()),
                "journal_path": str(JOURNAL_PATH),
                "candidates_path": str(CANDIDATE_PATH),
                "session": session,
                "all_time": {
                    "closed": all_time["closed"],
                    "wins": all_time["wins"],
                    "losses": all_time["losses"],
                    "scratches": all_time["scratches"],
                    "winrate": all_time["winrate"],
                    "sum_r": all_time["sum_r"],
                    "avg_r": all_time["avg_r"],
                    "note": "Archived. Not deleted. Used by research/edge. Not mixed into session WR.",
                },
            }
        )
        return primary

    @staticmethod
    def _tally(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        wins = losses = scratches = 0
        sum_r = 0.0
        sum_mfe = 0.0
        sum_mae = 0.0
        n_closed = 0
        live_wins = live_losses = 0
        live_sum_r = 0.0
        scalp_n = scalp_wins = scalp_losses = scalp_scratch = 0
        scalp_sum_r = 0.0
        for row in rows:
            n_closed += 1
            r = float(row.get("net_pnl_r") or row.get("R_multiple") or 0)
            sum_r += r
            sum_mfe += float(row.get("mfe_r") or 0)
            sum_mae += float(row.get("mae_r") or 0)
            is_scratch = bool(row.get("scratch")) or str(row.get("result") or "").upper() in (
                "BE",
                "SCRATCH",
            )
            if is_scratch:
                scratches += 1
            elif r > 0:
                wins += 1
            else:
                losses += 1
            if row.get("counts_for_live"):
                live_sum_r += r
                if r > 0:
                    live_wins += 1
                else:
                    live_losses += 1
            if str(row.get("exit_mode") or "").upper() == "SCALP":
                scalp_n += 1
                scalp_sum_r += r
                if is_scratch:
                    scalp_scratch += 1
                elif r > 0:
                    scalp_wins += 1
                else:
                    scalp_losses += 1
        closed = wins + losses + scratches
        wr = (wins / closed) if closed else 0.0
        live_closed = live_wins + live_losses
        scalp_wr = (scalp_wins / scalp_n) if scalp_n else 0.0
        return {
            "closed": closed,
            "wins": wins,
            "losses": losses,
            "scratches": scratches,
            "winrate": round(wr, 4),
            "sum_r": round(sum_r, 4),
            "avg_r": round(sum_r / closed, 4) if closed else 0.0,
            "avg_mfe_r": round(sum_mfe / n_closed, 4) if n_closed else 0.0,
            "avg_mae_r": round(sum_mae / n_closed, 4) if n_closed else 0.0,
            "live_closed": live_closed,
            "live_wins": live_wins,
            "live_losses": live_losses,
            "live_sum_r": round(live_sum_r, 4),
            "scalp_cohort": {
                "n": scalp_n,
                "wins": scalp_wins,
                "losses": scalp_losses,
                "scratches": scalp_scratch,
                "winrate": round(scalp_wr, 4),
                "sum_r": round(scalp_sum_r, 4),
                "avg_r": round(scalp_sum_r / scalp_n, 4) if scalp_n else 0.0,
                "note": "SCALP-exit paper only. Not mixed with the old 1.8R-TP cohort. Not live-ready.",
            },
        }


paper_journal = PaperJournal()
