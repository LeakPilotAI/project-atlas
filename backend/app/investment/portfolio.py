"""User investment profile. Never invent cash, value, or holdings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from app.investment.enums import InvestmentHorizon, RiskTolerance
from app.investment.models import HoldingInput, PortfolioInput
from app.investment.storage import PORTFOLIO_PATH, ensure_dirs


def _enum(cls, raw, default):
    s = str(raw or "").upper().strip()
    try:
        return cls(s) if s else default
    except ValueError:
        return default


def load_portfolio(path: Optional[Path] = None) -> PortfolioInput:
    ensure_dirs()
    p = path or PORTFOLIO_PATH
    if not p.exists():
        return PortfolioInput()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return PortfolioInput()
    if not isinstance(data, dict):
        return PortfolioInput()
    holdings: List[HoldingInput] = []
    for row in data.get("holdings") or []:
        if not isinstance(row, dict) or not row.get("symbol"):
            continue
        holdings.append(
            HoldingInput(
                symbol=str(row["symbol"]),
                shares=float(row.get("shares") or 0),
                average_cost=_opt_float(row.get("average_cost")),
                current_value=_opt_float(row.get("current_value")),
                sector=str(row.get("sector") or ""),
                portfolio_percent=_opt_float(row.get("portfolio_percent")),
            )
        )
    return PortfolioInput(
        portfolio_value=_opt_float(data.get("portfolio_value")),
        available_cash=_opt_float(data.get("available_cash")),
        holdings=holdings,
        maximum_position_percent=float(data.get("maximum_position_percent") or 15.0),
        sector_exposure=_sector_map(data.get("sector_exposure")),
        risk_tolerance=_enum(RiskTolerance, data.get("risk_tolerance"), RiskTolerance.UNKNOWN),
        investment_horizon=_enum(InvestmentHorizon, data.get("investment_horizon"), InvestmentHorizon.UNKNOWN),
        provided=bool(data.get("provided", True)),
        minimum_cash_reserve=_opt_float(data.get("minimum_cash_reserve")),
        maximum_sector_exposure_percent=_opt_float(data.get("maximum_sector_exposure_percent")),
        allow_fractional_shares=bool(data.get("allow_fractional_shares", False)),
        benchmark_symbol=str(data.get("benchmark_symbol") or "SPY").upper(),
    )


def _opt_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sector_map(raw) -> Dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def holding_value(h: HoldingInput, mark: Optional[float] = None) -> float:
    if h.current_value is not None:
        return max(0.0, float(h.current_value))
    if mark is not None and h.shares:
        return max(0.0, float(h.shares) * float(mark))
    return 0.0


def existing_position_value(portfolio: PortfolioInput, symbol: str, mark: Optional[float] = None) -> float:
    total = 0.0
    for h in portfolio.holdings:
        if h.symbol == str(symbol or "").upper().strip():
            total += holding_value(h, mark)
    return total


def sector_value(portfolio: PortfolioInput, sector: str, *, mark_by_symbol: Optional[Dict[str, float]] = None) -> float:
    if not sector:
        return 0.0
    if sector in (portfolio.sector_exposure or {}) and mark_by_symbol is None:
        try:
            return float(portfolio.sector_exposure[sector])
        except (TypeError, ValueError):
            pass
    total = 0.0
    for h in portfolio.holdings:
        if h.sector == sector:
            mk = None if not mark_by_symbol else mark_by_symbol.get(h.symbol)
            total += holding_value(h, mk)
    return total


def exposure_percent(value: float, portfolio_value: Optional[float]) -> Optional[float]:
    if portfolio_value is None or portfolio_value <= 0:
        return None
    return 100.0 * value / float(portfolio_value)
