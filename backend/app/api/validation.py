"""HTTP for Phase 6 paper validation. Read-only. Does not change gates."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("")
@router.get("/report")
async def validation_report() -> Dict[str, Any]:
    from app.services.paper_validation import full_report

    return full_report()


@router.get("/summary")
async def validation_summary() -> Dict[str, Any]:
    from app.services.paper_validation import readiness_report, uncertainty, load_paper_closes

    rows = load_paper_closes()
    rd = readiness_report(rows)
    return {
        "closed": rd["closed_trades"],
        "winrate": rd["observed_wr"],
        "expectancy": rd["observed_expectancy"],
        "total_r": rd["total_r"],
        "uncertainty": uncertainty(rows),
        "data_sufficiency": rd["data_sufficiency"],
        "statistical_stability": rd["statistical_stability"],
        "performance": rd["performance"],
        "risk": rd["risk"],
        "data_integrity": rd["data_integrity"],
        "conclusion": rd["conclusion"],
        "live_capital_allowed": False,
        "milestone": rd["milestone"],
    }


@router.get("/text")
async def validation_text_endpoint() -> Dict[str, str]:
    from app.services.paper_validation import validation_text

    return {"text": validation_text()}


@router.get("/edge")
async def edge_endpoint() -> Dict[str, Any]:
    from app.services.edge_diagnostics import edge_report

    return edge_report()


@router.get("/edge/text")
async def edge_text_endpoint() -> Dict[str, str]:
    from app.services.edge_diagnostics import edge_text

    return {"text": edge_text()}
