"""HTTP diagnostics for the paper pipeline. No strategy changes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

# Heavy research is read-only but may scan large durable JSONL histories. Keep the
# desktop/API surface responsive while a single background refresh completes.
_RESEARCH_RESPONSE_BUDGET_SECONDS = 2.5
# Heavy JSONL research can hold the CPython GIL long enough to starve /health even
# when it runs in a worker thread. Do not rebuild it on every dashboard poll.
_RESEARCH_CACHE_TTL_SECONDS = 60.0
_research_cache: Optional[Dict[str, Any]] = None
_research_cache_monotonic: float = 0.0
_research_task: Optional[asyncio.Task] = None


def _research_payload() -> Dict[str, Any]:
    from app.services.funnel_research import funnel_research
    from app.services.paper_pipeline import paper_pipeline
    from app.services.shadow_research import shadow_research

    payload = funnel_research.research_payload()
    # research_payload already contains the expensive shadow aggregation. Reuse it
    # instead of scanning the shadow history yet again.
    shadow = payload.get("shadow") or {}
    return {
        "last_24h": paper_pipeline.last_24h(),
        "bottleneck": payload.get("bottleneck"),
        "funnel": payload.get("funnel"),
        "funnel_text": paper_pipeline.funnel_24h_text(),
        "independent_gates": payload.get("independent_gates"),
        "distributions": payload.get("distributions"),
        "sensitivity": payload.get("sensitivity"),
        "shadow": shadow,
        "why_no_trade": payload.get("why_no_paper_trades"),
        "effective_config": paper_pipeline.effective_config(),
        # Avoid research_summary_text(), which recomputes the full research payload.
        "research_text": "ATLAS research snapshot loaded. Detailed research remains read-only.",
        "operational_surface": {"state": "FRESH", "background_refresh": False},
    }


def _research_warming_payload() -> Dict[str, Any]:
    from app.services.paper_pipeline import paper_pipeline

    return {
        "last_24h": paper_pipeline.last_24h(),
        "bottleneck": None,
        "funnel": None,
        "funnel_text": paper_pipeline.funnel_24h_text(),
        "independent_gates": {},
        "distributions": {},
        "sensitivity": {},
        "shadow": {},
        "why_no_trade": None,
        "effective_config": paper_pipeline.effective_config(),
        "research_text": "Research snapshot is refreshing in the background.",
        "operational_surface": {
            "state": "WARMING",
            "background_refresh": True,
            "read_only": True,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        },
    }


@router.get("/research")
async def diagnostics_research() -> Dict[str, Any]:
    global _research_cache, _research_cache_monotonic, _research_task

    loop = asyncio.get_running_loop()
    now = loop.time()

    if _research_task is not None and _research_task.done():
        try:
            _research_cache = _research_task.result()
            _research_cache_monotonic = now
        except Exception:
            pass
        _research_task = None

    cache_age = now - _research_cache_monotonic if _research_cache is not None else None
    if _research_cache is not None and cache_age is not None and cache_age < _RESEARCH_CACHE_TTL_SECONDS:
        fresh = dict(_research_cache)
        fresh["operational_surface"] = {
            "state": "FRESH",
            "background_refresh": False,
            "cache_age_seconds": round(cache_age, 3),
            "read_only": True,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }
        return fresh

    if _research_task is None:
        _research_task = asyncio.create_task(asyncio.to_thread(_research_payload))

    # Once a usable snapshot exists, never make a dashboard poll wait behind the
    # expensive refresh. Serve last-good data immediately while one refresh runs.
    if _research_cache is not None:
        stale = dict(_research_cache)
        stale["operational_surface"] = {
            "state": "STALE_WHILE_REFRESHING",
            "background_refresh": True,
            "cache_age_seconds": round(cache_age or 0.0, 3),
            "read_only": True,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }
        return stale

    try:
        result = await asyncio.wait_for(
            asyncio.shield(_research_task), timeout=_RESEARCH_RESPONSE_BUDGET_SECONDS
        )
        _research_cache = result
        _research_cache_monotonic = loop.time()
        _research_task = None
        return result
    except asyncio.TimeoutError:
        return _research_warming_payload()


@router.get("/paper")
async def diagnostics_paper() -> Dict[str, Any]:
    from app.services.paper_pipeline import paper_pipeline

    return paper_pipeline.as_json()


@router.get("")
async def diagnostics_root() -> Dict[str, Any]:
    from app.services.funnel_research import funnel_research
    from app.services.paper_pipeline import paper_pipeline

    base = paper_pipeline.as_json()
    base["why_no_paper_trades"] = funnel_research.why_no_paper_trades()
    base["independent_gates"] = funnel_research.independent_gates()
    base["funnel"] = funnel_research.sequential_funnel()
    return base


@router.get("/runtime-latency")
async def diagnostics_runtime_latency() -> Dict[str, Any]:
    from app.services.perp_alert_delivery import perp_alert_delivery_service

    from app.services.runtime_watchdog import runtime_watchdog

    loop = asyncio.get_running_loop()
    started = loop.time()
    await asyncio.sleep(0)
    event_loop_yield_ms = round((loop.time() - started) * 1000.0, 3)
    from app.investment.latest_index import latest_index
    from app.investment.history import _bar_cache
    from app.api.live import _live_snapshot
    from app.api.investment_board import _quality_snapshots
    from app.api.validation import _summary_snapshot, _edge_snapshot
    snapshots = {"live": _live_snapshot, "quality50": _quality_snapshots[50],
                 "quality100": _quality_snapshots[100], "validation": _summary_snapshot,
                 "edge": _edge_snapshot}
    return {
        "event_loop_yield_ms": event_loop_yield_ms,
        "event_loop_stalls": runtime_watchdog.snapshot(),
        "runtime_metrics": runtime_watchdog.metrics(),
        "read_models": {name: {"refreshes": cache.refreshes, "duration_ms": cache.duration_ms,
                                "in_flight": cache.task is not None, "error": cache.error}
                        for name, cache in snapshots.items()},
        "bounded_indexes": {"investment_files": len(latest_index.files),
                            "investment_rows_parsed": latest_index.parsed_rows,
                            "daily_history_files": len(_bar_cache)},
        "perp_alert_delivery": perp_alert_delivery_service.reconciliation_status(),
        "read_only": True,
        "execution": "PAPER_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


@router.get("/paper-reconciliation")
async def diagnostics_paper_reconciliation() -> Dict[str, Any]:
    from app.services.perp_alert_delivery import perp_alert_delivery_service
    from app.services.perp_paper_observability import reconciliation_summary

    # Never make a dashboard/diagnostic request pay for a full durable-history
    # scan. The observability layer caches by journal signature and TTL; the scan
    # itself remains off the event loop on a cache miss.
    current = await asyncio.to_thread(reconciliation_summary)
    return {
        "current": current,
        "runtime": perp_alert_delivery_service.reconciliation_status(),
        "read_only": True,
        "execution": "PAPER_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


@router.get("/discord")
async def diagnostics_discord() -> Dict[str, Any]:
    from app.alerts.discord import bot, get_subscriber_ids, is_discord_ready
    from app.core.config import get_settings

    s = get_settings()
    token = bool((s.discord_token or "").strip())
    ready = is_discord_ready()
    return {
        "discord_configured": token,
        "discord_bot_connected": bool(getattr(bot, "is_ready", lambda: False)()),
        "discord_ready": ready,
        "subscriber_count": len(get_subscriber_ids()),
        "owner_ids": s.discord_owner_id_list,
        "can_fetch_user": ready,
        "can_send_dm": ready and (len(get_subscriber_ids()) > 0 or bool(s.discord_owner_id_list)),
    }


@router.get("/paper-test")
@router.post("/paper-test")
async def diagnostics_paper_test() -> Dict[str, Any]:
    """Isolated TEST journal path. Never counts as PAPER/SHADOW/LIVE."""
    from app.alerts.discord import is_discord_ready, send_discord_alert
    from app.services.paper_journal import paper_journal
    from app.services.paper_pipeline import paper_pipeline

    symbol = "ATLAS_TEST"
    entry = 100.0
    stop = 99.0
    tp1 = 101.8
    tid = await paper_journal.open_trade(
        symbol=symbol,
        side="LONG",
        entry=entry,
        stop=stop,
        tp1=tp1,
        tp2=103.0,
        risk_usd=1.0,
        regime="TEST",
        notes="diagnostic TEST — not paper stats",
        source="diagnostics",
        strategy="pipeline_test",
        signal_score=0.0,
        features={"diagnostic": True},
        tier="test",
        counts_for_live=False,
        trade_type="TEST",
    )
    paper_journal.update_excursion(tid, 100.6)
    paper_journal.update_excursion(tid, 99.7)
    close_row = await paper_journal.close_trade(
        tid, exit_price=101.8, result="TEST_CLOSE", pnl_r=1.8, exit_reason="TEST"
    )
    stats = await paper_journal.stats()
    dm_ok = False
    if is_discord_ready():
        dm_ok = await send_discord_alert(
            symbol="TEST",
            title="Atlas · Paper pipeline TEST",
            description=(
                f"Diagnostic TEST trade `{tid}` opened and closed.\n"
                f"Does **not** count in /paper live stats.\n"
                f"MFE `{close_row.get('mfe_r')}` · MAE `{close_row.get('mae_r')}`"
            ),
            price=101.8,
            severity="INFO",
            opportunity=1,
            confidence=1,
            risk=1,
        )
        if dm_ok:
            paper_pipeline.last_discord_alert_at = datetime.now(timezone.utc).isoformat()

    return {
        "ok": bool(tid and close_row),
        "trade_id": tid,
        "trade_type": "TEST",
        "counts_for_live": False,
        "open_worked": bool(tid),
        "mfe_r": close_row.get("mfe_r"),
        "mae_r": close_row.get("mae_r"),
        "close_worked": bool(close_row),
        "stats_closed_excludes_test": True,
        "paper_closed_count": stats.get("closed"),
        "discord_ready": is_discord_ready(),
        "discord_delivered": dm_ok,
        "closed": close_row,
    }
