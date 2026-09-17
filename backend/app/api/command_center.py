from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter

from app.services.command_center_summary import live_command_center_summary
from app.services.perp_manual_service import perp_manual_service
from app.services.perp_paper_observability import build_paper_observability
from app.services.perp_setup_paper_mirror import perp_setup_paper_mirror

router = APIRouter(prefix="/api/command-center", tags=["command-center"])


def _build_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    setups = list(snapshot.get("setups") or [])
    snapshot["auto_paper"] = {
        **perp_setup_paper_mirror.status(),
        "included_in_paper_journal": True,
        "counts_for_live": False,
        "observability": build_paper_observability(setups),
    }
    return live_command_center_summary(snapshot)


@router.get("/summary")
async def command_center_summary() -> Dict[str, Any]:
    snapshot = perp_manual_service.snapshot()
    return await asyncio.to_thread(_build_summary, snapshot)
