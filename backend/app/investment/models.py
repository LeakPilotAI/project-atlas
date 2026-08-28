"""Normalized investment models. Values default to UNKNOWN — never invented."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar

from app.investment.enums import (
    AssetType,
    DataQuality,
    EvidenceQuality,
    InvestmentAlertState,
    InvestmentHorizon,
    RiskTolerance,
    ThesisState,
)

T = TypeVar("T")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


@dataclass
class MeasuredValue:
    """One metric with provenance. Missing data is MISSING, never guessed.

    Provenance (required on important points):
      source, retrieved_at, effective_timestamp, quality
    `timestamp` is kept as an alias of effective_timestamp (Phase 1).
    """

    value: Any = None
    source: str = "none"
    timestamp: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    effective_timestamp: Optional[datetime] = None
    quality: DataQuality = DataQuality.UNKNOWN
    availability: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if self.effective_timestamp is None and self.timestamp is not None:
            self.effective_timestamp = self.timestamp
        elif self.timestamp is None and self.effective_timestamp is not None:
            self.timestamp = self.effective_timestamp

    @classmethod
    def unknown(cls, source: str = "none", notes: str = "not provided") -> "MeasuredValue":
        fetched = _now()
        return cls(
            value=None,
            source=source,
            timestamp=None,
            retrieved_at=fetched,
            effective_timestamp=None,
            quality=DataQuality.MISSING,
            availability=False,
            notes=notes,
        )

    @classmethod
    def of(
        cls,
        value: Any,
        *,
        source: str,
        timestamp: Optional[datetime] = None,
        quality: DataQuality = DataQuality.FRESH,
        retrieved_at: Optional[datetime] = None,
        effective_timestamp: Optional[datetime] = None,
        notes: str = "",
    ) -> "MeasuredValue":
        if value is None:
            return cls.unknown(source=source, notes=notes or "null value")
        fetched = retrieved_at or _now()
        as_of = effective_timestamp or timestamp or fetched
        return cls(
            value=value,
            source=source,
            timestamp=as_of,
            retrieved_at=fetched,
            effective_timestamp=as_of,
            quality=quality,
            availability=True,
            notes=notes,
        )

    def is_usable(self) -> bool:
        return self.availability and self.quality in (DataQuality.FRESH, DataQuality.STALE) and self.value is not None

    def as_dict(self) -> Dict[str, Any]:
        q = self.quality.value if isinstance(self.quality, DataQuality) else self.quality
        return {
            "value": self.value,
            "source": self.source,
            "retrieved_at": _iso(self.retrieved_at),
            "effective_timestamp": _iso(self.effective_timestamp or self.timestamp),
            "quality": q,
            "availability": self.availability,
            "notes": self.notes,
        }


@dataclass
class InvestmentAsset:
    """Normalized long-term asset. No ticker universe hard-coded here."""

    symbol: str
    asset_type: AssetType = AssetType.UNKNOWN
    name: str = ""
    sector: str = ""
    industry: str = ""
    exchange: str = ""
    currency: str = "USD"
    price: MeasuredValue = field(default_factory=MeasuredValue.unknown)
    market_cap: MeasuredValue = field(default_factory=MeasuredValue.unknown)
    liquidity: MeasuredValue = field(default_factory=MeasuredValue.unknown)
    data_timestamp: Optional[datetime] = None
    active: bool = True

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol or "").upper().strip()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_type": self.asset_type.value,
            "name": self.name,
            "sector": self.sector,
            "industry": self.industry,
            "exchange": self.exchange,
            "currency": self.currency,
            "active": self.active,
            "price": self.price.as_dict(),
            "market_cap": self.market_cap.as_dict(),
            "data_timestamp": _iso(self.data_timestamp),
        }


@dataclass
class HoldingInput:
    symbol: str
    shares: float = 0.0
    average_cost: Optional[float] = None
    current_value: Optional[float] = None
    sector: str = ""

    def __post_init__(self) -> None:
        self.symbol = str(self.symbol or "").upper().strip()


@dataclass
class PortfolioInput:
    """User capital context. Allocation is forbidden without this."""

    portfolio_value: Optional[float] = None
    available_cash: Optional[float] = None
    holdings: List[HoldingInput] = field(default_factory=list)
    maximum_position_percent: float = 15.0
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    risk_tolerance: RiskTolerance = RiskTolerance.UNKNOWN
    investment_horizon: InvestmentHorizon = InvestmentHorizon.UNKNOWN
    provided: bool = False

    def is_complete_for_allocation(self) -> bool:
        return (
            self.provided
            and self.portfolio_value is not None
            and self.portfolio_value > 0
            and self.available_cash is not None
            and self.available_cash >= 0
        )


@dataclass
class InvestmentOpportunity:
    """Research record. opportunity_score is NOT a probability."""

    asset: InvestmentAsset
    timestamp: datetime = field(default_factory=_now)
    classification: InvestmentAlertState = InvestmentAlertState.NO_ACTION
    opportunity_score: Optional[float] = None  # 0–100 ordinal, not P(profit)
    confidence: Optional[float] = None  # 0–100, separate from score
    evidence_quality: EvidenceQuality = EvidenceQuality.UNKNOWN
    thesis_integrity: ThesisState = ThesisState.UNKNOWN
    valuation_score: Optional[float] = None
    fundamental_score: Optional[float] = None
    drawdown_score: Optional[float] = None
    risk_score: Optional[float] = None
    catalyst_score: Optional[float] = None
    historical_context: str = ""
    risks: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    missing_critical: List[str] = field(default_factory=list)
    scoring_version: str = ""
    component_scores: Dict[str, Optional[float]] = field(default_factory=dict)
    why_now: List[str] = field(default_factory=list)
    supports: List[str] = field(default_factory=list)
    weakens: List[str] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)
    invalidation: List[str] = field(default_factory=list)

    def as_probability_claim(self) -> str:
        raise RuntimeError("Investment scores are not probabilities. Do not claim chance of profit.")


@dataclass
class AllocationTier:
    index: int
    price: Optional[float] = None
    dollar_amount: Optional[float] = None
    share_quantity: Optional[float] = None


@dataclass
class AllocationPlan:
    symbol: str = ""
    available_buying_power: Optional[float] = None
    maximum_target_allocation: Optional[float] = None
    reserve_cash: Optional[float] = None
    number_of_tiers: int = 0
    tiers: List[AllocationTier] = field(default_factory=list)
    remaining_buying_power: Optional[float] = None
    blocked_reason: str = ""

    def is_actionable(self) -> bool:
        return not self.blocked_reason and self.number_of_tiers > 0


@dataclass
class PaperInvestmentAccount:
    """Separate simulated long-term book. Never mixes with Hyperliquid paper."""

    cash: float = 0.0
    shares: Dict[str, float] = field(default_factory=dict)
    orders: List[Dict[str, Any]] = field(default_factory=list)
    fills: List[Dict[str, Any]] = field(default_factory=list)
    portfolio_value: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    drawdown: float = 0.0
    dividends: float = 0.0
    benchmark: str = ""
    ledger_name: str = "paper_investment"

    def execute_broker_order(self, *_a: Any, **_k: Any) -> None:
        raise RuntimeError("No real brokerage execution. Investment engine is research/paper only.")
