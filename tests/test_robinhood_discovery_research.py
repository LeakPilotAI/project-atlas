from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.investment import robinhood_discovery_research as discovery
from app.investment import robinhood_universe_registry as registry
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


def test_research_failure_preserves_prior_lane_and_records_failure(monkeypatch, tmp_path):
    state_path = tmp_path / "universe.json"
    registry.upsert_discovery(
        [
            {
                "symbol": "KEEP",
                "listing_state": "TRADABLE",
                "tradable": True,
                "research_lane": "QUALITY_DIPS",
            }
        ],
        source="offline-test",
        path=state_path,
        events_path=tmp_path / "events.jsonl",
    )
    candidate = registry.snapshot(state_path)["symbols"]["KEEP"]
    monkeypatch.setattr(discovery, "research_candidates", lambda limit: [candidate])

    class FailedIngest:
        def __init__(self, *, universe, persist):
            pass

        async def ingest_symbol(self, entry, *, history_period):
            return SimpleNamespace(failures=[{"code": "PRICE_FAIL"}])

    def persist_failure(symbol, error_type):
        return registry.mark_research_failed(symbol, error_type, path=state_path)

    monkeypatch.setattr(discovery, "InvestmentIngest", FailedIngest)
    monkeypatch.setattr(discovery, "mark_research_failed", persist_failure)

    result = asyncio.run(discovery.research_batch(limit=1))
    stored = registry.snapshot(state_path)["symbols"]["KEEP"]

    assert result["results"] == [
        {
            "symbol": "KEEP",
            "research_lane": "QUALITY_DIPS",
            "research_status": "FAILED",
            "error": "ProviderDataUnavailable:PRICE_FAIL",
        }
    ]
    assert stored["research_lane"] == "QUALITY_DIPS"
    assert stored["last_research_status"] == "FAILED"
    assert stored["last_research_error"] == "ProviderDataUnavailable:PRICE_FAIL"

    registry.set_research_lane(
        "KEEP",
        "QUALITY_DIPS",
        reason="fresh offline evidence",
        path=state_path,
    )
    recovered = registry.snapshot(state_path)["symbols"]["KEEP"]
    assert recovered["last_research_status"] == "SUCCEEDED"
    assert "last_research_error" not in recovered
