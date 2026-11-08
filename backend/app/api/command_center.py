from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.command_center_summary import live_command_center_summary
from app.services.perp_manual_service import perp_manual_service
from app.services.perp_paper_observability import build_paper_observability
from app.services.perp_setup_paper_mirror import perp_setup_paper_mirror

router = APIRouter(prefix="/api/command-center", tags=["command-center"])

# The V6 evidence presentation intentionally reads many durable histories. Keep one
# background refresh in flight and bound the desktop/UI request latency.
_COMMAND_RESPONSE_BUDGET_SECONDS = 2.5
_command_cache: Optional[Dict[str, Any]] = None
_command_task: Optional[asyncio.Task] = None


def _build_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    setups = list(snapshot.get("setups") or [])
    snapshot["auto_paper"] = {
        **perp_setup_paper_mirror.status(),
        "included_in_paper_journal": True,
        "counts_for_live": False,
        "observability": build_paper_observability(setups),
    }
    result = live_command_center_summary(snapshot)
    result["operational_surface"] = {"state": "FRESH", "background_refresh": False}
    return result


def _warming_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    setups = list(snapshot.get("setups") or [])
    return {
        "domain": "ORCHESTRATION",
        "mode": "READ_ONLY",
        "execution": "NO_ORDER_ACTIONS",
        "perps": {
            "domain": "HYPERLIQUID_PERPS",
            "execution": "MANUAL_ONLY",
            "running": bool(snapshot.get("running")),
            "market_count": int(snapshot.get("market_count") or 0),
            "setup_count": len(setups),
            "last_error": snapshot.get("last_error"),
        },
        "investments": {"domain": "EQUITY_INVESTMENT", "execution": "MANUAL_ONLY"},
        "research": {"trading_readiness": "NOT_READY", "live_capital_allowed": False},
        "research_evidence": {"mode": "BACKGROUND_REFRESH_PENDING"},
        "guardrails": {
            "shared_symbols": False,
            "shared_capital_assumptions": False,
            "shared_performance": False,
            "shared_action_logic": False,
        },
        "research_guardrails": {
            "research_is_trading_readiness": False,
            "automatic_promotion": False,
            "live_capital_allowed": False,
        },
        "operational_surface": {
            "state": "WARMING",
            "background_refresh": True,
            "read_only": True,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        },
    }


@router.get("/summary")
async def command_center_summary() -> Dict[str, Any]:
    global _command_cache, _command_task

    snapshot = perp_manual_service.snapshot()

    if _command_task is not None and _command_task.done():
        try:
            _command_cache = _command_task.result()
        except Exception:
            pass
        _command_task = None

    if _command_task is None:
        _command_task = asyncio.create_task(asyncio.to_thread(_build_summary, snapshot))

    try:
        result = await asyncio.wait_for(
            asyncio.shield(_command_task), timeout=_COMMAND_RESPONSE_BUDGET_SECONDS
        )
        _command_cache = result
        _command_task = None
        return result
    except asyncio.TimeoutError:
        if _command_cache is not None:
            stale = dict(_command_cache)
            stale["operational_surface"] = {
                "state": "STALE_WHILE_REFRESHING",
                "background_refresh": True,
                "read_only": True,
                "live_capital_allowed": False,
                "automatic_real_money_execution": False,
            }
            return stale
        return _warming_summary(snapshot)
