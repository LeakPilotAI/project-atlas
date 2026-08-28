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

SHADOW_MIN_SCORE = 50.0
DEDUP_SECONDS = 900
SHADOW_EXPIRE_SECONDS = 6 * 3600
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
    """trade_type is always SHADOW. Real paper stays in paper_journal."""

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._open_shadows: Dict[str, Dict[str, Any]] = {}
        self._recent_fp: Dict[str, datetime] = {}
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
        rejection_stage: str = "",
        regime_normalized: str = "",
    ) -> Optional[str]:
        from app.services.paper_pipeline import paper_pipeline

        paper_pipeline.inc("shadow_evaluation_attempts")
        side_s = (side or "NONE").upper()
        symbol = symbol.upper()
        score_bucket = int(score // 5) * 5
        fp = self._fingerprint(symbol, side_s, score_bucket)
        last_seen = self._recent_fp.get(fp)
        if not self._dedup_ok(fp):
            paper_pipeline.inc("shadow_candidates_deduped")
            log.info("SHADOW DEDUP", symbol=symbol, side=side_s, decision="skip")
            return None

        cid = str(uuid.uuid4())[:12]
        ts = _iso()
        feats = dict(features or {})
        status = "QUALIFIED" if qualified else "REJECTED"
        reject_status = "QUALIFIED" if qualified else ("REJECTED_OTHER" if not failed_gates else str(failed_gates[0]).upper())
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
        from app.analytics.regime import normalize_regime

        stage = (rejection_stage or (failed_gates[0] if failed_gates else "") or "").lower()
        row: Dict[str, Any] = {
            "event": "candidate",
            "trade_type": "SHADOW",
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
            "regime_normalized": regime_normalized or normalize_regime(regime),
            "rejection_stage": stage or ("qualified" if qualified else "other"),
            "mark_price": entry,
            "signal_price": entry,
            "shadow_entry": entry,
            "stop_price": float(stop),
            "tp1_price": float(tp1),
            "tp2_price": float(tp2),
            "risk_price": risk,
            "raw_score": float(score),
            "required_score": float(required_score),
            "near_miss_gap": round(float(required_score) - float(score), 4),
            "features": feats,
            "notes": notes,
            "shadow_active": False,
            "mfe_r": 0.0,
            "mae_r": 0.0,
            "mfe_price": entry,
            "mae_price": entry,
        }
        track = side_s in ("LONG", "SHORT") and score >= SHADOW_MIN_SCORE and entry > 0 and len(self._open_shadows) < MAX_OPEN_SHADOWS
        if track:
            row["shadow_active"] = True
            row["lifecycle"] = "SHADOW_TRACKING"
            row["entry_at"] = ts
            self._open_shadows[cid] = row
        paper_pipeline.inc("shadow_candidates_recorded")
        if track:
            paper_pipeline.inc("shadow_open")
        self._append(CANDIDATES_PATH, row)
        return cid

    def update_prices(self, price_map: Dict[str, float]) -> List[Dict[str, Any]]:
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
            if hit_sl:
                outcome, exit_px, pnl_r, first_hit = "SHADOW_LOSS", stop, -1.0, "SL"
            elif hit_tp2:
                outcome, exit_px, pnl_r, first_hit = "SHADOW_WIN", tp2, abs(tp2 - entry) / risk, "TP2"
            elif hit_tp1:
                outcome, exit_px, pnl_r, first_hit = "SHADOW_WIN", tp1, abs(tp1 - entry) / risk, "TP1"
            elif age >= SHADOW_EXPIRE_SECONDS:
                exit_px = mark
                pnl_r = (mark - entry) / risk if side == "LONG" else (entry - mark) / risk
                first_hit = "EXPIRE"
                if abs(pnl_r) < 0.15:
                    outcome = "SHADOW_NEUTRAL"
                elif pnl_r > 0:
                    outcome = "SHADOW_WIN"
                else:
                    outcome = "SHADOW_LOSS"
            if outcome is None:
                continue
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
                "hypothetical_final_r": round(float(pnl_r or 0), 4),
                "mfe_r": round(float(p.get("mfe_r") or 0), 4),
                "mae_r": round(float(p.get("mae_r") or 0), 4),
                "holding_time_sec": int(age),
                "tp_would_have_been_reached": bool(first_hit in ("TP1", "TP2")),
                "sl_would_have_been_hit": bool(first_hit == "SL"),
                "sl_hit": bool(first_hit == "SL"),
                "tp_hit": bool(first_hit in ("TP1", "TP2")),
                "time_to_tp_sec": int(age) if first_hit in ("TP1", "TP2") else None,
                "time_to_sl_sec": int(age) if first_hit == "SL" else None,
                "expiration": bool(first_hit == "EXPIRE"),
            }
            self._append(CANDIDATES_PATH, resolved)
            resolved_out.append(resolved)
            to_drop.append(cid)
        for cid in to_drop:
            self._open_shadows.pop(cid, None)
        return resolved_out

    def nearest_misses(self, limit: int = 10, hours: float = 24.0) -> List[Dict[str, Any]]:
        cutoff = _now() - timedelta(hours=hours)
        misses: List[Dict[str, Any]] = []
        if not CANDIDATES_PATH.exists():
            return []
        try:
            with CANDIDATES_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if row.get("event") not in ("candidate", "shadow_open"):
                        continue
                    if row.get("qualified"):
                        continue
                    ts = _parse_iso(str(row.get("evaluated_at") or row.get("detected_at") or ""))
                    if ts and ts < cutoff:
                        continue
                    gap = float(row.get("near_miss_gap") or 0)
                    misses.append(
                        {
                            "symbol": row.get("symbol"),
                            "side": row.get("side"),
                            "score": row.get("raw_score"),
                            "required": row.get("required_score"),
                            "gap": gap,
                            "rejection_stage": row.get("rejection_stage"),
                        }
                    )
        except Exception as e:
            log.debug("nearest_misses failed", error=str(e)[:160])
            return []
        misses.sort(key=lambda x: float(x.get("gap") or 0))
        return misses[:limit]

    def funnel_stats(self, hours: float = 24.0) -> Dict[str, Any]:
        cutoff = _now() - timedelta(hours=hours)
        raw = 0
        qualified = 0
        rejection_counts: Dict[str, int] = defaultdict(int)
        resolved_n = wins = losses = 0
        sum_r = sum_mfe = sum_mae = 0.0
        tracked = 0
        by_side: Dict[str, int] = defaultdict(int)
        by_regime: Dict[str, int] = defaultdict(int)
        if CANDIDATES_PATH.exists():
            try:
                with CANDIDATES_PATH.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        ts = _parse_iso(
                            str(
                                row.get("evaluated_at")
                                or row.get("detected_at")
                                or row.get("resolved_at")
                                or ""
                            )
                        )
                        if ts and ts < cutoff:
                            continue
                        ev = row.get("event")
                        if ev in ("candidate", "shadow_open"):
                            raw += 1
                            if row.get("qualified") or row.get("status") == "QUALIFIED":
                                qualified += 1
                            else:
                                stage = str(
                                    row.get("rejection_stage")
                                    or (row.get("failed_gates") or ["other"])[0]
                                    or "other"
                                ).lower()
                                rejection_counts[stage] += 1
                            if row.get("shadow_active") or row.get("lifecycle") == "SHADOW_TRACKING":
                                tracked += 1
                            by_side[str(row.get("side") or "NONE")] += 1
                            by_regime[str(row.get("regime_normalized") or row.get("regime") or "UNKNOWN")] += 1
                        elif ev == "resolved" or row.get("lifecycle") == "RESOLVED":
                            resolved_n += 1
                            r = float(row.get("hypothetical_final_r") or row.get("hypothetical_r") or 0)
                            sum_r += r
                            sum_mfe += float(row.get("mfe_r") or 0)
                            sum_mae += float(row.get("mae_r") or 0)
                            if r > 0 or str(row.get("outcome") or "").endswith("WIN"):
                                wins += 1
                            else:
                                losses += 1
            except Exception as e:
                log.warning("funnel_stats failed", error=str(e)[:200])
        closed = wins + losses
        return {
            "hours": hours,
            "raw_candidates": raw,
            "qualified": qualified,
            "rejection_counts": dict(rejection_counts),
            "shadow_tracked": tracked,
            "shadow_open_now": len(self._open_shadows),
            "resolved": resolved_n,
            "shadow_wins": wins,
            "shadow_losses": losses,
            "shadow_winrate": round(wins / closed, 4) if closed else 0.0,
            "shadow_expectancy_r": round(sum_r / resolved_n, 4) if resolved_n else 0.0,
            "avg_mfe_r": round(sum_mfe / resolved_n, 4) if resolved_n else 0.0,
            "avg_mae_r": round(sum_mae / resolved_n, 4) if resolved_n else 0.0,
            "by_score": {},
            "by_regime": dict(by_regime),
            "by_side": dict(by_side),
            "nearest_misses": self.nearest_misses(5, hours),
            "pipeline_24h": {
                "raw": raw,
                "resolved": resolved_n,
                "open": len(self._open_shadows),
            },
        }

    def _empty_funnel(self, hours: float) -> Dict[str, Any]:
        return self.funnel_stats(hours)

    def research_summary_text(self, hours: float = 24.0) -> str:
        s = self.funnel_stats(hours)
        return (
            f"**ATLAS RESEARCH** (last {hours:.0f}h)\n"
            f"Shadow open: `{s['shadow_open_now']}`\n"
            f"_Shadow ≠ paper. Does not affect /paper PnL._"
        )


shadow_research = ShadowResearch()
