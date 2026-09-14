from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.investment.accumulation_ladder import accumulation_ladder_store
from app.investment.board import build_quality_dips_board
from app.investment.quality_dip_quotes import apply_quote_overlay, quality_dip_quote_service, quote_health
from app.investment.storage import OPPORTUNITIES_PATH, PLANS_PATH

router = APIRouter(prefix="/investments", tags=["investments"])
QUALITY_DIPS_HTML = Path(__file__).resolve().parents[1] / "static" / "quality_dips.html"


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
    symbols = {
        str(row.get("symbol") or "").upper().strip()
        for row in research
        if str(row.get("symbol") or "").strip()
    }
    quotes = await quality_dip_quote_service.get_many(symbols)
    board = build_quality_dips_board(apply_quote_overlay(research, quotes), plans, limit=limit)

    # Browser refreshes also reconcile level hits so the visual state updates as soon
    # as a fresh supported quote crosses a frozen level. The hit remains queued for
    # Discord until the background monitor confirms DM delivery.
    pending_hits = accumulation_ladder_store.sync(board)
    board = accumulation_ladder_store.overlay(board)

    counts = {"ACCUMULATE": 0, "PREPARE": 0, "WATCH": 0, "STAND_DOWN": 0}
    for row in board:
        stance = str(row.get("stance") or "WATCH")
        counts[stance] = counts.get(stance, 0) + 1

    active_ladders = sum(1 for row in board if row.get("accumulation_ladder"))
    pending_dm = sum(
        int((row.get("accumulation_status") or {}).get("pending_dm") or 0)
        for row in board
    )
    return {
        "domain": "EQUITY_INVESTMENT",
        "source": "investment_research_store+yfinance_intraday_quote_overlay",
        "execution": "MANUAL_ONLY",
        "count": len(board),
        "counts": counts,
        "quote_health": quote_health(quotes),
        "accumulation_alerts": {
            "active_ladders": active_ladders,
            "monitor_interval_sec": 30,
            "levels": ["L1", "L2", "L3", "L4"],
            "mode": "FROZEN_DIP_LEVELS_ONE_SHOT_PER_ACCUMULATION_CYCLE",
            "discord_dm": "quality_dip_discord_enabled",
            "pending_dm": pending_dm,
            "pending_events_seen_this_request": len(pending_hits),
            "broker_execution": False,
        },
        "board": board,
        "note": (
            "Research observations and timestamped market quotes are kept separate and labeled with source, session, and freshness. "
            "ACCUMULATE names carry a frozen dip ladder when a LIVE/FRESH quote is available. Browser refreshes reconcile hits immediately; Discord delivery remains durable and retryable. Atlas never places a Robinhood order."
        ),
    }


@router.get("/quality-dips/view", include_in_schema=False)
async def quality_dips_view() -> FileResponse:
    return FileResponse(
        QUALITY_DIPS_HTML,
        media_type="text/html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )
