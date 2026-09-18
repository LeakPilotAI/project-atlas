"""Forward V3 shadow-readiness report."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.investment.quality_dips_v3_forward_store import V3_FORWARD_PATH

MIN_UNIQUE_DAYS = 20
MIN_SYMBOLS = 10
MIN_EVALUATIONS = 200


def _parse_day(ts: Any) -> str | None:
    try:
        return datetime.fromisoformat(str(ts).replace("Z","+00:00")).date().isoformat()
    except Exception:
        return None


def load_forward_rows(path: Path = V3_FORWARD_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows=[]
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            row=json.loads(raw)
        except Exception:
            continue
        if isinstance(row,dict):
            rows.append(row)
    return rows


def forward_readiness(path: Path = V3_FORWARD_PATH) -> dict[str, Any]:
    rows=load_forward_rows(path)
    symbols={str(r.get("symbol") or "").upper() for r in rows if str(r.get("symbol") or "")}
    days={d for d in (_parse_day(r.get("timestamp")) for r in rows) if d}
    states=Counter(str(r.get("patient_state") or "UNKNOWN").upper() for r in rows)
    blockers=[]
    if len(rows) < MIN_EVALUATIONS: blockers.append("minimum evaluations not reached")
    if len(symbols) < MIN_SYMBOLS: blockers.append("minimum symbol coverage not reached")
    if len(days) < MIN_UNIQUE_DAYS: blockers.append("minimum calendar-day coverage not reached")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "evaluations": len(rows),
        "symbols": len(symbols),
        "unique_days": len(days),
        "state_counts": dict(states),
        "thresholds": {
            "min_evaluations": MIN_EVALUATIONS,
            "min_symbols": MIN_SYMBOLS,
            "min_unique_days": MIN_UNIQUE_DAYS,
        },
        "execution":"MANUAL_ONLY",
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
    }
