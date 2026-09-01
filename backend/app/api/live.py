"""Live command-center payload. Read-only. Does not change gates or place orders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from app.alerts.discord import is_discord_ready
from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["live"])


def _open_row(row: Dict[str, Any], coach: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    entry = row.get("actual_entry_price") or row.get("entry") or row.get("signal_price")
    stop = row.get("stop_price") or row.get("stop")
    tp1 = row.get("tp1_price") or row.get("tp1")
    c = coach or {}
    lifecycle = c.get("lifecycle") or row.get("lifecycle") or "OPEN"
    stale = c.get("stale_quote") if "stale_quote" in c else row.get("stale_quote")
    return {
        "trade_id": row.get("trade_id"),
        "symbol": row.get("symbol"),
        "side": row.get("side"),
        "entry": entry,
        "stop": stop,
        "tp1": tp1,
        "mark": c.get("mark") if c.get("mark") is not None else (row.get("mark") or entry),
        "mfe_r": c.get("mfe_r") if c.get("mfe_r") is not None else row.get("mfe_r"),
        "mae_r": c.get("mae_r") if c.get("mae_r") is not None else row.get("mae_r"),
        "opened_at": row.get("entry_timestamp") or row.get("opened_at") or row.get("signal_timestamp"),
        "regime": row.get("regime"),
        "tier": row.get("tier"),
        "counts_for_live": row.get("counts_for_live"),
        "stale_quote": stale,
        "lifecycle": lifecycle,
        "recovered": bool(c.get("recovered")),
        "error": c.get("error") or row.get("error"),
        "notes": row.get("notes"),
    }


@router.get("/live")
async def live() -> Dict[str, Any]:
    from app.services.opportunity_tracker import opportunity_tracker
    from app.services.paper_journal import paper_journal
    from app.services.paper_pipeline import paper_pipeline
    from app.services.paper_trade_tracker import paper_trade_tracker
    from app.services.perp_micro_coach import perp_micro_coach
    from app.services.quality_dip_scanner import quality_dip_scanner
    from app.services.scanner import scanner
    from app.services.performance import opportunities as list_opportunities

    settings = get_settings()
    paper: Dict[str, Any] = {}
    try:
        paper = paper_pipeline.as_json()
    except Exception as e:
        paper = {"error": str(e)[:200]}

    journal: Dict[str, Any] = {}
    opens: List[Dict[str, Any]] = []
    try:
        journal = await paper_journal.stats()
        coach_map: Dict[str, Dict[str, Any]] = {}
        try:
            for p in await perp_micro_coach.list_open_papers():
                coach_map[str(p.get("id") or p.get("trade_id"))] = p
        except Exception:
            coach_map = {}
        opens = [
            _open_row(r, coach_map.get(str(r.get("trade_id"))))
            for r in paper_journal.list_open()
        ]
    except Exception as e:
        journal = {"error": str(e)[:200]}

    opps: List[Dict[str, Any]] = []
    try:
        opps = await list_opportunities()
    except Exception:
        opps = []

    inv: Dict[str, Any] = {}
    try:
        from app.investment.diagnostics import load_last_cycle
        from app.investment.scan import investment_scanner

        inv = {
            "enabled": bool(getattr(settings, "investment_scan_enabled", False)),
            "running": bool(getattr(investment_scanner, "running", False)),
            "last_cycle": load_last_cycle() or {},
        }
    except Exception as e:
        inv = {"enabled": False, "error": str(e)[:160]}

    cfg = paper.get("effective_config") or {}
    h24 = paper.get("last_24h") or {}
    why = paper.get("why_no_trade") or {}
    if opens:
        why = dict(why)
        why["headline"] = f"{len(opens)} paper trade(s) currently open."
    last_open = paper.get("last_paper_open")
    last_qual = paper.get("last_qualified_setup")
    if not last_open and opens:
        last_open = max((str(r.get("opened_at") or "") for r in opens), default=None) or None
        last_qual = last_qual or last_open

    dip_paper: Dict[str, Any] = {}
    try:
        from app.investment.paper_book import PaperBook

        dip_paper = PaperBook.load().snapshot()
    except Exception:
        dip_paper = {}

    equity_tape: Dict[str, Any] = {}
    try:
        from app.investment.tape import public_payload as equity_tape_payload

        equity_tape = equity_tape_payload()
    except Exception as e:
        equity_tape = {"error": str(e)[:160], "rows": [], "nearest": [], "quiet": True}

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Watch-only. Discord is the alert feed. Atlas does not place broker orders.",
        "health": {
            "api": "ok",
            "hyperliquid_data": paper.get("hyperliquid_data"),
            "scanner": bool(getattr(scanner, "running", False)),
            "opportunity_tracker": bool(getattr(opportunity_tracker, "running", False)),
            "paper_tracker": bool(getattr(paper_trade_tracker, "running", False)),
            "perp_micro": bool(getattr(perp_micro_coach, "running", False)),
            "quality_dip": bool(getattr(quality_dip_scanner, "running", False)),
            "discord": bool(is_discord_ready()),
            "liquid_count": int(paper.get("liquid_count") or 0),
            "last_cycle_at": paper.get("last_cycle_at"),
            "last_error": paper.get("last_error"),
            "cycle_count": paper.get("cycle_count"),
        },
        "gates": {
            "rsi_long": cfg.get("rsi_long", settings.perp_micro_rsi_long),
            "rsi_short": cfg.get("rsi_short", settings.perp_micro_rsi_short),
            "extension_pct": cfg.get("extension", settings.perp_micro_min_extension_pct),
            "min_rr": cfg.get("minimum_rr", settings.perp_micro_min_rr),
            "min_volume": cfg.get("min_volume", settings.perp_micro_min_vol),
            "max_open": cfg.get("max_open", settings.perp_micro_max_open),
        },
        "funnel_24h": h24,
        "why_no_trade": why,
        "bottleneck": paper.get("bottleneck"),
        "warnings": paper.get("warnings") or [],
        "activity": {
            "last_market_data": paper.get("last_successful_market_data_fetch"),
            "last_candles": paper.get("last_successful_candle_fetch"),
            "last_evaluation": paper.get("last_candidate_evaluation"),
            "last_qualified": last_qual,
            "last_paper_open": last_open,
            "last_discord_alert": paper.get("last_discord_alert"),
            "discord_subscribers": paper.get("discord_subscribers"),
        },
        "journal": journal,
        "open_trades": opens,
        "opportunities": opps,
        "quality_dips": {
            "running": bool(getattr(quality_dip_scanner, "running", False)),
            "last_scan_at": getattr(quality_dip_scanner, "last_scan_at", None),
            "candidates": list(getattr(quality_dip_scanner, "last_snapshot", []) or []),
            "discord_enabled": bool(settings.quality_dip_discord_enabled),
            "auto_paper": bool(settings.quality_dip_auto_paper),
        },
        "major_tape": getattr(perp_micro_coach, "last_major_tape", {}) or {},
        "equity_majors_tape": equity_tape,
        "dip_paper": dip_paper,
        "investment": inv,
        "paper_lifecycle": {},
    }
    try:
        payload["paper_lifecycle"] = perp_micro_coach.lifecycle_snapshot()
    except Exception as e:
        payload["paper_lifecycle"] = {"error": str(e)[:160]}
    return payload
