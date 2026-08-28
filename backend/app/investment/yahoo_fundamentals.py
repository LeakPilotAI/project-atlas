"""Fundamentals + valuation from yfinance info. Missing stays MISSING."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.investment.bars import ProviderFailure
from app.investment.enums import DataQuality
from app.investment.freshness import classify_freshness
from app.investment.models import MeasuredValue
from app.investment.validate import validate_non_negative, validate_share_consistency, validate_shares
from app.investment.yfinance_client import ProviderCallError, YFinanceClient, utcnow

FUNDAMENTAL_KEYS = {
    "revenue": ("totalRevenue",),
    "earnings": ("netIncomeToCommon", "netIncome"),
    "eps": ("trailingEps",),
    "free_cash_flow": ("freeCashflow",),
    "operating_cash_flow": ("operatingCashflow",),
    "gross_margin": ("grossMargins",),
    "operating_margin": ("operatingMargins",),
    "net_margin": ("profitMargins",),
    "total_debt": ("totalDebt",),
    "cash": ("totalCash",),
    "shares_outstanding": ("sharesOutstanding",),
    "market_cap": ("marketCap",),
}

VALUATION_KEYS = {
    "pe": ("trailingPE",),
    "forward_pe": ("forwardPE",),
    "ps": ("priceToSalesTrailing12Months",),
    "pb": ("priceToBook",),
    "ev_ebitda": ("enterpriseToEbitda",),
}

HARD_ISSUE_CODES = {"NEGATIVE_VALUE", "INVALID_SHARES", "NEGATIVE_PRICE", "INCONSISTENT_SHARES"}


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        import math

        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except (TypeError, ValueError):
        return None


def _quality_from_issues(issues: List[Any], *, kind: str, ts: Any) -> DataQuality:
    if any(getattr(i, "code", "") in HARD_ISSUE_CODES for i in issues):
        return DataQuality.CONFLICTING
    if issues:
        return DataQuality.UNKNOWN
    return classify_freshness(ts, kind=kind)


class YahooFundamentalProvider:
    name = "yfinance"

    def __init__(self, client: Optional[YFinanceClient] = None) -> None:
        self.client = client or YFinanceClient()
        self.last_failure: Optional[ProviderFailure] = None

    async def get_metric(self, symbol: str, metric: str) -> MeasuredValue:
        bundle = await self.get_all(symbol)
        return bundle.get(metric) or MeasuredValue.unknown(self.name, f"unknown metric {metric}")

    async def get_all(self, symbol: str) -> Dict[str, MeasuredValue]:
        self.last_failure = None
        retrieved = utcnow()
        try:
            info = await self.client.info(symbol)
        except ProviderCallError as e:
            self.last_failure = e.failure
            return {k: MeasuredValue.unknown(self.name, e.failure.message) for k in FUNDAMENTAL_KEYS}
        except Exception as e:
            self.last_failure = ProviderFailure(
                code="PROVIDER_ERROR",
                message=str(e)[:200],
                source=self.name,
                symbol=symbol,
                retryable=True,
            )
            return {k: MeasuredValue.unknown(self.name, str(e)[:200]) for k in FUNDAMENTAL_KEYS}

        if not info:
            self.last_failure = ProviderFailure(
                code="EMPTY",
                message="empty info payload",
                source=self.name,
                symbol=symbol,
                retryable=True,
            )
            return {k: MeasuredValue.unknown(self.name, "empty info payload") for k in FUNDAMENTAL_KEYS}

        out: Dict[str, MeasuredValue] = {}
        raw_map: Dict[str, Optional[float]] = {}
        for name, keys in FUNDAMENTAL_KEYS.items():
            raw = None
            for k in keys:
                raw = _num(info.get(k))
                if raw is not None:
                    break
            raw_map[name] = raw
            issues = validate_non_negative(name, raw)
            if name == "shares_outstanding":
                issues.extend(validate_shares(raw))
            if raw is None:
                out[name] = MeasuredValue.unknown(self.name, f"{name} not in provider payload")
                continue
            quality = _quality_from_issues(issues, kind="fundamental", ts=retrieved)
            out[name] = MeasuredValue(
                value=raw,
                source=self.name,
                timestamp=retrieved,
                retrieved_at=retrieved,
                effective_timestamp=retrieved,
                quality=quality,
                availability=True,
                notes=",".join(i.code for i in issues),
            )

        share_issues = validate_share_consistency(
            shares=raw_map.get("shares_outstanding"),
            market_cap=raw_map.get("market_cap"),
            price=_num(info.get("regularMarketPrice") or info.get("currentPrice")),
        )
        if share_issues and "shares_outstanding" in out and out["shares_outstanding"].availability:
            mv = out["shares_outstanding"]
            codes = [i.code for i in share_issues]
            mv.notes = ",".join(x for x in [mv.notes, *codes] if x)
            mv.quality = DataQuality.CONFLICTING
        return out


class YahooValuationProvider:
    name = "yfinance"

    def __init__(self, client: Optional[YFinanceClient] = None) -> None:
        self.client = client or YFinanceClient()
        self.last_failure: Optional[ProviderFailure] = None

    async def get_valuation(self, symbol: str) -> MeasuredValue:
        all_m = await self.get_all(symbol)
        return all_m.get("pe") or MeasuredValue.unknown(self.name, "pe missing")

    async def get_all(self, symbol: str) -> Dict[str, MeasuredValue]:
        self.last_failure = None
        retrieved = utcnow()
        try:
            info = await self.client.info(symbol)
        except ProviderCallError as e:
            self.last_failure = e.failure
            missing = {k: MeasuredValue.unknown(self.name, e.failure.message) for k in VALUATION_KEYS}
            missing["fcf_yield"] = MeasuredValue.unknown(self.name, e.failure.message)
            missing["earnings_yield"] = MeasuredValue.unknown(self.name, e.failure.message)
            missing["price_to_fcf"] = MeasuredValue.unknown(self.name, e.failure.message)
            return missing
        except Exception as e:
            self.last_failure = ProviderFailure(
                code="PROVIDER_ERROR",
                message=str(e)[:200],
                source=self.name,
                symbol=symbol,
                retryable=True,
            )
            return {
                **{k: MeasuredValue.unknown(self.name, str(e)[:200]) for k in VALUATION_KEYS},
                "fcf_yield": MeasuredValue.unknown(self.name, str(e)[:200]),
                "earnings_yield": MeasuredValue.unknown(self.name, str(e)[:200]),
                "price_to_fcf": MeasuredValue.unknown(self.name, str(e)[:200]),
            }

        quality = classify_freshness(retrieved, kind="valuation")
        out: Dict[str, MeasuredValue] = {}
        for name, keys in VALUATION_KEYS.items():
            raw = None
            for k in keys:
                raw = _num(info.get(k))
                if raw is not None:
                    break
            if raw is None:
                out[name] = MeasuredValue.unknown(self.name, f"{name} not provided")
            else:
                issues = validate_non_negative(name, raw)
                out[name] = MeasuredValue(
                    value=raw,
                    source=self.name,
                    timestamp=retrieved,
                    retrieved_at=retrieved,
                    effective_timestamp=retrieved,
                    quality=_quality_from_issues(issues, kind="valuation", ts=retrieved) if issues else quality,
                    availability=True,
                    notes=",".join(i.code for i in issues),
                )

        # Derived only when both inputs exist. Never fake a yield from one side.
        price = _num(info.get("regularMarketPrice") or info.get("currentPrice"))
        fcf = _num(info.get("freeCashflow"))
        earnings = _num(info.get("netIncomeToCommon") or info.get("netIncome"))
        mcap = _num(info.get("marketCap"))

        if mcap is not None and mcap > 0 and fcf is not None:
            out["fcf_yield"] = MeasuredValue(
                value=fcf / mcap,
                source=self.name + "+derived",
                timestamp=retrieved,
                retrieved_at=retrieved,
                effective_timestamp=retrieved,
                quality=quality,
                availability=True,
                notes="fcf / market_cap",
            )
            if fcf == 0:
                out["price_to_fcf"] = MeasuredValue.unknown(self.name, "fcf is zero; ratio not invented")
            else:
                out["price_to_fcf"] = MeasuredValue(
                    value=mcap / fcf,
                    source=self.name + "+derived",
                    timestamp=retrieved,
                    retrieved_at=retrieved,
                    effective_timestamp=retrieved,
                    quality=quality,
                    availability=True,
                    notes="market_cap / fcf",
                )
        else:
            out["fcf_yield"] = MeasuredValue.unknown(self.name, "need market_cap and fcf")
            out["price_to_fcf"] = MeasuredValue.unknown(self.name, "need market_cap and fcf")

        if earnings is not None and mcap is not None and mcap > 0:
            out["earnings_yield"] = MeasuredValue(
                value=earnings / mcap,
                source=self.name + "+derived",
                timestamp=retrieved,
                retrieved_at=retrieved,
                effective_timestamp=retrieved,
                quality=quality,
                availability=True,
                notes="earnings / market_cap",
            )
        else:
            out["earnings_yield"] = MeasuredValue.unknown(self.name, "need earnings and market_cap")
        return out
