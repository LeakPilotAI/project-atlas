"""Hard architectural rules for the investment engine. Foundation only."""

from __future__ import annotations

from typing import Iterable, List

from app.investment.enums import DataQuality, EvidenceQuality, InvestmentAlertState
from app.investment.models import AllocationPlan, InvestmentOpportunity, PortfolioInput
from app.investment.storage import assert_storage_separated

HIGH_CONVICTION = {
    InvestmentAlertState.DEEP_VALUE,
    InvestmentAlertState.GENERATIONAL_OPPORTUNITY,
    InvestmentAlertState.ACCUMULATION,
}

SAFETY_RULES = (
    "No real brokerage order execution.",
    "No automatic real-money investment.",
    "No guaranteed returns.",
    "No buy-every-dip.",
    "No allocation without portfolio information.",
    "No high-conviction alert with missing critical data.",
    "No invented fundamentals.",
    "No future information in historical analysis.",
    "No survivorship-biased backtests.",
    "No ML in Phase 1.",
    "No automatic threshold optimization.",
    "No changes to the Hyperliquid trading engine.",
)


def refuse_high_conviction_if_missing(
    opportunity: InvestmentOpportunity,
    critical_fields: Iterable[str] | None = None,
) -> List[str]:
    """Return reasons a high-conviction alert must be blocked. Does not score."""
    reasons: List[str] = []
    missing = list(opportunity.missing_critical)
    if critical_fields:
        for name in critical_fields:
            if name not in missing:
                # caller may pass metric names already known missing
                pass
    if opportunity.evidence_quality in (EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN):
        reasons.append("evidence_quality insufficient")
    if opportunity.classification in HIGH_CONVICTION and missing:
        reasons.append("critical evidence missing: " + ", ".join(missing))
    if opportunity.classification in HIGH_CONVICTION and opportunity.asset.price.quality in (
        DataQuality.MISSING,
        DataQuality.UNKNOWN,
        DataQuality.CONFLICTING,
    ):
        reasons.append("price evidence not usable")
    return reasons


def allocation_without_portfolio(portfolio: PortfolioInput) -> AllocationPlan:
    if not portfolio.is_complete_for_allocation():
        return AllocationPlan(blocked_reason="portfolio information required")
    return AllocationPlan(blocked_reason="allocation algorithm not implemented in Phase 1")


def no_brokerage_execution() -> None:
    raise RuntimeError("Investment engine does not place real brokerage orders.")


def check_invariants() -> None:
    assert_storage_separated()
