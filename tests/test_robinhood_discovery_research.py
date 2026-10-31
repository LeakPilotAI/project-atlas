from __future__ import annotations

from types import SimpleNamespace

from app.investment.enums import EvidenceQuality, InvestmentAlertState, ThesisState
from app.investment.robinhood_discovery_research import classify_lane


def rec(*, thesis, evidence, classification, score, fundamentals=75, valuation=70, cash_flow=70):
    return SimpleNamespace(
        thesis=thesis,
        evidence_quality=evidence,
        classification=classification,
        opportunity_score=score,
        components=SimpleNamespace(
            fundamentals=fundamentals,
            valuation=valuation,
            cash_flow=cash_flow,
        ),
    )


def test_quality_dip_requires_existing_actionable_quality_classification():
    row = rec(
        thesis=ThesisState.INTACT,
        evidence=EvidenceQuality.MEDIUM,
        classification=InvestmentAlertState.ACCUMULATION,
        score=70,
    )
    assert classify_lane(row)[0] == "QUALITY_DIPS"


def test_strong_company_without_dip_stays_compounder_not_quality_dip():
    row = rec(
        thesis=ThesisState.STRONG,
        evidence=EvidenceQuality.HIGH,
        classification=InvestmentAlertState.WATCH,
        score=65,
    )
    assert classify_lane(row)[0] == "ESTABLISHED_COMPOUNDER"


def test_insufficient_evidence_never_promotes_to_quality_dip():
    row = rec(
        thesis=ThesisState.INTACT,
        evidence=EvidenceQuality.INSUFFICIENT,
        classification=InvestmentAlertState.ACCUMULATION,
        score=80,
    )
    assert classify_lane(row)[0] == "FRONTIER_RESEARCH"


def test_broken_thesis_is_excluded():
    row = rec(
        thesis=ThesisState.BROKEN,
        evidence=EvidenceQuality.HIGH,
        classification=InvestmentAlertState.THESIS_BROKEN,
        score=80,
    )
    assert classify_lane(row)[0] == "EXCLUDED"
