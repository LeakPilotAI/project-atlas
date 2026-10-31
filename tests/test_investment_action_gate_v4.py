from __future__ import annotations

from app.investment.action_gate import InvestmentReadiness, evaluate_investment_readiness
from app.investment.enums import AssetType, EvidenceQuality, InvestmentAlertState, ThesisState
from app.investment.research_models import ComponentScores, ResearchRecord


def rec(**overrides) -> ResearchRecord:
    values = dict(
        symbol="MSFT",
        asset_type=AssetType.STOCK,
        classification=InvestmentAlertState.ACCUMULATION,
        opportunity_score=78,
        evidence_quality=EvidenceQuality.HIGH,
        thesis=ThesisState.INTACT,
        components=ComponentScores(
            valuation=75,
            fundamentals=82,
            drawdown=70,
            thesis_integrity=85,
            risk=35,
        ),
    )
    values.update(overrides)
    return ResearchRecord(**values)


def test_clean_stock_can_accumulate() -> None:
    decision = evaluate_investment_readiness(rec())
    assert decision.stance is InvestmentReadiness.ACCUMULATE
    assert decision.ladder_eligible is True
    assert decision.domain == "EQUITY_INVESTMENT"
    assert decision.execution == "MANUAL_ONLY"


def test_etf_is_allowed() -> None:
    decision = evaluate_investment_readiness(rec(asset_type=AssetType.ETF))
    assert decision.stance is InvestmentReadiness.ACCUMULATE


def test_non_equity_asset_stands_down() -> None:
    decision = evaluate_investment_readiness(rec(asset_type=AssetType.OTHER))
    assert decision.stance is InvestmentReadiness.STAND_DOWN
    assert decision.ladder_eligible is False


def test_broken_thesis_stands_down() -> None:
    decision = evaluate_investment_readiness(rec(thesis=ThesisState.BROKEN))
    assert decision.stance is InvestmentReadiness.STAND_DOWN
    assert decision.ladder_eligible is False


def test_unknown_or_insufficient_evidence_cannot_accumulate() -> None:
    decision = evaluate_investment_readiness(rec(evidence_quality=EvidenceQuality.INSUFFICIENT))
    assert decision.stance is InvestmentReadiness.WATCH
    assert decision.ladder_eligible is False


def test_under_pressure_thesis_is_prepare_only() -> None:
    decision = evaluate_investment_readiness(rec(thesis=ThesisState.UNDER_PRESSURE))
    assert decision.stance is InvestmentReadiness.PREPARE
    assert decision.ladder_eligible is False


def test_low_evidence_is_prepare_only() -> None:
    decision = evaluate_investment_readiness(rec(evidence_quality=EvidenceQuality.LOW))
    assert decision.stance is InvestmentReadiness.PREPARE
    assert decision.ladder_eligible is False


def test_missing_core_component_is_prepare_only() -> None:
    decision = evaluate_investment_readiness(
        rec(components=ComponentScores(valuation=75, fundamentals=None, drawdown=70, thesis_integrity=85))
    )
    assert decision.stance is InvestmentReadiness.PREPARE
    assert decision.ladder_eligible is False


def test_watch_classification_stays_watch_even_with_good_evidence() -> None:
    decision = evaluate_investment_readiness(rec(classification=InvestmentAlertState.WATCH))
    assert decision.stance is InvestmentReadiness.WATCH
    assert decision.ladder_eligible is False
