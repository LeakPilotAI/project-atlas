"""Equity Majors Tape. Separate from Hyperliquid last_major_tape."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_TAPE: List[Dict[str, Any]] = []
_LAST_AT: Optional[str] = None
_QUIET_NOTE = "No major dislocations currently detected."


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_rows(rows: List[Dict[str, Any]]) -> None:
    global _TAPE, _LAST_AT
    _TAPE = list(rows)
    _LAST_AT = _now_iso()


def get_rows() -> List[Dict[str, Any]]:
    return list(_TAPE)


def last_at() -> Optional[str]:
    return _LAST_AT


def sort_key(row: Dict[str, Any]) -> tuple:
    score = row.get("move_score")
    score_n = float(score) if isinstance(score, (int, float)) else -1.0
    sev = str(row.get("classification") or "")
    rank = {
        "FUNDAMENTAL_BREAKDOWN": 0,
        "EXTREME_DISLOCATION": 1,
        "MAJOR_DISLOCATION": 2,
        "THESIS_DETERIORATING": 3,
        "ABNORMAL_SELLING": 4,
        "ELEVATED_SELLING": 5,
        "NORMAL_PULLBACK": 6,
        "NORMAL": 7,
        "UNKNOWN": 8,
    }.get(sev, 9)
    return (rank, -score_n)


def public_payload() -> Dict[str, Any]:
    rows = sorted(_TAPE, key=sort_key)
    abnormal = {
        "MAJOR_DISLOCATION",
        "EXTREME_DISLOCATION",
        "THESIS_DETERIORATING",
        "FUNDAMENTAL_BREAKDOWN",
        "ABNORMAL_SELLING",
    }
    hits = [r for r in rows if r.get("classification") in abnormal]
    nearest = rows[:3]
    quiet = not hits
    return {
        "updated_at": _LAST_AT,
        "quiet": quiet,
        "headline": _QUIET_NOTE if quiet else f"{len(hits)} abnormal equity move(s)",
        "nearest": [
            {
                "symbol": r.get("symbol"),
                "move_score": r.get("move_score"),
                "classification": r.get("classification"),
            }
            for r in nearest
        ],
        "rows": rows,
        "note": "Equity Majors Tape. Not Hyperliquid. Move score is unusualness, not a buy score.",
    }


def as_quality_dip_rows() -> List[Dict[str, Any]]:
    """Dashboard quality-dip list consumes the tape — no second Yahoo loop."""
    out: List[Dict[str, Any]] = []
    for r in sorted(_TAPE, key=sort_key):
        out.append(
            {
                "symbol": r.get("symbol"),
                "score": r.get("move_score"),
                "price": r.get("price"),
                "pct_from_high": None
                if r.get("drawdown") is None
                else round(abs(float(r["drawdown"])) * 100.0, 1),
                "chg_5d": None if r.get("ret_5d") is None else round(float(r["ret_5d"]) * 100.0, 1),
                "category": r.get("sector") or "stock",
                "classification": r.get("classification"),
                "thesis": r.get("thesis"),
            }
        )
    return out
