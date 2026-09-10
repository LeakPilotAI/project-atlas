from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Query

from app.investment.board import build_quality_dips_board
from app.investment.storage import OPPORTUNITIES_PATH, PLANS_PATH

router = APIRouter(prefix="/api/investments", tags=["investments"])


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


@router.get("/quality-dips")
async def quality_dips_board(limit: int = Query(50, ge=1, le=100)) -> Dict[str, Any]:
    research = _load_jsonl(OPPORTUNITIES_PATH)
    plans = _load_jsonl(PLANS_PATH)
    board = build_quality_dips_board(research, plans, limit=limit)
    counts = {"ACCUMULATE": 0, "PREPARE": 0, "WATCH": 0, "STAND_DOWN": 0}
    for row in board:
        stance = str(row.get("stance") or "WATCH")
        counts[stance] = counts.get(stance, 0) + 1
    return {
        "domain": "EQUITY_INVESTMENT",
        "source": "investment_research_store",
        "execution": "MANUAL_ONLY",
        "count": len(board),
        "counts": counts,
        "board": board,
        "note": (
            "Stocks/ETFs only. Readiness gates control whether a staged ladder may be shown. "
            "Opportunity scores are ordinal research rankings, not probabilities. Atlas places no Robinhood orders."
        ),
    }
