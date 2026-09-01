"""HTTP for Phase 6 paper validation. Read-only. Does not change gates."""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/validation", tags=["validation"])


def _json_http(body: Any, status_code: int = 200) -> JSONResponse:
    """Never let FastAPI/Starlette jsonable_encoder 500 this route.

    Starlette JSONResponse uses allow_nan=False. Pre-serialize with default=str
    so NaN/Inf/exotic types cannot crash the API. Always JSON, never HTML 500.
    """
    try:
        payload = json.loads(json.dumps(body, allow_nan=False, default=str))
    except Exception as e:
        payload = {
            "ok": False,
            "title": "ATLAS EDGE DIAGNOSTICS",
            "error": f"serialize: {type(e).__name__}: {str(e)[:180]}",
            "live_capital_allowed": False,
            "disclaimer": "Diagnostics failed to serialize. Journal was not rewritten.",
        }
    return JSONResponse(content=payload, status_code=status_code)


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
async def edge_endpoint() -> JSONResponse:
    try:
        from app.services.edge_diagnostics import edge_report

        body = edge_report()
    except Exception as e:
        body = {
            "ok": False,
            "title": "ATLAS EDGE DIAGNOSTICS",
            "error": f"{type(e).__name__}: {str(e)[:240]}",
            "live_capital_allowed": False,
            "baseline": {"n": 0, "winrate": 0.0, "expectancy": 0.0, "total_r": 0.0},
            "malformed_count": 0,
            "section_errors": [str(e)[:240]],
            "disclaimer": "Diagnostics failed to fully build. Journal was not rewritten.",
        }
    return _json_http(body, 200)


@router.get("/edge/text")
async def edge_text_endpoint() -> JSONResponse:
    try:
        from app.services.edge_diagnostics import edge_text

        body: Dict[str, Any] = {"text": edge_text()}
    except Exception as e:
        body = {"text": f"ATLAS EDGE DIAGNOSTICS failed: {type(e).__name__}: {str(e)[:180]}"}
    return _json_http(body, 200)