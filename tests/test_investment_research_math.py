import pytest
from app.investment.research_math import (
    compound_scenario,
    return_components,
    etf_research,
)


def test_contributions_and_nonreinvested_distributions_are_not_double_counted():
    result = compound_scenario(
        starting_capital=100,
        contribution=10,
        years=1,
        price_growth=0,
        distribution_yield=0.1,
        reinvest=False,
        contributions_per_year=1,
    )
    assert result["invested_value"] == 110
    assert result["cash_distributions"] == 10
    assert result["total_wealth"] == 120
    assert result["distribution_taxes"] is None


def test_adjusted_returns_do_not_add_distribution_twice():
    result = return_components(
        100, 110, distributions=5, start_adjusted=100, end_adjusted=115
    )
    assert result["TOTAL_RETURN"] == pytest.approx(0.15)
    assert result["DISTRIBUTION_RETURN"] == 0.05
    assert return_components(100, 110)["TOTAL_RETURN"] is None


def test_negative_scenario_and_missing_etf_fields_remain_visible():
    result = compound_scenario(
        starting_capital=100, contribution=0, years=1, price_growth=-0.2
    )
    assert result["total_wealth"] == pytest.approx(80)
    assert etf_research("ETF")["metrics"]["expense_ratio"]["status"] == "UNKNOWN"
    with pytest.raises(ValueError):
        compound_scenario(
            starting_capital=float("nan"), contribution=0, years=1, price_growth=0
        )


def test_future_dated_etf_evidence_is_unknown():
    result = etf_research(
        "ETF",
        {
            "expense_ratio": {
                "value": 0.001,
                "source": "provided",
                "as_of": "2099-01-01",
            }
        },
    )
    assert result["metrics"]["expense_ratio"]["status"] == "UNKNOWN"
