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
            log.info(
                "SHADOW DEDUP",
                symbol=symbol,
                side=side_s,
                score=score,
                score_bucket=score_bucket,
                fingerprint=fp,
                last_seen=str(last_seen),
                decision="skip",
            )
            return None
        log.info(
            "SHADOW DEDUP",
            symbol=symbol,
            side=side_s,
            score=score,
            score_bucket=score_bucket,
            fingerprint=fp,
            last_seen=str(last_seen),
            decision="record",
        )

        cid = str(uuid.uuid4())[:12]
        ts = _iso()
        feats = dict(features or {})
        status = "QUALIFIED" if qualified else "REJECTED"
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
            "mark_price": entry,
            "signal_price": entry,
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

        track = (
            side_s in ("LONG", "SHORT")
            and score >= SHADOW_MIN_SCORE
            and entry > 0
            and len(self._open_shadows) < MAX_OPEN_SHADOWS
        )
        if track:
            row["shadow_active"] = True
            row["lifecycle"] = "SHADOW_TRACKING"
            row["entry_at"] = ts
            self._open_shadows[cid] = row

        paper_pipeline.inc("shadow_candidates_recorded")
        if track:
            paper_pipeline.inc("shadow_open")
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
