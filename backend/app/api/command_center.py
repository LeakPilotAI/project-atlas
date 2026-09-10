from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.command_center_summary import live_command_center_summary
from app.services.perp_manual_service import perp_manual_service

router = APIRouter(prefix="/api/command-center", tags=["command-center"])


@router.get("/summary")
async def command_center_summary() -> Dict[str, Any]:
    return live_command_center_summary(perp_manual_service.snapshot())
