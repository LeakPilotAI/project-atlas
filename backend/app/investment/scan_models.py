"""Point-in-time scan observation. Append-only. Outcomes stay NULL at T."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.investment.enums import InvestmentAlertState
from app.investment.models import _iso
from app.investment.outcomes import empty_outcomes
from app.investment.research_models import ResearchRecord

SCAN_VERSION = "atlas-scan-5.1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ScanObservation:
    """One evaluated name at T. Qualified and rejected both persist."""

    observation_id: str = ""
    scan_id: str = ""
    scan_version: str = SCAN_VERSION
    as_of: datetime = field(default_factory=_now)
    symbol: str = ""
    qualified: bool = False
    classification: str = InvestmentAlertState.NO_ACTION.value
    blocking_reason: str = ""
    blocking_factors: List[str] = field(default_factory=list)
    field_quality: Dict[str, str] = field(default_factory=dict)
    data_source_status: Dict[str, str] = field(default_factory=dict)
    provider_failures: List[Dict[str, Any]] = field(default_factory=list)
    session: str = "MARKET_CLOSED"
    look_ahead_protected: bool = True
    research: Optional[ResearchRecord] = None
    outcomes: Dict[str, Optional[float]] = field(default_factory=empty_outcomes)
    fetched: Dict[str, bool] = field(default_factory=dict)
    evaluation: str = ""
    evaluation_reason: str = ""
    completeness: Dict[str, Any] = field(default_factory=dict)
    known_at: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observation_id:
            ts = self.as_of.strftime("%Y%m%dT%H%M%SZ")
            self.observation_id = f"{self.symbol or 'UNK'}-{ts}-{uuid4().hex[:8]}"
        if self.outcomes is None:
            self.outcomes = empty_outcomes()

    def as_dict(self) -> Dict[str, Any]:
        rec = self.research.as_dict() if self.research is not None else {}
        return {
            "observation_id": self.observation_id,
            "scan_id": self.scan_id,
            "scan_version": self.scan_version,
            "as_of": _iso(self.as_of),
            "timestamp": _iso(self.as_of),
            "symbol": self.symbol,
            "qualified": self.qualified,
            "classification": self.classification,
            "blocking_reason": self.blocking_reason,
            "blocking_factors": list(self.blocking_factors),
            "field_quality": dict(self.field_quality),
            "data_source_status": dict(self.data_source_status),
            "provider_failures": list(self.provider_failures),
            "session": self.session,
            "look_ahead_protected": True,
            "fetched": dict(self.fetched),
            "research": rec,
            "price": rec.get("price"),
            "opportunity_score": rec.get("opportunity_score"),
            "thesis": rec.get("thesis"),
            "evidence_quality": rec.get("evidence_quality"),
            "drawdown": rec.get("drawdown"),
            "components": rec.get("components"),
            "outcomes": dict(self.outcomes),
            "evaluation": self.evaluation,
            "evaluation_reason": self.evaluation_reason,
            "completeness": dict(self.completeness),
            "known_at": dict(self.known_at),
            "disclaimer": (
                "Point-in-time research observation. Scores used only data available at as_of. "
                "Outcome fields are NULL until a later enrichment pass. Not a probability. "
                "Not a recommendation. Not a brokerage order."
            ),
        }


@dataclass
class ScanReport:
    scan_id: str
    scan_version: str = SCAN_VERSION
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    session: str = "MARKET_CLOSED"
    universe: int = 0
    evaluated: int = 0
    failed: int = 0
    counts: Dict[str, int] = field(default_factory=dict)
    observations: List[ScanObservation] = field(default_factory=list)
    dashboard: str = ""
    data_health: str = ""
    error: str = ""
    alerts_emitted: int = 0
    evaluation_counts: Dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "scan_version": self.scan_version,
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "session": self.session,
            "universe": self.universe,
            "evaluated": self.evaluated,
            "failed": self.failed,
            "alerts_emitted": self.alerts_emitted,
            "counts": dict(self.counts),
            "evaluation_counts": dict(self.evaluation_counts),
            "error": self.error,
            "observation_ids": [o.observation_id for o in self.observations],
        }
