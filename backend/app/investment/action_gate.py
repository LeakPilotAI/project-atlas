"""Deterministic action gate for Atlas Quality Dips / Robinhood research.

Independent from Hyperliquid/perp code. Converts an already-scored investment
ResearchRecord into a conservative manual-action stance. Scores remain ordinal
research rankings, never probabilities or guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.investment.enums import AssetType, EvidenceQuality, InvestmentAlertState, ThesisState
from app.investment.research_models import ResearchRecord


class InvestmentReadiness(str, Enum):
    WATCH = "WATCH"
    PREPARE = "PREPARE"
    ACCUMULATE = "ACCUMULATE"
    STAND_DOWN = "STAND_DOWN"


@dataclass(frozen=True)
class ReadinessDecision:
    stance: InvestmentReadiness
    ladder_eligible: bool
    blockers: tuple[str, ...]
    reasons: tuple[str, ...]
    domain: str = "EQUITY_INVESTMENT"
    execution: str = "MANUAL_ONLY"

    def as_dict(self) -> dict:
        return {
            "stance": self.stance.value,
            "ladder_eligible": self.ladder_eligible,
            "blockers": list(self.blockers),
            "reasons": list(self.reasons),
            "domain": self.domain,
            "execution": self.execution,
        }


_ALLOWED_ASSET_TYPES = {AssetType.STOCK, AssetType.ETF, AssetType.SECTOR_ETF}
_ACTIONABLE_CLASSIFICATIONS = {
    InvestmentAlertState.ACCUMULATION,
    InvestmentAlertState.DEEP_VALUE,
    InvestmentAlertState.GENERATIONAL_OPPORTUNITY,
}


def evaluate_investment_readiness(rec: ResearchRecord) -> ReadinessDecision:
    blockers: list[str] = []
    reasons: list[str] = []

    if rec.asset_type not in _ALLOWED_ASSET_TYPES:
        blockers.append("Quality Dips accepts stocks and ETFs only")
    if rec.thesis is ThesisState.BROKEN or rec.classification is InvestmentAlertState.THESIS_BROKEN:
        blockers.append("investment thesis is broken")
    if rec.thesis is ThesisState.UNKNOWN:
        blockers.append("investment thesis is unknown")
    if rec.evidence_quality in {EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN}:
        blockers.append("evidence quality is insufficient")
    if rec.missing_critical:
        blockers.append("critical evidence is missing")

    if blockers:
        hard_stop = (
            "Quality Dips accepts stocks and ETFs only" in blockers
            or "investment thesis is broken" in blockers
        )
        return ReadinessDecision(
            InvestmentReadiness.STAND_DOWN if hard_stop else InvestmentReadiness.WATCH,
            False,
            tuple(blockers),
            tuple(reasons),
        )

    if rec.classification not in _ACTIONABLE_CLASSIFICATIONS:
        reasons.append("research classification is not an accumulation state")
        return ReadinessDecision(InvestmentReadiness.WATCH, False, (), tuple(reasons))

    if rec.evidence_quality is EvidenceQuality.LOW:
        reasons.append("low evidence quality requires confirmation before sizing a ladder")
        return ReadinessDecision(InvestmentReadiness.PREPARE, False, (), tuple(reasons))

    if rec.thesis in {ThesisState.DAMAGED, ThesisState.UNDER_PRESSURE}:
        reasons.append("thesis is under pressure; prepare levels but do not accumulate yet")
        return ReadinessDecision(InvestmentReadiness.PREPARE, False, (), tuple(reasons))

    required = {
        "valuation": rec.components.valuation,
        "fundamentals": rec.components.fundamentals,
        "drawdown": rec.components.drawdown,
        "thesis_integrity": rec.components.thesis_integrity,
    }
    missing_components = [name for name, value in required.items() if value is None]
    if missing_components:
        reasons.append("missing scored components: " + ", ".join(missing_components))
        return ReadinessDecision(InvestmentReadiness.PREPARE, False, (), tuple(reasons))

    reasons.append("actionable valuation/dislocation with sufficient evidence and intact thesis")
    return ReadinessDecision(InvestmentReadiness.ACCUMULATE, True, (), tuple(reasons))
