import pytest
from app.investment.benchmark_research import compare_benchmark


def test_negative_benchmark_comparison_remains_visible():
    result = compare_benchmark(
        [("1", 100), ("2", 90), ("3", 95)],
        [("1", 100), ("2", 105), ("3", 110)],
        symbol="SPY",
        return_basis="PRICE_RETURN",
    )
    assert not result["outperformed"]
    assert result["status"] == "THE_STRATEGY_DID_NOT_OUTPERFORM_THE_BENCHMARK"
    assert result["excess_return"] == pytest.approx(-0.15)
    assert result["strategy"]["max_drawdown"] == pytest.approx(0.1)


def test_no_interpolation_of_mismatched_benchmark_dates():
    result = compare_benchmark(
        [("1", 100), ("2", 90)],
        [("1", 100), ("3", 110)],
        symbol="SPY",
        return_basis="PRICE_RETURN",
    )
    assert result["status"] == "UNMATCHED_DATES"
    assert result["outperformed"] is None
