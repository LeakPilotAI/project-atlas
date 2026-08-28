"""Versioned research record. Scores are ordinal rankings, not probabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.investment.drawdown import DrawdownReport
from app.investment.enums import (
    AssetType,
    EvidenceQuality,
    InvestmentAlertState,
    ThesisState,
)
from app.investment.models import InvestmentAsset, InvestmentOpportunity, _iso, _now

SCORING_VERSION = "atlas-invest-3.0"

DISCLAIMER = (
    "Opportunity scores are ordinal research rankings (0–100), not probabilities, "
    "not recommendations, and not guarantees."
)


@dataclass
class ComponentScores:
    """Named 0–100 components. Missing stays None — never a fake 0."""

    valuation: Optional[int] = None
    fundamentals: Optional[int] = None
    drawdown: Optional[int] = None
    balance_sheet: Optional[int] = None
    growth: Optional[int] = None
    cash_flow: Optional[int] = None
    thesis_integrity: Optional[int] = None
    risk: Optional[int] = None
    evidence_quality: Optional[int] = None

    def as_dict(self) -> Dict[str, Optional[int]]:
        return {
            "valuation": self.valuation,
            "fundamentals": self.fundamentals,
            "drawdown": self.drawdown,
            "balance_sheet": self.balance_sheet,
            "growth": self.growth,
            "cash_flow": self.cash_flow,
            "thesis_integrity": self.thesis_integrity,
            "risk": self.risk,
            "evidence_quality": self.evidence_quality,
        }

    def present(self) -> Dict[str, int]:
        return {k: v for k, v in self.as_dict().items() if v is not None}


@dataclass
class Explainability:
    why_this_asset: List[str] = field(default_factory=list)
    why_interesting: List[str] = field(default_factory=list)
    why_now: List[str] = field(default_factory=list)
    supports_thesis: List[str] = field(default_factory=list)
    weakens_thesis: List[str] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)
    invalidation: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    data_quality_notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, List[str]]:
        return {
            "why_this_asset": list(self.why_this_asset),
            "why_interesting": list(self.why_interesting),
            "why_now": list(self.why_now),
            "supports_thesis": list(self.supports_thesis),
            "weakens_thesis": list(self.weakens_thesis),
            "missing_data": list(self.missing_data),
            "invalidation": list(self.invalidation),
            "risks": list(self.risks),
            "data_quality_notes": list(self.data_quality_notes),
        }


@dataclass
class ResearchRecord:
    """One scored opportunity. Append-only. Not a trade ticket."""

    scoring_version: str = SCORING_VERSION
    timestamp: datetime = field(default_factory=_now)
    symbol: str = ""
    asset_type: AssetType = AssetType.UNKNOWN
    name: str = ""
    price: Optional[float] = None
    classification: InvestmentAlertState = InvestmentAlertState.NO_ACTION
    opportunity_score: Optional[int] = None
    evidence_quality: EvidenceQuality = EvidenceQuality.UNKNOWN
    thesis: ThesisState = ThesisState.UNKNOWN
    components: ComponentScores = field(default_factory=ComponentScores)
    drawdown: DrawdownReport = field(default_factory=DrawdownReport)
    market_risk: List[str] = field(default_factory=list)
    fundamental_risk: List[str] = field(default_factory=list)
    data_risk: List[str] = field(default_factory=list)
    explain: Explainability = field(default_factory=Explainability)
    missing_critical: List[str] = field(default_factory=list)
    generational_blockers: List[str] = field(default_factory=list)
    input_snapshot: Dict[str, Any] = field(default_factory=dict)
    coverage_label: str = ""
    disclaimer: str = DISCLAIMER

    def as_probability_claim(self) -> str:
        raise RuntimeError("Investment scores are not probabilities. Do not claim chance of profit.")

    def to_opportunity(self, asset: InvestmentAsset) -> InvestmentOpportunity:
        return InvestmentOpportunity(
            asset=asset,
            timestamp=self.timestamp,
            classification=self.classification,
            opportunity_score=None if self.opportunity_score is None else float(self.opportunity_score),
            confidence=None,
            evidence_quality=self.evidence_quality,
            thesis_integrity=self.thesis,
            valuation_score=None if self.components.valuation is None else float(self.components.valuation),
            fundamental_score=None if self.components.fundamentals is None else float(self.components.fundamentals),
            drawdown_score=None if self.components.drawdown is None else float(self.components.drawdown),
            risk_score=None if self.components.risk is None else float(self.components.risk),
            historical_context=self.coverage_label,
            risks=list(self.explain.risks),
            reasons=list(self.explain.why_now),
            data_sources=["investment_snapshot", "investment_history"],
            missing_critical=list(self.missing_critical),
            scoring_version=self.scoring_version,
            component_scores={k: (None if v is None else float(v)) for k, v in self.components.as_dict().items()},
            why_now=list(self.explain.why_now),
            supports=list(self.explain.supports_thesis),
            weakens=list(self.explain.weakens_thesis),
            missing_data=list(self.explain.missing_data),
            invalidation=list(self.explain.invalidation),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scoring_version": self.scoring_version,
            "timestamp": _iso(self.timestamp) or datetime.now(timezone.utc).isoformat(),
            "symbol": self.symbol,
            "asset_type": self.asset_type.value,
            "name": self.name,
            "price": self.price,
            "classification": self.classification.value,
            "opportunity_score": self.opportunity_score,
            "evidence_quality": self.evidence_quality.value,
            "thesis": self.thesis.value,
            "components": self.components.as_dict(),
            "drawdown": self.drawdown.as_dict(),
            "market_risk": list(self.market_risk),
            "fundamental_risk": list(self.fundamental_risk),
            "data_risk": list(self.data_risk),
            "explain": self.explain.as_dict(),
            "missing_critical": list(self.missing_critical),
            "generational_blockers": list(self.generational_blockers),
            "input_snapshot": self.input_snapshot,
            "coverage_label": self.coverage_label,
            "disclaimer": self.disclaimer,
        }
