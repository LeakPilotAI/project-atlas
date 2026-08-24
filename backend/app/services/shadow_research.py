"""
Shadow candidate & rejection research layer.

RESEARCH ONLY — never affects paper PnL, live stats, risk, or Discord trade alerts.
Does not change qualification thresholds or scoring weights.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

log = structlog.get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CANDIDATES_PATH = DATA_DIR / "shadow_candidates.jsonl"
EVENTS_PATH = DATA_DIR / "shadow_events.jsonl"

# Research-only: shadow track if score >= this (NOT the live qualify threshold)
SHADOW_MIN_SCORE = 50.0
# Dedup same symbol+side within this window
DEDUP_SECONDS = 900  # 15 minutes
# Resolve shadow after this many seconds if neither SL nor TP hit
SHADOW_EXPIRE_SECONDS = 6 * 3600  # 6 hours
# Max open shadow tracks in memory
MAX_OPEN_SHADOWS = 80


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).isoformat()


def _parse_iso(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return _now()


class ShadowResearch:
    """
    Lifecycle: DETECTED → EVALUATED → QUALIFIED|REJECTED → SHADOW_TRACKING → RESOLVED

    trade_type is always SHADOW for this module. Real paper stays in paper_journal.
    """

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._open_shadows: Dict[str, Dict[str, Any]] = {}
        self._recent_fp: Dict[str, datetime] = {}  # fingerprint -> last logged
        self._load_open()

    def _append(self, path: Path, row: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def _load_open(self) -> None:
        if not CANDIDATES_PATH.exists():
            return
        resolved: Set[str] = set()
        opens: Dict[str, Dict[str, Any]] = {}
        try:
            with CANDIDATES_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    cid = row.get("candidate_id")
                    if not cid:
                        continue
                    st = row.get("lifecycle") or row.get("status")
                    if st == "RESOLVED" or row.get("event") == "resolved":
                        resolved.add(cid)
                    elif row.get("event") in ("candidate", "shadow_open") or st in (
                        "SHADOW_TRACKING",
                        "REJECTED",
                        "QUALIFIED",
                    ):
                        if row.get("shadow_active"):
                            opens[cid] = row
            for cid, row in opens.items():
                if cid not in resolved:
                    self._open_shadows[cid] = row
        except Exception as e:
            log.warning("shadow load failed", error=str(e)[:200])

    def _fingerprint(self, symbol: str, side: str, score_bucket: int) -> str:
        return f"{symbol}|{side}|{score_bucket}"

    def _dedup_ok(self, fp: str) -> bool:
        last = self._recent_fp.get(fp)
        if last and (_now() - last).total_seconds() < DEDUP_SECONDS:
            return False
        self._recent_fp[fp] = _now()
        # prune old
        cutoff = _now() - timedelta(seconds=DEDUP_SECONDS * 3)
        self._recent_fp = {k: v for k, v in self._recent_fp.items() if v >= cutoff}
        return True

    def record_evaluation(
        self,
        *,
        symbol: str,
        side: Optional[str],
        mark_price: float,
        score: float,
        required_score: float,
        qualified: bool,
        failed_gates: List[str],
        features: Optional[Dict[str, Any]] = None,
        regime: str = "",
        strategy: str = "rsi_extension_v1",
        timeframe: str = "5m",
        stop: Optional[float] = None,
        tp1: Optional[float] = None,
        tp2: Optional[float] = None,
        notes: str = "",
    ) -> Optional[str]:
        """
        Call BEFORE/AT final qualify decision. Does not change trading logic.
        Returns candidate_id or None if deduped.
        """
        side_s = (side or "NONE").upper()
        symbol = symbol.upper()
        score_bucket = int(score // 5) * 5
        fp = self._fingerprint(symbol, side_s, score_bucket)
        if not self._dedup_ok(fp):
            return None

        cid = str(uuid.uuid4())[:12]
        ts = _iso()
        feats = dict(features or {})
        status = "QUALIFIED" if qualified else "REJECTED"
        # Detailed reject codes
        if qualified:
            reject_status = "QUALIFIED"
        elif not failed_gates:
            reject_status = "REJECTED_OTHER"
        elif len(failed_gates) == 1:
            g = failed_gates[0].upper()
            if "SCORE" in g:
                reject_status = "REJECTED_SCORE"
            elif "REGIME" in g or "STRUCTURE" in g or "EMA" in g:
                reject_status = "REJECTED_REGIME"
            elif "VOL" in g and "ATR" not in g:
                reject_status = "REJECTED_VOLUME"
            elif "LIQ" in g or "OI" in g or "THIN" in g or "JUNK" in g:
                reject_status = "REJECTED_LIQUIDITY"
            elif "RR" in g or "RISK" in g or "ATR" in g:
                reject_status = "REJECTED_RISK"
            elif "RSI" in g or "EXT" in g or "CONFIRM" in g:
                reject_status = "REJECTED_CONFIRMATION"
            else:
                reject_status = "REJECTED_OTHER"
        else:
            reject_status = "REJECTED_OTHER"

        # Shadow SL/TP if not provided — same methodology as micro coach ATR style
        entry = float(mark_price)
        if stop is None or tp1 is None:
            atr = float(feats.get("atr") or entry * 0.008)
            if side_s == "LONG":
                stop = entry - 1.5 * atr
                tp1 = entry + 2.5 * atr
                tp2 = entry + 4.0 * atr
            elif side_s == "SHORT":
                stop = entry + 1.5 * atr
                tp1 = entry - 2.5 * atr
                tp2 = entry - 4.0 * atr
            else:
                stop = entry
                tp1 = entry
                tp2 = entry

        risk = abs(entry - float(stop)) or 1e-12
        near_miss_gap = float(required_score) - float(score)

        row: Dict[str, Any] = {
            "event": "candidate",
            "trade_type": "SHADOW",  # never PAPER
            "candidate_id": cid,
            "lifecycle": "EVALUATED",
            "status": status,
            "reject_status": reject_status,
            "failed_gates": list(failed_gates),
            "detected_at": ts,
            "evaluated_at": ts,
            "symbol": symbol,
            "side": side_s,
            "timeframe": timeframe,
            "strategy": strategy,
            "regime": regime,
            "mark_price": entry,
            "signal_price": entry,  # same moment — no anomaly lag
            "shadow_entry": entry,
            "stop_price": float(stop),
            "tp1_price": float(tp1),
            "tp2_price": float(tp2),
            "risk_price": risk,
            "raw_score": float(score),
            "required_score": float(required_score),
            "near_miss_gap": round(near_miss_gap, 4),
            "features": feats,
            "notes": notes,
            "shadow_active": False,
            "mfe_r": 0.0,
            "mae_r": 0.0,
            "mfe_price": entry,
            "mae_price": entry,
        }

        # Shadow track if research threshold met and has a side
        track = (
            side_s in ("LONG", "SHORT")
            and score >= SHADOW_MIN_SCORE
            and entry > 0
            and len(self._open_shadows) < MAX_OPEN_SHADOWS
        )
        if track:
            row["shadow_active"] = True
            row["lifecycle"] = "SHADOW_TRACKING"
            row["entry_at"] = ts  # hypothetical entry timestamp
            self._open_shadows[cid] = row

        self._append(CANDIDATES_PATH, row)
        log.debug(
            "shadow candidate",
            candidate_id=cid,
            symbol=symbol,
            side=side_s,
            score=score,
            status=status,
            failed_gates=failed_gates,
            shadow=track,
        )
        return cid

    def update_prices(self, price_map: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Chronological shadow MFE/MAE + SL/TP resolution using only post-entry marks.
        Returns list of newly resolved rows.
        """
        resolved_out: List[Dict[str, Any]] = []
        to_drop: List[str] = []
        now = _now()

        for cid, p in list(self._open_shadows.items()):
            sym = p["symbol"]
            mark = price_map.get(sym)
            if mark is None or mark <= 0:
                continue
            entry = float(p["shadow_entry"])
            stop = float(p["stop_price"])
            tp1 = float(p["tp1_price"])
            tp2 = float(p.get("tp2_price") or tp1)
            risk = float(p.get("risk_price") or abs(entry - stop) or 1e-12)
            side = p["side"]

            if side == "LONG":
                fav = (mark - entry) / risk
                adv = (entry - mark) / risk
                hit_sl = mark <= stop
                hit_tp1 = mark >= tp1
                hit_tp2 = mark >= tp2
            else:
                fav = (entry - mark) / risk
                adv = (mark - entry) / risk
                hit_sl = mark >= stop
                hit_tp1 = mark <= tp1
                hit_tp2 = mark <= tp2

            if fav > float(p.get("mfe_r") or 0):
                p["mfe_r"] = fav
                p["mfe_price"] = mark
            if adv > float(p.get("mae_r") or 0):
                p["mae_r"] = adv
                p["mae_price"] = mark
            p["last_mark"] = mark

            entry_at = _parse_iso(p.get("entry_at") or p.get("evaluated_at") or _iso())
            age = (now - entry_at).total_seconds()

            outcome = None
            exit_px = None
            pnl_r = None
            first_hit = None

            # First-touch resolution (no hindsight ranking beyond chronological hits)
            if hit_sl and hit_tp1:
                # Ambiguous same bar — conservative: SL if MAE path, else use age order
                # Prefer SL for research honesty when both true on same update
                outcome = "SHADOW_LOSS"
                exit_px = stop
                pnl_r = -1.0
                first_hit = "SL"
            elif hit_sl:
                outcome = "SHADOW_LOSS"
                exit_px = stop
                pnl_r = -1.0
                first_hit = "SL"
            elif hit_tp2:
                outcome = "SHADOW_WIN"
                exit_px = tp2
                pnl_r = abs(tp2 - entry) / risk
                first_hit = "TP2"
            elif hit_tp1:
                outcome = "SHADOW_WIN"
                exit_px = tp1
                pnl_r = abs(tp1 - entry) / risk
                first_hit = "TP1"
            elif age >= SHADOW_EXPIRE_SECONDS:
                # Expire at last mark
                outcome = "EXPIRED"
                exit_px = mark
                if side == "LONG":
                    pnl_r = (mark - entry) / risk
                else:
                    pnl_r = (entry - mark) / risk
                if abs(pnl_r) < 0.15:
                    outcome = "SHADOW_NEUTRAL"
                elif pnl_r > 0:
                    outcome = "SHADOW_WIN"
                else:
                    outcome = "SHADOW_LOSS"
                first_hit = "EXPIRE"

            if outcome is None:
                continue

            hold_s = age
            resolved = {
                **{k: v for k, v in p.items() if k != "event"},
                "event": "resolved",
                "trade_type": "SHADOW",
                "lifecycle": "RESOLVED",
                "shadow_active": False,
                "resolved_at": _iso(),
                "outcome": outcome,
                "first_hit": first_hit,
                "exit_price": exit_px,
                "hypothetical_r": round(float(pnl_r or 0), 4),
                "mfe_r": round(float(p.get("mfe_r") or 0), 4),
                "mae_r": round(float(p.get("mae_r") or 0), 4),
                "holding_time_sec": int(hold_s),
                "tp1_hit": first_hit in ("TP1", "TP2"),
                "tp2_hit": first_hit == "TP2",
                "sl_hit": first_hit == "SL",
            }
            self._append(CANDIDATES_PATH, resolved)
            self._append(EVENTS_PATH, {"event": "shadow_resolved", **resolved})
            resolved_out.append(resolved)
            to_drop.append(cid)
            log.info(
                "shadow resolved",
                candidate_id=cid,
                symbol=sym,
                outcome=outcome,
                r=resolved["hypothetical_r"],
                mfe_r=resolved["mfe_r"],
                mae_r=resolved["mae_r"],
            )

        for cid in to_drop:
            self._open_shadows.pop(cid, None)
        return resolved_out

    def nearest_misses(self, limit: int = 10, hours: float = 24.0) -> List[Dict[str, Any]]:
        """Candidates closest to required_score that were REJECTED."""
        cutoff = _now() - timedelta(hours=hours)
        misses: List[Dict[str, Any]] = []
        if not CANDIDATES_PATH.exists():
            return []
        seen_fp: Set[str] = set()
        try:
            with CANDIDATES_PATH.open("r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("event") != "candidate":
                    continue
                if row.get("status") == "QUALIFIED":
                    continue
                ts = _parse_iso(row.get("evaluated_at") or row.get("detected_at") or "")
                if ts < cutoff:
                    break
                gap = float(row.get("near_miss_gap") or 0)
                if gap < 0:
                    continue  # already above threshold but rejected for other gate
                fp = f"{row.get('symbol')}|{row.get('side')}"
                if fp in seen_fp:
                    continue
                seen_fp.add(fp)
                misses.append(
                    {
                        "symbol": row.get("symbol"),
                        "side": row.get("side"),
                        "score": row.get("raw_score"),
                        "required": row.get("required_score"),
                        "gap": gap,
                        "failed_gates": row.get("failed_gates"),
                        "reject_status": row.get("reject_status"),
                    }
                )
                if len(misses) >= limit * 3:
                    break
        except Exception as e:
            log.warning("nearest_misses failed", error=str(e)[:200])
        misses.sort(key=lambda x: (float(x.get("gap") or 99), -float(x.get("score") or 0)))
        return misses[:limit]

    def funnel_stats(self, hours: float = 24.0) -> Dict[str, Any]:
        cutoff = _now() - timedelta(hours=hours)
        raw = 0
        by_reject: Dict[str, int] = defaultdict(int)
        qualified = 0
        shadow_tracked = 0
        resolved = 0
        wins = losses = neutral = expired = 0
        sum_r = 0.0
        sum_mfe = 0.0
        sum_mae = 0.0
        score_buckets: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"n": 0, "wins": 0, "sum_r": 0.0, "mfe": 0.0, "mae": 0.0}
        )
        regime_buckets: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"n": 0, "wins": 0, "sum_r": 0.0}
        )
        side_buckets: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"n": 0, "wins": 0, "sum_r": 0.0}
        )

        if not CANDIDATES_PATH.exists():
            return self._empty_funnel(hours)

        try:
            with CANDIDATES_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    ts_s = row.get("evaluated_at") or row.get("resolved_at") or row.get("detected_at")
                    ts = _parse_iso(ts_s or "")
                    if ts < cutoff:
                        continue

                    if row.get("event") == "candidate":
                        raw += 1
                        if row.get("status") == "QUALIFIED":
                            qualified += 1
                        else:
                            by_reject[row.get("reject_status") or "REJECTED_OTHER"] += 1
                        if row.get("shadow_active") or row.get("lifecycle") == "SHADOW_TRACKING":
                            shadow_tracked += 1

                    if row.get("event") == "resolved" or row.get("lifecycle") == "RESOLVED":
                        if row.get("trade_type") != "SHADOW":
                            continue
                        resolved += 1
                        outcome = row.get("outcome") or ""
                        r = float(row.get("hypothetical_r") or 0)
                        sum_r += r
                        sum_mfe += float(row.get("mfe_r") or 0)
                        sum_mae += float(row.get("mae_r") or 0)
                        if outcome == "SHADOW_WIN":
                            wins += 1
                        elif outcome == "SHADOW_LOSS":
                            losses += 1
                        elif outcome == "EXPIRED":
                            expired += 1
                        else:
                            neutral += 1

                        sc = float(row.get("raw_score") or 0)
                        if sc < 60:
                            b = "0-59"
                        elif sc < 70:
                            b = "60-69"
                        elif sc < 80:
                            b = "70-79"
                        elif sc < 85:
                            b = "80-84"
                        elif sc < 90:
                            b = "85-89"
                        else:
                            b = "90+"
                        sb = score_buckets[b]
                        sb["n"] += 1
                        sb["sum_r"] += r
                        sb["mfe"] += float(row.get("mfe_r") or 0)
                        sb["mae"] += float(row.get("mae_r") or 0)
                        if r > 0:
                            sb["wins"] += 1

                        reg = str(row.get("regime") or "unknown")[:32]
                        rb = regime_buckets[reg]
                        rb["n"] += 1
                        rb["sum_r"] += r
                        if r > 0:
                            rb["wins"] += 1

                        side = str(row.get("side") or "?")
                        sdb = side_buckets[side]
                        sdb["n"] += 1
                        sdb["sum_r"] += r
                        if r > 0:
                            sdb["wins"] += 1
        except Exception as e:
            log.warning("funnel_stats failed", error=str(e)[:200])

        closed = wins + losses
        wr = (wins / closed) if closed else 0.0
        exp = (sum_r / resolved) if resolved else 0.0

        def _fmt_bucket(d: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
            out = {}
            for k, v in d.items():
                n = int(v["n"])
                out[k] = {
                    "n": n,
                    "winrate": round((v["wins"] / n) if n else 0.0, 4),
                    "avg_r": round((v["sum_r"] / n) if n else 0.0, 4),
                    "expectancy": round((v["sum_r"] / n) if n else 0.0, 4),
                }
            return out

        return {
            "hours": hours,
            "raw_candidates": raw,
            "qualified": qualified,
            "rejection_counts": dict(by_reject),
            "shadow_tracked": shadow_tracked + len(self._open_shadows),
            "shadow_open_now": len(self._open_shadows),
            "resolved": resolved,
            "shadow_wins": wins,
            "shadow_losses": losses,
            "shadow_neutral": neutral,
            "shadow_expired": expired,
            "shadow_winrate": round(wr, 4),
            "shadow_expectancy_r": round(exp, 4),
            "avg_mfe_r": round(sum_mfe / resolved, 4) if resolved else 0.0,
            "avg_mae_r": round(sum_mae / resolved, 4) if resolved else 0.0,
            "sum_hypothetical_r": round(sum_r, 4),
            "by_score": _fmt_bucket(score_buckets),
            "by_regime": _fmt_bucket(regime_buckets),
            "by_side": _fmt_bucket(side_buckets),
            "nearest_misses": self.nearest_misses(8, hours),
            "paths": {
                "candidates": str(CANDIDATES_PATH),
                "events": str(EVENTS_PATH),
            },
        }

    def _empty_funnel(self, hours: float) -> Dict[str, Any]:
        return {
            "hours": hours,
            "raw_candidates": 0,
            "qualified": 0,
            "rejection_counts": {},
            "shadow_tracked": 0,
            "shadow_open_now": 0,
            "resolved": 0,
            "shadow_wins": 0,
            "shadow_losses": 0,
            "shadow_winrate": 0.0,
            "shadow_expectancy_r": 0.0,
            "avg_mfe_r": 0.0,
            "avg_mae_r": 0.0,
            "by_score": {},
            "by_regime": {},
            "by_side": {},
            "nearest_misses": [],
        }

    def research_summary_text(self, hours: float = 24.0) -> str:
        s = self.funnel_stats(hours)
        lines = [
            f"**ATLAS RESEARCH** (last {hours:.0f}h)",
            "",
            f"Candidates: `{s['raw_candidates']}` · Qualified: `{s['qualified']}`",
            f"Shadow open: `{s['shadow_open_now']}` · Resolved: `{s['resolved']}`",
            f"Shadow: `{s['shadow_wins']}W` / `{s['shadow_losses']}L` · "
            f"WR `{s['shadow_winrate']*100:.1f}%` · Exp `{s['shadow_expectancy_r']:+.2f}R`",
            f"Avg MFE `{s['avg_mfe_r']:+.2f}R` · Avg MAE `{s['avg_mae_r']:+.2f}R`",
            "",
            "_Shadow ≠ paper. Does not affect /paper PnL._",
        ]
        rej = s.get("rejection_counts") or {}
        if rej:
            lines.append("")
            lines.append("**Reject funnel**")
            for k, v in sorted(rej.items(), key=lambda x: -x[1])[:8]:
                lines.append(f"• `{k}`: {v}")
        misses = s.get("nearest_misses") or []
        if misses:
            lines.append("")
            lines.append("**Nearest misses**")
            for m in misses[:5]:
                lines.append(
                    f"• `{m.get('symbol')}` {m.get('side')} "
                    f"{m.get('score')}/{m.get('required')} "
                    f"(gap {m.get('gap')}) · {m.get('reject_status')}"
                )
        by_score = s.get("by_score") or {}
        if by_score:
            lines.append("")
            lines.append("**By score (resolved)**")
            for b in ("60-69", "70-79", "80-84", "85-89", "90+"):
                if b in by_score:
                    x = by_score[b]
                    lines.append(
                        f"• `{b}` n={x['n']} WR {x['winrate']*100:.0f}% avgR {x['avg_r']:+.2f}"
                    )
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "…"
        return text


shadow_research = ShadowResearch()