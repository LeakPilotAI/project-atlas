"""Local read-only research views and stateless scenario arithmetic."""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app.investment.daily_research_plan import PLAN_PATH
from app.investment.prospective_evidence import read_records
from app.investment.prospective_report import evidence_report
from app.investment.research_math import compound_scenario

router = APIRouter(prefix="/api/investments/prospective", tags=["prospective research"])


@router.get("/report")
def report():
    plans = read_records(PLAN_PATH)
    from app.investment.policy_research import evaluate_challengers
    from app.investment.portfolio import load_portfolio
    from app.investment.adaptive_valuation import REVISIONS

    valuations = {row["symbol"]: row for row in read_records(REVISIONS)}
    return {
        "daily_plan": plans[-1] if plans else None,
        "plan_history_count": len(plans),
        "latest_valuation_revisions": list(valuations.values()),
        "policies": evaluate_challengers(),
        **evidence_report(benchmark_symbol=load_portfolio().benchmark_symbol),
    }


@router.get("/plans")
def plans():
    return {"plans": read_records(PLAN_PATH), "execution": "MANUAL_ONLY"}


@router.get("/view")
def view():
    return FileResponse(
        Path(__file__).resolve().parents[1] / "static" / "prospective_research.html"
    )


class Scenario(BaseModel):
    starting_capital: float = Field(ge=0)
    contribution: float = Field(ge=0)
    years: float = Field(ge=0, le=100)
    price_growth: float = Field(gt=-1)
    distribution_yield: float = Field(default=0, ge=0)
    reinvest: bool = True
    annual_fee: float = Field(default=0, ge=0, lt=1)
    contributions_per_year: int = 12
    distribution_tax_rate: float | None = Field(default=None, ge=0, le=1)


@router.post("/compound")
def compound(scenario: Scenario):
    try:
        return compound_scenario(**scenario.model_dump())
    except (ValueError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc
