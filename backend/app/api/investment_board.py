from __future__ import annotations

import asyncio
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
from app.investment.quality_dips_v3_delivery import deliver_v3_events
from app.investment.quality_dips_v3_forward_store import append_v3_forward_observation
from app.investment.quality_dips_v3_forward_readiness import forward_readiness, forward_diagnostics
from app.investment.quality_dips_v3_state import detect_v3_events, quality_dips_v3_state_store
from app.investment.storage import OPPORTUNITIES_PATH, PLANS_PATH
from app.investment.robinhood_universe_registry import snapshot as robinhood_universe_snapshot, research_candidates
from app.investment.robinhood_universe_discovery import sync_official_rhj_assets

router = APIRouter(prefix="/investments", tags=["investments"])
QUALITY_DIPS_HTML = Path(__file__).resolve().parents[1] / "static" / "quality_dips.html"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    from app.investment.latest_index import latest_index
    return latest_index.read(path)




async def _build_quality_dips_board(limit: int) -> Dict[str, Any]:
    research = await asyncio.to_thread(_load_jsonl, OPPORTUNITIES_PATH)
    plans = await asyncio.to_thread(_load_jsonl, PLANS_PATH)
    symbols = {str(row.get("symbol") or "").upper().strip() for row in research if str(row.get("symbol") or "").strip()}
    # Never make the dashboard wait for an external analyst-target provider. Serve
    # last-known evidence immediately and refresh stale/missing targets in background.
    target_refresh_scheduled = quality_dips_v2_target_cache.schedule_refresh(symbols)
    quotes = await quality_dip_quote_service.get_many(symbols)
    quoted_research = apply_quote_overlay(research, quotes)
    board = build_quality_dips_board(quoted_research, plans, limit=limit)
    board = await asyncio.to_thread(attach_v2_board, board, quoted_research)

    pending_hits = accumulation_ladder_store.sync(board)
    board = accumulation_ladder_store.overlay(board)

    v3_events: list[dict[str, Any]] = []
    for row in board:
        symbol = str(row.get("symbol") or "").upper().strip()
        v3 = dict((row.get("quality_dips_v2") or {}).get("quality_dips_v3") or {})
        if not symbol or not v3:
            continue
        source_row = next((x for x in quoted_research if str(x.get("symbol") or "").upper().strip() == symbol), {})
        await asyncio.to_thread(
            append_v3_forward_observation,
            symbol=symbol,
            price=source_row.get("price") if isinstance(source_row, dict) else None,
            plan=v3,
            source_timestamp=str((source_row or {}).get("timestamp") or "") if isinstance(source_row, dict) else None,
        )
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
    v3_delivery = await deliver_v3_events(v3_events)

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
            "delivery": v3_delivery,
            # Both reports share one file-signature cached PIT load. Keep the
            # immutable evidence file intact without allocating/parsing it twice
            # per dashboard refresh.
            "forward_readiness": await asyncio.to_thread(forward_readiness),
            "forward_diagnostics": await asyncio.to_thread(forward_diagnostics),
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


from app.services.runtime_snapshot import RuntimeSnapshot
_quality_snapshots = {50: RuntimeSnapshot(ttl=10), 100: RuntimeSnapshot(ttl=10)}


@router.get("/quality-dips")
async def quality_dips_board(limit: int = Query(50, ge=1, le=100)) -> Dict[str, Any]:
    # Two bounded refresh cohorts preserve default coverage and larger requests.
    cohort = 50 if limit <= 50 else 100
    async def build():
        return await _build_quality_dips_board(cohort)
    result = await _quality_snapshots[cohort].get(build, {
        "domain": "EQUITY_INVESTMENT", "execution": "MANUAL_ONLY",
        "board": [], "counts": {}, "quote_health": {},
        "live_capital_allowed": False, "automatic_real_money_execution": False,
    }, budget=2.0)
    result["board"] = result["board"][:limit]
    result["count"] = len(result["board"])
    result["counts"] = {state: sum(row.get("stance") == state for row in result["board"])
                        for state in ("ACCUMULATE", "PREPARE", "WATCH", "STAND_DOWN")}
    return result


@router.get("/quality-dips/view", include_in_schema=False)
async def quality_dips_view() -> FileResponse:
    return FileResponse(QUALITY_DIPS_HTML, media_type="text/html", headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"})


@router.get("/robinhood-universe/research-status")
async def robinhood_research_status() -> Dict[str, Any]:
    from app.services.robinhood_universe_research import robinhood_universe_research_service
    return robinhood_universe_research_service.status()


@router.post("/robinhood-universe/research-batch")
async def robinhood_research_batch(limit: int = Query(4, ge=1, le=8)) -> Dict[str, Any]:
    """Explicit bounded research pass; never brokerage execution."""
    from app.investment.robinhood_discovery_research import research_batch
    return await research_batch(limit=limit)


@router.get("/robinhood-universe/research-queue")
async def robinhood_research_queue(limit: int = Query(40, ge=1, le=200)) -> Dict[str, Any]:
    rows = await asyncio.to_thread(research_candidates, limit=limit)
    return {
        "count": len(rows),
        "candidates": rows,
        "policy": "BOUNDED_DISCOVERY_QUEUE_NOT_FULL_CATALOG_HIGH_FREQUENCY_SCAN",
        "execution": "RESEARCH_ONLY_MANUAL",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


@router.get("/robinhood-universe")
async def robinhood_universe(sync: bool = Query(False)) -> Dict[str, Any]:
    """Read-only coverage view. Optional sync never authenticates or trades."""
    sync_result: dict[str, Any] | None = None
    if sync:
        try:
            sync_result = await sync_official_rhj_assets()
        except Exception as exc:
            sync_result = {
                "error": type(exc).__name__,
                "coverage_scope": "OFFICIAL_ROBINHOOD_STOCK_TOKEN_ASSETS_NOT_FULL_US_BROKERAGE_UNIVERSE",
            }
    state = await asyncio.to_thread(robinhood_universe_snapshot)
    symbols = state.get("symbols") if isinstance(state, dict) else {}
    rows = list(symbols.values()) if isinstance(symbols, dict) else []
    listing_counts: dict[str, int] = {}
    lane_counts: dict[str, int] = {}
    for row in rows:
        listing = str(row.get("listing_state") or "UNKNOWN")
        lane = str(row.get("research_lane") or "UNCLASSIFIED")
        listing_counts[listing] = listing_counts.get(listing, 0) + 1
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
    return {
        "coverage": {
            "total_symbols": len(rows),
            "listing_state_counts": listing_counts,
            "research_lane_counts": lane_counts,
            "updated_at": state.get("updated_at") if isinstance(state, dict) else None,
            "full_robinhood_brokerage_coverage_proven": False,
            "note": "Coverage registry is durable. Official RHJ assets are a verified source but are not the complete Robinhood Financial US brokerage catalog.",
        },
        "sync": sync_result,
        "symbols": sorted(rows, key=lambda row: str(row.get("symbol") or "")),
        "execution": "RESEARCH_ONLY_MANUAL",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
