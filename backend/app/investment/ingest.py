"""Pull universe → providers → history → snapshots. No scoring. Not started by main.py."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.investment.history import append_bars, load_bars, load_dates
from app.investment.models import MeasuredValue
from app.investment.quality_report import summarize_snapshots
from app.investment.snapshot import InvestmentSnapshot, persist_snapshot, snapshot_from_parts
from app.investment.universe import InvestmentUniverse, UniverseEntry, load_universe
from app.investment.yahoo_fundamentals import YahooFundamentalProvider, YahooValuationProvider
from app.investment.yahoo_price import YahooPriceProvider
from app.investment.yfinance_client import YFinanceClient


@dataclass
class FetchPlan:
    """Which provider calls to make. Cached fields are reused, never invented."""

    price: bool = True
    history: bool = True
    fundamentals: bool = True
    valuation: bool = True


def history_fetch_kwargs(symbol: str, *, root=None, period: str = "5y") -> dict:
    """Incremental history: only request dates on/after the last stored session."""
    dates = load_dates(symbol, root)
    if dates:
        return {"start": max(dates)}
    return {"period": period}


def _consume_failure(provider: object, failures: list) -> None:
    fail = getattr(provider, "last_failure", None)
    if fail is None:
        return
    as_dict = getattr(fail, "as_dict", None)
    failures.append(as_dict() if callable(as_dict) else dict(fail))


class InvestmentIngest:
    def __init__(
        self,
        *,
        universe: Optional[InvestmentUniverse] = None,
        price: Optional[YahooPriceProvider] = None,
        fundamentals: Optional[YahooFundamentalProvider] = None,
        valuation: Optional[YahooValuationProvider] = None,
        history_root=None,
        snapshot_path: Optional[Path] = None,
        persist: bool = True,
        read_only: bool = False,
    ) -> None:
        if type(read_only) is not bool or read_only and (persist or any(
                value is None for value in (universe, price, fundamentals, valuation, history_root))
                or snapshot_path is not None):
            raise ValueError("RESEARCH_READ_ONLY_EXPLICIT_INPUTS_REQUIRED")
        self.read_only = read_only
        self._read_only_mode = read_only
        self._read_only_history = {}
        if read_only:
            self.universe, self.price, self.fundamentals, self.valuation = universe, price, fundamentals, valuation
        else:
            client = YFinanceClient()
            self.universe = universe or load_universe()
            self.price = price or YahooPriceProvider(client)
            self.fundamentals = fundamentals or YahooFundamentalProvider(client)
            self.valuation = valuation or YahooValuationProvider(client)
        self.history_root = history_root
        self.snapshot_path = snapshot_path
        self.persist = persist
        self.last_snapshots: List[InvestmentSnapshot] = []

    async def ingest_symbol(
        self,
        entry: UniverseEntry,
        *,
        history_period: str = "5y",
        fetch: Optional[FetchPlan] = None,
        prior: Optional[InvestmentSnapshot] = None,
    ) -> InvestmentSnapshot:
        if self.read_only is not self._read_only_mode or self.read_only and (self.persist or self.snapshot_path is not None):
            raise ValueError("RESEARCH_READ_ONLY_MODE_CHANGED")
        plan = fetch or FetchPlan()
        failures: list = []

        if plan.price:
            try:
                px = await self.price.get_price(entry.symbol)
            except Exception as e:
                px = MeasuredValue.unknown("yfinance", str(e)[:200])
                failures.append({"symbol": entry.symbol, "code": "PRICE_FAIL", "message": str(e)[:200]})
            _consume_failure(self.price, failures)
        elif prior is not None:
            px = prior.price
        else:
            px = MeasuredValue.unknown("cache", "price fetch skipped; no prior snapshot")

        bars = []
        stored = {"written": 0}
        if plan.history:
            try:
                kwargs = history_fetch_kwargs(entry.symbol, root=self.history_root, period=history_period)
                bars = await self.price.get_daily_ohlcv(entry.symbol, **kwargs)
            except Exception as e:
                bars = []
                failures.append({"symbol": entry.symbol, "code": "HISTORY_FAIL", "message": str(e)[:200]})
            _consume_failure(self.price, failures)
            stored = append_bars(entry.symbol, bars, root=self.history_root) if bars and not self.read_only else {"written": 0}
            if self.read_only and bars:
                self._read_only_history[entry.symbol] = tuple(bars)

        if plan.fundamentals:
            try:
                funds = await self.fundamentals.get_all(entry.symbol)
            except Exception as e:
                funds = {}
                failures.append({"symbol": entry.symbol, "code": "FUND_FAIL", "message": str(e)[:200]})
            _consume_failure(self.fundamentals, failures)
        elif prior is not None:
            funds = dict(prior.fundamentals)
        else:
            funds = {}

        if plan.valuation:
            try:
                val = await self.valuation.get_all(entry.symbol)
            except Exception as e:
                val = {}
                failures.append({"symbol": entry.symbol, "code": "VAL_FAIL", "message": str(e)[:200]})
            _consume_failure(self.valuation, failures)
        elif prior is not None:
            val = dict(prior.valuation)
        else:
            val = {}

        latest = bars[-1] if bars else (prior.latest_bar if prior is not None else None)
        snap = snapshot_from_parts(
            entry,
            price=px,
            fundamentals=funds,
            valuation=val,
            latest_bar=latest,
            failures=failures if failures else (list(prior.failures) if prior is not None and not plan.price else failures),
            history_rows_stored=int(stored.get("written") or 0),
        )
        if self.persist:
            persist_snapshot(snap, path=self.snapshot_path)
        return snap

    def research_bars(self, symbol):
        if not self.read_only or self.persist:
            raise ValueError("RESEARCH_READ_ONLY_HISTORY_REQUIRED")
        if symbol in self._read_only_history:
            return self._read_only_history[symbol]
        return tuple(load_bars(symbol, root=self.history_root))

    async def ingest_universe(self, *, history_period: str = "5y") -> List[InvestmentSnapshot]:
        out: List[InvestmentSnapshot] = []
        for entry in self.universe:
            if not entry.active:
                continue
            out.append(await self.ingest_symbol(entry, history_period=history_period))
        self.last_snapshots = out
        return out

    def quality_text(self) -> str:
        return summarize_snapshots(self.last_snapshots)
