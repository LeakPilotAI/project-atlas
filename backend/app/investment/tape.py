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
    from app.investment.buy_prep import ACTION_RANK, from_tape_row

    out: List[Dict[str, Any]] = []
    for r in _TAPE:
        prep = from_tape_row(r)
        dd = r.get("drawdown")
        off = None if dd is None else round(abs(float(dd)) * 100.0, 1)
        r1 = r.get("ret_1d")
        r5 = r.get("ret_5d")
        out.append(
            {
                "symbol": r.get("symbol"),
                "name": r.get("name") or r.get("symbol"),
                "score": r.get("move_score"),
                "price": r.get("price"),
                "pct_from_high": off,
                "chg_1d": None if r1 is None else round(float(r1) * 100.0, 1),
                "chg_5d": None if r5 is None else round(float(r5) * 100.0, 1),
                "vs_spy": None if r.get("vs_spy") is None else round(float(r["vs_spy"]) * 100.0, 1),
                "category": r.get("sector") or "stock",
                "classification": r.get("classification"),
                "thesis": r.get("thesis"),
                "evidence": r.get("evidence"),
                "investment_class": r.get("investment_class"),
                "action": prep.get("action"),
                "action_reason": prep.get("reason"),
                "notify": bool(prep.get("notify")),
                "rel_volume": r.get("rel_volume"),
            }
        )
    out.sort(key=lambda row: (ACTION_RANK.get(str(row.get("action") or "QUIET"), 9), -(row.get("pct_from_high") or 0)))
    return out
