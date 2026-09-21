"""Matched-date return comparisons; no interpolation or hidden underperformance."""

import math
from statistics import mean, stdev


def path_metrics(points, periods_per_year=252):
    if len(points) < 2:
        return {"status": "INSUFFICIENT_EVIDENCE"}
    values = [float(value) for _, value in points]
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("Positive finite equity values required")
    returns = [b / a - 1 for a, b in zip(values, values[1:])]
    peak = values[0]
    drawdown = 0
    for value in values:
        peak = max(peak, value)
        drawdown = max(drawdown, 1 - value / peak)
    volatility = (
        stdev(returns) * math.sqrt(periods_per_year) if len(returns) > 1 else None
    )
    return {
        "status": "MEASURED",
        "total_return": values[-1] / values[0] - 1,
        "max_drawdown": drawdown,
        "annualized_volatility": volatility,
        "annualized_mean_over_volatility_zero_cash_assumption": (
            mean(returns) * periods_per_year / volatility if volatility else None
        ),
        "periods": len(returns),
    }


def compare_benchmark(
    strategy, benchmark, *, symbol, return_basis, periods_per_year=252
):
    if return_basis not in {"PRICE_RETURN", "TOTAL_RETURN"}:
        raise ValueError("Explicit matching return basis required")
    dates_a = [date for date, _ in strategy]
    dates_b = [date for date, _ in benchmark]
    if (
        dates_a != dates_b
        or len(set(dates_a)) != len(dates_a)
        or dates_a != sorted(dates_a)
    ):
        return {"status": "UNMATCHED_DATES", "outperformed": None}
    a, b = path_metrics(strategy, periods_per_year), path_metrics(
        benchmark, periods_per_year
    )
    if a["status"] != "MEASURED" or b["status"] != "MEASURED":
        return {"status": "INSUFFICIENT_EVIDENCE", "outperformed": None}
    excess = a["total_return"] - b["total_return"]
    return {
        "status": (
            "THE_STRATEGY_DID_NOT_OUTPERFORM_THE_BENCHMARK"
            if excess <= 0
            else "OBSERVED_OUTPERFORMANCE_NOT_PROOF_OF_EDGE"
        ),
        "benchmark_symbol": symbol,
        "return_basis": return_basis,
        "strategy": a,
        "benchmark": b,
        "excess_return": excess,
        "outperformed": excess > 0,
        "note": "Identical dates and return convention required. Distribution contribution and deployment require separately observed cash flows.",
    }
