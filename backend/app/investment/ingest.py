"""Pull universe → providers → history → snapshots. No scoring. Not started by main.py."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.investment.history import append_bars
from app.investment.models import MeasuredValue
from app.investment.quality_report import summarize_snapshots
from app.investment.snapshot import InvestmentSnapshot, persist_snapshot, snapshot_from_parts
from app.investment.universe import InvestmentUniverse, UniverseEntry, load_universe
from app.investment.yahoo_fundamentals import YahooFundamentalProvider, YahooValuationProvider
from app.investment.yahoo_price import YahooPriceProvider
from app.investment.yfinance_client import YFinanceClient


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
    ) -> None:
        client = YFinanceClient()
        self.universe = universe or load_universe()
        self.price = price or YahooPriceProvider(client)
        self.fundamentals = fundamentals or YahooFundamentalProvider(client)
        self.valuation = valuation or YahooValuationProvider(client)
        self.history_root = history_root
        self.snapshot_path = snapshot_path
        self.persist = persist
        self.last_snapshots: List[InvestmentSnapshot] = []

    async def ingest_symbol(self, entry: UniverseEntry, *, history_period: str = "5y") -> InvestmentSnapshot:
        failures: list = []
        try:
            px = await self.price.get_price(entry.symbol)
        except Exception as e:
            px = MeasuredValue.unknown("yfinance", str(e)[:200])
            failures.append({"symbol": entry.symbol, "code": "PRICE_FAIL", "message": str(e)[:200]})
        _consume_failure(self.price, failures)

        try:
            bars = await self.price.get_daily_ohlcv(entry.symbol, period=history_period)
        except Exception as e:
            bars = []
            failures.append({"symbol": entry.symbol, "code": "HISTORY_FAIL", "message": str(e)[:200]})
        _consume_failure(self.price, failures)
        stored = append_bars(entry.symbol, bars, root=self.history_root) if bars else {"written": 0}

        try:
            funds = await self.fundamentals.get_all(entry.symbol)
        except Exception as e:
            funds = {}
            failures.append({"symbol": entry.symbol, "code": "FUND_FAIL", "message": str(e)[:200]})
        _consume_failure(self.fundamentals, failures)

        try:
            val = await self.valuation.get_all(entry.symbol)
        except Exception as e:
            val = {}
            failures.append({"symbol": entry.symbol, "code": "VAL_FAIL", "message": str(e)[:200]})
        _consume_failure(self.valuation, failures)

        latest = bars[-1] if bars else None
        snap = snapshot_from_parts(
            entry,
            price=px,
            fundamentals=funds,
            valuation=val,
            latest_bar=latest,
            failures=failures,
            history_rows_stored=int(stored.get("written") or 0),
        )
        if self.persist:
            persist_snapshot(snap, path=self.snapshot_path)
        return snap

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
