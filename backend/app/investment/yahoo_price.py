"""PriceDataProvider backed by yfinance. No recommendations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from app.investment.bars import OhlcvBar, ProviderFailure, parse_session_date
from app.investment.enums import DataQuality
from app.investment.freshness import classify_freshness
from app.investment.models import MeasuredValue
from app.investment.validate import validate_ohlc
from app.investment.yfinance_client import ProviderCallError, YFinanceClient, utcnow

RETRYABLE_ABORT = {"RATE_LIMIT", "TIMEOUT", "PROVIDER_ERROR", "DEPENDENCY", "MISSING_TICKER"}


class YahooPriceProvider:
    name = "yfinance"

    def __init__(self, client: Optional[YFinanceClient] = None) -> None:
        self.client = client or YFinanceClient()
        self.last_failure: Optional[ProviderFailure] = None

    async def get_price(self, symbol: str) -> MeasuredValue:
        self.last_failure = None
        retrieved = utcnow()
        info: dict = {}
        try:
            info = await self.client.info(symbol)
        except ProviderCallError as e:
            self.last_failure = e.failure
            if e.failure.code in RETRYABLE_ABORT:
                return MeasuredValue.unknown(source=self.name, notes=e.failure.message)
            info = {}
        except Exception as e:
            self.last_failure = ProviderFailure(
                code="PROVIDER_ERROR",
                message=str(e)[:200],
                source=self.name,
                symbol=symbol,
                retryable=True,
            )
            return MeasuredValue.unknown(source=self.name, notes=str(e)[:200])

        if not info:
            return await self._from_last_close(symbol, retrieved, notes="empty info")

        price = _first_number(info, "regularMarketPrice", "currentPrice", "lastPrice", "previousClose")
        market_ts = _epoch(info.get("regularMarketTime"))
        notes = ""
        if price is None:
            return await self._from_last_close(symbol, retrieved, notes="no price field")
        if price == 0:
            return MeasuredValue(
                value=0.0,
                source=self.name,
                timestamp=market_ts or retrieved,
                retrieved_at=retrieved,
                effective_timestamp=market_ts or retrieved,
                quality=DataQuality.UNKNOWN,
                availability=True,
                notes="SUSPICIOUS_ZERO",
            )
        if market_ts is None:
            market_ts = retrieved
            notes = "market time missing; used retrieve time"
        quality = classify_freshness(market_ts, kind="price", now=retrieved)
        self.last_failure = None
        return MeasuredValue(
            value=float(price),
            source=self.name,
            timestamp=market_ts,
            retrieved_at=retrieved,
            effective_timestamp=market_ts,
            quality=quality,
            availability=True,
            notes=notes,
        )

    async def _from_last_close(self, symbol: str, retrieved: datetime, *, notes: str) -> MeasuredValue:
        bars = await self.get_daily_ohlcv(symbol, period="5d")
        if bars and bars[-1].close is not None:
            b = bars[-1]
            ts = b.effective_timestamp or retrieved
            # Last session close is real data, labeled as such — not an invented quote.
            return MeasuredValue(
                value=float(b.close),
                source=self.name,
                timestamp=ts,
                retrieved_at=retrieved,
                effective_timestamp=ts,
                quality=classify_freshness(ts, kind="daily_bar", now=retrieved),
                availability=True,
                notes=f"last daily close ({notes})",
            )
        if self.last_failure is None:
            self.last_failure = ProviderFailure(
                code="EMPTY",
                message=notes,
                source=self.name,
                symbol=symbol,
                retryable=True,
            )
        return MeasuredValue.unknown(source=self.name, notes=notes)

    async def get_daily_ohlcv(
        self,
        symbol: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        period: str = "5y",
    ) -> List[OhlcvBar]:
        self.last_failure = None
        try:
            df = await self.client.history(symbol, start=start, end=end, period=period, interval="1d")
        except ProviderCallError as e:
            self.last_failure = e.failure
            return []
        except Exception as e:
            self.last_failure = ProviderFailure(
                code="PROVIDER_ERROR",
                message=str(e)[:200],
                source=self.name,
                symbol=symbol,
                retryable=True,
            )
            return []
        return dataframe_to_bars(df, source=self.name, retrieved_at=utcnow())


def dataframe_to_bars(df: Any, *, source: str, retrieved_at: datetime) -> List[OhlcvBar]:
    bars: List[OhlcvBar] = []
    if df is None:
        return bars
    empty = getattr(df, "empty", True)
    if empty:
        return bars
    for idx, row in df.iterrows():
        session = parse_session_date(idx)
        if not session:
            continue
        o = _num(row.get("Open"))
        h = _num(row.get("High"))
        l = _num(row.get("Low"))
        c = _num(row.get("Close"))
        v = _num(row.get("Volume"))
        adj = _num(row.get("Adj Close"))
        issues = validate_ohlc(session_date=session, open_=o, high=h, low=l, close=c, volume=v)
        if issues and any(i.code == "IMPOSSIBLE_OHLC" for i in issues):
            quality = DataQuality.CONFLICTING.value
        elif issues:
            quality = DataQuality.UNKNOWN.value
        else:
            quality = classify_freshness(
                datetime.fromisoformat(session).replace(tzinfo=timezone.utc),
                kind="daily_bar",
                now=retrieved_at,
            ).value
        bars.append(
            OhlcvBar(
                session_date=session,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=v,
                adjusted_close=adj,
                source=source,
                retrieved_at=retrieved_at,
                effective_timestamp=datetime.fromisoformat(session).replace(tzinfo=timezone.utc),
                quality=quality,
                issues=[i.code for i in issues],
            )
        )
    return bars


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        import math

        x = float(v)
        if math.isnan(x):
            return None
        return x
    except (TypeError, ValueError):
        return None


def _first_number(info: dict, *keys: str) -> Optional[float]:
    for k in keys:
        n = _num(info.get(k))
        if n is not None:
            return n
    return None


def _epoch(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    try:
        return datetime.fromtimestamp(float(v), tz=timezone.utc)
    except Exception:
        return None
