from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.investment.accumulation_ladder import LADDER_PCTS, accumulation_ladder_store
from app.investment.board import build_quality_dips_board
from app.investment.quality_dip_quotes import apply_quote_overlay, quality_dip_quote_service, quote_health
from app.investment.quality_dips_v2_board import attach_v2_board
from app.investment.quality_dips_v2_target_cache import quality_dips_v2_target_cache
from app.investment.quality_dips_v3_alerts import freeze_v3_entry_snapshot, format_v3_alert
from app.investment.quality_dips_v3_state import detect_v3_events, quality_dips_v3_state_store
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
    symbols = {str(row.get("symbol") or "").upper().strip() for row in research if str(row.get("symbol") or "").strip()}
    # Never make the dashboard wait for an external analyst-target provider. Serve
    # last-known evidence immediately and refresh stale/missing targets in background.
    target_refresh_scheduled = quality_dips_v2_target_cache.schedule_refresh(symbols)
    quotes = await quality_dip_quote_service.get_many(symbols)
    quoted_research = apply_quote_overlay(research, quotes)
    board = build_quality_dips_board(quoted_research, plans, limit=limit)
    board = attach_v2_board(board, quoted_research)

    pending_hits = accumulation_ladder_store.sync(board)
    board = accumulation_ladder_store.overlay(board)

    v3_events: list[dict[str, Any]] = []
    for row in board:
        symbol = str(row.get("symbol") or "").upper().strip()
        v3 = dict((row.get("quality_dips_v2") or {}).get("quality_dips_v3") or {})
        if not symbol or not v3:
            continue
        previous = quality_dips_v3_state_store.previous(symbol)
        for event in detect_v3_events(previous, v3):
            if not quality_dips_v3_state_store.event_seen(str(event.get("key") or "")):
                payload = dict(event)
                if str(event.get("event_type") or "") == "ENTRY_LEVEL_REACHED":
                    payload["frozen_entry_snapshot"] = freeze_v3_entry_snapshot(
                        symbol=symbol,
                        event=event,
                        plan=v3,
                    )
                payload["message"] = format_v3_alert(event, v3)
                quality_dips_v3_state_store.mark_event(
                    str(event.get("key") or ""),
                    symbol=symbol,
                    event_type=str(event.get("event_type") or "UNKNOWN"),
                    payload=payload,
                )
                v3_events.append(payload)
        quality_dips_v3_state_store.remember(symbol, v3)
    quality_dips_v3_state_store.save()

    counts = {"ACCUMULATE": 0, "PREPARE": 0, "WATCH": 0, "STAND_DOWN": 0}
    v2_counts = {"WATCH": 0, "ACCUMULATION": 0, "DEEP_VALUE": 0, "GENERATIONAL": 0, "THESIS_BROKEN": 0}
    for row in board:
        stance = str(row.get("stance") or "WATCH")
        counts[stance] = counts.get(stance, 0) + 1
        state = str((row.get("quality_dips_v2") or {}).get("patient_state") or "WATCH")
        v2_counts[state] = v2_counts.get(state, 0) + 1

    active_ladders = sum(1 for row in board if row.get("accumulation_ladder"))
    pending_dm = sum(int((row.get("accumulation_status") or {}).get("pending_dm") or 0) for row in board)
    target_complete = sum(1 for s in symbols if len(quality_dips_v2_target_cache.sources(s)) >= 3)
    return {
        "domain": "EQUITY_INVESTMENT",
        "source": "investment_research_store+robinhood_underlying+yfinance_fallback",
        "execution": "MANUAL_ONLY",
        "count": len(board),
        "counts": counts,
        "quality_dips_v2": {
            "cycle": "QUALITY_DIPS_V2_PATIENT_CAPITAL",
            "operational_repair": "V2_1_RUNTIME_EVIDENCE",
            "counts": v2_counts,
            "normalization_evidence_complete_symbols": target_complete,
            "normalization_evidence_requested_symbols": len(symbols),
            "normalization_refresh_mode": "BACKGROUND_STALE_WHILE_REVALIDATE",
            "normalization_refresh_scheduled": target_refresh_scheduled,
            "minimum_upside_hurdle_pct": 29.0,
            "generational_upside_hurdle_pct": 50.0,
            "levels": {"L1": 29.0, "L2": 35.0, "L3": 40.0, "L4": 50.0},
            "execution": "MANUAL_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "price_alone_breaks_thesis": False,
        },
        "quote_health": quote_health(quotes),
        "quality_dips_v3": {
            "cycle": "QUALITY_DIPS_V3_MARGIN_OF_SAFETY",
            "events_seen_this_request": len(v3_events),
            "events": v3_events,
            "execution": "MANUAL_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        },
        "accumulation_alerts": {
            "active_ladders": active_ladders,
            "monitor_interval_sec": 30,
            "levels": ["L1", "L2", "L3", "L4"],
            "level_pcts": [round(x * 100.0, 2) for x in LADDER_PCTS],
            "mode": "FROZEN_DIP_LEVELS_ONE_SHOT_PER_ACCUMULATION_CYCLE",
            "discord_dm": "quality_dip_discord_enabled",
            "pending_dm": pending_dm,
            "pending_events_seen_this_request": len(pending_hits),
            "broker_execution": False,
        },
        "board": board,
        "note": (
            "Legacy Quality Dips scoring remains intact. Quality Dips V2 is attached as a read-only patient-capital research projection with explicit valuation, trend, and staged-entry fields. "
            "V2.1 runtime evidence uses provider-supplied analyst targets, scored business-quality pillars, and stored daily OHLCV; missing evidence fails closed. Atlas never places a Robinhood order."
        ),
    }


@router.get("/quality-dips/view", include_in_schema=False)
async def quality_dips_view() -> FileResponse:
    return FileResponse(QUALITY_DIPS_HTML, media_type="text/html", headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"})
