"""Point-in-time safe Hyperliquid historical import normalization for Atlas research."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from app.backtest.io import HistoricalContext
from app.backtest.historical import HistoricalBar


@dataclass(frozen=True)
class HistoricalMarketContext:
    timestamp: str
    open_interest_usd: float
    volume_24h_usd: float
    htf_regime_aligned: bool|None = None
    htf_trend: str|None = None


def _iso_from_ms(value:int)->str:
    return datetime.fromtimestamp(value/1000.0,tz=timezone.utc).isoformat().replace("+00:00","Z")


def _index_context(rows:Iterable[HistoricalMarketContext])->dict[str,HistoricalMarketContext]:
    out:dict[str,HistoricalMarketContext]={}
    for row in rows:
        if row.timestamp in out:raise ValueError(f"duplicate historical context timestamp: {row.timestamp}")
        if row.open_interest_usd<0 or row.volume_24h_usd<0:raise ValueError(f"negative historical market context at {row.timestamp}")
        if row.htf_trend is None and row.htf_regime_aligned is None:raise ValueError(f"missing historical HTF context at {row.timestamp}")
        if row.htf_trend is not None and row.htf_trend.upper() not in {"UP","DOWN","FLAT","UNKNOWN","OFF"}:raise ValueError(f"invalid historical htf_trend at {row.timestamp}: {row.htf_trend}")
        out[row.timestamp]=row
    return out


def _index_funding(rows:Sequence[Mapping])->list[tuple[int,float]]:
    out=[]
    for row in rows:
        try:out.append((int(row.get("time") or 0),float(row.get("funding_rate") or row.get("fundingRate") or 0.0)))
        except (TypeError,ValueError):continue
    return sorted(out)


def _funding_at(timestamp_ms:int,index:list[tuple[int,float]])->float:
    value=0.0
    for ts,rate in index:
        if ts>timestamp_ms:break
        value=rate
    return value


def normalize_hyperliquid_history(*,symbol:str,timeframe:str,candles:Sequence[Mapping],funding_history:Sequence[Mapping],historical_context:Iterable[HistoricalMarketContext])->list[HistoricalContext]:
    context_index=_index_context(historical_context);funding_index=_index_funding(funding_history);out=[]
    for candle in candles:
        try:
            ts_ms=int(candle.get("time") or candle.get("t") or 0)
            if ts_ms<=0:raise ValueError("missing candle time")
            timestamp=_iso_from_ms(ts_ms)
            ctx=context_index.get(timestamp)
            if ctx is None:raise ValueError(f"missing point-in-time OI/volume/HTF context for {timestamp}")
            bar=HistoricalBar(timestamp=timestamp,symbol=symbol.upper(),timeframe=timeframe,open=float(candle["open"]),high=float(candle["high"]),low=float(candle["low"]),close=float(candle["close"]),volume=float(candle["volume"]),funding_rate=_funding_at(ts_ms,funding_index))
            out.append(HistoricalContext(bar,ctx.open_interest_usd,ctx.volume_24h_usd,ctx.htf_regime_aligned,ctx.htf_trend.upper() if ctx.htf_trend else None))
        except KeyError as exc:raise ValueError(f"candle missing field: {exc.args[0]}") from exc
    timestamps=[x.bar.timestamp for x in out]
    if not out:raise ValueError("no historical candles supplied")
    if timestamps!=sorted(timestamps) or len(set(timestamps))!=len(timestamps):raise ValueError("normalized Hyperliquid candles must have unique ascending timestamps")
    return out


def write_canonical_csv(rows:Sequence[HistoricalContext],path:Path)->Path:
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    use_trend=all(row.htf_trend is not None for row in rows)
    fields=["timestamp","symbol","timeframe","open","high","low","close","volume","funding_rate","open_interest_usd","volume_24h_usd"]+(["htf_trend"] if use_trend else ["htf_regime_aligned"])
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
        for row in rows:
            b=row.bar;data={"timestamp":b.timestamp,"symbol":b.symbol,"timeframe":b.timeframe,"open":b.open,"high":b.high,"low":b.low,"close":b.close,"volume":b.volume,"funding_rate":b.funding_rate,"open_interest_usd":row.open_interest_usd,"volume_24h_usd":row.volume_24h_usd}
            if use_trend:data["htf_trend"]=row.htf_trend
            else:data["htf_regime_aligned"]=str(row.htf_regime_aligned).lower()
            w.writerow(data)
    return path
