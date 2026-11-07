from app.investment.quality_dips_v2_valuation import build_normalization_window, from_research_row


def test_requires_three_explicit_estimates_for_complete_window():
    out = build_normalization_window([
        {"value": 100, "provenance": "DCF"},
        {"value": 120, "provenance": "HISTORICAL_MULTIPLE"},
    ])
    assert out["complete"] is False
    assert out["conservative"] is None
    assert out["base"] is None
    assert out["optimistic"] is None


def test_three_explicit_estimates_build_low_median_high_window():
    out = build_normalization_window([
        {"value": 130, "provenance": "ANALYST_CONSENSUS"},
        {"value": 100, "provenance": "DCF"},
        {"value": 115, "provenance": "HISTORICAL_MULTIPLE"},
    ])
    assert out["complete"] is True
    assert out["conservative"] == 100
    assert out["base"] == 115
    assert out["optimistic"] == 130


def test_invalid_provenance_is_rejected():
    out = build_normalization_window([
        {"value": 100, "provenance": "MADE_UP"},
        {"value": 120, "provenance": "DCF"},
        {"value": 130, "provenance": "SECTOR_RELATIVE"},
        {"value": 140, "provenance": "OWNER_EARNINGS"},
    ])
    assert out["complete"] is True
    assert out["source_count"] == 3
    assert all(p["provenance"] != "MADE_UP" for p in out["provenance"])


def test_nonpositive_values_are_rejected():
    out = build_normalization_window([
        {"value": 0, "provenance": "DCF"},
        {"value": -5, "provenance": "SECTOR_RELATIVE"},
    ])
    assert out["source_count"] == 0
    assert out["complete"] is False


def test_research_row_preserves_provenance_and_manual_only_boundary():
    row = {
        "symbol": "MSFT",
        "timestamp": "2026-09-17T00:00:00+00:00",
        "valuation_sources": [
            {"value": 400, "provenance": "DCF", "as_of": "2026-09-16"},
            {"value": 430, "provenance": "HISTORICAL_MULTIPLE", "as_of": "2026-09-16"},
            {"value": 460, "provenance": "ANALYST_CONSENSUS", "as_of": "2026-09-16"},
        ],
    }
    out = from_research_row(row)
    assert out["symbol"] == "MSFT"
    assert out["valuation_window_complete"] is True
    assert out["normalization_value"] == {"conservative": 400.0, "base": 430.0, "optimistic": 460.0}
    assert len(out["valuation_provenance"]) == 3
    assert out["execution"] == "MANUAL_ONLY"
    assert out["live_capital_allowed"] is False
    assert out["automatic_real_money_execution"] is False


def test_no_sources_means_no_fabricated_fair_values():
    out = from_research_row({"symbol": "ABC"})
    assert out["valuation_window_complete"] is False
    assert out["normalization_value"] == {"conservative": None, "base": None, "optimistic": None}
