"""ETF-specific research from existing local daily bars and dated supplied facts."""

from datetime import datetime, timezone
from app.investment.history import load_bars
from app.investment.universe import load_universe
from app.investment.research_math import etf_research, return_components
from app.investment.benchmark_research import path_metrics


def local_etf_report(config, bars_loader=load_bars, symbols=None):
    if symbols is None:
        symbols = config.get("etf_symbols") or [
            entry.symbol
            for entry in load_universe()
            if entry.active and entry.asset_type.value == "ETF"
        ]
    today = datetime.now(timezone.utc).date().isoformat()
    reports = []
    for symbol in symbols:
        facts = dict((config.get("etf_evidence") or {}).get(symbol) or {})
        bars = sorted(
            (
                bar
                for bar in bars_loader(symbol)
                if bar.session_date < today and bar.close and bar.close > 0
            ),
            key=lambda bar: bar.session_date,
        )
        components = {
            "PRICE_RETURN": None,
            "DISTRIBUTION_RETURN": None,
            "TOTAL_RETURN": None,
        }
        if len(bars) >= 2:
            start, end = bars[0], bars[-1]
            metrics = path_metrics([(bar.session_date, bar.close) for bar in bars])
            components = return_components(
                start.close,
                end.close,
                start_adjusted=start.adjusted_close,
                end_adjusted=end.adjusted_close,
            )
            for key, value in (
                ("volatility", metrics["annualized_volatility"]),
                ("drawdown", metrics["max_drawdown"]),
                ("total_return", components["TOTAL_RETURN"]),
            ):
                if value is not None:
                    facts[key] = {
                        "value": value,
                        "source": "LOCAL_STORED_DAILY_BARS",
                        "as_of": end.session_date,
                        "window_start": start.session_date,
                        "return_basis": (
                            "PRICE_RETURN"
                            if key != "total_return"
                            else components.get("total_return_method")
                        ),
                    }
        report = etf_research(symbol, facts)
        report["return_components"] = components
        report["distribution_note"] = (
            "Cash distribution history unavailable unless explicitly supplied. Adjusted return never added to dividend return."
        )
        reports.append(report)
    return reports
