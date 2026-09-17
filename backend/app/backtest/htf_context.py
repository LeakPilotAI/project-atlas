"""Point-in-time HTF context matching the production perp-micro 1h trend rule.

Production uses the latest completed 1h close versus SMA20: UP above +0.2%, DOWN
below -0.2%, otherwise FLAT. Historical derivation must never expose an unfinished
1h candle to a 5m decision timestamp.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from typing import Iterable,Literal

Trend=Literal["UNKNOWN","UP","DOWN","FLAT"]

@dataclass(frozen=True)
class HtfClose:
    open_timestamp:str
    close:float


def _dt(value:str)->datetime:
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def trend_from_completed_closes(closes:list[float])->Trend:
    if len(closes)<20:return "UNKNOWN"
    sma=sum(closes[-20:])/20
    if sma<=0:return "UNKNOWN"
    last=closes[-1]
    if last>sma*1.002:return "UP"
    if last<sma*0.998:return "DOWN"
    return "FLAT"


def htf_allows_side(side:str,trend:str)->bool:
    trend=str(trend).upper();side=str(side).upper()
    if trend in {"UNKNOWN","OFF","FLAT"}:return True
    if side=="LONG":return trend=="UP"
    if side=="SHORT":return trend=="DOWN"
    return False


def derive_1h_trend_by_timestamp(decision_timestamps:Iterable[str],hourly:Iterable[HtfClose])->dict[str,Trend]:
    """Return trend visible at each decision time using completed 1h candles only.

    HtfClose.open_timestamp is the 1h candle open; it becomes usable one hour later.
    """
    rows=sorted(hourly,key=lambda x:_dt(x.open_timestamp))
    if len({_dt(x.open_timestamp) for x in rows})!=len(rows):raise ValueError("duplicate 1h candle timestamp")
    if any(x.close<=0 for x in rows):raise ValueError("1h closes must be positive")
    decisions=sorted((_dt(x),str(x)) for x in decision_timestamps)
    out:dict[str,Trend]={};visible:list[float]=[];i=0
    for when,label in decisions:
        while i<len(rows) and _dt(rows[i].open_timestamp)+timedelta(hours=1)<=when:
            visible.append(float(rows[i].close));i+=1
        out[label]=trend_from_completed_closes(visible)
    return out
