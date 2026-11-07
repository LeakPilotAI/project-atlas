from datetime import UTC, datetime, timedelta

import pytest

from app.services.personal_paper_strategy_signal import evaluate_iex_quality_dips_signal

NOW = datetime(2026, 11, 6, 20, tzinfo=UTC)


def quote(price="80"):
    return {"symbol": "MSFT", "state": "FRESH", "bid": price, "ask": price,
            "bid_lots": 2, "ask_lots": 2, "timestamp": NOW.isoformat(),
            "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}


def research():
    return {"symbol": "MSFT", "source_verified": True, "timestamp": NOW.isoformat(),
            "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
            "quality_score": 80, "fundamentals_score": 80,
            "valuation_score": 70, "drawdown_percentile": 80,
            "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}


def test_recomputed_signal_uses_provider_ask_not_caller_eligibility():
    result = evaluate_iex_quality_dips_signal(quote=quote(), symbol="MSFT", now=NOW,
                                               research={**research(), "paper_execution_eligible": True,
                                                         "classification": "GENERATIONAL"})
    assert result["candidate"] is True
    assert result["plan"]["patient_state"] == "ACCUMULATION"
    assert result["paper_fill_authorized"] is False
    assert result["research_provenance_attested"] is False
    assert "L1" in result["reached_levels"]


def test_recomputed_signal_refuses_unverified_or_stale_research():
    with pytest.raises(ValueError, match="PROVENANCE_UNVERIFIED"):
        evaluate_iex_quality_dips_signal(quote=quote(), symbol="MSFT", now=NOW,
                                          research={**research(), "source_verified": False})
    with pytest.raises(ValueError, match="STALE_OR_FUTURE"):
        evaluate_iex_quality_dips_signal(quote=quote(), symbol="MSFT", now=NOW,
                                          research={**research(), "timestamp":
                                                    (NOW - timedelta(days=2)).isoformat()})


def test_recomputed_signal_not_candidate_when_ask_above_ladder():
    result = evaluate_iex_quality_dips_signal(quote=quote("101"), symbol="MSFT", now=NOW,
                                               research=research())
    assert result["candidate"] is False
    assert result["paper_fill_authorized"] is False


def test_leased_v3_refuses_fake_provider_and_missing_operator():
    from app.investment.alpaca_iex import IEXFeed
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import inspect_leased_iex_v3_candidate
    feed = IEXFeed(["MSFT"], clock=lambda: NOW.timestamp())
    with pytest.raises(ValueError, match="LEASED_IEX_V3_DEPENDENCIES_REQUIRED"):
        inspect_leased_iex_v3_candidate(
            installation=object(), request={"action": "AUTO_PAPER"}, components=(),
            provider=object(), symbol="MSFT", now=NOW, research=research())
    with pytest.raises(ValueError, match="LEASED_IEX_V3_DEPENDENCIES_REQUIRED"):
        inspect_leased_iex_v3_candidate(
            installation=None, request={"action": "AUTO_PAPER"}, components=(),
            provider=PersonalPaperIEXProvider(feed), symbol="MSFT", now=NOW,
            research=research())
    with pytest.raises(ValueError, match="LEASED_IEX_V3_DEPENDENCIES_REQUIRED"):
        inspect_leased_iex_v3_candidate(
            installation=object(), request={"action": "READ_ONLY"}, components=(),
            provider=PersonalPaperIEXProvider(feed), symbol="MSFT", now=NOW,
            research=research())
