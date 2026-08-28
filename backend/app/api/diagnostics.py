"""HTTP diagnostics for the paper pipeline. No strategy changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/research")
async def diagnostics_research() -> Dict[str, Any]:
    from app.services.paper_pipeline import paper_pipeline
    from app.services.shadow_research import shadow_research

    shadow = shadow_research.funnel_stats(24.0)
    return {
        "last_24h": paper_pipeline.last_24h(),
        "bottleneck": paper_pipeline.bottleneck_text(),
        "funnel_text": paper_pipeline.funnel_24h_text(),
        "shadow": shadow,
        "why_no_trade": paper_pipeline.why_no_trade(),
        "effective_config": paper_pipeline.effective_config(),
    }


@router.get("/paper")
async def diagnostics_paper() -> Dict[str, Any]:
    from app.services.paper_pipeline import paper_pipeline

    return paper_pipeline.as_json()


@router.get("")
async def diagnostics_root() -> Dict[str, Any]:
    from app.services.paper_pipeline import paper_pipeline

    return paper_pipeline.as_json()


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
