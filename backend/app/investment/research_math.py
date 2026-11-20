"""Local scenario arithmetic; inputs are assumptions, not forecasts or promises."""

import math
from datetime import datetime, timezone


def finite(value, name, minimum=None):
    value = float(value)
    if not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f"Invalid {name}")
    return value


def compound_scenario(
    *,
    starting_capital,
    contribution,
    years,
    price_growth,
    distribution_yield=0,
    reinvest=True,
    annual_fee=0,
    contributions_per_year=12,
    distribution_tax_rate=None,
):
    capital = finite(starting_capital, "starting capital", 0)
    contribution = finite(contribution, "contribution", 0)
    years = finite(years, "years", 0)
    if years > 100 or contributions_per_year not in (1, 4, 12, 26, 52):
        raise ValueError("Horizon <=100 years; frequency 1,4,12,26,52")
    growth = finite(price_growth, "price growth", -0.999)
    yield_rate = finite(distribution_yield, "distribution yield", 0)
    fee = finite(annual_fee, "fee", 0)
    tax = (
        0 if distribution_tax_rate is None else finite(distribution_tax_rate, "tax", 0)
    )
    if tax > 1 or fee >= 1:
        raise ValueError("Tax must be <=1 and fee <1")
    n = contributions_per_year
    steps = round(years * n)
    if not math.isclose(steps / n, years):
        raise ValueError("Horizon must comprise whole contribution periods")
    initial = capital
    cash_distributions = paid_fees = paid_taxes = 0.0
    path = []
    for step in range(1, steps + 1):
        distribution = capital * yield_rate / n
        taxes = distribution * tax
        cost = capital * fee / n
        capital *= (1 + growth) ** (1 / n)
        capital -= cost
        if capital < 0:
            raise ValueError("Assumptions exhaust invested capital")
        if reinvest:
            capital += distribution - taxes
        else:
            cash_distributions += distribution - taxes
        capital += contribution  # End-of-period contributions.
        finite(capital, "scenario value", 0)
        paid_fees += cost
        paid_taxes += taxes
        if step % n == 0 or step == steps:
            path.append(
                {
                    "years": step / n,
                    "invested_value": capital,
                    "cash_distributions": cash_distributions,
                    "total_wealth": capital + cash_distributions,
                }
            )
    return {
        "starting_capital": initial,
        "contributed": contribution * steps,
        "invested_value": capital,
        "cash_distributions": cash_distributions,
        "total_wealth": capital + cash_distributions,
        "fees": paid_fees,
        "distribution_taxes": paid_taxes if distribution_tax_rate is not None else None,
        "path": path,
        "assumptions": {
            "price_growth": growth,
            "distribution_yield": yield_rate,
            "annual_fee": fee,
            "distribution_tax_rate": distribution_tax_rate,
            "reinvest": reinvest,
            "contribution_frequency": n,
            "contribution_timing": "END_OF_PERIOD",
            "capital_gains_tax": "NOT_MODELED",
            "inflation": "NOT_MODELED",
        },
        "note": "Price growth excludes distributions. Do not enter total return as price growth. Constant assumptions; no guaranteed result.",
    }


def return_components(
    start_price, end_price, distributions=None, start_adjusted=None, end_adjusted=None
):
    start = finite(start_price, "start price", 0.000001)
    end = finite(end_price, "end price", 0)
    price = end / start - 1
    distribution = (
        None
        if distributions is None
        else finite(distributions, "distributions", 0) / start
    )
    # Adjusted prices already include adjustments; never add distributions twice.
    adjusted = None
    if start_adjusted is not None and end_adjusted is not None:
        adjusted = (
            finite(end_adjusted, "adjusted end", 0)
            / finite(start_adjusted, "adjusted start", 0.000001)
            - 1
        )
    return {
        "PRICE_RETURN": price,
        "DISTRIBUTION_RETURN": distribution,
        "TOTAL_RETURN": (
            adjusted
            if adjusted is not None
            else price + distribution if distribution is not None else None
        ),
        "total_return_method": (
            "PROVIDER_ADJUSTED_PRICE"
            if adjusted is not None
            else "UNREINVESTED_DISTRIBUTIONS" if distribution is not None else "UNKNOWN"
        ),
    }


ETF_FIELDS = (
    "expense_ratio",
    "index_methodology",
    "diversification",
    "sector_concentration",
    "top_holding_concentration",
    "liquidity",
    "spread",
    "aum",
    "volatility",
    "drawdown",
    "distribution_yield",
    "distribution_history",
    "distribution_growth",
    "total_return",
    "tracking_behavior",
    "portfolio_overlap",
)


def etf_research(symbol, evidence=None):
    evidence = evidence or {}
    fields = {}
    for field in ETF_FIELDS:
        source = evidence.get(field)
        valid = (
            isinstance(source, dict)
            and source.get("source")
            and source.get("as_of")
            and source.get("value") is not None
        )
        if valid:
            try:
                as_of = datetime.fromisoformat(
                    str(source["as_of"]).replace("Z", "+00:00")
                )
                valid = as_of.replace(
                    tzinfo=as_of.tzinfo or timezone.utc
                ) <= datetime.now(timezone.utc)
            except ValueError:
                valid = False
        fields[field] = source if valid else {"value": None, "status": "UNKNOWN"}
    return {
        "symbol": symbol,
        "metrics": fields,
        "evidence_complete": all(
            row.get("value") is not None for row in fields.values()
        ),
        "note": "ETF evidence requires a source and timestamp. Yield alone never establishes suitability.",
        "execution": "MANUAL_ONLY",
    }
