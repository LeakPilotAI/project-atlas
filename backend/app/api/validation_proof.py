from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.investment.storage import OPPORTUNITIES_PATH, OUTCOMES_PATH
from app.services.outcome_research import load_paper_closes
from app.services.validation_proof import _jsonl, build_validation_proof

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("/proof")
async def validation_proof() -> Dict[str, Any]:
    return build_validation_proof(
        paper_rows=load_paper_closes(),
        opportunity_rows=_jsonl(OPPORTUNITIES_PATH),
        outcome_rows=_jsonl(OUTCOMES_PATH),
    )
