"""Stateful investment alerts. Same classification does not re-fire."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.investment.enums import EvidenceQuality, InvestmentAlertState, ThesisState
from app.investment.research import generational_gate
from app.investment.research_models import ResearchRecord
from app.investment.storage import ALERT_STATE_PATH, ensure_dirs

COOLDOWN = {
    InvestmentAlertState.WATCH: timedelta(hours=24),
    InvestmentAlertState.ACCUMULATION: timedelta(hours=12),
    InvestmentAlertState.DEEP_VALUE: timedelta(hours=6),
    InvestmentAlertState.GENERATIONAL_OPPORTUNITY: timedelta(hours=0),
    InvestmentAlertState.THESIS_BROKEN: timedelta(hours=0),
    InvestmentAlertState.NO_ACTION: timedelta(hours=48),
}

SCORE_DELTA = 8
PRICE_MOVE = 0.08
DRAWDOWN_DELTA = 0.05


@dataclass
class AlertSnapshot:
    symbol: str
    classification: InvestmentAlertState
    last_alert_at: Optional[datetime] = None
    last_score: Optional[int] = None
    last_price: Optional[float] = None
    last_drawdown: Optional[float] = None
    last_thesis: Optional[str] = None


@dataclass
class AlertDecision:
    emit: bool
    reason: str
    classification: InvestmentAlertState
    priority: str = "NORMAL"  # NORMAL · HIGH
    suppressed: bool = False
    previous: Optional[InvestmentAlertState] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


class AlertStore:
    def __init__(self, path: Optional[Path] = None, *, persist: bool = True) -> None:
        self.path = path if path is not None else (ALERT_STATE_PATH if persist else None)
        self._by_symbol: Dict[str, AlertSnapshot] = {}
        self.load()

    def load(self) -> None:
        self._by_symbol = {}
        if not self.path or not Path(self.path).exists():
            return
        try:
            data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        except Exception:
            return
        rows = data.get("symbols") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict) or not row.get("symbol"):
                continue
            try:
                cls = InvestmentAlertState(str(row.get("classification") or "NO_ACTION"))
            except ValueError:
                cls = InvestmentAlertState.NO_ACTION
            snap = AlertSnapshot(
                symbol=str(row["symbol"]).upper(),
                classification=cls,
                last_alert_at=_parse(row.get("last_alert_at")),
                last_score=row.get("last_score"),
                last_price=row.get("last_price"),
                last_drawdown=row.get("last_drawdown"),
                last_thesis=row.get("last_thesis"),
            )
            self._by_symbol[snap.symbol] = snap

    def save(self) -> None:
        if not self.path:
            return
        ensure_dirs()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for s in self._by_symbol.values():
            rows.append(
                {
                    "symbol": s.symbol,
                    "classification": s.classification.value,
                    "last_alert_at": s.last_alert_at.isoformat() if s.last_alert_at else None,
                    "last_score": s.last_score,
                    "last_price": s.last_price,
                    "last_drawdown": s.last_drawdown,
                    "last_thesis": s.last_thesis,
                }
            )
        Path(self.path).write_text(json.dumps({"symbols": rows}, indent=2), encoding="utf-8")

    def get(self, symbol: str) -> Optional[AlertSnapshot]:
        return self._by_symbol.get(str(symbol or "").upper())

    def put(self, snap: AlertSnapshot) -> None:
        self._by_symbol[snap.symbol] = snap
        self.save()


def enforce_generational_safety(rec: ResearchRecord) -> InvestmentAlertState:
    """Never emit GENERATIONAL if the Phase 3 gate would fail."""
    cls = rec.classification
    if rec.thesis is ThesisState.BROKEN:
        return InvestmentAlertState.THESIS_BROKEN
    if rec.evidence_quality in (EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN):
        if cls in (
            InvestmentAlertState.GENERATIONAL_OPPORTUNITY,
            InvestmentAlertState.DEEP_VALUE,
            InvestmentAlertState.ACCUMULATION,
        ):
            return InvestmentAlertState.WATCH if rec.opportunity_score and rec.opportunity_score >= 40 else InvestmentAlertState.NO_ACTION
    if cls is not InvestmentAlertState.GENERATIONAL_OPPORTUNITY:
        return cls
    ok, _ = generational_gate(
        thesis=rec.thesis,
        evidence=rec.evidence_quality,
        dd=rec.drawdown,
        valuation_score=rec.components.valuation,
        fundamentals_score=rec.components.fundamentals,
        balance_sheet_score=rec.components.balance_sheet,
        cash_flow_score=rec.components.cash_flow,
        risk_score=rec.components.risk,
        opportunity_score=rec.opportunity_score,
    )
    if ok:
        return InvestmentAlertState.GENERATIONAL_OPPORTUNITY
    if rec.classification in (InvestmentAlertState.DEEP_VALUE, InvestmentAlertState.ACCUMULATION):
        return rec.classification
    return InvestmentAlertState.WATCH if rec.opportunity_score and rec.opportunity_score >= 40 else InvestmentAlertState.NO_ACTION


def _material(prev: AlertSnapshot, rec: ResearchRecord) -> Optional[str]:
    if rec.opportunity_score is not None and prev.last_score is not None:
        if abs(rec.opportunity_score - prev.last_score) >= SCORE_DELTA:
            return f"score moved {prev.last_score} → {rec.opportunity_score}"
    if rec.price is not None and prev.last_price not in (None, 0):
        move = abs(rec.price - prev.last_price) / abs(prev.last_price)
        if move >= PRICE_MOVE:
            return f"price moved {move:.0%}"
    dd = rec.drawdown.current_drawdown
    if dd is not None and prev.last_drawdown is not None:
        if abs(dd - prev.last_drawdown) >= DRAWDOWN_DELTA:
            return f"drawdown moved {prev.last_drawdown:.0%} → {dd:.0%}"
    return None


def evaluate_alert(
    rec: ResearchRecord,
    store: AlertStore,
    *,
    now: Optional[datetime] = None,
) -> AlertDecision:
    now = now or _now()
    symbol = rec.symbol
    cls = enforce_generational_safety(rec)
    prev = store.get(symbol)

    if cls is InvestmentAlertState.THESIS_BROKEN:
        if prev and prev.classification is InvestmentAlertState.THESIS_BROKEN:
            return AlertDecision(
                emit=False,
                reason="thesis already flagged BROKEN; duplicate suppressed",
                classification=cls,
                priority="HIGH",
                suppressed=True,
                previous=prev.classification,
            )
        return AlertDecision(
            emit=True,
            reason="ANY STATE → THESIS_BROKEN",
            classification=cls,
            priority="HIGH",
            previous=None if prev is None else prev.classification,
        )

    if prev is None:
        emit = cls is not InvestmentAlertState.NO_ACTION
        return AlertDecision(
            emit=emit,
            reason="first observation" if emit else "first observation is NO_ACTION",
            classification=cls,
            previous=None,
        )

    if cls != prev.classification:
        return AlertDecision(
            emit=True,
            reason=f"{prev.classification.value} → {cls.value}",
            classification=cls,
            priority="HIGH" if cls is InvestmentAlertState.GENERATIONAL_OPPORTUNITY else "NORMAL",
            previous=prev.classification,
        )

    # same classification: identical re-scan must not fire
    why = _material(prev, rec)
    if why is None:
        return AlertDecision(
            emit=False,
            reason=f"{cls.value} → {cls.value} duplicate suppressed",
            classification=cls,
            suppressed=True,
            previous=prev.classification,
        )
    cd = COOLDOWN.get(cls, timedelta(hours=24))
    if prev.last_alert_at and now - prev.last_alert_at < cd:
        return AlertDecision(
            emit=False,
            reason=f"cooldown active ({cd}); {why}",
            classification=cls,
            suppressed=True,
            previous=prev.classification,
        )
    return AlertDecision(
        emit=True,
        reason=f"material change during {cls.value}: {why}",
        classification=cls,
        previous=prev.classification,
    )


def commit_alert(rec: ResearchRecord, decision: AlertDecision, store: AlertStore, *, now: Optional[datetime] = None) -> None:
    now = now or _now()
    prev = store.get(rec.symbol)
    store.put(
        AlertSnapshot(
            symbol=rec.symbol,
            classification=decision.classification,
            last_alert_at=now if decision.emit else (prev.last_alert_at if prev else None),
            last_score=rec.opportunity_score,
            last_price=rec.price,
            last_drawdown=rec.drawdown.current_drawdown,
            last_thesis=rec.thesis.value,
        )
    )
