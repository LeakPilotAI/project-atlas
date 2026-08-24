"""Performance HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.performance_service import get_performance_report

router = APIRouter(prefix="/api", tags=["performance"])


@router.get("/performance")
async def performance():
    return await get_performance_report()