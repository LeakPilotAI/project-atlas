"""Deterministic, research-only historical replay primitives for Atlas.

This module deliberately has no exchange adapter and no production-setting mutation path.
Callers provide timestamped bars and a point-in-time signal function. Orders generated
at bar i are filled at bar i+1 open so the decision cannot consume its own fill bar.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, Iterable, Literal, Sequence

Side = Literal["LONG", "SHORT"]


@dataclass(frozen=True)
class HistoricalBar:
    timestamp: str
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    funding_rate: float = 0.0


@dataclass(frozen=True)
class BacktestSignal:
    side: Side
    stop_price: float
    target_price: float


@dataclass(frozen=True)
class BacktestAssumptions:
    risk_usd: float = 1.0
    fee_bps_per_fill: float = 3.5
    slippage_bps_per_fill: float = 1.0
    initial_equity_usd: float = 10_000.0
    intrabar_priority: Literal["STOP_FIRST", "TARGET_FIRST"] = "STOP_FIRST"


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    side: Side
    signal_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    quantity: float
    gross_pnl_usd: float
    fees_usd: float
    slippage_usd: float
    funding_usd: float
    net_pnl_usd: float
    net_r: float
    exit_reason: str


SignalFn = Callable[[Sequence[HistoricalBar]], BacktestSignal | None]


def _validate_bars(bars: Iterable[HistoricalBar]) -> list[HistoricalBar]:
    rows=list(bars)
    if not rows:
        raise ValueError("historical dataset is empty")
    key={(b.symbol,b.timeframe) for b in rows}
    if len(key)!=1:
        raise ValueError("one deterministic run requires exactly one symbol/timeframe")
    timestamps=[b.timestamp for b in rows]
    if timestamps!=sorted(timestamps) or len(set(timestamps))!=len(timestamps):
        raise ValueError("bars must have unique ascending timestamps")
    for b in rows:
        if min(b.open,b.high,b.low,b.close)<=0 or b.low>b.high:
            raise ValueError(f"invalid OHLC bar at {b.timestamp}")
    return rows


def _slipped(price:float,side:Side,is_entry:bool,bps:float)->float:
    adverse=1 if (side=="LONG") == is_entry else -1
    return price*(1+adverse*bps/10_000.0)


def _exit_on_bar(side:Side,bar:HistoricalBar,stop:float,target:float,priority:str)->tuple[float,str]|None:
    stop_hit=bar.low<=stop if side=="LONG" else bar.high>=stop
    target_hit=bar.high>=target if side=="LONG" else bar.low<=target
    if stop_hit and target_hit:
        return (stop,"STOP") if priority=="STOP_FIRST" else (target,"TARGET")
    if stop_hit:return stop,"STOP"
    if target_hit:return target,"TARGET"
    return None


def run_historical_backtest(bars:Iterable[HistoricalBar],signal_fn:SignalFn,assumptions:BacktestAssumptions=BacktestAssumptions())->dict:
    rows=_validate_bars(bars);trades:list[BacktestTrade]=[];equity=assumptions.initial_equity_usd;curve=[equity];i=0
    while i<len(rows)-1:
        history=tuple(rows[:i+1])  # strict PIT view: signal sees nothing after rows[i]
        signal=signal_fn(history)
        if signal is None:
            i+=1;continue
        raw_entry=rows[i+1].open;entry=_slipped(raw_entry,signal.side,True,assumptions.slippage_bps_per_fill)
        risk_per_unit=(entry-signal.stop_price) if signal.side=="LONG" else (signal.stop_price-entry)
        reward_per_unit=(signal.target_price-entry) if signal.side=="LONG" else (entry-signal.target_price)
        if risk_per_unit<=0 or reward_per_unit<=0:
            raise ValueError("signal stop/target must define positive risk and reward from next-bar entry")
        qty=assumptions.risk_usd/risk_per_unit;exit_i=None;raw_exit=None;reason=None;funding=0.0
        for j in range(i+1,len(rows)):
            funding += abs(qty*rows[j].open)*rows[j].funding_rate*(1 if signal.side=="LONG" else -1)
            hit=_exit_on_bar(signal.side,rows[j],signal.stop_price,signal.target_price,assumptions.intrabar_priority)
            if hit:
                raw_exit,reason=hit;exit_i=j;break
        if exit_i is None:
            exit_i=len(rows)-1;raw_exit=rows[exit_i].close;reason="END_OF_DATA"
        exit_price=_slipped(float(raw_exit),signal.side,False,assumptions.slippage_bps_per_fill)
        direction=1 if signal.side=="LONG" else -1
        gross=qty*(exit_price-entry)*direction
        fees=(abs(qty*entry)+abs(qty*exit_price))*assumptions.fee_bps_per_fill/10_000.0
        slippage=abs(qty*(entry-raw_entry))+abs(qty*(float(raw_exit)-exit_price))
        net=gross-fees-funding;net_r=net/assumptions.risk_usd
        trade=BacktestTrade(rows[i].symbol,signal.side,rows[i].timestamp,rows[i+1].timestamp,rows[exit_i].timestamp,entry,exit_price,signal.stop_price,signal.target_price,qty,gross,fees,slippage,funding,net,net_r,str(reason))
        trades.append(trade);equity+=net;curve.append(equity);i=exit_i+1
    wins=sum(t.net_pnl_usd>0 for t in trades);gross_win=sum(max(t.net_pnl_usd,0) for t in trades);gross_loss=-sum(min(t.net_pnl_usd,0) for t in trades)
    peak=curve[0];max_dd=0.0
    for value in curve:
        peak=max(peak,value);max_dd=max(max_dd,peak-value)
    metrics={"trade_count":len(trades),"win_rate":wins/len(trades) if trades else 0.0,"expectancy_r":sum(t.net_r for t in trades)/len(trades) if trades else 0.0,"total_r":sum(t.net_r for t in trades),"profit_factor":gross_win/gross_loss if gross_loss>0 else None,"max_drawdown_usd":max_dd,"ending_equity_usd":equity,"fees_usd":sum(t.fees_usd for t in trades),"slippage_usd":sum(t.slippage_usd for t in trades),"funding_usd":sum(t.funding_usd for t in trades)}
    payload={"mode":"RESEARCH_ONLY_HISTORICAL_BACKTEST","symbol":rows[0].symbol,"timeframe":rows[0].timeframe,"dataset":{"first_timestamp":rows[0].timestamp,"last_timestamp":rows[-1].timestamp,"bar_count":len(rows)},"assumptions":asdict(assumptions),"trades":[asdict(t) for t in trades],"equity_curve_usd":curve,"metrics":metrics,"production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"));payload["run_id"]=sha256(canonical.encode()).hexdigest()[:20]
    return payload


def persist_backtest_result(result:dict,output_dir:Path)->Path:
    output_dir.mkdir(parents=True,exist_ok=True);run_id=str(result["run_id"]);path=output_dir/f"{run_id}.json"
    text=json.dumps(result,sort_keys=True,indent=2)+"\n"
    if path.exists() and path.read_text(encoding="utf-8")!=text:
        raise RuntimeError("deterministic run_id collision with different result content")
    path.write_text(text,encoding="utf-8");return path
