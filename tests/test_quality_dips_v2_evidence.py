from app.investment.quality_dips_v2_evidence import adapt_research_row


def _base_row():
    return {
        "symbol": "TEST",
        "price": 70.0,
        "timestamp": "2026-09-17T00:00:00+00:00",
        "evidence_quality": "HIGH",
        "thesis": "INTACT",
        "classification": "ACCUMULATION",
        "opportunity_score": 91,
        "components": {
            "quality": 92,
            "fundamentals": 93,
            "valuation": 94,
        },
        "drawdown": {"historical_percentile": 96},
        "normalization_value": {
            "conservative": 110.0,
            "base": 120.0,
            "optimistic": 135.0,
        },
        "trend": {
            "short_term": "UP",
            "intermediate_term": "BASE_BUILDING",
            "long_term": "UP",
            "momentum": "IMPROVING",
            "relative_strength": "IMPROVING",
            "sector_regime": "NEUTRAL",
            "market_regime": "RISK_ON",
            "source": "fixture",
            "as_of": "2026-09-17T00:00:00+00:00",
        },
    }


def test_adapter_is_read_only_and_manual_only():
    out = adapt_research_row(_base_row())
    assert out["read_only"] is True
    assert out["execution"] == "MANUAL_ONLY"
    assert out["live_capital_allowed"] is False
    assert out["automatic_real_money_execution"] is False


def test_adapter_surfaces_existing_trend_evidence():
    out = adapt_research_row(_base_row())
    assert out["trend"]["short_term"] == "UP"
    assert out["trend"]["intermediate_term"] == "BASE_BUILDING"
    assert out["trend"]["market_regime"] == "RISK_ON"


def test_adapter_does_not_fabricate_missing_normalization_values():
    row = _base_row()
    row.pop("normalization_value")
    out = adapt_research_row(row)
    assert out["normalization_value"]["conservative"] is None
    assert out["conservative_upside_pct"] is None
    assert "conservative_normalization_value" in out["missing_v2_evidence"]
    assert out["patient_state"] == "WATCH"


def test_adapter_preserves_legacy_fields_for_comparison():
    out = adapt_research_row(_base_row())
    assert out["legacy_classification"] == "ACCUMULATION"
    assert out["legacy_opportunity_score"] == 91


def test_adapter_classifies_strong_extreme_discount_without_mutation():
    row = _base_row()
    before = repr(row)
    out = adapt_research_row(row)
    assert out["patient_state"] == "GENERATIONAL"
    assert repr(row) == before


def test_broken_thesis_routes_to_thesis_broken_when_evidence_complete():
    row = _base_row()
    row["thesis"] = "BROKEN"
    row["classification"] = "THESIS_BROKEN"
    out = adapt_research_row(row)
    assert out["patient_state"] == "THESIS_BROKEN"


def test_value_trap_blocks_actionable_state():
    row = _base_row()
    row["flags"] = {"value_trap": True}
    out = adapt_research_row(row)
    assert out["patient_state"] == "WATCH"
    assert out["value_trap"] is True


def test_missing_trend_stays_unknown_not_invented():
    row = _base_row()
    row.pop("trend")
    out = adapt_research_row(row)
    assert out["trend"]["short_term"] is None
    assert out["trend"]["long_term"] is None
    assert out["trend"]["source"] is None
