from __future__ import annotations

from app.investment.engine import can_personalize
from app.investment.enums import AssetType, EvidenceQuality, InvestmentAlertState, ThesisState
from app.investment.models import PortfolioInput
from app.investment.research_models import ComponentScores, ResearchRecord


def portfolio() -> PortfolioInput:
    return PortfolioInput(
        portfolio_value=50_000,
        available_cash=10_000,
        minimum_cash_reserve=2_000,
        provided=True,
    )


def record(**overrides) -> ResearchRecord:
    values = dict(
        symbol="MSFT",
        asset_type=AssetType.STOCK,
        classification=InvestmentAlertState.ACCUMULATION,
        opportunity_score=80,
        evidence_quality=EvidenceQuality.HIGH,
        thesis=ThesisState.INTACT,
        components=ComponentScores(
            valuation=80,
            fundamentals=85,
            drawdown=75,
            thesis_integrity=90,
            risk=30,
        ),
    )
    values.update(overrides)
    return ResearchRecord(**values)


def test_complete_portfolio_and_clean_record_can_personalize() -> None:
    assert can_personalize(record(), portfolio()) is True


def test_complete_portfolio_cannot_override_under_pressure_thesis() -> None:
    assert can_personalize(record(thesis=ThesisState.UNDER_PRESSURE), portfolio()) is False


def test_complete_portfolio_cannot_override_low_evidence() -> None:
    assert can_personalize(record(evidence_quality=EvidenceQuality.LOW), portfolio()) is False


def test_complete_portfolio_cannot_override_missing_core_score() -> None:
    rec = record(components=ComponentScores(valuation=80, fundamentals=85, drawdown=None, thesis_integrity=90))
    assert can_personalize(rec, portfolio()) is False


def test_non_equity_record_cannot_personalize() -> None:
    assert can_personalize(record(asset_type=AssetType.OTHER), portfolio()) is False
